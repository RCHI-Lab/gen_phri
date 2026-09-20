#!/usr/bin/env python3
"""Export recorded static placement candidates, without simulating or calling models.

Run on rtx3 with the Genesis Python environment. All generated files go to --out.
The source repository is read only. Historical rooms are reconstructed from the
original room assets and the exact removal lists retained by the orchestrator.
"""
import argparse, hashlib, json, os, sys, copy
from pathlib import Path
from datetime import datetime, timezone
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R
from PIL import Image
import xml.etree.ElementTree as ET

ROOT=Path('/home/npechuk/src/gen_sim_phri')
sys.path.insert(0,str(ROOT))
RX90=np.eye(4); RX90[:3,:3]=R.from_euler('x',90,degrees=True).as_matrix()
YUP=np.eye(4); YUP[:3,:3]=R.from_euler('x',-90,degrees=True).as_matrix()
TEXTURE=ROOT/'human_generation/smplitex/requested_20260914/SMPLitex-texture-00024.png'
XML=ROOT/'resources/stretch/stretch_gs_virtual_base_bathing_sphere_rotated_big_aruco.xml'
CASES={
 'accept':('room2_t07_itch_relief_scalp',{'before':4,'after':0}),
 'resume':('room2_t13_sponge_bathi_right_foot',{'before':4,'after':9}),
 'backtrack':('room2_t16_back_percuss_mid_back',{'before':4,'after':1}),
}
def stamp(p):
 p=Path(p);return dict(source=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mtime_utc=datetime.fromtimestamp(p.stat().st_mtime,timezone.utc).isoformat(),bytes=p.stat().st_size)
def T(pos,quat):
 m=np.eye(4);m[:3,:3]=R.from_quat(quat,scalar_first=True).as_matrix();m[:3,3]=pos;return m
def origin(e):
 m=np.eye(4)
 if e is not None:
  m[:3,3]=[float(x) for x in e.get('xyz','0 0 0').split()]
  m[:3,:3]=R.from_euler('xyz',[float(x) for x in e.get('rpy','0 0 0').split()]).as_matrix()
 return m
def add(scene,mesh,name,matrix):
 scene.add_geometry(mesh,node_name=name,geom_name=name,transform=YUP@matrix)

def historical_room(key,side,run):
 base=ROOT/'scene_generation/scenesmith/data'
 drops=[]
 if key=='resume':
  source=ROOT/'scene_assets/scenesmith/NotGenerated_scene_036/scene_drake.json'
  drops=['dining_room_dining_table_0','dining_room_dining_chair_3']
  evidence='orchestrator_log.jsonl line 144, latest scene selection before resume line165; scene036 confirmed by saved scene_selection_human_0_a2.log'
 elif key=='backtrack' and side=='before':
  source=base/'room2_t13_sponge_bathi_right_foot/room_scene.json'
  drops=['bedroom_armchair_0']
  evidence='Full undropped original scene071 survives in t13 later scene snapshot; t16 selection log line11 removes bedroom_armchair_0; source scene071 confirmed by fetch/convert logs.'
 else:
  source=base/run/'room_scene.json';evidence='Original room selection remains the same for this snapshot.'
 data=json.loads(source.read_text())
 asset_root=(source.parent/data['asset_root']).resolve()
 sys.path.insert(0,str(ROOT/'scene_generation/scenesmith'))
 from substitute_furniture import entity_group
 kept=[e for e in data['entities'] if entity_group(e['name']) not in drops]
 return kept,asset_root,dict(source=stamp(source),drop=drops,evidence=evidence,room_marker=data.get('_room'))

def room(scene,entities,asset_root,support):
 sources=[];support_bounds=[];culled=[]
 for e in entities:
  name=e['name']
  if any(k in name.lower() for k in ['ceiling','downlight','recessed_light','flush_mount','smoke_alarm','spotlight']):culled.append(name);continue
  body=T(e['pose']['translation'],e['pose']['quaternion_wxyz'])
  for vi,v in enumerate(e.get('visual',[])):
   if v['type']!='mesh':raise ValueError(('Unexpected visual',name,v['type']))
   source=asset_root/v['file']
   # Genesis itself prefers the sibling cached GLB when it exists.
   if source.suffix=='.gltf' and source.with_suffix('.glb').exists():source=source.with_suffix('.glb')
   vis=T(v['pose_in_body']['translation'],v['pose_in_body']['quaternion_wxyz'])
   scale=float(v.get('scale',1));matrix=body@vis@RX90@np.diag([scale,scale,scale,1])
   src=trimesh.load_scene(source,process=False)
   for ni,node in enumerate(src.graph.nodes_geometry):
    local,g=src.graph[node];mesh=src.geometry[g].copy();world=matrix@local
    add(scene,mesh,f'room__{name}__{vi}_{ni}',world)
    if name==support:support_bounds.append(trimesh.transform_points(mesh.vertices,world))
   sources.append(dict(**stamp(source),entity=name,world_matrix=matrix.tolist()))
 return np.concatenate(support_bounds),dict(mesh_sources=sources,ceiling_cull=culled)

