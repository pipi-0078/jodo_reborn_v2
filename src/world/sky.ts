import * as THREE from 'three/webgpu';
import { SkyMesh } from 'three/addons/objects/SkyMesh.js';

// 「従是西方過十万億仏土」— 太陽は常に西(-X方向)の低い位置に置く
const SUN_ELEVATION_DEG = 7;
const SUN_AZIMUTH_DEG = 270;

export function createSky(scene: THREE.Scene, renderer: THREE.WebGPURenderer): { sunDirection: THREE.Vector3 } {
  const sky = new SkyMesh();
  sky.scale.setScalar(2000);
  sky.turbidity.value = 5;
  sky.rayleigh.value = 2.2;
  sky.mieCoefficient.value = 0.008;
  sky.mieDirectionalG.value = 0.85;

  const phi = THREE.MathUtils.degToRad(90 - SUN_ELEVATION_DEG);
  const theta = THREE.MathUtils.degToRad(SUN_AZIMUTH_DEG);
  const sunDirection = new THREE.Vector3().setFromSphericalCoords(1, phi, theta);
  sky.sunPosition.value.copy(sunDirection);

  // 空そのものから環境マップを焼き、金銀瑠璃玻璃と水面に反射を与える
  try {
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envScene = new THREE.Scene();
    envScene.add(sky);
    scene.environment = pmrem.fromScene(envScene, 0.04).texture;
    scene.environmentIntensity = 0.7;
  } catch (error) {
    console.warn('環境マップの生成に失敗(反射なしで続行):', error);
  }
  scene.add(sky); // fromSceneで一時シーンへ移るため、本シーンへ戻す

  // 西日(主光源)
  const sun = new THREE.DirectionalLight(0xffdfae, 2.6);
  sun.position.copy(sunDirection).multiplyScalar(300);
  scene.add(sun);

  // 空からの回り込み光
  const hemi = new THREE.HemisphereLight(0xf7dfae, 0x8a6a2f, 0.9);
  scene.add(hemi);

  // 金色の靄で遠景を溶かす(空間が狭まったぶん、靄も近くに)
  scene.fog = new THREE.Fog(0xf0cd8e, 45, 420);

  return { sunDirection };
}
