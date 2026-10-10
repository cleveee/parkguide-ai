"""Create an unapproved acceptance template after the real human gold split."""
import json

from parkguide.evaluation import final_configurations, final_snapshot
from parkguide.runtime import ROOT, digest, read_jsonl


def main():
    folder=ROOT/'data/evaluation'
    if not (folder/'split-manifest.json').exists():
        raise SystemExit('HUMAN_REVIEW_PENDING: verify all 40 gold drafts and run gold-split first')
    development=read_jsonl(folder/'dev.jsonl')
    snapshot=final_snapshot(folder/'sealed-test.jsonl',final_configurations())
    template={
        'human_verifier':None,'verified_at':None,'all_gates_passed':False,
        'accepted_dev_hash':digest(development),'accepted_snapshot_hash':digest(snapshot),
        'gates':{name:False for name in ('corpus_pipeline','evidence_coverage','answer_correctness','refusal','claim_support','safeguards','six_dialogues','reproduction')},
        'note':'A real human must review saved development evidence against docs/EVALUATION.md, record verifier/date and confirm each gate. This template grants no approval.'
    }
    path=folder/'dev-acceptance.template.json'
    with path.open('x') as stream:
        stream.write(json.dumps(template,indent=2)+'\n')
    print(f'Unapproved review template: {path}; final test was not called.')


if __name__=='__main__':
    main()
