import * as THREE from 'three/webgpu';
import { createSky } from './world/sky';
import { createGround } from './world/ground';
import { createPond } from './world/pond';
import { sampleGround } from './world/layout';
import { FirstPersonWalker } from './controls/firstPerson';

async function main(): Promise<void> {
  const renderer = new THREE.WebGPURenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.85;
  document.body.appendChild(renderer.domElement);
  await renderer.init(); // WebGPU非対応環境では自動でWebGL 2にフォールバック

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 4000);

  // 骨格: 空・黄金の大地・七宝池。建物や木々はギャラリーで承認を得てから据える。
  createSky(scene, renderer);
  createGround(scene, true);
  createPond(scene);

  const overlay = document.getElementById('overlay')!;
  const walker = new FirstPersonWalker(camera, document.body, overlay, sampleGround);
  scene.add(walker.controls.object);

  // 動作検証用フック(ヘッドレステストからカメラを動かす)
  (window as unknown as { __camera?: THREE.PerspectiveCamera }).__camera = camera;
  (window as unknown as { __scene?: THREE.Scene }).__scene = scene;

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  const timer = new THREE.Timer();
  renderer.setAnimationLoop(() => {
    timer.update();
    const dt = Math.min(timer.getDelta(), 0.05);
    walker.update(dt);
    renderer.render(scene, camera);
  });
}

main().catch((error) => {
  console.error('起動に失敗しました:', error);
});
