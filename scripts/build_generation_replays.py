"""Assemble the recorded scenario replays; no model calls or new verdicts.

Input directory contains records.json from collect_generation_records.py (run on
rtx3) and source/motion-after.mp4. --rendered-scenes contains the hand-warming
export/renders and spine-before-furnished.mp4 (see README for reproduction).
--walkthrough points to the existing paper-video-walkthrough.
Requires Pillow and imageio-ffmpeg. All transitions are presentation edits.
"""
from pathlib import Path
import argparse, hashlib, json, subprocess
from PIL import Image
import imageio_ffmpeg

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser()
ap.add_argument('--source', type=Path, required=True)
ap.add_argument('--walkthrough', type=Path, required=True)
ap.add_argument('--rendered-scenes', type=Path, required=True)
a = ap.parse_args()
OUT = ROOT / 'docs/media/generation'
OUT.mkdir(parents=True, exist_ok=True)
WORK = a.source / 'edit'
WORK.mkdir(exist_ok=True)
ff = imageio_ffmpeg.get_ffmpeg_exe()
records = json.loads((a.source / 'records.json').read_text())
walk = a.walkthrough / 'assets/generation/critic_hero_v2'

def run(*args):
    subprocess.run([ff, '-hide_banner', '-loglevel', 'error', '-y', *map(str, args)], check=True)

def encode_args(path):
    return ['-an', '-r', '24', '-c:v', 'libx264', '-preset', 'fast', '-crf', '22', '-pix_fmt', 'yuv420p', '-threads', '2', '-movflags', '+faststart', path]

