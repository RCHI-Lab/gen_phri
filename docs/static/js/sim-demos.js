// Demonstration of Generated Simulations: category dropdown, thumbnail grid,
// video player, interactive three.js scene and typed-out generation config.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { MeshoptDecoder } from 'three/addons/libs/meshopt_decoder.module.js';

const TYPE_DURATION_MS = 3500;
const PLAYBACK_RATE = 2; // the clips are slow in real time; play them at 2x
// The scenario shown when the page first loads, rather than the first of the first family.
const DEFAULT_CATEGORY = 'lotion_application';
const DEFAULT_TASK = 't03'; // Left hand and arm
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

const els = {
  section: document.getElementById('sim-demos'),
  category: document.getElementById('sim-category'),
  grid: document.getElementById('sim-grid'),
  prompt: document.getElementById('sim-prompt'),
  promptCategory: document.getElementById('sim-prompt-category'),
  promptTitle: document.getElementById('sim-prompt-title'),
  promptText: document.getElementById('sim-prompt-text'),
  video: document.getElementById('sim-video'),
  viewer: document.getElementById('sim-viewer'),
  status: document.getElementById('sim-viewer-status'),
  reset: document.getElementById('sim-viewer-reset'),
  code: document.getElementById('sim-code'),
  codeScroll: document.getElementById('sim-code-scroll'),
};

let data = null;
let current = null;
let sectionVisible = false;
let motionPaused = document.documentElement.dataset.motionPaused === 'true';
function syncPlayback() {
  if (sectionVisible && !motionPaused && !document.hidden) els.video.play().catch(() => {});
  else els.video.pause();
}
window.addEventListener('site-motion-change', event => {
  motionPaused = event.detail.paused;
  syncPlayback();
});
document.addEventListener('visibilitychange', syncPlayback);

// ---------------------------------------------------------------- 3D viewer

const viewer = (() => {
  let renderer, scene, camera, controls, loader, root = null, home = null;
  let loadToken = 0;
  let running = false;
  let wantRunning = false;

  function init() {
    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    els.viewer.prepend(renderer.domElement);

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0xa9cdef); // sky seen through windows, as in the videos
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.add(new THREE.HemisphereLight(0xffffff, 0x888888, 0.6));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(5, 10, 5);
    scene.add(sun);

    camera = new THREE.PerspectiveCamera(50, 1, 0.02, 100);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;

    const draco = new DRACOLoader();
    draco.setDecoderPath('https://www.gstatic.com/draco/versioned/decoders/1.5.6/');
    loader = new GLTFLoader();
    loader.setDRACOLoader(draco);
    loader.setMeshoptDecoder(MeshoptDecoder);

    new ResizeObserver(resize).observe(els.viewer);
    resize();
    els.reset.addEventListener('click', resetView);
    setRunning(wantRunning);
  }

  function resize() {
    const { clientWidth: w, clientHeight: h } = els.viewer;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }

  function loop() {
    if (!running) return;
    controls.update();
    renderer.render(scene, camera);
    requestAnimationFrame(loop);
  }

  function setRunning(on) {
    wantRunning = on;
    if (on === running || !renderer) return;
    running = on;
    if (on) loop();
  }

  function resetView() {
    if (!home) return;
    camera.fov = home.fov;
    camera.position.copy(home.position);
    controls.target.copy(home.target);
    camera.updateProjectionMatrix();
    controls.update();
  }

  function dispose(obj) {
    obj.traverse((o) => {
      if (o.geometry) o.geometry.dispose();
      const mats = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      for (const m of mats) {
        for (const v of Object.values(m)) if (v && v.isTexture) v.dispose();
        m.dispose();
      }
    });
  }

  function frameBounds(obj) {
    const box = new THREE.Box3().setFromObject(obj);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3()).length();
    return {
      fov: 50,
      target: center,
      position: center.clone().add(new THREE.Vector3(0.6, 0.5, 0.6).multiplyScalar(size * 0.6)),
    };
  }

  async function load(task) {
    if (!renderer) init();
    const token = ++loadToken;
    els.status.hidden = false;
    els.status.textContent = 'Loading scene…';

    const cameraPromise = fetch(task.camera).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    let gltf;
    try {
      gltf = await loader.loadAsync(task.scene, (e) => {
        if (token === loadToken && e.lengthComputable) {
          els.status.textContent = `Loading scene… ${Math.round((100 * e.loaded) / e.total)}%`;
        }
      });
    } catch (err) {
      console.error(`Failed to load ${task.scene}:`, err);
      if (token === loadToken) els.status.textContent = 'Scene unavailable';
      return;
    }
    const meta = await cameraPromise;
    if (token !== loadToken) {
      dispose(gltf.scene);
      return;
    }

    if (root) {
      scene.remove(root);
      dispose(root);
    }
    root = gltf.scene;
    scene.add(root);

    const cam = meta && meta.camera;
    home = cam
      ? { fov: cam.fov || 50, position: new THREE.Vector3(...cam.position), target: new THREE.Vector3(...cam.target) }
      : frameBounds(root);
    const radius = new THREE.Box3().setFromObject(root).getSize(new THREE.Vector3()).length();
    controls.maxDistance = Math.max(radius, 3);
    resetView();
    els.status.hidden = true;
  }

  return { load, setRunning };
})();

