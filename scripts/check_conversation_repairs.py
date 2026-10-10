"""Real development-only dialogues; never opens gold or sealed test questions."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import Lock

from parkguide.budget import Budget
from parkguide.chat import answer
from parkguide.runtime import ROOT


DIALOGUES = [
    ('screenshot', 'yose', [
        ('Are pets allowed on trails?', 'answer'),
        ('i dont understand', 'answer'),
        ('the thing you just said, i need more info.', 'answer')]),
    ('new-subject', 'yose', [
        ('How far should I stay from bears outside developed areas?', 'answer'),
        ('Can you explain that more simply?', 'answer'),
        ('Actually, what about deer?', 'answer')]),
    ('companion', 'grca', [
        ('Where can I take my dog?', 'answer'),
        ('What if I carry him below the rim?', 'answer'),
        ('Can we use a park shuttle instead?', 'answer')]),
    ('clarification', 'yose', [
        ('Can I bring it?', 'clarify'),
        ('My dog on the trails.', 'answer'),
        ("I didn't understand that.", 'answer')]),
    ('live-and-reset', 'yose', [
        ('What are the pet rules?', 'answer'),
        ("What about today's road closures?", 'refuse'),
        ('What are the food storage rules?', 'answer')]),
    ('park-scope', 'yell', [
        ('Can I take my dog on boardwalks?', 'answer'),
        ('What about Yosemite?', 'refuse'),
        ('And can I leave him in the car?', 'refuse')]),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', choices=[item[0] for item in DIALOGUES])
    parser.add_argument('--workers', type=int, choices=[1, 2], default=2)
    args = parser.parse_args()
    timestamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT / 'artifacts/conversation-repairs' / timestamp
    directory.mkdir(parents=True, exist_ok=False)
    before = Budget().summary()
    (directory / 'run.json').write_text(json.dumps({
        'dialogues': DIALOGUES,
        'code_hashes': {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in sorted((ROOT / 'src/parkguide').glob('*.py'))},
        'config_sha256': hashlib.sha256((ROOT / 'config/project.json').read_bytes()).hexdigest(),
    }, indent=2) + '\n')
    records = []
    write_lock = Lock()

    def run_dialogue(dialogue):
        name, park, turns = dialogue
        history = []
        for number, (question, expected) in enumerate(turns, 1):
            result = answer(question, history, selected_park=park, rerank=False)
            checks = {
                'expected_action': result['response']['action'] == expected,
                'guards_pass': not result['guard_errors'],
                'same_park_evidence': all(f'/{park}/planyourvisit/' in item['source_url'] for item in result['contexts']),
            }
            record = {'dialogue_id': name, 'turn': number, 'expected_action': expected,
                      'checks': checks, 'result': result}
            with write_lock:
                records.append(record)
                with (directory / 'turns.jsonl').open('a') as handle:
                    handle.write(json.dumps(record, ensure_ascii=False) + '\n')
            ids = list(dict.fromkeys(identifier for claim in result['response']['claims'] for identifier in claim['evidence_ids']))[:5]
            history.extend([{'role': 'user', 'content': question},
                            {'role': 'assistant', 'content': result['rendered'],
                             **({'evidence_ids': ids} if ids else {})}])
            print(json.dumps({'dialogue': name, 'turn': number, 'action': result['response']['action'],
                              'plan': result['dialogue']['action'], 'query': result['retrieval_query'],
                              'answer': result['response']['answer'], 'checks': checks}), flush=True)
    selected = [dialogue for dialogue in DIALOGUES if not args.only or dialogue[0] == args.only]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        list(executor.map(run_dialogue, selected))
    after = Budget().summary()
    summary = {'scope': 'local real Azure calls, frozen corpus, hosted retrieval profile (reranker off)',
               'grading': 'operational checks and AI source review; no human accuracy score',
               'turns': len(records), 'checks_passed': sum(all(item['checks'].values()) for item in records),
               'estimated_ledger_delta_usd': after['estimated_committed_usd'] - before['estimated_committed_usd'],
               'cost_note': 'Shared local ledger window; may include concurrent local browser checks.',
               'budget_before': before, 'budget_after': after}
    (directory / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'evidence_directory': str(directory), **summary}), flush=True)


if __name__ == '__main__':
    main()
