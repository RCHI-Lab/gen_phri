// Render saved placements with a shared camera, room and presentation palette.
// Usage: NODE_PATH=... node scripts/render_hand_warming.cjs /path/to/export
const {chromium}=require('playwright');
const fs=require('node:fs/promises'),path=require('node:path'),http=require('node:http');
const root=path.resolve(process.argv[2]);
const html=`<!doctype html><style>body{margin:0}canvas{display:block}</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
const renderer=new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setSize(1280,720);renderer.setPixelRatio(1);
renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;renderer.toneMappingExposure=1.1;
renderer.shadowMap.enabled=true;renderer.shadowMap.type=THREE.PCFSoftShadowMap;
document.body.append(renderer.domElement);
const scene=new THREE.Scene();scene.background=new THREE.Color('#ecece6');
const pmrem=new THREE.PMREMGenerator(renderer);const env=new RoomEnvironment();scene.environment=pmrem.fromScene(env,.06).texture;scene.environmentIntensity=.6;
scene.add(new THREE.HemisphereLight(0xfffaf0,0xa5adb0,1.2));
const sunlight=new THREE.DirectionalLight(0xfff5df,2.0);sunlight.castShadow=true;sunlight.shadow.mapSize.set(2048,2048);sunlight.shadow.camera.left=-7;sunlight.shadow.camera.right=7;sunlight.shadow.camera.top=7;sunlight.shadow.camera.bottom=-7;sunlight.shadow.normalBias=.02;sunlight.shadow.bias=-.00005;sunlight.shadow.radius=4;scene.add(sunlight);scene.add(sunlight.target);
const fill=new THREE.DirectionalLight(0xeaf5ff,.5);fill.position.set(-3,4,5);scene.add(fill);
const before=await fetch('before.json').then(r=>r.json());const after=await fetch('after.json').then(r=>r.json());
const camera=new THREE.PerspectiveCamera(before.camera.fov,1280/720,.03,80);
camera.position.fromArray(before.camera.position);camera.lookAt(new THREE.Vector3().fromArray(before.camera.target));
sunlight.position.fromArray(before.camera.target).add(new THREE.Vector3(3,6,3));sunlight.target.position.fromArray(before.camera.target);
const model=(await new GLTFLoader().loadAsync('before.glb')).scene;scene.add(model);model.updateMatrixWorld(true);
const humans=[];window.nodeNames=[];
model.traverse(node=>{if(!node.isMesh)return;window.nodeNames.push(node.name);node.castShadow=true;node.receiveShadow=true;
 const name=node.name.toLowerCase();
 if(name.includes('human__')){humans.push({node,position:node.position.clone()});node.castShadow=true;return;}

});
const p0=before.config.pos,p1=after.config.pos;const delta=new THREE.Vector3(p1[0]-p0[0],p1[2]-p0[2],-(p1[1]-p0[1]));
window.draw=async(t)=>{const u=t*t*(3-2*t);for(const h of humans)h.node.position.copy(h.position).addScaledVector(delta,u);renderer.render(scene,camera);};
window.camera=camera;window.scene=scene;window.draw(0);window.ready=true;
</script>`;
(async()=>{const server=http.createServer(async(req,res)=>{try{if(req.url==='/'){res.setHeader('Content-Type','text/html');return res.end(html)}const file=path.join(root,decodeURIComponent(req.url.slice(1)));if(!file.startsWith(root+path.sep))throw Error('path');res.end(await fs.readFile(file))}catch(e){res.statusCode=404;res.end()}});await new Promise(r=>server.listen(0,'127.0.0.1',r));const browser=await chromium.launch({channel:'chrome',headless:true});try{const page=await browser.newPage({viewport:{width:1280,height:720}});page.on('pageerror',e=>console.error(e));await page.goto('http://127.0.0.1:'+server.address().port);await page.waitForFunction(()=>window.ready,{},{timeout:120000});await fs.writeFile(path.join(root,'render-nodes.json'),JSON.stringify(await page.evaluate(()=>window.nodeNames),null,2));
 for(const [side,t] of [['before',0],['after',1]]){await page.evaluate(t=>window.draw(t),t);await page.locator('canvas').screenshot({path:path.join(root,side+'.png')});}
 if(!process.env.POSTERS_ONLY){await fs.mkdir(path.join(root,'bridge'),{recursive:true});for(let i=0;i<36;i++){await page.evaluate(t=>window.draw(t),i/35);await page.locator('canvas').screenshot({path:path.join(root,'bridge',String(i).padStart(3,'0')+'.png')});}}
 console.log('Rendered placement endpoints and saved-translation bridge.');
 }finally{await browser.close();server.close();}})().catch(e=>{console.error(e);process.exit(1)});
