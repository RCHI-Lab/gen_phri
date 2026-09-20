"""Read-only evidence collector. Run on rtx3 and save stdout as records.json.

Retains original critic JSON, generator code, saved parameters, timestamps, and
hashes of the source renders/videos. It never generates or changes run data.
"""
from pathlib import Path
import json,hashlib,datetime
root=Path('/home/npechuk/src/gen_sim_phri'); records={}
paths={
'human-generation': ['human_generation/pose_generation/data/room2_t35_itch_relief_back_of_neck/human_0/iter_00','human_generation/pose_generation/data/room2_t35_itch_relief_back_of_neck/human_0/iter_01'],
'human-placement': ['scene_generation/human_placement/data/room2_t38_hand_warming_left_wrist_and_fingers/human_0/iter_00','scene_generation/human_placement/data/room2_t38_hand_warming_left_wrist_and_fingers/human_0/iter_01'],
'robot-placement': ['scene_generation/robot_placement/data/prone_back_leg_bathing/iter_00','scene_generation/robot_placement/data/prone_back_leg_bathing/iter_01'],
'robot-motion': ['robot_motion_generation/data/room2_t28_skin_assessm_spine/iter_00','robot_motion_generation/data/room2_t28_skin_assessm_spine/iter_01']}
for stage,pair in paths.items():
 records[stage]={}
 for side,path in zip(['before','after'],pair):
  records[stage][side]={}
  for filename in ['critique.json','human_config.json','placement_state.json','robot_config.json','generated_placement.py','generated_trajectory.py','metrics.json','human_0/reachable.json','human_0/metrics.json','human_0/image.png','human_0/view_cam.mp4','iso.png']:
   p=root/path/filename
   if not p.exists():continue
   b=p.read_bytes();r={'source':str(p.relative_to(root)),'sha256':hashlib.sha256(b).hexdigest(),'mtime_utc':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat()}
   if p.suffix=='.json':r['record']=json.loads(b)
   if p.suffix=='.py':r['code']=b.decode()
   records[stage][side][filename]=r
  if stage=='human-generation':
   p=(root/path).parent/'stage_report.json';b=p.read_bytes()
   records[stage][side]['stage_report.json']={'source':str(p.relative_to(root)),'sha256':hashlib.sha256(b).hexdigest(),'mtime_utc':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat(),'record':json.loads(b)}
print(json.dumps(records,indent=2))
