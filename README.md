# GenPHRI project website

Static research site. The published site lives in `docs/`; no build step is required.

## Preview

From this repository, run:

```sh
python3 -m http.server 8000
```

Open **http://localhost:8000/docs/**. The gallery uses Three.js and Draco from the CDNs declared in the page and viewer, so the interactive 3D scenes require an internet connection on first load.

## Editing

- `docs/index.html`: research narrative, authors, results, and links.
- `docs/static/css/site.css`: page design and responsive layouts.
- `docs/static/js/site.js`: media loading, motion controls, and deferred gallery initialization.
- `docs/static/js/generation.js` and `docs/static/css/generation.css`: the synchronized scenario-generation replay and right-side critic panel.
- `docs/data/scenario-generation.json`: original critic records, source hashes, saved parameters, rendering provenance, and the four stage descriptions.
- `docs/media/generation/`: three 15-second replays and one 24-second motion replay, their posters, and the pipeline film’s critic badge.
- `docs/static/js/sim-demos.js`: existing 50-task video, configuration, and 3D explorer.
- `docs/static/js/orchestrator-scenes.js`: paired interactive views of recorded orchestrator candidates, using two reusable WebGL canvases.
- `docs/media/orchestrator/scenes/`: eight exported scenes, camera/source metadata, four SMPLitex textures, and rendered fallback thumbnails.
- `docs/demos/tasks.json`: the gallery's scenario catalog.
- `docs/media/`: web-optimized videos and poster images.
- `docs/data/generation-examples.json`: selected recorded critic and orchestrator outputs.
- `docs/data/orchestrator-examples.json`: complete selected decision records, subsequent events, supporting metrics, and media provenance for the four interactive action examples.
- `scripts/render_completion_chart.py`: regenerates the desktop and mobile result charts from the paper’s participant means and standard deviations.
- `docs/static/vendor/highlight/`: vendored highlight.js YAML syntax highlighting and license.

Paper and code links are intentionally marked **forthcoming** until public URLs are available.

## Research and media provenance

Research text, author order, and results follow `HRI_2027/root.tex` as supplied on September 19, 2026. The palette and Linux Libertine figure typography follow the paper's teaser and method figures. The video-led presentation takes inspiration from [SceneSmith](https://scenesmith.github.io/) and [RoboGen](https://robogen-ai.github.io/); no source code or media from those sites is included.

`docs/media/sources.json` maps the optimized clips to their source files in the supplied Downloads and `gen_sim_phri` materials. All clips are silent H.264, 1280 pixels wide, 24 fps, with fast-start metadata. Original source files are unchanged.

The original construction-stage clips (retained in `docs/media/`) and 99-second film come from `gen_sim_phri/paper-video-walkthrough`. Its `README.md`, `film_manifest_revision2.json`, and asset-level provenance document the presentation reconstructions. In particular:

- The human pose reveal interpolates a saved generated pose; it is not an optimization trace.
- The robot-placement stage reveals the initial robot proposal in place. It runs for the same 7.08 seconds as the human generation and placement clips. The full film also contains an illustrated slide between historical placement proposals; that slide is not a navigation trajectory.
- The standalone direct and policy clips use different participants at 4× speed, with continuous footage from the start and no stitching or added blur. Direct execution uses source seconds 0–56 of `sam3 bathing 5.mp4` (14 seconds on the site); policy learning uses source seconds 0–72 of `policy bathing 12.mp4` (18 seconds on the site). Both sources are in `gen_sim_phri/videos-user-studies/`. The 99-second pipeline film retains its original excerpts.
- The study montage uses the supplied version with faces blurred.
- The critic-revision film compares saved proposals for task 16. Base–furniture clearance improves, but this is not a claim that all reachability gates pass.

The earlier critic examples and orchestrator excerpts were read from saved runs on rtx3. Their repository-relative source paths and original selected records are retained in `generation-examples.json`. The new interactive generation section uses condensed feedback backed by the complete records in `scenario-generation.json`, as detailed below.

The orchestration explorer expands the paper's three action families into four cases: accept, steer by retrying, steer by resuming, and backtrack. The examples were verified against rtx3 on September 19, 2026:

