import * as THREE from 'three/webgpu';
import { positionLocal, vec3, mix, smoothstep } from 'three/tsl';

// 「従是西方過十万億仏土」— 太陽は常に西(-X方向)の低い位置に置く
const SUN_ELEVATION_DEG = 7;
const SUN_AZIMUTH_DEG = 270;

export function createSky(scene: THREE.Scene, renderer: THREE.WebGPURenderer): { sunDirection: THREE.Vector3 } {
  const phi = THREE.MathUtils.degToRad(90 - SUN_ELEVATION_DEG);
  const theta = THREE.MathUtils.degToRad(SUN_AZIMUTH_DEG);
  const sunDirection = new THREE.Vector3().setFromSphericalCoords(1, phi, theta);

  // 空のドーム: 天頂は淡い瑠璃、中空は乳白、地平は金。西の光源のまわりだけ白く抜ける。
  // 物理空(SkyMesh)は低い西日だと全面ベージュになり、部材が全部同じ明るさに溶けた(9/3)
  const sky = new THREE.Mesh(
    new THREE.SphereGeometry(1800, 48, 24),
    new THREE.MeshBasicNodeMaterial({ side: THREE.BackSide, fog: false, depthWrite: false }),
  );
  const dir = positionLocal.normalize();
  const elevation = dir.y.clamp(0.0, 1.0);
  const horizon = vec3(1.0, 0.86, 0.58);
  const mid = vec3(0.92, 0.89, 0.84);
  const zenith = vec3(0.56, 0.66, 0.86);
  const band = mix(horizon, mid, smoothstep(0.0, 0.16, elevation));
  const base = mix(band, zenith, smoothstep(0.12, 0.65, elevation));
  const sunDot = dir.dot(vec3(sunDirection.x, sunDirection.y, sunDirection.z)).clamp(0.0, 1.0);
  const glowColor = vec3(1.0, 0.93, 0.74).mul(sunDot.pow(28.0)).mul(1.8)
    .add(vec3(1.0, 0.86, 0.58).mul(sunDot.pow(4.0)).mul(0.35));
  (sky.material as THREE.MeshBasicNodeMaterial).colorNode = base.add(glowColor);

  // 空そのものから環境マップを焼き、金銀瑠璃玻璃に反射を与える
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
  const hemi = new THREE.HemisphereLight(0xe6e6ee, 0x8a6a2f, 0.9);
  scene.add(hemi);

  // 無量光: 西の空、中島の向こうに光の源を置く(加算スプライト)
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: makeSunGlowTexture(), color: 0xfff1cc, transparent: true, opacity: 0.85,
    blending: THREE.AdditiveBlending, depthWrite: false, fog: false,
  }));
  glow.position.copy(sunDirection).multiplyScalar(1500);
  glow.scale.set(900, 900, 1);
  scene.add(glow);

  // 金色の靄で遠景を溶かす(空気遠近: 遠い並木ほど光に溶ける)
  scene.fog = new THREE.Fog(0xf4dca6, 30, 300);

  return { sunDirection };
}

// 光源の輝き(中心は白、外へ金色に薄れる)
function makeSunGlowTexture(): THREE.Texture {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.12, 'rgba(255,245,220,0.75)');
  gradient.addColorStop(0.35, 'rgba(255,225,160,0.28)');
  gradient.addColorStop(0.7, 'rgba(255,210,140,0.07)');
  gradient.addColorStop(1, 'rgba(255,200,120,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}
