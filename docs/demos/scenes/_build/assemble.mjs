// Stage 2: merge room gltfs + human.glb + robot.glb into one web-optimised GLB (Y-up) + camera json.
// usage: node assemble.mjs <work/tNN> <out_dir>
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const HERE = path.dirname(new URL(import.meta.url).pathname);
const REPO = path.resolve(HERE, '../../../..'); // docs/demos/scenes/_build -> repo root
const SCRATCH = process.env.WEB_SCENE_SCRATCH || path.join(REPO, 'local-data/scene-build');
const NODE_DIR = process.env.WEB_SCENE_NODE || path.join(SCRATCH, 'node');
const req = (m) => require(path.join(NODE_DIR, 'node_modules', m));
const { NodeIO, Document } = req('@gltf-transform/core');
const { ALL_EXTENSIONS, EXTMeshoptCompression, EXTTextureWebP } = req('@gltf-transform/extensions');
const F = req('@gltf-transform/functions');
const { MeshoptEncoder, MeshoptDecoder, MeshoptSimplifier } = req('meshoptimizer');
const sharp = req('sharp');

const [workDir, outDir] = process.argv.slice(2);
const parts = JSON.parse(fs.readFileSync(path.join(workDir, 'parts.json'), 'utf8'));
const task = parts.task;

await MeshoptEncoder.ready; await MeshoptDecoder.ready; await MeshoptSimplifier.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({
  'meshopt.encoder': MeshoptEncoder, 'meshopt.decoder': MeshoptDecoder });

const doc = new Document();
const scene = doc.createScene('scene');
doc.getRoot().setDefaultScene(scene);
// Z-up (sim) -> Y-up: (x,y,z) -> (x,z,-y) == rotation of -90 deg about X
const S = Math.SQRT1_2;
const mkRoot = (name) => { const n = doc.createNode(name).setRotation([-S, 0, 0, S]); scene.addChild(n); return n; };
const roots = { room: mkRoot('room'), human: mkRoot('human'), robot: mkRoot('robot') };

const partNodes = []; // {name, node, file}
async function mergeInto(file, parent, nodeName, matrix) {
  const src = await io.read(file);
  const map = F.mergeDocuments(doc, src);
  const holder = doc.createNode(nodeName);
  if (matrix) holder.setMatrix(matrix);
  parent.addChild(holder);
  for (const s of src.getRoot().listScenes()) {
    const ts = map.get(s);
    for (const child of ts.listChildren()) { ts.removeChild(child); holder.addChild(child); }
    ts.dispose();
  }
  return holder;
}

for (const p of parts.parts) {
  const node = await mergeInto(p.file, roots.room, p.name, p.matrix);
  partNodes.push({ name: p.name, node, file: p.file });
}
await mergeInto(path.join(workDir, 'human.glb'), roots.human, 'human_body', null);
await mergeInto(path.join(workDir, 'robot.glb'), roots.robot, 'stretch3', null);
for (const s of doc.getRoot().listScenes()) if (s !== scene) s.dispose();

