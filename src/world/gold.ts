import * as THREE from 'three/webgpu';
import { positionLocal, vec3, mix, smoothstep } from 'three/tsl';

// 「黄金為地」— 純金の質感。
// 金は「自分の色」より「何を映しているか」で見え方が決まる。空(淡い青)を映すと軽く白っぽくなるので、
// 金専用の暖色の環境マップ(天頂は深い琥珀、中空は金、地平は白金の光、足元は暗い琥珀)を焼き、
// 純金の反射色(線形 1.0, 0.766, 0.336)・金属度 1.0 で統一する(9/4)。

// 純金の反射色。少し赤みに寄せると古金のように重く見える(9/4 「もう少し重厚に」)
export const PURE_GOLD = new THREE.Color().setRGB(1.0, 0.71, 0.29, THREE.LinearSRGBColorSpace);

// 金として扱うマテリアル名(glb 側の命名)。宝樹の幹・枝も金
const GOLD_NAMES = /^(gold|paving|floor|wall|goldfloor|goldcol|kinpaku|tsuchime|migaki|hameita|gtiles|shippo|petal_gold|bark|twig)/;
// 銀と玻璃(七宝楼閣の欄干・壁・階段)。空を映すと白く軽いので、銀専用の暗めの無彩色環境を映す
const SILVER_NAMES = /^(silver|hari)/;
export const PURE_SILVER = new THREE.Color().setRGB(0.95, 0.93, 0.88, THREE.LinearSRGBColorSpace);

let goldEnvironment: THREE.Texture | null = null;
let silverEnvironment: THREE.Texture | null = null;

export function isGoldMaterial(material: THREE.Material): boolean {
  return GOLD_NAMES.test(material.name);
}

// 勾配ドームから環境マップを焼く。palette は [足元, 地平, 中空, 天頂] の線形色
function bakeEnvironment(renderer: THREE.WebGPURenderer, sunDirection: THREE.Vector3,
  palette: [number[], number[], number[], number[]], glowColor: number[]): THREE.Texture {
  const dome = new THREE.Mesh(
    new THREE.SphereGeometry(100, 32, 16),
    new THREE.MeshBasicNodeMaterial({ side: THREE.BackSide }),
  );
  const dir = positionLocal.normalize();
  const up = dir.y;
  const [below, horizon, mid, zenith] = palette.map((c) => vec3(c[0], c[1], c[2]));
  const upper = mix(mix(horizon, mid, smoothstep(0.03, 0.30, up)), zenith, smoothstep(0.28, 0.85, up));
  const lower = mix(horizon, below, smoothstep(0.0, 0.35, up.negate()));
  const base = mix(lower, upper, smoothstep(-0.02, 0.02, up));
  const sunDot = dir.dot(vec3(sunDirection.x, sunDirection.y, sunDirection.z)).clamp(0.0, 1.0);
  const glow = vec3(1.0, 0.95, 0.85).mul(sunDot.pow(40.0)).mul(2.6)
    .add(vec3(glowColor[0], glowColor[1], glowColor[2]).mul(sunDot.pow(6.0)).mul(0.4));
  (dome.material as THREE.MeshBasicNodeMaterial).colorNode = base.add(glow);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envScene = new THREE.Scene();
  envScene.add(dome);
  return pmrem.fromScene(envScene, 0.04).texture;
}

// 金専用・銀専用の環境マップを焼く(空とは別)。西に光源の照り返し
export function createGoldEnvironment(renderer: THREE.WebGPURenderer, sunDirection: THREE.Vector3): THREE.Texture | null {
  try {
    goldEnvironment = bakeEnvironment(renderer, sunDirection, [
      [0.10, 0.055, 0.015],   // 足元: 暗い琥珀(金の底に重みが出る)
      [0.98, 0.78, 0.42],     // 地平: 金の光
      [0.68, 0.40, 0.13],     // 中空: 深い金
      [0.16, 0.09, 0.025],    // 天頂: ほぼ黒に近い琥珀(映り込みの陰が重さになる)
    ], [1.0, 0.8, 0.45]);
    silverEnvironment = bakeEnvironment(renderer, sunDirection, [
      [0.08, 0.075, 0.07],    // 足元: 暗い灰
      [0.90, 0.86, 0.78],     // 地平: 暖かい白
      [0.50, 0.47, 0.44],     // 中空: 灰
      [0.14, 0.13, 0.13],     // 天頂: 濃い灰
    ], [1.0, 0.9, 0.7]);
    return goldEnvironment;
  } catch (error) {
    console.warn('金の環境マップの生成に失敗(空の反射で続行):', error);
    return null;
  }
}

// マテリアルを純金にする(名前が金のものだけ)。テクスチャ付きは模様を活かし、反射だけ差し替える
// 銀・玻璃は同じ考えで、暗めの無彩色環境を映す重い銀に
export function applyPureGold(material: THREE.Material): void {
  if (SILVER_NAMES.test(material.name)) {
    applyPureSilver(material as THREE.MeshStandardMaterial);
    return;
  }
  if (!isGoldMaterial(material)) return;
  const gold = material as THREE.MeshStandardMaterial;
  if (!('metalness' in gold)) return;
  if (goldEnvironment) {
    gold.envMap = goldEnvironment;
    gold.envMapIntensity = 1.0;
  }
  // 粗さは 0.36〜0.42: 鏡のように磨いた金より、少し鈍い方が厚みを感じる
  if (gold.map) {
    gold.metalness = Math.max(gold.metalness, 0.95);
    gold.roughness = Math.min(gold.roughness, 0.45);
  } else {
    gold.color.copy(PURE_GOLD);
    gold.metalness = 1.0;
    gold.roughness = Math.min(Math.max(gold.roughness, 0.36), 0.42);
  }
  gold.needsUpdate = true;
}

function applyPureSilver(silver: THREE.MeshStandardMaterial): void {
  if (!('metalness' in silver)) return;
  if (silverEnvironment) {
    silver.envMap = silverEnvironment;
    silver.envMapIntensity = 1.0;
  }
  if (silver.name.startsWith('silver')) {
    silver.color.copy(PURE_SILVER);
    silver.metalness = 1.0;
    silver.roughness = Math.min(Math.max(silver.roughness, 0.3), 0.38);
  }
  silver.needsUpdate = true;
}