// ------------------------------------------------------------ typed config

const typer = (() => {
  let timer = null;
  const cache = new Map();

  function highlight(text) {
    if (window.hljs) return window.hljs.highlight(text, { language: 'yaml', ignoreIllegals: true }).value;
    return text.replace(/[&<>]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' })[c]);
  }

  function stop() {
    if (timer) cancelAnimationFrame(timer);
    timer = null;
    els.codeScroll.classList.remove('typing');
  }

  async function type(task) {
    stop();
    els.code.innerHTML = '';
    let text = cache.get(task.config);
    if (text === undefined) {
      try {
        const res = await fetch(task.config);
        text = res.ok ? await res.text() : '';
        const lines = text.split(/\r?\n/);
        while (lines.length && (!lines[0].trim() || lines[0].trimStart().startsWith('#'))) lines.shift();
        text = lines.join('\n');
      } catch (err) {
        text = '';
      }
      cache.set(task.config, text);
    }
    if (current !== task) return;

    if (reduceMotion) {
      els.code.innerHTML = highlight(text);
      return;
    }

    const start = performance.now();
    let shown = 0;
    els.codeScroll.scrollTop = 0;
    els.codeScroll.classList.add('typing');
    const step = (now) => {
      const n = Math.min(text.length, Math.ceil((text.length * (now - start)) / TYPE_DURATION_MS));
      if (n !== shown) {
        shown = n;
        els.code.innerHTML = highlight(text.slice(0, n));
        els.codeScroll.scrollTop = els.codeScroll.scrollHeight;
      }
      if (n < text.length) timer = requestAnimationFrame(step);
      else stop();
    };
    timer = requestAnimationFrame(step);
  }

  return { type };
})();

// --------------------------------------------------------------- gallery UI

const FADE_MS = reduceMotion ? 0 : 300;
const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function selectTask(task) {
  for (const btn of els.grid.children) {
    btn.classList.toggle('active', btn.dataset.id === task.id);
    btn.setAttribute('aria-pressed', String(btn.dataset.id === task.id));
  }
  if (current === task) return;
  const first = current === null;
  current = task;

  // Show the first-frame poster at once; the video follows when downloaded.
  els.video.removeAttribute('src');
  els.video.poster = task.poster;
  if (!first && FADE_MS) {
    els.video.classList.remove('is-switching');
    void els.video.offsetWidth; // restart the animation
    els.video.classList.add('is-switching');
  }
  fetchVideo(task).then((url) => {
    if (current !== task) return;
    els.video.src = url;
    els.video.defaultPlaybackRate = PLAYBACK_RATE;
    els.video.playbackRate = PLAYBACK_RATE;
    syncPlayback();
    prefetchCategory(task);
  });

  if (sectionVisible) activate();

  if (!first) {
    els.prompt.classList.add('is-leaving');
    await wait(FADE_MS);
    if (current !== task) return;
  }
  els.promptCategory.textContent = `Family: ${data.categories.find((c) => c.id === task.category).label}.`;
  els.promptTitle.textContent = `Location: ${task.name}.`;
  els.promptText.textContent = task.prompt;
  els.prompt.classList.remove('is-leaving');
}

// Videos are small (0.3-4 MB), so download each one whole with fetch() and
// play it from a blob URL. Unlike streaming <video src>, this is fast on any
// static server (including ones without HTTP Range support), and a clip that
// was prefetched plays instantly.
const videoUrls = new Map();
function fetchVideo(task) {
  if (!videoUrls.has(task.id)) {
    videoUrls.set(task.id, fetch(task.video)
      .then((r) => (r.ok ? r.blob() : Promise.reject(r.status)))
      .then((blob) => URL.createObjectURL(blob))
      .catch(() => task.video));
  }
  return videoUrls.get(task.id);
}

// Once the selected video is playing, quietly fetch the rest of its category
// one at a time so the next click is instant.
let prefetchToken = 0;
async function prefetchCategory(task) {
  const token = ++prefetchToken;
  for (const t of data.tasks) {
    if (t.category !== task.category || videoUrls.has(t.id)) continue;
    await fetchVideo(t);
    if (token !== prefetchToken) return;
  }
}

// Wait until the video can play (or a short timeout) before starting the
// much larger scene download, so the two don't compete for bandwidth.
function videoReady(timeoutMs) {
  if (els.video.readyState >= 3) return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      els.video.removeEventListener('canplay', done);
      els.video.removeEventListener('error', done);
      clearTimeout(timer);
      resolve();
    };
    const timer = setTimeout(done, timeoutMs);
    els.video.addEventListener('canplay', done);
    els.video.addEventListener('error', done);
  });
}

