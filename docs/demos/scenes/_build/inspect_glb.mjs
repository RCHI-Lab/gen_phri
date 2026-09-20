import path from 'node:path'; import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const S = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const req = (m) => require(path.join(S, 'node/node_modules', m));
const { NodeIO } = req('@gltf-transform/core'); const { ALL_EXTENSIONS } = req('@gltf-transform/extensions');
const { MeshoptDecoder } = req('meshoptimizer'); await MeshoptDecoder.ready;
const io = new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({ 'meshopt.decoder': MeshoptDecoder });
for (const f of process.argv.slice(2)) {
  const doc = await io.read(f); const root = doc.getRoot();
  const top = root.getDefaultScene().listChildren().map((n) => n.getName());
  let noNormals = 0, prims = 0; const emissive = new Set(), unlit = [], blend = [], dbl = [];
  for (const m of root.listMeshes()) for (const p of m.listPrimitives()) { prims++; if (!p.getAttribute('NORMAL')) noNormals++; }
  for (const m of root.listMaterials()) { const e = m.getEmissiveFactor(); if (e.some((v) => v > 0) || m.getEmissiveTexture()) emissive.add(m.getName() + ':' + e);
    if (m.getAlphaMode() !== 'OPAQUE') blend.push(m.getName() + ':' + m.getAlphaMode()); if (m.getDoubleSided()) dbl.push(m.getName()); }
  const texMax = Math.max(...root.listTextures().map((t) => Math.max(...(t.getSize() || [0]))));
  console.log(path.basename(f), JSON.stringify({ top, prims, noNormals, emissive: [...emissive], blend, doubleSided: dbl.length, mats: root.listMaterials().length, texMax, ext: root.listExtensionsUsed().map((e) => e.extensionName) }));
}
