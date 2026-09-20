#!/usr/bin/env python3
"""Stage 1 of the web-scene pipeline (per task).

Produces, in <work>/<task>/ :
  human.glb   posed SMPL-X segments (sim Z-up world coordinates, textured)
  robot.glb   posed Stretch 3 (sim Z-up world coordinates, flat PBR colours)
  parts.json  room part list: gltf path + 4x4 matrix (sim Z-up world) for each visual,
              plus camera/room info for stage 2 (assemble.mjs).

Conventions (verified by overlay against images/middle.jpg):
  * Genesis quaternions are wxyz.
  * Room .gltf meshes are Y-up; Genesis/Drake rotate them to Z-up with Rx(+90):
    world = T_entity * Rx(+90) * S(scale) * p_gltf.
  * motion_states.npz qpos = concatenation of entities with n_qs>0 in layout order;
    robot (21) = [joint_base_x, wheels(2), lift, arm l3..l0, wrist yaw/pitch/roll, gripper slide,
    finger L, rubber L x/y, finger R, rubber R x/y, head pan, tilt, nav cam]; human (31) = one dof
    per non-root link in layout order (z,y,x per ball joint, fixed wrist/ankle).
  * Human meshes are baked in the seated/lying pose; joint values are ~0 but applied anyway.
"""
import glob
import argparse, json, os, re, sys, hashlib
import numpy as np
import trimesh
from scipy.spatial.transform import Rotation as R
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))  # docs/demos/scenes/_build -> repo root
SCRATCH = os.environ.get("WEB_SCENE_SCRATCH", os.path.join(REPO, "local-data/scene-build"))
EXPORT = os.environ.get("WEB_SCENE_EXPORT") or next(
    (p for p in [os.path.join(SCRATCH, "export")] + sorted(glob.glob(os.path.join(SCRATCH, "final_tasks_export_*")))
     if os.path.isdir(p)), os.path.join(SCRATCH, "export"))  # set up by _build/setup.sh
STRETCH_XML = os.environ.get(
    "STRETCH_XML", os.path.join(SCRATCH, "robot/stretch_mujoco/stretch_mujoco/models/stretch_mj_3.3.0.xml"))
ROBOT_CACHE = os.path.join(SCRATCH, "cache/robot_geoms.npz")

HUMAN_URDF_SCALE = 0.9   # utils/human_scale.py in the generation code
RX90 = np.array([[1, 0, 0, 0], [0, 0, -1, 0], [0, 1, 0, 0], [0, 0, 0, 1]], float)  # gltf Y-up -> Z-up

ROBOT_JOINTS = ["joint_base_x", "joint_right_wheel", "joint_left_wheel", "joint_lift",
                "joint_arm_l3", "joint_arm_l2", "joint_arm_l1", "joint_arm_l0",
                "joint_wrist_yaw", "joint_wrist_pitch", "joint_wrist_roll",
                "joint_gripper_slide", "joint_gripper_finger_left_open", "rubber_left_x", "rubber_left_y",
                "joint_gripper_finger_right_open", "rubber_right_x", "rubber_right_y",
                "joint_head_pan", "joint_head_tilt", "joint_head_nav_cam"]


def T(pos, quat_wxyz, scale=1.0):
    M = np.eye(4)
    q = np.asarray(quat_wxyz, float)
    M[:3, :3] = R.from_quat([q[1], q[2], q[3], q[0]]).as_matrix() * scale
    M[:3, 3] = pos
    return M


