"""Verify the replay evidence, media hashes, and exact rtx3 source bytes."""
import argparse
import hashlib
import json
import shlex
import subprocess
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--remote', action='store_true')
args = ap.parse_args()
root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'docs/data/scenario-generation.json').read_text())
stages = data['stages']
sources = {}
for key, stage in stages.items():
    for ext, digest in stage['media_sha256'].items():
        p = root / f'docs/media/generation/{key}.{ext}'
        assert hashlib.sha256(p.read_bytes()).hexdigest() == digest, p
    before, after = (stage['records'][side] for side in ['before', 'after'])
    assert before['critique.json']['mtime_utc'] < after['critique.json']['mtime_utc']
    assert stage['beforeSeverity'] == before['critique.json']['record']['severity']
    assert stage['afterSeverity'] == after['critique.json']['record']['severity']
    for side in [before, after]:
        for record in side.values():
            sources[record['source']] = record['sha256']

placement = stages['human-placement']['records']
bx = placement['before']['placement_state.json']['record']['x_norm']
ax = placement['after']['placement_state.json']['record']['x_norm']
assert abs(ax - bx - .07) < 1e-9
assert placement['after']['critique.json']['record']['severity'] == 'mild'
motion = stages['robot-motion']['records']
assert motion['before']['human_0/reachable.json']['record']['reachable_waypoints'] == 5
assert motion['after']['human_0/reachable.json']['record']['reachable_waypoints'] == 6
assert 'standoff_dist + 0.1' in motion['before']['generated_trajectory.py']['code']
assert 'p_spine + 0.15' in motion['after']['generated_trajectory.py']['code']
assert '0.35 * mid_sh + 0.65 * mid_hip' in motion['after']['generated_trajectory.py']['code']
robot = stages['robot-placement']
for side, digest in zip(['before', 'after'], robot['rendering_manifest']['candidate_source_sha256']):
    assert robot['records'][side]['generated_placement.py']['sha256'] == digest
assert robot['rendering_manifest']['hero_id'] == 96
rendered_motion = stages['robot-motion']['rendering_provenance']
assert rendered_motion['reachability'] == {'total_waypoints': 6, 'reachable_waypoints': 5}
for source in rendered_motion['sources']:
    sources[source['source']] = source['sha256']
hand = stages['human-placement']['rendering_provenance']
for side in ['before', 'after']:
    for key in ['recorded_config', 'source_room']:
        source = hand[side][key]
        sources[source['source']] = source['sha256']
# Only the recorded root translation is animated between placement candidates.
for key in ['joint_angles', 'betas', 'quat']:
    assert hand['before']['config'].get(key) == hand['after']['config'].get(key), key
assert stages['human-generation']['resultFeedback'] == 'Pose Accepted'
assert stages['human-placement']['resultFeedback'] == 'Placement Improved'
pose = stages['human-generation']
pose_records = pose['records']
report = pose_records['after']['stage_report.json']['record']
assert report['run'] == 'room2_t35_itch_relief_back_of_neck'
assert report['iterations_used'] == 2 and report['accepted_iter'] == 1
assert report['iterations'][1]['generator_action']['type'] == 'apply_deltas'
assert report['iterations'][1]['generator_action']['model_calls'] == 0
for side, iteration in [('before', 0), ('after', 1)]:
    assert report['iterations'][iteration]['critique'] == pose_records[side]['critique.json']['record']
    for source in pose['rendering_provenance'][side]['source']['source_files']:
        sources[source['file']] = source['sha256']
for joint, delta in [('left_hip', 12), ('right_hip', -12)]:
    before = pose_records['before']['human_config.json']['record']['joint_angles'][joint]['z']
    after = pose_records['after']['human_config.json']['record']['joint_angles'][joint]['z']
    assert after - before == delta
orchestration = json.loads((root/'docs/data/orchestrator-examples.json').read_text())
assert pose_records['before']['human_config.json']['source'] != orchestration['supporting_records']['retry_before_human_config']['source']
assert pose_records['after']['human_config.json']['source'] != orchestration['supporting_records']['retry_after_human_config']['source']
if args.remote:
    script = """import hashlib,json,sys
from pathlib import Path
root=Path('/home/npechuk/src/gen_sim_phri')
sources=json.load(sys.stdin)
for path,digest in sources.items():
 assert hashlib.sha256((root/path).read_bytes()).hexdigest()==digest,path
print('PASS: all '+str(len(sources))+' recorded source files match rtx3.')
"""
    subprocess.run(['ssh', 'rtx3', 'python3 -c ' + shlex.quote(script)], input=json.dumps(sources), text=True, check=True)
print('PASS: four chronological pairs, exact parameters, limited outcome claims, and all eight media hashes.')
