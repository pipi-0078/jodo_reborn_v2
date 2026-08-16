// いったん更地:アセットギャラリー(gallery.html)で部材を揃えてから再建立する。
// 池・並木などの旧実装は src/world/ に残してあり、承認済みアセットで組み直す予定。
import * as THREE from 'three/webgpu';
import { createSky } from './world/sky';
import { createGround } from './world/ground';
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

  createSky(scene, renderer);
  createGround(scene);

  const overlay = document.getElementById('overlay')!;
  const walker = new FirstPersonWalker(camera, document.body, overlay);
  scene.add(walker.controls.object);

  // 動作検証用フック(ヘッドレステストからカメラを動かす)
  (window as unknown as { __camera?: THREE.PerspectiveCamera }).__camera = camera;

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
