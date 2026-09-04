import * as THREE from 'three/webgpu';
import { pass, mrt, output, emissive } from 'three/tsl';
import { bloom } from 'three/addons/tsl/display/BloomNode.js';
import { createSky } from './world/sky';
import { createGoldEnvironment } from './world/gold';
import { createGround } from './world/ground';
import { createPond } from './world/pond';
import { createProps } from './world/props';
import { createFallingFlowers } from './world/petals';
import { sampleGround } from './world/layout';
import { FirstPersonWalker } from './controls/firstPerson';

async function main(): Promise<void> {
  const renderer = new THREE.WebGPURenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.78;
  document.body.appendChild(renderer.domElement);
  await renderer.init(); // WebGPU非対応環境では自動でWebGL 2にフォールバック

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(70, window.innerWidth / window.innerHeight, 0.1, 4000);

  // 空・黄金の大地・七宝池の骨格に、ギャラリーで承認済みのアセットを据える(如来は別途)
  const { sunDirection } = createSky(scene, renderer);
  createGoldEnvironment(renderer, sunDirection); // 金専用の暖色の環境マップ(部材の読み込み前に)
  createGround(scene, true);
  createPond(scene);
  await createProps(scene);
  const flowers = createFallingFlowers(scene); // 雨天曼陀羅華

  // 後処理: 発光(蓮の光・灯籠)だけを滲ませるブルーム。
  // 輝度しきい値で選ぶと日向の金の地面まで滲んで全体が白飛びするので、発光チャンネル(MRT)だけを使う(9/3)
  const postProcessing = new THREE.PostProcessing(renderer);
  const scenePass = pass(scene, camera);
  scenePass.setMRT(mrt({ output, emissive }));
  const scenePassColor = scenePass.getTextureNode('output');
  const emissivePass = scenePass.getTextureNode('emissive');
  const bloomPass = bloom(emissivePass, 1.4, 0.7, 0.0);
  // 輝度ブルーム(煌めき用)は閾値 2.5 でも西日の地面の照り返しが滲んで白く飛ぶので、メイン空間では使わない(9/4)。
  // ギャラリー(床の照り返しが弱い)だけで使う
  postProcessing.outputNode = scenePassColor.add(bloomPass);

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
    flowers.update(dt);
    postProcessing.render();
  });
}

main().catch((error) => {
  console.error('起動に失敗しました:', error);
});
