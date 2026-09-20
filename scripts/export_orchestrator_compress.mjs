// Lossless geometry compression for exported snapshots. Only textures resized.
import fs from 'node:fs';
import path from 'node:path';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const dep=process.env.ORCHESTRATOR_NODE||'/tmp/orchestrator-node/node_modules';
const {NodeIO}=await import(path.join(dep,'@gltf-transform/core/dist/index.js'));
const {ALL_EXTENSIONS,EXTMeshoptCompression}=await import(path.join(dep,'@gltf-transform/extensions/dist/index.js'));
const F=await import(path.join(dep,'@gltf-transform/functions/dist/index.js'));
const {MeshoptEncoder,MeshoptDecoder}=await import(path.join(dep,'meshoptimizer/index.js'));
const sharp=require(path.join(dep,'sharp'));
await MeshoptEncoder.ready;await MeshoptDecoder.ready;
const io=new NodeIO().registerExtensions(ALL_EXTENSIONS).registerDependencies({'meshopt.encoder':MeshoptEncoder,'meshopt.decoder':MeshoptDecoder});
const [src,dest]=process.argv.slice(2);const doc=await io.read(src);
const triangleCount=d=>d.getRoot().listNodes().reduce((sum,n)=>sum+(n.getMesh()?.listPrimitives()||[]).reduce((s,p)=>s+(p.getIndices()?.getCount()||p.getAttribute('POSITION').getCount())/3,0),0);
const triangles=triangleCount(doc);
// Keep the original geometry values. No quantize(), simplify(), or normal edits.
const needsAlpha=new Set(doc.getRoot().listMaterials().filter(m=>m.getAlphaMode()!=='OPAQUE').map(m=>m.getBaseColorTexture()));
for(const t of doc.getRoot().listTextures()){
 const im=t.getImage();if(!im)continue;
 const s=sharp(Buffer.from(im));const meta=await s.metadata();
 const alpha=needsAlpha.has(t)&&meta.hasAlpha;
 const out=alpha?await s.resize(1024,1024,{fit:'inside',withoutEnlargement:true}).png().toBuffer():await s.resize(1024,1024,{fit:'inside',withoutEnlargement:true}).flatten({background:'#fff'}).jpeg({quality:86}).toBuffer();
 t.setImage(new Uint8Array(out)).setMimeType(alpha?'image/png':'image/jpeg');
}
await doc.transform(F.dedup(),F.prune(),F.unpartition());
// QUANTIZE here means no meshopt filters. Inputs remain original FLOAT32 data.
doc.createExtension(EXTMeshoptCompression).setRequired(true).setEncoderOptions({method:EXTMeshoptCompression.EncoderMethod.QUANTIZE});
fs.mkdirSync(path.dirname(dest),{recursive:true});await io.write(dest,doc);
const checked=await io.read(dest);const after=triangleCount(checked);
if(after!==triangles)throw Error(`Triangle count changed: ${triangles} -> ${after}`);
console.log(JSON.stringify({src,dest,bytes:fs.statSync(dest).size,triangles,geometry:'Original float32 positions and indices; lossless EXT_meshopt_compression. No simplification or quantization.'}));