def human(scene,cfg,out):
 from argparse import Namespace
 from human_generation.generate_actuated_mesh import main as generate
 out.mkdir(parents=True,exist_ok=True);config=out/'human_config.json';config.write_text(json.dumps(cfg,indent=2))
 urdf=out/'actuate-smplx.urdf'
 if not urdf.exists():
  generate(Namespace(output_dir=str(out),smplx_model_folder=str(ROOT/'resources/models'),seed=0,pose='big_t',config_json=str(config),opaque=False,gender='neutral',uv_map='smplx_uv.obj',smplx_to_uvid_map='smplx_to_uvid_map.pkl',texture=str(TEXTURE),texture_uv_layout='smpl'))
 parsed=ET.parse(urdf).getroot();parents={j.find('child').get('link'):(j.find('parent').get('link'),origin(j.find('origin'))) for j in parsed.findall('joint')}
 scale=np.diag([.9,.9,.9,1]);base=T(cfg['pos'],cfg['quat'])@scale;cache={'base_link':base}
 def world(name):
  if name not in cache:
   p,m=parents[name];cache[name]=world(p)@m
  return cache[name]
 tex=Image.open(TEXTURE).convert('RGB');verts=[];sources=[]
 for link in parsed.findall('link'):
  v=link.find('visual')
  if v is None:continue
  p=out/v.find('geometry/mesh').get('filename');mesh=trimesh.load(p,force='mesh',process=False)
  mat=trimesh.visual.material.PBRMaterial(name='human_skin',baseColorTexture=tex,metallicFactor=0,roughnessFactor=.88)
  mesh.visual=trimesh.visual.TextureVisuals(uv=mesh.visual.uv,material=mat)
  matrix=world(link.get('name'))@origin(v.find('origin'))
  add(scene,mesh,'human__'+link.get('name'),matrix);verts.append(trimesh.transform_points(mesh.vertices,matrix));sources.append(stamp(p))
 return np.concatenate(verts),dict(method='Deterministic original SMPL-X segment generator from recorded betas and axis-angle joint values; no random pose, optimization or simulation; root transform and scale0.9 preserved. Only texture/face UV registration changed.',config=cfg,generated_urdf=stamp(urdf),generated_meshes=sources,generator=stamp(ROOT/'human_generation/generate_actuated_mesh.py'),model=stamp(ROOT/'resources/models/smplx/SMPLX_NEUTRAL.npz'),texture=stamp(TEXTURE))

