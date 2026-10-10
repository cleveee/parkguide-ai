"""Measure current B0–B3 on non-gold diagnostics, then six actual dialogues."""
import json

from parkguide.evaluation import dialogues, final_configurations, run
from parkguide.runtime import ROOT


def main():
    variants=final_configurations()
    result=run(ROOT/'data/evaluation/diagnostic.jsonl',variants,diagnostic=True)
    (ROOT/'artifacts/latest-diagnostic.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'baseline_run':result['run']},indent=2),flush=True)
    selected=next(variant for variant in variants if variant['name']=='B3')
    result=dialogues(ROOT/'data/evaluation/dialogues.jsonl',build_id=selected['build_id'],rerank=selected['rerank'])
    (ROOT/'artifacts/latest-dialogues.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)


if __name__=='__main__':
    main()
