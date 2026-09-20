"""Export the two saved hand-warming placements on rtx3 for presentation renders.

Uses the existing scene exporter; exact source configs and support geometry are
retained. Only texture, room appearance, lighting and camera may change.
"""
from pathlib import Path
import argparse
import json
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R
import export_orchestrator_scenes as ex

ap=argparse.ArgumentParser()
ap.add_argument('--out',type=Path,required=True)
a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
run='room2_t38_hand_warming_left_wrist_and_fingers'
base=ex.ROOT/'scene_generation/human_placement/data'/run/'human_0'
ex.TEXTURE=ex.ROOT/'human_generation/smplitex/requested_20260914/SMPLitex-texture-00002.png'
for side,index in [('before',0),('after',1)]:
 src=base/f'iter_{index:02d}'/'human_config.json';cfg=json.loads(src.read_text())
 room_src=Path(cfg['scene_json']);data=json.loads(room_src.read_text())
 asset_root=(room_src.parent/data['asset_root']).resolve()
 scene=trimesh.Scene()
 sv,room_proof=ex.room(scene,data['entities'],asset_root,cfg['furniture_name'])
 hv,human_proof=ex.human(scene,cfg,a.out/'work'/side)
 body_rot=R.from_quat(cfg['quat'],scalar_first=True).as_matrix()
 forward=body_rot[:,2];forward[2]=0;forward/=np.linalg.norm(forward)
 right=np.cross(forward,[0,0,1])
 target=np.array(cfg['pos'])+np.array([0,0,-.1])
 eye=target+forward*3.0+right*1.2+np.array([0,0,1.0])
 camera={'position':(ex.YUP[:3,:3]@eye).tolist(),'target':(ex.YUP[:3,:3]@target).tolist(),'fov':42}
 path=a.out/f'{side}.glb';scene.export(path)
 proof={'recorded_config':ex.stamp(src),'config':cfg,'source_room':ex.stamp(room_src),'room':room_proof,'human':human_proof,'camera':camera,'export':ex.stamp(path),'policy':'Original room, sofa, recorded pose, root transform and scale retained. SMPLitex appearance and presentation materials/camera/lighting only.'}
 (a.out/f'{side}.json').write_text(json.dumps(proof,indent=2))
 print('Exported',side,path.stat().st_size,flush=True)
