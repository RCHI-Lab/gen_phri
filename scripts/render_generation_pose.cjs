// Render the two original pose meshes with one camera and lighting setup.
// Export with export_orchestrator_pose.py, then pass the directory containing
// before.glb/json and after.glb/json. Requires Playwright and Chrome.
const {chromium} = require('playwright');
const fs = require('node:fs/promises'), path = require('node:path'), http = require('node:http');
const root = path.resolve(process.argv[2]);
const html = `<!doctype html><style>body{margin:0}canvas{display:block}</style>
<script type="importmap">{"imports":{"three":"https://cdn.jsdelivr.net/npm/three@0.169.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.169.0/examples/jsm/"}}</script>
<script type="module">
import * as THREE from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
const renderer = new THREE.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
renderer.setSize(1280,720);renderer.setPixelRatio(1);
renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;
document.body.append(renderer.domElement);
const scene=new THREE.Scene();scene.background=new THREE.Color('#f2f3f0');
const pmrem=new THREE.PMREMGenerator(renderer);scene.environment=pmrem.fromScene(new RoomEnvironment(),.04).texture;scene.environmentIntensity=.7;
scene.add(new THREE.HemisphereLight(0xffffff,0x9ba6ad,1.2));
const key=new THREE.DirectionalLight(0xfff2df,2);key.position.set(2,4,4);scene.add(key);
const fill=new THREE.DirectionalLight(0xeaf5ff,.7);fill.position.set(-3,1,2);scene.add(fill);
const metadata=await Promise.all(['before','after'].map(s=>fetch(s+'.json').then(r=>r.json())));
const bounds=new THREE.Box3();for(const m of metadata){bounds.expandByPoint(new THREE.Vector3(...m.bounds.min));bounds.expandByPoint(new THREE.Vector3(...m.bounds.max));}
const target=bounds.getCenter(new THREE.Vector3());
const camera=new THREE.PerspectiveCamera(35,1280/720,.01,20);camera.position.copy(target).add(new THREE.Vector3(.7,.35,3));camera.lookAt(target);
const loader=new GLTFLoader();const models=await Promise.all(['before','after'].map(s=>loader.loadAsync(s+'.glb')));
models.forEach(m=>scene.add(m.scene));
window.draw=side=>{models.forEach((m,i)=>m.scene.visible=i===side);renderer.render(scene,camera);};
window.presentation={camera:{position:camera.position.toArray(),target:target.toArray(),fov:35},background:'#f2f3f0',geometry:'Original saved meshes; shared camera and lighting; only SMPLitex appearance is changed.'};
window.draw(0);window.ready=true;
</script>`;
(async()=>{
 const server=http.createServer(async(req,res)=>{try{
  if(req.url==='/'){res.setHeader('Content-Type','text/html');return res.end(html);}
  const file=path.join(root,decodeURIComponent(req.url.slice(1)));
  if(!file.startsWith(root+path.sep))throw Error('path');
  res.end(await fs.readFile(file));
 }catch(e){res.statusCode=404;res.end();}});
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1280,height:720}});
  await page.goto('http://127.0.0.1:'+server.address().port);
  await page.waitForFunction(()=>window.ready,null,{timeout:120000});
  for(const [i,side] of ['before','after'].entries()){
   await page.evaluate(i=>window.draw(i),i);
   await page.locator('canvas').screenshot({path:path.join(root,side+'.png')});
  }
  await fs.writeFile(path.join(root,'presentation.json'),JSON.stringify(await page.evaluate(()=>window.presentation),null,2));
  console.log('Rendered distinct critic pose candidates with a shared camera.');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
