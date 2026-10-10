import json

import pytest

from parkguide import evaluation
from parkguide.guards import validate_answer
from parkguide.chat import answer, preflight_response, resolve_query, table_followup_filters
from parkguide.runtime import digest, write_jsonl


def test_pdf_numbers_touching_known_units_are_valid_but_record_ids_are_not():
    from decimal import Decimal
    from parkguide.guards import numeric_values
    assert numeric_values('1120ft, 305m, 1.5mi, ZX9401, v12beta') == {Decimal('1120'), Decimal('305'), Decimal('1.5')}
    context=[{'chunk_id':'c','text':'The ridge is 1120ft below the rim.'}]
    payload={'action':'answer','claims':[{'text':'Its vertical descent is 1,120 feet.','evidence_ids':['c']}]}
    assert validate_answer(payload,context)==[]


def test_chat_trace_history_is_a_snapshot_of_preceding_turns():
    history=[{'role':'user','content':'Previous question'},{'role':'assistant','content':'Previous answer'}]
    result=answer('Look up my private booking ZX9401.',history,enforce_gate=False)
    history[0]['content']='Changed later'
    history.append({'role':'user','content':'Future question'})
    assert len(result['history'])==2
    assert result['history'][0]['content']=='Previous question'


def test_human_review_creates_separate_revision_without_rewriting_authoring_seal(tmp_path, monkeypatch):
    import parkguide.chat as chat
    monkeypatch.setattr(evaluation,'ROOT',tmp_path)
    monkeypatch.setattr(chat,'ROOT',tmp_path)
    path=tmp_path/'data/evaluation/gold-drafts.jsonl'
    rows=[]
    for category,count in evaluation.CATEGORIES.items():
        for index in range(count):
            rows.append({'item_id':f'{category}-{index}','category':category,'expected_action':'refuse','verification_status':'human_review_pending'})
    write_jsonl(path,rows)
    original=evaluation.seal_drafts(path)
    assert chat.gold_drafts_ready()
    for row in rows:
        row.update(verification_status='human_verified',human_verifier='Synthetic test reviewer',verified_at='fixture date')
    write_jsonl(path,rows)
    assert not chat.gold_drafts_ready()
    with pytest.raises(RuntimeError,match='immutable'):
        evaluation.seal_drafts(path)
    evaluation.split_gold(path)
    assert chat.gold_drafts_ready()
    assert json.loads((path.parent/'gold-draft-manifest.json').read_text())==original
    assert len((path.parent/'dev.jsonl').read_text().splitlines())==24
    assert len((path.parent/'sealed-test.jsonl').read_text().splitlines())==16


def test_comma_numbers_and_explicit_source_witnessed_arithmetic():
    context = [{"chunk_id": "c", "text": "Trailhead elevation 7260 feet; Cedar Ridge 6120 feet."}]
    def check(text):
        return validate_answer({"action": "answer", "claims": [{"text": text, "evidence_ids": ["c"]}]}, context)
    assert check("The elevations are 7,260 and 6,120 feet; 7,260 - 6,120 = 1,140 feet.") == []
    assert check('7,260 ft - 6,120 ft = 1,140 ft below the rim.') == []
    assert "number_without_source_witness" in check("7,260 - 6,120 = 1,150 feet.")
    assert "number_without_source_witness" in check("7,260 - 6,000 = 1,260 feet.")
    assert "number_without_source_witness" in check("The difference is 1,140 feet.")
    assert check('7,260 ft - 6,120 feet = 1,140 ft.')==[]
    assert 'invalid_calculation' in check('7,260 ft - 6,120 miles = 1,140 ft.')


def test_requested_date_can_be_repeated_but_other_numbers_need_sources():
    context=[{'chunk_id':'c','text':'Volume 51 Issue 8 covers September 23 to November 24, 2026.'}]
    def payload(text):
        return {'action':'answer','claims':[{'text':text,'evidence_ids':['c']}]}
    assert validate_answer(payload('October 15, 2026 falls within those guide dates.'),context,question='My visit is October 15, 2026.')==[]
    assert 'number_without_source_witness' in validate_answer(payload('October 15, 2026 has a 15 dollar fee.'),context,question='My visit is October 15, 2026.')


def test_no_relevant_chunk_is_unscorable_not_zero_mrr():
    item = {"evidence": [{"doc_id": "d", "start": 0, "end": 5}]}
    metrics = evaluation.retrieval_metrics(item, [], [])
    assert metrics['mrr'] is None and metrics['recall_20'] is None
    assert metrics['evidence_coverage_20'] == 0


def test_ambiguous_entry_and_private_lookup_need_no_generator():
    assert preflight_response('Can I go in whenever?',[],{})['action']=='clarify'
    assert preflight_response('Has the office recovered passport PZ1184 today?',[],{})['action']=='refuse'
    response=preflight_response('Give me a personal painkiller dose.',[],{})
    assert response['action']=='refuse' and 'medical professional' in response['answer']
    assert preflight_response('What services are at Grand Canyon?',[],{'parks':['grca']}) is None


