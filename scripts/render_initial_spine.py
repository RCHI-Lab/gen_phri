"""Reconstruct task 28's initial motion on rtx3 with the archived room renderer.

Run using the Genesis Python environment. This reads the original trajectory and
frozen scene inputs; all generated files go to --out. The original video did not
survive, so the result is explicitly recorded as a reconstruction.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('/home/npechuk/src/gen_sim_phri')
ap = argparse.ArgumentParser()
ap.add_argument('--out', type=Path, required=True)
ap.add_argument('--provenance-only', action='store_true')
a = ap.parse_args()
a.out = a.out.resolve()
archive = ROOT / 'runs/texture_room2_20260914'
code = archive / 'code'
renderer = code / 'robot_motion_generation/render_robot_motion_demo.py'
scene = archive / 't28/inputs/scene_original'
initial = ROOT / 'robot_motion_generation/data/room2_t28_skin_assessm_spine/iter_00'
camera = initial / 'human_0/view_camera.json'
args = ['--human_idx', '0', '--input_dir', str(initial), '--output_dir', str(a.out),
        '--scene_dir', str(scene), '--robot', 'stretch', '--task', 'scratching',
        '--headless', '--target_segments', 'spine,spine1,spine2',
        '--seated_view', 'back', '--view_camera_json', str(camera)]
overrides = {'PYOPENGL_PLATFORM': 'egl', 'TOOL_LIFT_KEYS': 'scratcher', 'CONTACT_MIN_STEPS': '4'}
if not a.provenance_only:
    subprocess.run([sys.executable, str(renderer), *args], cwd=code,
                   env={**os.environ, **overrides}, check=True)

def stamp(path):
    return {'source': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

sources = [renderer, initial/'generated_trajectory.py', camera,
           ROOT/'scene_assets/scenesmith/NotGenerated_scene_025/scene_drake.json']
sources += sorted(p for p in scene.rglob('*') if p.is_file())
proof = {'kind': 'reconstruction_from_saved_initial_trajectory',
         'sources': [stamp(p) for p in sources], 'render_args': args,
         'environment': overrides, 'working_directory': str(code),
         'video': stamp(a.out/'human_0/view_cam.mp4'),
         'reachability': json.loads((a.out/'human_0/reachable.json').read_text()),
         'limitation': 'Archived renderer and frozen scene reproduce the saved trajectory; this is not the original recording or a new critic evaluation.'}
(a.out/'spine-provenance.json').write_text(json.dumps(proof, indent=2)+'\n')
