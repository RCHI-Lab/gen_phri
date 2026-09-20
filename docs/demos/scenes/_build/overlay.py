#!/usr/bin/env python3
"""Project human/robot (and optionally room) vertices through view_camera.json onto images/middle.jpg."""
import glob
import json, os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import trimesh

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))  # docs/demos/scenes/_build -> repo root
SCRATCH = os.environ.get("WEB_SCENE_SCRATCH", os.path.join(REPO, "local-data/scene-build"))
EXPORT = os.environ.get("WEB_SCENE_EXPORT") or next(
    (p for p in [os.path.join(SCRATCH, "export")] + sorted(glob.glob(os.path.join(SCRATCH, "final_tasks_export_*")))
     if os.path.isdir(p)), os.path.join(SCRATCH, "export"))  # set up by _build/setup.sh
RX90 = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)


def project(P, cam, W=1280, H=720):
    pos = np.array(cam["pos"]); look = np.array(cam["lookat"]); up = np.array(cam.get("up", [0, 0, 1]))
    f = look - pos; f /= np.linalg.norm(f)
    r = np.cross(f, up); r /= np.linalg.norm(r)
    u = np.cross(r, f)
    d = P - pos
    x, y, z = d @ r, d @ u, d @ f
    fy = (H / 2) / np.tan(np.radians(cam["fov"]) / 2)   # vertical fov
    ok = z > 0.05
    return np.stack([W / 2 + fy * x / z, H / 2 - fy * y / z], 1), ok


def room_points(parts, n=60000):
    pts = []
    for p in parts:
        try:
            s = trimesh.load(p["file"], force="scene")
        except Exception as e:
            continue
        M = np.array(p["matrix"]).reshape(4, 4).T
        for g in s.dump():
            v = np.asarray(g.vertices)
            if len(v) > 3000:
                v = v[np.random.default_rng(0).choice(len(v), 3000, replace=False)]
            v = np.c_[v, np.ones(len(v))] @ M.T
            pts.append(v[:, :3])
    return np.concatenate(pts)


def main(task, with_room=True):
    wd = os.path.join(SCRATCH, "work", task)
    parts = json.load(open(os.path.join(wd, "parts.json")))
    cam = parts["cam"]
    img = plt.imread(os.path.join(EXPORT, task, "images/middle.jpg"))
    H, W = img.shape[:2]
    fig = plt.figure(figsize=(W / 100, H / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.imshow(img); ax.set_xlim(0, W); ax.set_ylim(H, 0); ax.axis("off")
    if with_room:
        rp = room_points(parts["parts"])
        uv, ok = project(rp, cam, W, H)
        ax.scatter(uv[ok, 0], uv[ok, 1], s=0.2, c="yellow", alpha=0.25)
    for name, col in (("human_verts.npy", "cyan"), ("robot_verts.npy", "magenta")):
        P = np.load(os.path.join(wd, name)).astype(float)
        uv, ok = project(P, cam, W, H)
        ax.scatter(uv[ok, 0], uv[ok, 1], s=0.3, c=col, alpha=0.35)
    out = os.path.join(SCRATCH, "overlays", f"{task}.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    fig.savefig(out, dpi=100); print(out)


if __name__ == "__main__":
    main(sys.argv[1], "--no-room" not in sys.argv)