def test_table_followup_reads_only_a_known_page_in_the_latest_park(monkeypatch):
    url='https://www.nps.gov/grca/planyourvisit/trail-distances.htm'
    monkeypatch.setattr('parkguide.store.load_documents',lambda db:[{'source_url':url,'has_table':True}])
    history=[{'role':'assistant','content':f'[Trail table]({url}) [Unknown](https://www.nps.gov/grca/fake.htm)'}]
    assert table_followup_filters('Does it have water marked in that table?',history,{'parks':['grca']},'unused')['source_url']==[url]
    assert 'source_url' not in table_followup_filters('What about that table?',history,{'parks':['yose']},'unused')
    assert 'source_url' not in table_followup_filters('Switch to Yosemite and show that table.',history,{'parks':['yose']},'unused')


def test_entry_clarification_carries_question_to_search():
    query,_=resolve_query("I mean Yosemite's Hetch Hetchy entrance station.",[{'role':'user','content':'Can I go in whenever?'}])
    assert 'entrance opening hours' in query


def test_runtime_review_withholds_only_unsupported_claim_and_keeps_raw_trace():
    context={'chunk_id':'c','text':'Opening is at noon.','source_url':'https://www.nps.gov/yose/planyourvisit/hours.htm'}
    def retriever(*args,**kwargs):
        return {'candidates':[context],'final':[context],'timings':{}}
    def generator(*args,**kwargs):
        return {'action':'answer','answer':'Opening is noon. Road closes at 9.','claims':[{'text':'Opening is noon.','evidence_ids':['c']},{'text':'Road closes at 9.','evidence_ids':['c']}],'usage':{}}
    def reviewer(*args):
        return {'decisions':[{'claim_index':0,'supported':True},{'claim_index':1,'supported':False}]}
    result=answer('What are the opening hours?',mode='bm25',generator=generator,retriever=retriever,reviewer=reviewer,enforce_gate=False)
    assert result['response']['action']=='answer' and len(result['response']['claims'])==1
    assert len(result['raw_response']['claims'])==2 and result['citation_review']['withheld_claims']==1
    assert 'Road closes' not in result['rendered'] and result['guard_errors']==[]


def test_failed_runtime_review_withholds_answer():
    context={'chunk_id':'c','text':'Opening is at noon.','source_url':'https://www.nps.gov/yose/planyourvisit/hours.htm'}
    def reviewer(*args):
        raise RuntimeError('Safe contract failure')
    result=answer('What are the opening hours?',mode='bm25',generator=lambda *args,**kwargs:{'action':'answer','answer':'Opening is noon.','claims':[{'text':'Opening is noon.','evidence_ids':['c']}],'usage':{}},retriever=lambda *args,**kwargs:{'candidates':[context],'final':[context],'timings':{}},reviewer=reviewer,enforce_gate=False)
    assert result['response']['action']=='refuse' and result['citation_review']['error']['type']=='RuntimeError'


def test_table_difference_uses_source_cells_and_preserves_original_model_answer():
    context={'chunk_id':'c','doc_id':'d','text':'| Stop | Distance (mi) |\n| --- | --- |\n| Birch Point | 7 |\n| Willow Ridge | 2.5 |','source_url':'https://www.nps.gov/grca/example.htm'}
    raw={'action':'answer','answer':'The endpoints are 7 and 2.5 mi.','claims':[{'text':'The endpoints are 7 and 2.5 mi.','evidence_ids':['c']}],'usage':{}}
    result=answer('How much farther is Birch Point than Willow Ridge?',mode='bm25',generator=lambda *args,**kwargs:raw,retriever=lambda *args,**kwargs:{'candidates':[context],'final':[context],'timings':{}},enforce_gate=False)
    assert '7 - 2.5 = 4.5 mi' in result['rendered']
    assert result['source_derivation']['result']=='4.5' and result['guard_errors']==[]
    assert result['raw_response']==raw


def test_closed_book_citations_are_not_failed_identities():
    item = {"expected_action": "answer", "required_facts": []}
    result = {"closed_book": True, "response": {"action": "answer", "answer": "Fact", "claims": [{"text": "Fact", "evidence_ids": []}]}, "contexts": [], "guard_errors": []}
    assert evaluation.provisional_grade(item, result)['citation_identity_valid'] is None


def test_final_test_rejects_stale_development_acceptance(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, 'ROOT', tmp_path)
    folder = tmp_path/'data/evaluation'
    folder.mkdir(parents=True)
    rows = [{"item_id": f"G{i}", "verification_status": "human_verified", "human_verifier": "actual reviewer fixture", "verified_at": "fixture date"} for i in range(16)]
    write_jsonl(folder/'sealed-test.jsonl', rows)
    write_jsonl(folder/'dev.jsonl', [{'item_id':'dev fixture'}])
    (folder/'split-manifest.json').write_text(json.dumps({'test_hash':digest(rows),'dev_hash':digest([{'item_id':'dev fixture'}])}))
    (folder/'dev-acceptance.json').write_text(json.dumps({'human_verifier':'fixture','verified_at':'fixture','all_gates_passed':True,'accepted_snapshot_hash':'outdated'}))
    monkeypatch.setattr(evaluation,'final_snapshot',lambda *args: {'code_hash':'new'})
    with pytest.raises(RuntimeError,match='does not match'):
        evaluation._final_gate(folder/'sealed-test.jsonl',[{'name':name} for name in ['B0','B1','B2','B3']])
    assert not (tmp_path/'artifacts/final-test').exists()
