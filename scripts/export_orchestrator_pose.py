#!/usr/bin/env python3
"""Export saved retry pose URDF visuals without resampling body geometry.

Requires numpy, scipy, trimesh and Pillow. Supply an unmodified downloaded URDF
folder and a copy of the source repo's human_generation UV registration package.
All joints remain at zero, matching the original pose renderer: joint angles
are already baked into the saved mesh vertices. Head registration changes UVs
only; source OBJ geometry and all node transforms are preserved.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image
from scipy.spatial.transform import Rotation
import trimesh


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def transform(origin):
    mat = np.eye(4)
    if origin is not None:
        mat[:3, 3] = np.fromstring(origin.get('xyz', '0 0 0'), sep=' ')
        mat[:3, :3] = Rotation.from_euler('xyz', np.fromstring(origin.get('rpy', '0 0 0'), sep=' ')).as_matrix()
    return mat


def export(args):
    sys.path.insert(0, str(args.uv_tools))
    from human_generation.smplitex_uv import fix_head_uv
    root = ET.parse(args.source / 'actuate-smplx.urdf').getroot()
    parents = {j.find('child').get('link'): (j.find('parent').get('link'), transform(j.find('origin'))) for j in root.findall('joint')}
    cache = {'base_link': np.eye(4)}
    def world(link):
        if link not in cache:
            parent, local = parents[link]
            cache[link] = world(parent) @ local
        return cache[link]
    texture = Image.open(args.texture).convert('RGB')
    material = trimesh.visual.material.PBRMaterial(name='human_skin', baseColorTexture=texture, metallicFactor=0.0, roughnessFactor=.85, doubleSided=True)
    scene = trimesh.Scene()
    provenance = {'source_host': 'rtx3', 'source_directory': args.remote_source, 'texture_sha256': sha(args.texture), 'source_files': [{'file': args.remote_source + '/actuate-smplx.urdf', 'sha256': sha(args.source / 'actuate-smplx.urdf')}], 'geometry_treatment': 'Original saved URDF meshes and zero-joint forward kinematics. No mesh simplification, regenerated body, or geometry edits. Original Y-up coordinates retained.', 'uv_registration': None}
    vertices = []
    with tempfile.TemporaryDirectory() as tmp:
        for link in root.findall('link'):
            visual = link.find('visual')
            if visual is None:
                continue
            source = args.source / visual.find('geometry/mesh').get('filename')
            actual = source
            if source.name == 'head.obj':
                actual = Path(tmp) / 'head.obj'
                provenance['uv_registration'] = fix_head_uv(source, actual, texture_path=args.texture)
            mesh = trimesh.load(actual, force='mesh', process=False)
            original = trimesh.load(source, force='mesh', process=False)
            assert np.array_equal(mesh.vertices, original.vertices)
            assert np.array_equal(mesh.faces, original.faces)
            mesh.visual = trimesh.visual.TextureVisuals(uv=mesh.visual.uv, material=material)
            local = world(link.get('name')) @ transform(visual.find('origin'))
            mesh.apply_transform(local)
            scene.add_geometry(mesh, node_name=link.get('name'), geom_name=link.get('name'))
            vertices.append(mesh.vertices.copy())
            provenance['source_files'].append({'file': args.remote_source + '/' + str(source.relative_to(args.source)), 'sha256': sha(source), 'vertices': len(mesh.vertices), 'faces': len(mesh.faces)})
    # The pose-generation URDF already uses Y as the human's vertical axis.
    # Keep those coordinates, giving the 3D viewer a naturally seated human.
    allv = np.concatenate(vertices)
    lo, hi = allv.min(axis=0), allv.max(axis=0)
    target = (lo+hi)/2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scene.export(args.output)
    meta = {'background': '#f2f3f0', 'camera': {'position': (target + [1.6,.35,2.7]).tolist(), 'target': target.tolist(), 'fov': 35}, 'bounds': {'min':lo.tolist(),'max':hi.tolist()}, 'source': provenance}
    args.output.with_suffix('.json').write_text(json.dumps(meta, indent=2)+'\n')
    print(json.dumps({'output':str(args.output),'bounds':meta['bounds'],'bytes':args.output.stat().st_size,'vertices':len(allv)}))

if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--remote-source',required=True)
    p.add_argument('--uv-tools',type=Path,required=True)
    p.add_argument('--texture',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    export(p.parse_args())