def robot(scene,cfg):
 import mujoco
 m=mujoco.MjModel.from_xml_path(str(XML));d=mujoco.MjData(m)
 q={'joint_base_x':0,'joint_lift':.85,'joint_arm_l0':.005,'joint_arm_l1':.005,'joint_arm_l2':.005,'joint_arm_l3':.005,'joint_wrist_yaw':0,'joint_wrist_pitch':-.3,'joint_wrist_roll':0,'joint_head_pan':-1.57,'joint_head_tilt':-.3}
 for name,value in q.items():d.qpos[m.jnt_qposadr[m.joint(name).id]]=value
 mujoco.mj_kinematics(m,d)
 # Stretch.configure rotates the generated placement frame +90deg about Z.
 base=T(cfg['robot_pos'],cfg['robot_quat']);base[:3,:3]=R.from_euler('z',90,degrees=True).as_matrix()@base[:3,:3]
 vertices=[];geoms=[]
 for g in range(m.ngeom):
  if m.geom_group[g]!=2:continue
  typ=m.geom_type[g]
  if typ==mujoco.mjtGeom.mjGEOM_MESH:
   mid=m.geom_dataid[g];va,vn=m.mesh_vertadr[mid],m.mesh_vertnum[mid];fa,fn=m.mesh_faceadr[mid],m.mesh_facenum[mid]
   mesh=trimesh.Trimesh(m.mesh_vert[va:va+vn].copy(),m.mesh_face[fa:fa+fn].copy(),process=False)
  elif typ==mujoco.mjtGeom.mjGEOM_SPHERE:mesh=trimesh.creation.icosphere(subdivisions=3,radius=m.geom_size[g,0])
  elif typ==mujoco.mjtGeom.mjGEOM_BOX:mesh=trimesh.creation.box(extents=2*m.geom_size[g])
  elif typ==mujoco.mjtGeom.mjGEOM_CYLINDER:mesh=trimesh.creation.cylinder(radius=m.geom_size[g,0],height=2*m.geom_size[g,1],sections=40)
  else:raise ValueError(('Unsupported visual geom',g,int(typ)))
  matid=m.geom_matid[g];rgba=m.mat_rgba[matid] if matid>=0 else m.geom_rgba[g]
  mesh.visual=trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(name='robot_'+(m.material(matid).name if matid>=0 else str(g)),baseColorFactor=rgba,metallicFactor=.3 if matid>=0 and 'Metal' in m.material(matid).name else 0,roughnessFactor=.55))
  local=np.eye(4);local[:3,:3]=d.geom_xmat[g].reshape(3,3);local[:3,3]=d.geom_xpos[g];world=base@local
  name=m.body(m.geom_bodyid[g]).name;add(scene,mesh,f'robot__{name}__{g}',world);vertices.append(trimesh.transform_points(mesh.vertices,world));geoms.append(dict(index=g,body=name,type=int(typ),matrix=world.tolist(),vertices=len(mesh.vertices),faces=len(mesh.faces)))
 return np.concatenate(vertices),dict(source=stamp(XML),joint_positions=q,other_joint_positions='MuJoCo default qpos0, matching freshly built Genesis renderer without simulation',configure_rotation='+90 degrees world Z, applied by original Stretch.configure',world_base_matrix=base.tolist(),visual_geometries=geoms,tool='Actual placement-renderer default bathing sphere MJCF, including actual visual sphere; no approximate scratcher substituted.')

def main():
 global TEXTURE
 ap=argparse.ArgumentParser();ap.add_argument('--out',default='/tmp/orchestrator-3d');ap.add_argument('--case',choices=list(CASES));a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 for key,(run,sides) in CASES.items():
  if a.case and key!=a.case:continue
  TEXTURE=ROOT/f'human_generation/smplitex/requested_20260914/SMPLitex-texture-{dict(accept="00002",resume="00001",backtrack="00026")[key]}.png'
  for side,iteration in sides.items():
   name=f'{key}-{side}';print('EXPORT',name,flush=True);src=ROOT/'scene_generation/robot_placement/data'/run/f'iter_{iteration:02d}'/'robot_config.json';cfg=json.loads(src.read_text());scene=trimesh.Scene()
   entities,asset_root,rp=historical_room(key,side,run);sv,rs=room(scene,entities,asset_root,cfg['human_config']['furniture_name']);hv,hp=human(scene,cfg['human_config'],out/'work'/name);rv,bp=robot(scene,cfg)
   vv=np.concatenate([sv,hv,rv]);low=vv.min(0);high=vv.max(0);center=(low+high)/2;size=high-low;hr=R.from_quat(cfg['human_config']['quat'],scalar_first=True).as_matrix();face=hr[:,2];head=hr[:,1];axis=face if abs(face[2])<abs(head[2]) else np.cross([0,0,1],head);axis2=np.cross([0,0,1],axis)
   eye=center+axis*size[:2].max()+axis2*size[:2].max()+np.array([0,0,1.0]);fov=60
   if key=='backtrack':eye=center+np.array([0,0,3.8]);fov=42
   camera=dict(camera=dict(position=(YUP[:3,:3]@eye).tolist(),target=(YUP[:3,:3]@center).tolist(),fov=fov),bounds=dict(min=scene.bounds[0].tolist(),max=scene.bounds[1].tolist()),subjectBounds=dict(min=trimesh.transform_points(vv,YUP).min(0).tolist(),max=trimesh.transform_points(vv,YUP).max(0).tolist()))
   path=out/f'{name}.glb';scene.export(path)
   (out/f'{name}.json').write_text(json.dumps(camera,indent=2))
   proof=dict(case=key,side=side,run=run,iteration=iteration,recorded_config=stamp(src),config=cfg,room={**rp,**rs},human=hp,robot=bp,coordinate_conversion='Z-up simulation to Y-up viewer: (x,y,z)->(x,z,-y)',export=stamp(path),geometry_policy='No mesh simplification; original room and robot meshes transformed by recorded configuration. Original SMPL-X generated deterministically from recorded parameters. Texture, UV registration and camera are presentation changes only.')
   (out/f'{name}.provenance.json').write_text(json.dumps(proof,indent=2));print('DONE',name,path.stat().st_size,flush=True)
if __name__=='__main__':main()
