"""Verify actual decisions, candidate chronology, outcomes, and saved rtx3 media.

Use --remote to also compare all retained records and image bytes directly to rtx3.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT / 'docs/data/orchestrator-examples.json').read_text())
cases = data['cases']
for name, action in {'accept': 'accept_best_iter', 'retry': 'retry_with_context',
                     'resume': 'steer_continue', 'backtrack': 'backtrack'}.items():
    case = cases[name]
    assert case['record']['action'] == action
    previous = case['record']['t']
    for row in case['following_records']:
        assert row['record']['t'] >= previous, f'{name}: out-of-order evidence'
        previous = row['record']['t']

records = data['supporting_records']
def metrics(name):
    return {row['name']: row['value'] for row in records[name]['record']}

report = records['accepted_placement_report']['record']
assert report['best_iter'] == 0 and report['iterations_used'] == 5
assert metrics('accept_before_metrics')['target_reachable_frac'] == .0976
assert metrics('accept_after_metrics')['target_reachable_frac'] == .2927
assert any(not m['passed'] for m in records['accept_before_metrics']['record'] if m.get('gate'))
assert all(m['passed'] for m in records['accept_after_metrics']['record'] if m.get('gate'))
assert records['accept_after_critique']['record']['severity'] == 'moderate'

retry = cases['retry']
assert retry['record']['stage'] == 'pose_generation'
assert records['retry_before_critique']['record']['severity'] == 'moderate'
assert records['retry_after_critique']['record']['severity'] == 'negligible'
retry_report = records['retry_after_stage_report']['record']
assert retry_report['accepted_iter'] == retry_report['best_iter'] == 0
assert retry_report['final_status'] == 'accepted'
assert any(r['record'].get('stage') == 'pose_generation' and r['record'].get('final_status') == 'accepted'
           for r in retry['following_records'])
# The accepted pose still has minor contacts; never describe it as collision-free.
assert any(m['flagged'] for m in retry_report['metrics'])

resume = cases['resume']
assert resume['record']['granted'] == 5
continuation = next(r['record'] for r in resume['following_records'] if r['record']['event'] == 'stage_start')
assert continuation['resume'] and continuation['max_iters'] == 10
assert next(r['record'] for r in resume['following_records'] if r['record']['event'] == 'stage_end')['final_status'] == 'budget_exhausted'
assert cases['backtrack']['record']['target'] == 'human_placement'
assert metrics('backtrack_before_metrics')['target_reachable_frac'] == 0
assert all(m['passed'] for m in records['backtrack_after_metrics']['record'] if m.get('gate'))
assert any(r['record'].get('stage') == 'robot_placement' and r['record'].get('final_status') == 'accepted'
           for r in cases['backtrack']['following_records'])
for side in ['before', 'after']:
    assert any(not m['passed'] for m in records[f'resume_{side}_metrics']['record'] if m.get('gate'))

assert len(data['assets']) == 8
for asset in data['assets']:
    digest = hashlib.sha256((ROOT / 'docs' / asset['file']).read_bytes()).hexdigest()
    assert digest == asset['sha256'] == asset['source_sha256'], asset['file']
    decision_time = cases[asset['case']]['record']['t']
    if asset['case'] == 'accept' or asset['side'] == 'before':
        assert asset['source_mtime_utc'] < decision_time, asset['file']
    else:
        assert asset['source_mtime_utc'] > decision_time, asset['file']
        ends = [r['record']['t'] for r in cases[asset['case']]['following_records']
                if r['record'].get('event') == 'stage_end'
                and r['record'].get('stage') == cases[asset['case']]['record']['stage']]
        assert asset['source_mtime_utc'] < ends[0], asset['file']
print('PASS: four genuine action types, candidate chronology, acceptance limits, and eight original image hashes.')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--remote', action='store_true')
if parser.parse_args().remote:
    # Pass evidence as stdin data, never interpolate source records into shell code.
    verifier = '''import datetime,hashlib,json,pathlib,sys
x=json.load(sys.stdin); root=pathlib.Path(x['source_repository'])
for c in x['cases'].values():
    lines=(root/c['source']).read_text().splitlines()
    selected=[{'line':c['line'],'record':c['record']}]+c.get('preceding_records',[])+c['following_records']
    for row in selected:
        assert json.loads(lines[row['line']-1])==row['record'], (c['source'],row['line'])
for r in x['supporting_records'].values():
    assert json.loads((root/r['source']).read_text())==r['record'], r['source']
for a in x['assets']:
    p=root/a['source']
    assert hashlib.sha256(p.read_bytes()).hexdigest()==a['source_sha256'], str(p)
    assert datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat()==a['source_mtime_utc'], str(p)
print('PASS: every retained decision, surrounding event, supporting record, and original image matches rtx3.')
'''
    import shlex
    subprocess.run(['ssh', data['source_host'], 'python3 -c ' + shlex.quote(verifier)],
                   input=json.dumps(data), text=True, check=True)
