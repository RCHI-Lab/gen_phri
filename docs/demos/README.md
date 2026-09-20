# Demo assets: "Demonstration of Generated Simulations"

Everything this section needs is committed here, so a fresh clone of the repository
serves the site as-is. Nothing is fetched at runtime except the three.js library
(from a CDN, declared in the import map in `docs/index.html`).

## Running the site

```bash
npx http-server docs -p 8000 -c-1
```

Then open <http://localhost:8000>.

Use a server that supports HTTP Range requests, as this one does. Python's
`python3 -m http.server` does not, which makes the page's larger videos load very
slowly in Chrome.

## What is here

| Path | Size | Contents |
|---|---|---|
| `tasks.json` | 32 KB | The manifest the page reads: 9 categories, 50 tasks, and each task's prompt and asset paths. |
| `videos/` | 30 MB | One clip per task, 720p, no audio. |
| `posters/` | 2 MB | First frame of each clip, shown while the video loads. |
| `thumbs/` | 1 MB | Grid thumbnails, taken from the middle of each clip. |
| `configs/` | 200 KB | Each task's `pipeline_config.yaml`, typed out in the panel. |
| `scenes/` | 201 MB | One `.glb` per task with the room, the person and the robot, plus a `.json` giving the starting camera. |

The page code lives in [`../static/js/sim-demos.js`](../static/js/sim-demos.js) and
[`../static/css/sim-demos.css`](../static/css/sim-demos.css).

### About the scenes

Each `.glb` holds a frozen moment of the simulation, at the same frame as that
task's thumbnail, with three top-level nodes: `room`, `human` and `robot`. Rooms come
from the SceneSmith dataset, using the exact layout each task ran with. Files are
Y-up, in metres, compressed with `EXT_meshopt_compression`, and average 4 MB.

Two approximations: the robot's tool meshes are not in the generation records, so the
bathing and scratching tools are stand-in shapes, and the robot's sticker textures are
replaced with plain grey.

## Rebuilding the scenes

Only needed if the underlying data changes; the built files are already committed.

You need the generation records (`final_tasks_50_*.tar.gz`, about 500 MB), which are
not in git. Put the archive in `local-data/` or pass its path:

```bash
docs/demos/scenes/_build/setup.sh [path/to/final_tasks_50_*.tar.gz]
local-data/scene-build/venv/bin/python docs/demos/scenes/_build/run_all.py
```

`setup.sh` installs everything into `local-data/scene-build`, which is git-ignored:
a Python virtualenv, the Node packages for glTF processing, and the Hello Robot
`stretch_mujoco` model. It needs `python3`, `node`, `npm`, `curl`, `tar` and `git`,
and touches nothing outside that folder. Set `WEB_SCENE_SCRATCH` to put it elsewhere.

`run_all.py` downloads each of the 34 SceneSmith rooms in turn (about 435 MB each),
builds every task using that room, then deletes it, so peak disk use stays modest.
Add `--tasks t07,t12` for specific tasks and `--jobs N` to change how many rooms are
processed at once. Rebuilding one task takes a few minutes, mostly downloading.

Scripts in [`scenes/_build/`](scenes/_build/):

| Script | Role |
|---|---|
| `setup.sh` | Installs the toolchain and unpacks the records. |
| `run_all.py` | Fetches rooms and runs the two stages below per task. |
| `build_parts.py` | Poses the human and robot from the recorded state, lists the room parts. |
| `assemble.mjs` | Merges everything into one optimised GLB and writes the camera json. |
| `overlay.py` | Check: projects the model onto the task's video still. |
| `render_preview.sh`, `preview.html` | Check: renders a built GLB from the original camera. |
| `inspect_glb.mjs` | Prints a GLB's nodes, extensions and sizes. |

## Regenerating videos, thumbnails and posters

From the same records, with `ffmpeg`:

```bash
X=local-data/scene-build/export        # the extracted records
for t in $X/t??; do
  n=$(basename "$t")
  ffmpeg -y -i "$t/final.mp4" -an -c:v libx264 -preset slow -crf 32 \
    -pix_fmt yuv420p -movflags +faststart "docs/demos/videos/$n.mp4"
  ffmpeg -y -i "$t/images/middle.jpg" -vf scale=480:-2 -q:v 4 "docs/demos/thumbs/$n.jpg"
  ffmpeg -y -i "docs/demos/videos/$n.mp4" -frames:v 1 -vf scale=960:-2 -q:v 5 \
    "docs/demos/posters/$n.jpg"
done
```

`tasks.json` is built from each task's `specs/task.md` (title, category, region,
posture and the suite description used as the prompt).