def load_task(task):
    tdir = os.path.join(EXPORT, task)
    man = json.load(open(os.path.join(EXPORT, "MANIFEST.json")))["tasks"]
    entry = [x for x in man if "t%02d" % x["index"] == task][0]
    cfg_path = os.path.join(EXPORT, entry["effective_robot_config"])
    urdf = os.path.join(os.path.dirname(cfg_path), "human_urdf", "actuate-smplx.urdf")
    frame = [im for im in json.load(open(os.path.join(tdir, "images/manifest.json")))["images"]
             if im["path"].endswith("middle.jpg")][0]["frame_index_zero_based"]
    d = np.load(os.path.join(tdir, "data/motion_states.npz"))
    header = json.loads(str(d["header"]))
    qpos = d["qpos"].astype(np.float64)
    frame = min(frame, len(qpos) - 1)
    return dict(tdir=tdir, cfg=json.load(open(cfg_path)), urdf=urdf, frame=frame, header=header,
                q=qpos[frame], room=json.load(open(os.path.join(tdir, "inputs/room_scene.json"))),
                cam=json.load(open(os.path.join(tdir, "inputs/view_camera.json"))))


def split_entities(header, q):
    """Return list of (layout, base_pose, qslice) per entity."""
    out, off = [], 0
    for lay, base in zip(header["layout"], header["base_poses"]):
        n = lay["n_qs"]
        out.append((lay, base, q[off:off + n]))
        off += n
    assert off == len(q), (off, len(q))
    return out


# ---------------------------------------------------------------- room
def is_ceiling_ish(name):
    n = name.lower()
    return any(k in n for k in ("ceiling", "downlight", "recessed_light", "flush_mount", "smoke_alarm", "spotlight"))


def room_parts(info, scene_dir):
    ents = split_entities(info["header"], info["q"])
    robot_i = [i for i, (l, _, _) in enumerate(ents) if "link_lift" in l["links"]][0]
    room_ents = ents[:robot_i]
    parts, gi = [], 0
    # header room entities: any Genesis entity not from room_scene (plane, grass) is skipped by name
    genesis = [(l, b, s) for (l, b, s) in room_ents
               if l["links"][0] not in ("plane_baselink", "grass_ground_glb_baselink")]
    visuals = []
    culled = []
    for e in info["room"]["entities"]:
        if is_ceiling_ish(e["name"]):   # room_render.load_scene_entities(cull_ceiling=True)
            culled.append(e["name"]); continue
        if e.get("articulated"):
            print("WARN articulated entity (visuals used at body pose):", e["name"])
        for v in e["visual"]:
            if v["type"] != "mesh":
                print("WARN non-mesh visual skipped", e["name"], v["type"]); continue
            visuals.append((e, v))
    if len(genesis) != len(visuals):
        print("WARN genesis/visual count mismatch", len(genesis), len(visuals))
    dyn, ptr = 0, 0
    for k, (e, v) in enumerate(visuals):
        scale = float(v.get("scale", 1.0))
        body = T(e["pose"]["translation"], e["pose"]["quaternion_wxyz"])
        pib = T(v["pose_in_body"]["translation"], v["pose_in_body"]["quaternion_wxyz"])
        W = body @ pib
        stem = os.path.splitext(os.path.basename(v["file"]))[0]
        j = ptr
        while j < len(genesis) and genesis[j][0]["links"][0] != stem + "_glb_baselink":
            j += 1
        if j < len(genesis):
            if j != ptr:
                print("WARN skipped genesis entities", [g[0]["links"][0] for g in genesis[ptr:j]])
            lay, base, qs = genesis[j]; ptr = j + 1
            if len(qs) == 7:   # free body: pos + quat(wxyz) at this frame
                if qs[2] < -0.5:   # fell through the floor in simulation: invisible in the video, omit
                    print("WARN dynamic prop fell out of the room, omitted:", e["name"], np.round(qs[:3], 2))
                    continue
                W = T(qs[:3], qs[3:7]); dyn += 1
            elif len(qs) == 0:
                Wb = T(base["pos"], base["quat"])
                if np.abs(Wb[:3, 3] - W[:3, 3]).max() > 1e-3:
                    print("WARN base pose differs from layout", e["name"], Wb[:3, 3], W[:3, 3])
            else:
                print("WARN unexpected n_qs", e["name"], len(qs))
        else:
            print("WARN no genesis entity for", e["name"], "(included at layout pose)")
        M = W @ RX90 @ np.diag([scale, scale, scale, 1.0])
        f = os.path.join(scene_dir, v["file"])
        if not os.path.exists(f):
            print("WARN missing", f); continue
        parts.append(dict(name=e["name"], file=f, matrix=M.T.reshape(-1).tolist(), scale=scale))
    return parts, dyn


