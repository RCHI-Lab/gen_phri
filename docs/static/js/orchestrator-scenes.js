// Two reusable, on-demand scene viewers for the recorded before/after candidates.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const section = document.getElementById('orchestration');
section.dataset.scenesEnabled = 'true';
let inView = false;

function dispose(object) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  object.traverse(node => {
    if (node.geometry) geometries.add(node.geometry);
    for (const material of [].concat(node.material || [])) {
      materials.add(material);
      Object.values(material).forEach(value => { if (value?.isTexture) textures.add(value); });
    }
  });
  geometries.forEach(value => value.dispose());
  materials.forEach(value => value.dispose());
  textures.forEach(value => value.dispose());
}

function createViewer() {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1;
  const canvas = renderer.domElement;
  canvas.tabIndex = 0;
  canvas.setAttribute('role', 'img');
  canvas.setAttribute('aria-keyshortcuts', 'ArrowLeft ArrowRight ArrowUp ArrowDown + - Home');
  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  const studio = new RoomEnvironment();
  const environment = pmrem.fromScene(studio, 0.04);
  scene.environment = environment.texture;
  studio.dispose();
  pmrem.dispose();
  scene.add(new THREE.HemisphereLight(0xffffff, 0x888888, 0.65));
  const sun = new THREE.DirectionalLight(0xffffff, 1.2);
  sun.position.set(5, 10, 5);
  scene.add(sun);
  const camera = new THREE.PerspectiveCamera(50, 1, 0.02, 100);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.12;
  controls.screenSpacePanning = true;
  const draco = new DRACOLoader().setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/');
  const loader = new GLTFLoader().setDRACOLoader(draco).setMeshoptDecoder(MeshoptDecoder);
  let host, model, home, currentURL, token = 0, frame = 0, active = false;

  function invalidate() {
    if (active && !frame) frame = requestAnimationFrame(render);
  }
  function render() {
    frame = 0;
    if (!active) return;
    controls.update();
    renderer.render(scene, camera);
  }
  controls.addEventListener('change', invalidate);
  function resize() {
    if (!host?.clientWidth || !host.clientHeight) return;
    renderer.setSize(host.clientWidth, host.clientHeight, false);
    camera.aspect = host.clientWidth / host.clientHeight;
    camera.updateProjectionMatrix();
    invalidate();
  }
  const observer = new ResizeObserver(resize);
  function setActive(value) {
    active = value;
    controls.enabled = value;
    if (value) invalidate();
    else { cancelAnimationFrame(frame); frame = 0; }
  }
  function reset() {
    if (!home) return;
    controls.reset();
    camera.position.fromArray(home.position);
    controls.target.fromArray(home.target);
    camera.fov = home.fov || 50;
    camera.updateProjectionMatrix();
    controls.update();
    invalidate();
  }
  canvas.addEventListener('keydown', event => {
    if (!home) return;
    if (event.key === 'Home') { event.preventDefault(); reset(); return; }
    const keys = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', '+', '=', '-'];
    if (!keys.includes(event.key)) return;
    event.preventDefault();
    const offset = camera.position.clone().sub(controls.target);
    const spherical = new THREE.Spherical().setFromVector3(offset);
    if (event.key === 'ArrowLeft') spherical.theta -= 0.12;
    if (event.key === 'ArrowRight') spherical.theta += 0.12;
    if (event.key === 'ArrowUp') spherical.phi -= 0.10;
    if (event.key === 'ArrowDown') spherical.phi += 0.10;
    if (event.key === '+' || event.key === '=') spherical.radius *= 0.86;
    if (event.key === '-') spherical.radius *= 1.16;
    spherical.radius = THREE.MathUtils.clamp(spherical.radius, controls.minDistance, controls.maxDistance);
    spherical.makeSafe();
    camera.position.copy(controls.target).add(new THREE.Vector3().setFromSpherical(spherical));
    controls.update();
    invalidate();
  });

  async function load(nextHost) {
    const request = ++token;
    observer.disconnect();
    host = nextHost;
    host.prepend(canvas);
    observer.observe(host);
    const description = host.querySelector('img')?.alt || host.dataset.label;
    canvas.setAttribute('aria-label', description + '. Drag to orbit, scroll to zoom. Arrow keys rotate, plus and minus zoom, Home resets.');
    resize();
    if (currentURL === host.dataset.scene && model) {
      host.dataset.state = 'ready';
      setActive(inView && !document.hidden);
      return;
    }
    home = null;
    host.dataset.state = 'loading';
    const status = host.querySelector('.action-scene-status');
    status.textContent = 'Loading scene…';
    setActive(false);
    if (model) { scene.remove(model); dispose(model); model = null; }
    try {
      const response = await fetch(host.dataset.camera);
      if (!response.ok) throw new Error(`Camera unavailable: ${response.status}`);
      const meta = await response.json();
      if (request !== token) return;
      const gltf = await loader.loadAsync(host.dataset.scene);
      if (request !== token) { dispose(gltf.scene); return; }
      model = gltf.scene;
      scene.add(model);
      scene.background = new THREE.Color(meta.background || 0xa9cdef);
      scene.environmentIntensity = meta.subjectBounds ? 0.45 : 1;
      sun.intensity = meta.subjectBounds ? 0.95 : 1.2;
      home = meta.camera;
      controls.minDistance = 0.3;
      controls.maxDistance = Math.max(new THREE.Box3().setFromObject(model).getSize(new THREE.Vector3()).length(), 4);
      reset();
      controls.saveState();
      currentURL = host.dataset.scene;
      // Draw before removing the fallback, including while reduced motion is enabled.
      resize();
      renderer.render(scene, camera);
      host.dataset.state = 'ready';
      setActive(inView && !document.hidden);
    } catch (error) {
      if (request !== token) return;
      host.dataset.state = 'error';
      status.textContent = 'Scene unavailable. Select this action to retry.';
      console.warn('Orchestrator scene could not load:', error);
    }
  }
  return { load, reset, setActive };
}

let viewers;
function select() {
  const panel = section.querySelector('.action-panel:not([hidden])');
  if (!panel) return;
  if (!viewers) {
    try { viewers = [createViewer(), createViewer()]; }
    catch (error) {
      section.querySelectorAll('.action-scene-status').forEach(status => { status.textContent = '3D is unavailable in this browser.'; });
      return;
    }
  }
  panel.querySelectorAll('.action-scene').forEach((host, index) => viewers[index].load(host));
}
section.querySelectorAll('[data-reset-scenes]').forEach(button => button.addEventListener('click', () => viewers?.forEach(viewer => viewer.reset())));
window.addEventListener('orchestrator-action-change', select);
document.addEventListener('visibilitychange', () => viewers?.forEach(viewer => viewer.setActive(inView && !document.hidden)));
new IntersectionObserver(entries => {
  inView = entries.some(entry => entry.isIntersecting);
  if (inView && !viewers) select();
  viewers?.forEach(viewer => viewer.setActive(inView && !document.hidden));
}, { rootMargin: '100px' }).observe(section);
