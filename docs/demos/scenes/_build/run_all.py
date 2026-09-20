#!/usr/bin/env python3
"""Download each SceneSmith scene once, build all tasks that use it, then delete the scene.

Run _build/setup.sh first; it installs everything into <repo>/local-data/scene-build
(export/, venv/, node/, robot/) and prints the command below. Override that location
with $WEB_SCENE_SCRATCH.

usage: local-data/scene-build/venv/bin/python docs/demos/scenes/_build/run_all.py
         [--tasks t07,t12] [--jobs 3] [--out docs/demos/scenes] [--keep]
Pipeline: build_parts.py (poses human/robot, lists room parts) -> assemble.mjs (merge + optimise + camera json).
Verify: overlay.py tNN (vertex projection on images/middle.jpg); render_preview.sh + preview.html (three.js render).
"""
import glob
import argparse, json, os, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))  # docs/demos/scenes/_build -> repo root
SCRATCH = os.environ.get("WEB_SCENE_SCRATCH", os.path.join(REPO, "local-data/scene-build"))
EXPORT = os.environ.get("WEB_SCENE_EXPORT") or next(
    (p for p in [os.path.join(SCRATCH, "export")] + sorted(glob.glob(os.path.join(SCRATCH, "final_tasks_export_*")))
     if os.path.isdir(p)), os.path.join(SCRATCH, "export"))  # set up by _build/setup.sh
SCENES = os.path.join(SCRATCH, "scenes")
PY = os.path.join(SCRATCH, "venv/bin/python")
DEFAULT_OUT = os.path.dirname(HERE)  # docs/demos/scenes


def sh(cmd, log):
    with open(log, "a") as f:
        f.write("$ " + " ".join(cmd) + "\n"); f.flush()
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode:
        raise RuntimeError(f"failed ({r.returncode}): {' '.join(cmd[:3])} see {log}")


def do_scene(scene_dir, entries, out, keep):
    logdir = os.path.join(SCRATCH, "logs"); os.makedirs(logdir, exist_ok=True)
    log = os.path.join(logdir, scene_dir + ".log")
    dest = os.path.join(SCENES, scene_dir)
    tar = os.path.join(SCENES, entries[0]["archive_url"].split("/")[-1])
    results = {}
    try:
        if not os.path.isdir(dest) or not os.listdir(dest):
            if not os.path.exists(tar) or os.path.getsize(tar) < 1e6:
                sh(["curl", "-fsSL", "--retry", "5", entries[0]["archive_url"], "-o", tar + ".part"], log)
                os.replace(tar + ".part", tar)
            os.makedirs(dest, exist_ok=True)
            sh(["tar", "-xf", tar, "-C", dest, "--exclude=*/mujoco/usd/*", "--exclude=*.blend"], log)
        for e in entries:
            t = e["task"]
            try:
                sh([PY, os.path.join(HERE, "build_parts.py"), t, "--scene_dir", dest], log)
                sh(["node", os.path.join(HERE, "assemble.mjs"), os.path.join(SCRATCH, "work", t), out], log)
                results[t] = os.path.getsize(os.path.join(out, t + ".glb"))
            except Exception as ex:
                results[t] = "ERROR " + str(ex)
    except Exception as ex:
        for e in entries:
            results.setdefault(e["task"], "ERROR " + str(ex))
    finally:
        if not keep:
            if os.path.exists(tar): os.remove(tar)
            shutil.rmtree(dest, ignore_errors=True)
    print(scene_dir, results, flush=True)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", default="")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    idx = json.load(open(os.path.join(EXPORT, "SCENE_INDEX.json")))
    want = set(a.tasks.split(",")) if a.tasks else None
    groups = {}
    for e in idx:
        if want and e["task"] not in want: continue
        groups.setdefault(e["scene_directory"], []).append(e)
    os.makedirs(a.out, exist_ok=True); os.makedirs(SCENES, exist_ok=True)
    all_res = {}
    with ThreadPoolExecutor(a.jobs) as ex:
        for r in ex.map(lambda kv: do_scene(kv[0], kv[1], a.out, a.keep), groups.items()):
            all_res.update(r)
    json.dump(all_res, open(os.path.join(SCRATCH, "logs", "results_%d.json" % int(time.time())), "w"), indent=1, sort_keys=True)
    bad = {k: v for k, v in all_res.items() if not isinstance(v, int)}
    print("done", len(all_res), "failed", bad)


if __name__ == "__main__":
    main()