# ---------------------------------------------------------------- human
def human_glb(info, out):
    root = ET.parse(info["urdf"]).getroot()
    udir = os.path.dirname(info["urdf"])
    joints = {}
    for j in root.findall("joint"):
        o = j.find("origin")
        xyz = np.array([float(x) for x in o.get("xyz").split()])
        rpy = [float(x) for x in (o.get("rpy") or "0 0 0").split()]
        ax = j.find("axis")
        axis = np.array([float(x) for x in (ax.get("xyz") if ax is not None else "1 0 0").split()])
        joints[j.find("child").get("link")] = dict(parent=j.find("parent").get("link"), xyz=xyz, rpy=rpy,
                                                   axis=axis, type=j.get("type"))
    ents = split_entities(info["header"], info["q"])
    lay, base, qs = [e for e in ents if "left_upperarm_link" in e[0]["links"]][0]
    links = lay["links"]
    assert len(qs) == len(links) - 1
    qmap = {ln: qs[i] for i, ln in enumerate(links[1:])}
    base_T = T(base["pos"], base["quat"])
    # Genesis loads the URDF with scale=HUMAN_URDF_SCALE (0.9), applied to joint origins and meshes
    cache = {links[0]: base_T @ np.diag([HUMAN_URDF_SCALE] * 3 + [1.0])}

    def world(link):
        if link in cache: return cache[link]
        jt = joints[link]
        L = np.eye(4)
        L[:3, :3] = R.from_euler("xyz", jt["rpy"]).as_matrix()
        L[:3, 3] = jt["xyz"]
        J = np.eye(4)
        if jt["type"] in ("revolute", "continuous"):
            J[:3, :3] = R.from_rotvec(jt["axis"] / np.linalg.norm(jt["axis"]) * qmap.get(link, 0.0)).as_matrix()
        cache[link] = world(jt["parent"]) @ L @ J
        return cache[link]

    tex = None
    scene = trimesh.Scene()
    allv = []
    for link in root.findall("link"):
        vis = link.find("visual")
        if vis is None: continue
        o = vis.find("origin")
        V = np.eye(4)
        if o is not None:
            V[:3, :3] = R.from_euler("xyz", [float(x) for x in (o.get("rpy") or "0 0 0").split()]).as_matrix()
            V[:3, 3] = [float(x) for x in (o.get("xyz") or "0 0 0").split()]
        fn = os.path.join(udir, vis.find("geometry/mesh").get("filename"))
        m = trimesh.load(fn, force="mesh", process=False)
        M = world(link.get("name")) @ V
        m.apply_transform(M)
        if tex is None:
            from PIL import Image
            tex = Image.open(os.path.join(os.path.dirname(fn), "material_0.png")).convert("RGB")
        uv = m.visual.uv if hasattr(m.visual, "uv") and m.visual.uv is not None else None
        mat = trimesh.visual.material.PBRMaterial(name="human_skin", baseColorTexture=tex,
                                                  metallicFactor=0.0, roughnessFactor=0.8)
        m.visual = trimesh.visual.TextureVisuals(uv=uv, material=mat)
        scene.add_geometry(m, geom_name=link.get("name"), node_name=link.get("name"))
        allv.append(np.asarray(m.vertices))
    scene.export(out)
    return np.concatenate(allv)


