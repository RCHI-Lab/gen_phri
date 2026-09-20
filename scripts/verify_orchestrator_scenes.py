"""Verify eight scene exports, four paired SMPLitex appearances, and source hashes.

Use --remote to compare source files and texture files with the actual rtx3 records.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shlex
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SCENES = ROOT / 'docs/media/orchestrator/scenes'
textures = json.loads((SCENES / 'human-textures.json').read_text())
assert set(textures) == {'accept', 'retry', 'resume', 'backtrack'}
assert len({texture['id'] for texture in textures.values()}) == 4
assert len({texture['sha256'] for texture in textures.values()}) == 4
sources = {}
manifest = json.loads((ROOT / 'docs/data/orchestrator-examples.json').read_text())['interactive_scenes']
assert len(manifest) == 8
for snapshot in manifest:
    for kind in ['scene', 'metadata', 'poster']:
        asset = snapshot[kind]
        assert hashlib.sha256((ROOT / 'docs' / asset['file']).read_bytes()).hexdigest() == asset['sha256'], asset['file']
for case, texture in textures.items():
    assert hashlib.sha256((ROOT / texture['file']).read_bytes()).hexdigest() == texture['sha256']
    sources[texture['source']] = texture['sha256']
    for side in ['before', 'after']:
        name = f'{case}-{side}'
        meta = json.loads((SCENES / f'{name}.json').read_text())
        assert all(math.isfinite(value) for key in ['position', 'target'] for value in meta['camera'][key])
        assert 10 <= meta['camera']['fov'] <= 100
        assert meta['source']['texture_sha256'] == texture['sha256'], name
        assert meta['source']['source_files'], name
        for source in meta['source']['source_files']:
            if source['file'] in sources:
                assert sources[source['file']] == source['sha256'], source['file']
            sources[source['file']] = source['sha256']
        raw = (SCENES / f'{name}.glb').read_bytes()
        magic, version, length = struct.unpack_from('<4sII', raw)
        assert magic == b'glTF' and version == 2 and length == len(raw), name
        size, kind = struct.unpack_from('<I4s', raw, 12)
        assert kind == b'JSON'
        gltf = json.loads(raw[20:20+size])
        human_materials = [m for m in gltf.get('materials', []) if 'human' in m.get('name', '').lower()]
        assert human_materials and all(m.get('pbrMetallicRoughness', {}).get('baseColorTexture') for m in human_materials), name
        assert gltf['meshes'] and gltf['nodes'] and gltf['scenes'], name
print('PASS: eight textured GLBs, valid cameras, four distinct SMPLitex textures, consistent before/after appearance.')

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--remote', action='store_true')
if parser.parse_args().remote:
    verifier = '''import hashlib,json,pathlib,sys
sources=json.load(sys.stdin); root=pathlib.Path('/home/npechuk/src/gen_sim_phri')
for source,digest in sources.items():
    path=root/source
    assert hashlib.sha256(path.read_bytes()).hexdigest()==digest, source
print('PASS: '+str(len(sources))+' original scene/texture source files match rtx3 SHA-256 hashes.')
'''
    subprocess.run(['ssh', 'rtx3', 'python3 -c ' + shlex.quote(verifier)], input=json.dumps(sources), text=True, check=True)
