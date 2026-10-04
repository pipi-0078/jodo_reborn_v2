import { useGalleryBackdrop, usesGalleryBackdrop } from '../../galleryBackdrop';
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { loadShari } from './asset';

const embedded = new URLSearchParams(location.search).get('embedded') === '1';
document.body.classList.toggle('embedded', embedded);
const scene = new THREE.Scene();
scene.background = new THREE.Color('#e9e7ee');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: usesGalleryBackdrop });
renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 0.8;
document.body.append(renderer.domElement);
const room = new RoomEnvironment();
const pmrem = new THREE.PMREMGenerator(renderer);
scene.environment = pmrem.fromScene(room).texture;
room.dispose();
pmrem.dispose();
scene.add(new THREE.HemisphereLight(0xffffff, 0xc5b8cd, 0.35));
const light = new THREE.DirectionalLight(0xffffff, 0.4);
light.position.set(2, 4, 3);
scene.add(light);
const camera = new THREE.PerspectiveCamera(36, 1, 0.005, 30);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = false;
controls.minDistance = 0.12;
controls.maxDistance = 6;
useGalleryBackdrop(scene, renderer, camera, controls, -0.6);
let viewName = 'side';
let paused = matchMedia('(prefers-reduced-motion: reduce)').matches;
let dirty = true;
let mixer: THREE.AnimationMixer | undefined;
let group: THREE.Group | undefined;
let time = 0;
function view(name: string) {
  viewName = name;
  if (name === 'face') {
    controls.target.set(0.348, 0.097, 0);
    camera.position.copy(controls.target).add(new THREE.Vector3(0, 0, 0.20));
  } else {
    const distance = Math.max(1.15, 1.15 / camera.aspect) / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)));
    controls.target.set(-0.04, 0, 0);
    camera.position.copy(controls.target).add(new THREE.Vector3(
      name === 'front' ? distance : name === 'back' ? -distance : 0,
      0, name === 'side' ? distance : 0,
    ));
  }
  controls.update();
  dirty = true;
}
function syncPause() {
  const button = document.getElementById('pause')!;
  button.textContent = paused ? '再開' : '一時停止';
  button.setAttribute('aria-pressed', String(paused));
}
for (const name of ['side', 'front', 'back', 'face']) document.getElementById(name)!.onclick = () => view(name);
document.getElementById('pause')!.onclick = () => { paused = !paused; syncPause(); dirty = true; };
syncPause();
function resize() {
  const top = usesGalleryBackdrop ? 0 : innerWidth < 650 ? (embedded ? 105 : 195) : 0;
  const height = Math.max(usesGalleryBackdrop ? 1 : 150, innerHeight - top);
  renderer.domElement.style.marginTop = top + 'px';
  renderer.setSize(innerWidth, height);
  camera.aspect = innerWidth / height;
  camera.updateProjectionMatrix();
  view(viewName);
}
resize();
addEventListener('resize', resize);
controls.addEventListener('change', () => { dirty = true; });
try {
  const { gltf, clip, data } = await loadShari();
  group = gltf.scene;
  group.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (mesh.isMesh) mesh.frustumCulled = false;
  });
  mixer = new THREE.AnimationMixer(group);
  mixer.clipAction(clip).play();
  mixer.update(0);
  scene.add(group);
  view(viewName);
  document.getElementById('status')!.textContent = 'ドラッグで回転、スクロールで拡大';
  const url = URL.createObjectURL(new Blob([data], { type: 'model/gltf-binary' }));
  const download = document.getElementById('download') as HTMLAnchorElement;
  download.href = url;
  download.hidden = false;
  addEventListener('pagehide', () => URL.revokeObjectURL(url), { once: true });
  const inspection = {
    scene, camera, renderer, controls, group, mixer, clip,
    pose(t: number) {
      paused = true;
      time = t;
      mixer!.setTime(t);
      group!.updateMatrixWorld(true);
      syncPause();
      renderer.render(scene, camera);
    },
    pause(value = true) { paused = value; syncPause(); },
  };
  Object.assign(window, { __shari: inspection, __ready: true });
} catch (error) {
  document.getElementById('status')!.textContent = '読み込みに失敗しました。再読み込みしてください。';
  console.error(error);
}
let last = performance.now();
renderer.setAnimationLoop(() => {
  const now = performance.now();
  const dt = Math.min((now - last) / 1000, 0.05);
  last = now;
  if (document.hidden) return;
  if (mixer && !paused) {
    time += dt;
    mixer.setTime(time);
    dirty = true;
  }
  if (dirty) {
    renderer.render(scene, camera);
    dirty = false;
  }
});