# ---------------------------------------------------------------- robot
def robot_cache():
    import mujoco, fast_simplification
    if os.path.exists(ROBOT_CACHE):
        return dict(np.load(ROBOT_CACHE, allow_pickle=True))["geoms"].tolist()
    m = mujoco.MjModel.from_xml_path(STRETCH_XML)
    geoms = []
    for g in range(m.ngeom):
        if m.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH or m.geom_group[g] != 2:
            continue
        mid = m.geom_dataid[g]
        va, vn = m.mesh_vertadr[mid], m.mesh_vertnum[mid]
        fa, fn = m.mesh_faceadr[mid], m.mesh_facenum[mid]
        v = m.mesh_vert[va:va + vn].astype(np.float64)
        f = m.mesh_face[fa:fa + fn].astype(np.int64)
        mesh = trimesh.Trimesh(v, f, process=True)
        nf = len(mesh.faces)
        target = nf if nf <= 2500 else max(2500, int(nf * 0.12))
        if target < nf:
            vs, fs = fast_simplification.simplify(mesh.vertices, mesh.faces, 1 - target / nf)
            mesh = trimesh.Trimesh(vs, fs, process=True)
        mesh = trimesh.graph.smooth_shade(mesh, angle=np.radians(35))
        matid = m.geom_matid[g]
        if matid >= 0:
            name = m.material(matid).name; rgba = m.mat_rgba[matid].tolist()
        else:
            name = "geom_rgba"; rgba = m.geom_rgba[g].tolist()
        if "Sticker" in name:
            rgba = [0.85, 0.85, 0.85, 1.0]
        geoms.append(dict(body=m.body(m.geom_bodyid[g]).name, geom=g, v=np.asarray(mesh.vertices),
                          f=np.asarray(mesh.faces), n=np.asarray(mesh.vertex_normals), mat=name, rgba=rgba,
                          faces_orig=int(fn)))
    os.makedirs(os.path.dirname(ROBOT_CACHE), exist_ok=True)
    np.savez(ROBOT_CACHE, geoms=np.array(geoms, dtype=object))
    print("robot cache faces", sum(g["faces_orig"] for g in geoms), "->", sum(len(g["f"]) for g in geoms))
    return geoms


ROBOT_BASE_AXIS = np.array([1.0, 0.0, 0.0])   # joint_base_x slides along entity x (verified by overlay)
ROBOT_BASE_EXTRA = np.eye(3)                  # base_link_mobile relative to entity frame


