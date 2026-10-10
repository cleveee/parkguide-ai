"""Local UI preview using one recorded answer, with no Azure/model requests.

Run from the checkout: PYTHONPATH=src python scripts/run_source_preview_demo.py
The real source-preview endpoint still reads and verifies the saved HTML.
"""
from copy import deepcopy
import json
import os
from pathlib import Path

os.environ.setdefault('PARKGUIDE_WEB_PORT', '8537')
from parkguide import web
import uvicorn

root = Path(__file__).resolve().parents[1]
recorded = json.loads((root / 'artifacts/reliability/production-final-ui-response.json').read_text())
examples = {(recorded['selected_park'], recorded['question']): recorded}
for line in (root / 'artifacts/user-testing/20261010T190949Z-deployed-1daf0ab-3db8cd/turns.jsonl').read_text().splitlines():
    turn = json.loads(line)
    question = turn['request']['question']
    if question in ('Can I walk my pet dog on the paved road to Mirror Lake?', 'How many miles one way is Cedar Ridge from the South Kaibab trailhead?'):
        response = turn['http']['body']
        examples[(response['selected_park'], question)] = response
metadata = web.metadata


def demo_metadata():
    value = metadata()
    value['chat'] = {'ready': True, 'reason': 'UI demo with one recorded answer; no model requests.'}
    return value


def demo_answer(request):
    example = examples.get((request.selected_park, request.question.strip()))
    if example is None:
        raise web.WebError(422, 'preview_demo', 'This preview uses a recorded answer. Choose Yosemite and ask: Can I carry my dog to Vernal Fall?')
    value = deepcopy(example)
    value['inspector']['ledger_window'] = {'captured': False, 'reason': 'Recorded answer for UI verification. This request made no model calls.'}
    return value


web.metadata = demo_metadata
web.run_chat = demo_answer
print('Recorded-answer UI demo; source pages are real saved files. No model calls.', flush=True)
print('Choose Yosemite and ask: Can I carry my dog to Vernal Fall?', flush=True)
uvicorn.run(web.app, host=web.HOST, port=web.PORT)