def frame(source, dest, crop=None):
    im = Image.open(source).convert('RGB')
    if crop: im = im.crop(crop)
    scale = min(1280 / im.width, 720 / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.Resampling.LANCZOS)
    bg = Image.new('RGB',(1280,720),(242,243,240))
    bg.paste(im,((1280-im.width)//2,(720-im.height)//2))
    bg.save(dest)

def pair_film(stage, before, after, after_video=False):
    # 0–3 candidate, 3–7 feedback, 7–8.2 dissolve, 8.2–15 revised.
    args=['-loop','1','-framerate','24','-i',before]
    if not after_video: args+=['-loop','1','-framerate','24']
    args+=['-i',after]
    after_filter='setpts=PTS-STARTPTS'
    if after_video: after_filter='setpts=(PTS-STARTPTS)*0.292' # 26.48 s into 7.73 s; remaining tail held.
    filters=f'[0:v]trim=duration=8.2,setpts=PTS-STARTPTS,setsar=1,format=yuv420p,fps=24,settb=1/24[a];[1:v]{after_filter},fps=24,scale=1280:720,setsar=1,tpad=stop_mode=clone:stop_duration=8,trim=duration=8,format=yuv420p,fps=24,settb=1/24[b];[a][b]xfade=transition=fade:duration=1.2:offset=7,trim=duration=15[v]'
    run(*args,'-filter_complex',filters,'-map','[v]',*encode_args(OUT/f'{stage}.mp4'))
    Image.open(before).save(OUT/f'{stage}.jpg',quality=92)

pose = a.rendered_scenes / 'pose'
pair_film('human-generation',pose/'before.png',pose/'after.png')
hand = a.rendered_scenes / 'hand-warming'
run('-loop','1','-framerate','24','-i',hand/'before.png',
    '-framerate','30','-i',hand/'bridge/%03d.png',
    '-loop','1','-framerate','24','-i',hand/'after.png',
    '-filter_complex','[0:v]trim=duration=7,setpts=PTS-STARTPTS,setsar=1[a];[1:v]fps=24,tpad=stop_mode=clone:stop_duration=1,trim=duration=1.2,setpts=PTS-STARTPTS,setsar=1[b];[2:v]trim=duration=6.8,setpts=PTS-STARTPTS,setsar=1[c];[a][b][c]concat=n=3:v=1:a=0,trim=duration=15[v]',
    '-map','[v]',*encode_args(OUT/'human-placement.mp4'))
Image.open(hand/'before.png').convert('RGB').save(OUT/'human-placement.jpg',quality=92)
# Give both complete motion attempts time to play. The rejected attempt is a new
# render of the original trajectory using the archived furnished-scene renderer.
initial = a.rendered_scenes/'spine-before-furnished.mp4'
run('-i',initial,'-i',a.source/'source/motion-after.mp4',
    '-filter_complex','[0:v]setpts=(PTS-STARTPTS)*11/34.56,fps=24,scale=1280:720,setsar=1,tpad=stop_mode=clone:stop_duration=2,trim=duration=12.2,settb=1/24[a];[1:v]setpts=(PTS-STARTPTS)*11.8/26.48,fps=24,scale=1280:720,setsar=1,tpad=stop_mode=clone:stop_duration=2,trim=duration=13,settb=1/24[b];[a][b]xfade=transition=fade:duration=1.2:offset=11,trim=duration=24[v]',
    '-map','[v]',*encode_args(OUT/'robot-motion.mp4'))
run('-i',initial,'-frames:v','1','-q:v','2',OUT/'robot-motion.jpg')
# The bathing film already has an actual function-derived 1.2 s revision bridge.
run('-i',walk/'robot_candidate00_hero.mp4','-i',walk/'robot_revision_move_hero.mp4','-i',walk/'robot_candidate01_hero.mp4',
    '-filter_complex','[0:v]trim=start=1.4,setpts=PTS-STARTPTS,fps=24,tpad=stop_mode=clone:stop_duration=7,trim=duration=7,setsar=1[a];[1:v]setpts=PTS-STARTPTS,fps=24,tpad=stop_mode=clone:stop_duration=1,trim=duration=1.2,setsar=1[b];[2:v]setpts=PTS-STARTPTS,fps=24,tpad=stop_mode=clone:stop_duration=1,trim=duration=6.8,setsar=1[c];[a][b][c]concat=n=3:v=1:a=0,trim=duration=15[v]',
    '-map','[v]',*encode_args(OUT/'robot-placement.mp4'))
run('-i',OUT/'robot-placement.mp4','-frames:v','1','-q:v','2',OUT/'robot-placement.jpg')

stages={
'human-generation':dict(task='Back-of-neck itch relief',beforeLabel='Initial pose · iteration 00',afterLabel='Revised pose · iteration 01',outcomeLabel='Pose accepted',
 description='The knees, lower legs and feet intersect. The next local iteration applies the critic’s hip adjustments and clears the collisions.',
 feedback='Move both knees outward to separate the legs and feet. Rotate the left hip outward by 12° and the right hip outward by 12°.',
 change='Apply the critic’s joint deltas: left hip z +12°, right hip z −12°. The pose generator continues within the same stage execution.',
 outcome='Iteration 01 is accepted with negligible critic severity. Recorded self-collision pairs decrease from six to zero.',
 presentation='Task 35’s original saved URDF meshes with SMPLitex appearance, shared camera and lighting. The 1.2-second dissolve compares adjacent local critic-loop iterations; it does not depict an orchestrator retry or optimizer trace.',
 parameters={'critic_suggested_hip_z_delta_deg':[12,-12],'hip_z_deg_before':[-12,12],'hip_z_deg_after':[0,0],'self_collision_pairs_before':6,'self_collision_pairs_after':0},
 rendering_provenance={**{side:json.loads((pose/f'{side}.json').read_text()) for side in ['before','after']},'presentation':json.loads((pose/'presentation.json').read_text())}),
'human-placement':dict(task='Hand warming',beforeLabel='Initial placement · iteration 00',afterLabel='Revised placement · iteration 01',outcomeLabel='Placement improved',
 description='The lower legs intersect the seat. Moving the person forward clears the front cushion.',
 feedback='Move the person forward on the seat so the lower legs clear the front cushion.',
 change='Seat position x: 0.6585 → 0.7285 (+0.07 in normalized furniture coordinates).',
 outcome='The next critic reports a valid placement with mild severity. A 12 mm forearm intersection remains.',
 presentation='Original room and sofa geometry with saved pose and root transforms, SMPLitex appearance, shared camera and softer lighting. The 1.2-second translation illustrates the exact saved root-position change; it is not a simulated body movement.',
 rendering_provenance={side:json.loads((hand/f'{side}.json').read_text()) for side in ['before','after']},
 parameters={'x_norm_before':0.6585,'x_norm_after':0.7284999999999999,'delta_x_norm':0.07,'remaining_forearm_intersection_mm':12}),
'robot-placement':dict(task='Back and leg bathing',beforeLabel='Initial placement · iteration 00',afterLabel='Revised placement · iteration 01',outcomeLabel='Placement revised',
 description='A placement near the shoulders limits ankle access. The next proposal moves toward the hips.',
 feedback='Move the robot toward the hips to reach the back and ankles.',
 change='Shift the base 48 cm toward the hips; keep the 75 cm side standoff.',
 outcome='The original run’s revised placement received negligible critic severity, with balanced access to the back and legs.',
 presentation='The pipeline film’s original placement functions replayed on settled human 96 with the same furnished room. The 1.2-second slide illustrates the proposal change; it is not a navigation trajectory. The critic evaluated the original human 0.',
 parameters={'longitudinal_offset_m_before':0.18,'longitudinal_offset_m_after':-0.30,'shift_m':0.48,'side_standoff_m':0.75},
 rendering_manifest=json.loads((walk/'manifest.json').read_text())),
'robot-motion':dict(task='Spine assessment',beforeLabel='Initial motion · iteration 00',afterLabel='Revised motion · iteration 01',outcomeLabel='Motion accepted',
 description='The retreat is out of reach and the lowest contact is too low. Regeneration shortens the retreat and raises the contact.',
 feedback='Shorten the retreat to stay within reach. Move the lowest contact upward from the hips onto the spine.',
 change='Shorten the retreat from 25 to 15 cm and raise the lowest contact. Reachable waypoints: 5/6 → 6/6.',
 outcome='All six revised waypoints are reachable. The saved critic reports a valid trajectory with negligible severity.',
 presentation='The original iteration-00 trajectory rerendered with the archived furnished-scene renderer at approximately 3.14× speed, followed by the recorded iteration-01 video at approximately 2.24× speed. The 1.2-second dissolve compares attempts. The initial motion is a reconstruction from saved code and scene inputs, not a surviving original recording.',
 timeline_seconds={'initial':0,'feedback':7,'regenerate':11,'revised':12.2,'end':24},
 rendering_provenance=json.loads((a.rendered_scenes/'spine-provenance.json').read_text()),
 parameters={'retreat_m_before':0.25,'retreat_m_after':0.15,'lowest_contact_hip_weight_before':0.8,'lowest_contact_hip_weight_after':0.65,'reachable_waypoints_before':5,'reachable_waypoints_after':6,'total_waypoints':6})}
for stage,obj in stages.items():
    obj['resultFeedback']={'human-generation':'Pose Accepted','human-placement':'Placement Improved','robot-placement':'Placement Accepted','robot-motion':'Motion Accepted'}[stage]
    obj.update(video=f'media/generation/{stage}.mp4',poster=f'media/generation/{stage}.jpg',records=records[stage],
        beforeSeverity=records[stage]['before']['critique.json']['record']['severity'],
        afterSeverity=records[stage]['after']['critique.json']['record']['severity'])
    obj['media_sha256']={ext:hashlib.sha256((OUT/f'{stage}.{ext}').read_bytes()).hexdigest() for ext in ['mp4','jpg']}
    for side in ['before','after']:
        assert records[stage][side]['critique.json']['record']['summary']
manifest={'source_host':'rtx3','source_root':'/home/npechuk/src/gen_sim_phri','verified_on':'2026-09-20',
 'timeline_seconds':{'initial':0,'feedback':3,'regenerate':7,'revised':8.2,'end':15},
 'feedback_policy':'On-screen speech is condensed from the original records, which are included verbatim. Parameters distinguish critic suggestions from measured outcomes.',
 'stages':stages}
(ROOT/'docs/data/scenario-generation.json').write_text(json.dumps(manifest,indent=2)+'\n')
print('Built three 15-second replays, a 24-second motion replay, and provenance manifest.')