def robot_glb(info, out, tool):
    import mujoco
    m = mujoco.MjModel.from_xml_path(STRETCH_XML)
    d = mujoco.MjData(m)
    ents = split_entities(info["header"], info["q"])
    lay, base, qs = [e for e in ents if "link_lift" in e[0]["links"]][0]
    assert len(qs) == 21
    Tb = T(base["pos"], base["quat"])
    pos = Tb[:3, 3] + Tb[:3, :3] @ (ROBOT_BASE_AXIS * qs[0])
    Rm = Tb[:3, :3] @ ROBOT_BASE_EXTRA
    xyzw = R.from_matrix(Rm).as_quat()
    d.qpos[:7] = [*pos, xyzw[3], *xyzw[:3]]
    for name, val in zip(ROBOT_JOINTS[1:], qs[1:]):
        d.qpos[m.jnt_qposadr[m.joint(name).id]] = val
    mujoco.mj_kinematics(m, d)
    geoms = robot_cache()
    bymat = {}
    for g in geoms:
        gi = g["geom"]
        Rg = d.geom_xmat[gi].reshape(3, 3); pg = d.geom_xpos[gi]
        v = g["v"] @ Rg.T + pg
        n = g["n"] @ Rg.T
        bymat.setdefault((g["mat"], tuple(g["rgba"])), []).append((v, g["f"], n))
    # tool primitive, in link_SG3_gripper_body frame (+z points from the wrist toward the fingertips)
    bid = m.body("link_SG3_gripper_body").id
    Rb = d.xmat[bid].reshape(3, 3); pb = d.xpos[bid]
    # Approximations of the custom tools (the real tool meshes live in the unreleased MJCF):
    #   bathing   : white stem + ~44 mm ball just beyond the fingertips
    #   scratching: yellow block held in the fingertips + thin spike continuing forward (~85 mm tip offset)
    tool_parts = []
    if tool == "bathing":
        rod = trimesh.creation.cylinder(radius=0.006, segment=[[0, 0, 0.06], [0, 0, TOOL_TIP_Z - 0.02]], sections=12)
        ball = trimesh.creation.icosphere(subdivisions=2, radius=0.022); ball.apply_translation([0, 0, TOOL_TIP_Z])
        tool_parts = [(rod, "tool_white", (0.95, 0.95, 0.95, 1.0)), (ball, "tool_white", (0.95, 0.95, 0.95, 1.0))]
    elif tool == "scratching":
        block = trimesh.graph.smooth_shade(trimesh.creation.box(extents=[0.04, 0.05, 0.045]), angle=0.5)
        block.apply_translation([0, 0, 0.235])
        spike = trimesh.creation.cylinder(radius=0.003, segment=[[0, 0, 0.255], [0, 0, 0.33]], sections=10)
        y = (0.95, 0.78, 0.1, 1.0)
        tool_parts = [(block, "tool_yellow", y), (spike, "tool_yellow", y)]
    for p, mname, col in tool_parts:
        v = np.asarray(p.vertices) @ Rb.T + pb
        bymat.setdefault((mname, col), []).append(
            (v, np.asarray(p.faces), np.asarray(p.vertex_normals) @ Rb.T))
    scene = trimesh.Scene()
    allv = []
    for (mat, rgba), items in bymat.items():
        vs, fs, ns, off = [], [], [], 0
        for v, f, n in items:
            vs.append(v); fs.append(f + off); ns.append(n); off += len(v)
        mesh = trimesh.Trimesh(np.concatenate(vs), np.concatenate(fs), vertex_normals=np.concatenate(ns), process=False)
        metal = 0.6 if mat == "Reflective_Metal" else 0.0
        mesh.visual = trimesh.visual.TextureVisuals(material=trimesh.visual.material.PBRMaterial(
            name=mat, baseColorFactor=[float(c) for c in rgba], metallicFactor=metal, roughnessFactor=0.5))
        scene.add_geometry(mesh, geom_name="robot_" + mat, node_name="robot_" + mat)
        allv.append(mesh.vertices)
    scene.export(out)
    # also report where the grasp centre / gripper body is, for overlay debugging
    gc = d.xpos[m.body("link_grasp_center").id]
    return np.concatenate(allv), dict(gripper_body=pb.tolist(), grasp_center=gc.tolist())


TOOL_TIP_Z = 0.25


def task_tool(task):
    s = open(os.path.join(EXPORT, task, "configs/motion_invocation.json")).read()
    mm = re.findall(r'"--task",\s*"(\w+)"', s)
    return mm[0] if mm else "bathing"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--scene_dir", required=True)
    ap.add_argument("--work", default=os.path.join(SCRATCH, "work"))
    a = ap.parse_args()
    info = load_task(a.task)
    wd = os.path.join(a.work, a.task); os.makedirs(wd, exist_ok=True)
    parts, dyn = room_parts(info, a.scene_dir)
    hv = human_glb(info, os.path.join(wd, "human.glb"))
    rv, dbg = robot_glb(info, os.path.join(wd, "robot.glb"), task_tool(a.task))
    np.save(os.path.join(wd, "human_verts.npy"), hv[::3].astype(np.float32))
    np.save(os.path.join(wd, "robot_verts.npy"), rv[::5].astype(np.float32))
    # floors / walls for camera clamping
    json.dump(dict(task=a.task, frame=info["frame"], parts=parts, dynamic_props=dyn, cam=info["cam"],
                   tool=task_tool(a.task), debug=dbg), open(os.path.join(wd, "parts.json"), "w"), indent=1)
    print(a.task, "frame", info["frame"], "room parts", len(parts), "dynamic", dyn, "human v", len(hv), "robot v", len(rv))


if __name__ == "__main__":
    main()