// ---------------- camera / bounds (computed before geometry edits; transforms are unaffected)
const bbox = (n) => F.getBounds(n);
const floors = partNodes.filter((p) => /\/floors\//.test(p.file)).map((p) => bbox(p.node));
const walls = partNodes.filter((p) => /\/walls\/[^/]*\//.test(p.file) && !/exterior/.test(p.file)).map((p) => bbox(p.node));
const zup2yup = ([x, y, z]) => [x, z, -y];
const cam = parts.cam;
const target = zup2yup(cam.lookat), eye0 = zup2yup(cam.pos);
let dir = target.map((t, i) => t - eye0[i]); const d0 = Math.hypot(...dir); dir = dir.map((v) => v / d0);
const inside = (b, p, m) => p[0] > b.min[0] + m && p[0] < b.max[0] - m && p[2] > b.min[2] + m && p[2] < b.max[2] - m;
let floor = floors.find((b) => inside(b, target, 0)) || null;
if (!floor && floors.length) floor = floors.reduce((a, b) => ({ min: a.min.map((v, i) => Math.min(v, b.min[i])), max: a.max.map((v, i) => Math.max(v, b.max[i])) }));
const wallTop = walls.length ? Math.max(...walls.map((b) => b.max[1])) : 2.6;
let D = 2.75, eye;
const MARGIN = 0.2;
for (; D >= d0; D -= 0.05) {
  eye = target.map((t, i) => t - dir[i] * D);
  if (!floor || (inside(floor, eye, MARGIN) && eye[1] < wallTop - 0.15 && eye[1] > 0.2)) break;
}
if (D < d0) { D = d0; eye = eye0; }
const all = F.getBounds(scene);
const r4 = (a) => a.map((v) => Math.round(v * 1e4) / 1e4);
const camJson = { camera: { position: r4(eye), target: r4(target), fov: cam.fov }, bounds: { min: r4(all.min), max: r4(all.max) } };

// ---------------- optimisation
const smallMaterials = new Set();
{ // textures only used by small props -> 512 px
  const matSize = new Map();
  for (const p of partNodes) {
    const b = bbox(p.node); const diag = Math.hypot(...b.max.map((v, i) => v - b.min[i]));
    p.node.traverse((n) => { const m = n.getMesh(); if (!m) return;
      for (const prim of m.listPrimitives()) { const mat = prim.getMaterial(); if (mat) matSize.set(mat, Math.max(matSize.get(mat) || 0, diag)); } });
  }
  for (const [m, d] of matSize) if (d < 0.6) smallMaterials.add(m);
}
const texInfo = new Map(); // texture -> {max, alpha}
for (const mat of doc.getRoot().listMaterials()) {
  const small = smallMaterials.has(mat);
  const alpha = mat.getAlphaMode() !== 'OPAQUE';
  const reg = (t, isBase) => { if (!t) return; const e = texInfo.get(t) || { max: 512, alpha: false };
    if (!small) e.max = 1024; if (isBase && alpha) e.alpha = true; texInfo.set(t, e); };
  reg(mat.getBaseColorTexture(), true); reg(mat.getNormalTexture()); reg(mat.getMetallicRoughnessTexture());
  reg(mat.getOcclusionTexture()); reg(mat.getEmissiveTexture());
}

await doc.transform(F.dedup(), F.prune());
let usesWebp = false;
for (const tex of doc.getRoot().listTextures()) {
  const info = texInfo.get(tex) || { max: 1024, alpha: false };
  const img = tex.getImage(); if (!img) continue;
  let s = sharp(Buffer.from(img)); const meta = await s.metadata();
  const hasAlpha = info.alpha && meta.hasAlpha;
  s = s.resize({ width: info.max, height: info.max, fit: 'inside', withoutEnlargement: true });
  let out, mime;
  if (hasAlpha) { out = await s.webp({ quality: 85 }).toBuffer(); mime = 'image/webp'; usesWebp = true; }
  else { out = await s.flatten({ background: '#ffffff' }).jpeg({ quality: 85, mozjpeg: true }).toBuffer(); mime = 'image/jpeg'; }
  tex.setImage(new Uint8Array(out)).setMimeType(mime).setURI('');
}
if (usesWebp) doc.createExtension(EXTTextureWebP).setRequired(true);

await doc.transform(
  F.dedup(),
  F.weld(),
  (d) => {
    // simplify only heavy primitives
    for (const mesh of d.getRoot().listMeshes()) for (const prim of mesh.listPrimitives()) {
      const idx = prim.getIndices(); const pos = prim.getAttribute('POSITION'); if (!pos) continue;
      const tris = (idx ? idx.getCount() : pos.getCount()) / 3;
      if (tris > 6000) {
        const ratio = Math.max(6000 / tris, 0.15);
        F.simplifyPrimitive(prim, { simplifier: MeshoptSimplifier, ratio, error: 0.002, lockBorder: true });
        const after = (prim.getIndices() ? prim.getIndices().getCount() : prim.getAttribute('POSITION').getCount()) / 3;
        if (after > Math.max(8000, tris * ratio * 1.5)) {
          // Stubborn dense meshes (e.g. articulated furniture parts) are triangle soups with per-face
          // normals, so weld cannot merge vertices and simplify cannot collapse edges. Drop the flat
          // normals (three.js flat-shades primitives without NORMAL), weld, then simplify.
          const n = prim.getAttribute('NORMAL');
          if (n) { prim.setAttribute('NORMAL', null); if (!n.listParents().some((p) => p.propertyType !== 'Root')) n.dispose(); }
          F.weldPrimitive(prim);
          const cnt = (prim.getIndices() ? prim.getIndices().getCount() : prim.getAttribute('POSITION').getCount()) / 3;
          F.simplifyPrimitive(prim, { simplifier: MeshoptSimplifier, ratio: Math.max(8000 / cnt, 0.1), error: 0.01, lockBorder: false });
        }
      }
    }
  },
  F.prune(),
  F.unpartition(),
  F.meshopt({ encoder: MeshoptEncoder, level: 'medium' }),
);

fs.mkdirSync(outDir, { recursive: true });
const glbPath = path.join(outDir, `${task}.glb`);
await io.write(glbPath, doc);
fs.writeFileSync(path.join(outDir, `${task}.json`), JSON.stringify(camJson, null, 1));
let tris = 0; for (const m of doc.getRoot().listMeshes()) for (const p of m.listPrimitives()) tris += (p.getIndices()?.getCount() ?? p.getAttribute('POSITION').getCount()) / 3;
console.log(JSON.stringify({ task, bytes: fs.statSync(glbPath).size, tris, textures: doc.getRoot().listTextures().length, webp: usesWebp, camDist: Math.round(D * 100) / 100 }));