- **Accept:** task 7, scalp itch relief, robot placement, September 11 at 22:30 UTC (log line 151). The last candidate (`iter_04`) puts the robot by the knees and fails scalp reachability (9.76%). The orchestrator selects the earlier best (`iter_00`), behind the chair: target reachability is 29.27%, all hard gates pass, and the moderate front-side approach preference remains unresolved. The comparison shows selection of an existing candidate, not a newly generated placement.
- **Retry:** task 39, head and neck towel drying, pose generation, September 12 at 08:22 UTC (log line 215). The last rejected pose (`iter_04`) leaves the arms behind the hips. A contextual retry produces an accepted pose (`iter_00`) with bent elbows and hands forward over the lap. Both original renders survive in the `t39_pose_before_retry_2330` archive, with timestamps bracketing this exact decision. The accepted pose has negligible critic severity; minor resting-contact flags remain.
- **Resume:** task 13, robot placement, September 11 at 22:32 UTC. The orchestrator grants five more iterations. Saved images bracket the intervention (`iter_04` and `iter_09`); the base moves, but reachability still fails. The page labels the revised orientation “Proper angle”; the recorded stage outcome remains budget exhausted, with reachability still flagged.
- **Backtrack:** task 16, robot placement to human placement, September 11 at 15:45 UTC. Before is the rejected robot placement (`iter_04`) with zero target reachability. The backtrack reruns scene selection and human placement, opening access on a different bed; after is the first accepted post-backtrack robot placement (`iter_01`). The paired renders' timestamps and metrics match the log sequence. No additional orchestrator retry intervenes.

The original eight rtx3 comparison images remain as source evidence, with their hashes and timestamps retained. The displayed comparisons are now interactive exports of those recorded configurations, with SMPLitex appearance changes and face UV registration. Each action uses a different existing SMPLitex texture, shared across its before/after pair. Scene metadata records the exact source files, transformations, and any reconstruction from saved parameters; no new behavior is generated. Fallback thumbnails are re-rendered from these same interactive scenes. Task names and reasoning are condensed. These selected histories include superseded attempts; they are not used to recompute the paper's aggregate recovery counts. Full rationales, original log line numbers and timestamps, supporting reports, and asset hashes are in `orchestrator-examples.json`. The explorer uses the paper's Libertine typography and aqua/coral/gold palette. The viewers support orbit, zoom, pan, and reset; arrow keys rotate, plus/minus zoom, and Home restores the camera. Only two action-viewer WebGL contexts are retained, and scenes load on demand. All examples remain readable without JavaScript using the new thumbnails.

Validate the evidence with `python3 scripts/verify_orchestrator_examples.py`; add `--remote` to compare every selected log record, supporting report, and image directly with rtx3. For browser checks, serve this repo on port 8011 and run `node scripts/test_orchestration.cjs` with Playwright available (and Chrome installed). The check covers keyboard navigation, mobile/tablet layouts, compact task labels and reasoning, paired media, and the no-JavaScript fallback. Run `python3 scripts/verify_orchestrator_scenes.py --remote` for the 3D source/texture checks and `node scripts/test_orchestrator_scenes.cjs` for real WebGL loading, orbit/zoom/reset, and context reuse. Re-render fallback thumbnails with `node scripts/render_orchestrator_posters.cjs` against the preview server.

## Interactive scenario generation

The standalone Critic Feedback block is replaced by feedback beside the stage viewer. The first three stages show an initial attempt (0–3 s), condensed critic feedback (3–7 s), a presentation transition (7–8.2 s), and the revised result (8.2–15 s). Spine assessment runs for 24 seconds, with feedback at 7 s, regeneration at 11 s, and the revised result at 12.2 s so both motion attempts are visible. The task uses the shared yellow prompt treatment. The critic speech changes to the recorded outcome after regeneration. Phase buttons jump to each part; clicking the video or pressing Space/K pauses or resumes playback. The Initial attempt button restarts it. Stage tabs support arrow keys and Home/End. Reduced motion disables automatic playback; explicit playback remains available. The critic moves below the video on narrow screens. Native controls remain as a fallback if the record manifest cannot load. Only the selected clip is loaded, and its temporary object URL is released when another clip is ready. This allows seeking even on simple preview servers without HTTP range support.

These are four different recorded tasks, not one continuous run:

- **Human generation:** task 35, back-of-neck itch relief, local iterations 00 and 01. The critic identifies intersecting legs and recommends left-hip z +12° and right-hip z −12°. The next iteration applies these exact deltas (generator action `apply_deltas`, zero generator model calls), reducing six recorded self-collision pairs to zero. Both iterations belong to one accepted pose-generation stage report. This is a local critic correction, distinct from the orchestration explorer’s task-39 contextual retry after budget exhaustion. The original saved meshes receive SMPLitex appearance and a shared camera; the dissolve is an editorial comparison.
- **Human placement:** task 38, iterations 00 and 01. The saved seat coordinate changes from 0.6585 to 0.7285. The saved room and sofa geometry are rerendered with SMPLitex appearance, softer lighting and a shared camera that shows the seating contact. A 1.2-second translation illustrates the exact root-position change; it is not a simulated body movement. The next critic reports mild severity and a remaining 12 mm forearm intersection.
- **Robot placement:** the deployed back-and-leg bathing task, iterations 00 and 01. The pipeline film’s furnished human-96 replay preserves the original placement functions’ 48 cm longitudinal change and 75 cm side standoff. Historical critiques refer to human 0. The illustrated slide is not a navigation trajectory or a new verdict on human 96.
- **Robot motion:** task 28, iterations 00 and 01. The saved generator reduces retreat from 25 to 15 cm and changes the lowest point’s hip blend weight from 0.80 to 0.65. Reachability improves from 5/6 to 6/6 waypoints. The original initial trajectory is reconstructed with the archived furnished-scene renderer at approximately 3.14× speed, followed by the recorded revised motion at approximately 2.24× speed. The reconstruction also reports 5/6 reachable waypoints. No original initial-motion recording survives in the run directory; hashes, render arguments and reconstruction provenance are retained in the manifest.

The original records remain verbatim in the saved manifest. Recheck source bytes and media with `python3 scripts/verify_generation.py --remote`. To rebuild:

1. Run `scripts/collect_generation_records.py` on rtx3 and save stdout as `WORK/records.json`. Copy task 28’s `iter_01/human_0/view_cam.mp4` to `WORK/source/motion-after.mp4`.
2. Export task 35’s `iter_00/human_urdf` and `iter_01/human_urdf` with `scripts/export_orchestrator_pose.py`, using SMPLitex texture 00024 and the original source paths for provenance. Copy the before/after GLB and JSON files into `RENDERS/pose`, then run `node scripts/render_generation_pose.cjs RENDERS/pose` to produce the paired images.
3. Put `scripts/export_hand_warming.py` beside `scripts/export_orchestrator_scenes.py` on rtx3. Run the former with the Genesis Python environment and `--out RENDERS/hand-warming`. Copy its before.glb, before.json and after.json locally, then run `node scripts/render_hand_warming.cjs RENDERS/hand-warming` with Playwright available to generate the endpoints and transition frames. No large temporary GLBs are published.
4. Run `scripts/render_initial_spine.py --out OUTPUT` in the Genesis Python environment on rtx3 (optionally select a free GPU with CUDA_VISIBLE_DEVICES). Copy `OUTPUT/human_0/view_cam.mp4` locally as `RENDERS/spine-before-furnished.mp4` and `OUTPUT/spine-provenance.json` as `RENDERS/spine-provenance.json`. Original run files remain untouched.
5. Run `python3 scripts/build_generation_replays.py --source WORK --walkthrough PATH_TO_paper-video-walkthrough --rendered-scenes RENDERS`. The builder requires Pillow and imageio-ffmpeg.


For browser verification, serve the repo on port 8012 and run `node scripts/test_generation.cjs` with Playwright available. Set `BASE_URL` to use another preview URL. The check covers all four sources, phase seeking, actual playback and regeneration, keyboard controls, global pause, reduced motion, and desktop/tablet/mobile layouts.

## Results terminology

The percentages shown are **mean target completion**, not binary trial success. Chart whiskers show ±1 standard deviation across participants, using the paper’s reported values. Real-world measurements require physical contact/removal; simulated measurements use a 2 cm proximity threshold. The 12-participant study evaluates two tasks on one robot. The 50-scenario gallery is a simulation result, not a claim of 50 real-world deployments.