let activated = null;
async function activate() {
  if (!current || activated === current) return;
  const task = (activated = current);
  typer.type(task);
  await videoReady(2000);
  if (current === task) {
    try { await viewer.load(task); }
    catch (error) {
      els.status.hidden = false;
      els.status.textContent = 'The 3D scene is unavailable in this browser. You can still watch the scenario video.';
      console.warn('Could not initialize the scene viewer:', error);
    }
  }
}

let categoryToken = 0;
async function showCategory(categoryId, preferredTaskId) {
  const token = ++categoryToken;
  const tasks = data.tasks.filter((t) => t.category === categoryId);
  // Switch the video first so its download starts during the grid fade.
  if (tasks.length) selectTask(tasks.find((t) => t.id === preferredTaskId) || tasks[0]);
  if (els.grid.children.length) {
    els.grid.classList.add('is-leaving');
    await wait(FADE_MS);
    if (token !== categoryToken) return;
  }
  els.grid.innerHTML = '';
  els.grid.classList.remove('is-leaving');
  for (const [i, task] of tasks.entries()) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'sim-thumb';
    btn.style.setProperty('--i', i);
    btn.dataset.id = task.id;
    btn.title = task.name;
    btn.setAttribute('aria-label', task.name);
    btn.setAttribute('aria-pressed', String(task === current));
    const img = document.createElement('img');
    img.src = task.thumb;
    img.alt = task.name;
    img.loading = 'lazy';
    const label = document.createElement('span');
    label.className = 'sim-thumb-label';
    label.textContent = task.name;
    btn.append(img, label);
    btn.addEventListener('click', () => selectTask(task));
    btn.addEventListener('pointerenter', () => fetchVideo(task));
    btn.classList.toggle('active', task === current);
    els.grid.append(btn);
  }
}

async function main() {
  if (!els.section) return;
  data = await fetch('demos/tasks.json').then((r) => r.json());

  for (const c of data.categories) {
    const opt = document.createElement('option');
    opt.value = c.id;
    opt.textContent = c.label;
    els.category.append(opt);
  }
  els.category.addEventListener('change', () => showCategory(els.category.value));

  // Defer the heavy scene download and typing until the section is on screen.
  new IntersectionObserver(([entry]) => {
    sectionVisible = entry.isIntersecting;
    viewer.setRunning(sectionVisible);
    syncPlayback();
    if (sectionVisible) activate();
  }).observe(els.section);

  // Fall back to the first family if the named default is ever removed from tasks.json.
  const start = data.categories.some((c) => c.id === DEFAULT_CATEGORY)
    ? DEFAULT_CATEGORY
    : data.categories[0].id;
  els.category.value = start;
  showCategory(start, DEFAULT_TASK);
}

main().catch(error => {
  els.grid.textContent = 'Scenarios could not load. Reload the page to try again.';
  console.warn('Could not load scenario data:', error);
});
