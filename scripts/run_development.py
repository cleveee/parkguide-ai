"""Run paid non-gold development comparisons and real conversations."""
import json

from parkguide.evaluation import dialogues, run
from parkguide.retrieval import load_reranker
from parkguide.runtime import ROOT


def main():
    fixed=json.loads((ROOT/'artifacts/builds/fixed.json').read_text())['build_id']
    structure=json.loads((ROOT/'artifacts/builds/structure.json').read_text())['build_id']
    load_reranker()
    # Six ablation labels retain the original run convention: B3 here means
    # the reranking ablation. Formal final_batch() uses the selected setting.
    variants=[{'name':'B0','build_id':fixed,'closed_book':True}, {'name':'B1','build_id':fixed,'mode':'bm25','rerank':False}, {'name':'B2','build_id':fixed,'mode':'dense','rerank':False}, {'name':'C1','build_id':structure,'mode':'dense','rerank':False}, {'name':'C2','build_id':structure,'mode':'hybrid','rerank':False}, {'name':'B3','build_id':structure,'mode':'hybrid','rerank':True}]
    result=run(ROOT/'data/evaluation/diagnostic.jsonl',variants,diagnostic=True)
    (ROOT/'artifacts/latest-controlled.json').write_text(json.dumps(result,indent=2)+'\n')
    (ROOT/'artifacts/latest-diagnostic.json').write_text(json.dumps(result,indent=2)+'\n')
    settings=json.loads((ROOT/'config/project.json').read_text())
    result=dialogues(ROOT/'data/evaluation/dialogues.jsonl',build_id=structure,rerank=settings['retrieval'].get('default_rerank',True))
    (ROOT/'artifacts/latest-dialogues.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
