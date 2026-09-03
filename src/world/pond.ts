import * as THREE from 'three/webgpu';
import {
  positionLocal, positionWorld, time, sin, vec2, vec3, color, uv, texture, mix, smoothstep,
  mx_noise_float, normalMap as normalMapNode, normalView, positionViewDirection,
} from 'three/tsl';
import {
  POND_OUTER, WATER_LEVEL, POND_DEPTH, ISLAND_RADIUS, ISLAND_TOP, ISLAND_FOOT, ISLAND_WATERLINE, BANK_INNER,
} from './layout';

// 「七宝池 八功徳水充満其中 池底純以金沙布地」
// 池底には四宝(金・銀・瑠璃・玻璃)の砂が吹き溜まりを作って敷かれる。
export function createPond(scene: THREE.Scene): void {
  // 斜面と水位(-0.5m)の交点
  const bankWaterline = POND_OUTER - (-WATER_LEVEL) * (POND_OUTER - BANK_INNER) / -POND_DEPTH;
  const islandWaterline = ISLAND_WATERLINE;

  const loader = new THREE.TextureLoader();

  // 砂のマテリアル。同じテクスチャを角度・縮尺を変えて三重に貼り、低周波ノイズで切り替える
  // (アンチタイリング: 1.6m ごとに同じ模様が繰り返す規則性を消す 9/3)
  // 水面下の砂は光が減衰して暗く青みがかる(tintで表現)
  // ripple: 水流の砂紋入り(池底の平場用)。斜面に貼ると横線が地層に見えるので、斜面は砂紋なし
  const makeSand = (repeatU: number, repeatV = repeatU, side: THREE.Side = THREE.FrontSide,
    depth = false, ripple = false): THREE.Material => {
    const file = ripple ? 'pond_sand' : 'pond_sand_flat';
    const map = loader.load(`${import.meta.env.BASE_URL}textures/${file}.png`);
    map.wrapS = map.wrapT = THREE.RepeatWrapping;
    map.colorSpace = THREE.SRGBColorSpace;
    map.anisotropy = 8;
    const normalTex = loader.load(`${import.meta.env.BASE_URL}textures/${file}_normal.png`);
    normalTex.wrapS = normalTex.wrapT = THREE.RepeatWrapping;
    normalTex.anisotropy = 8;

    const base = uv().mul(vec2(repeatU, repeatV));
    const c1 = Math.cos(0.62), s1 = Math.sin(0.62);
    const alt1 = vec2(base.x.mul(c1).sub(base.y.mul(s1)), base.x.mul(s1).add(base.y.mul(c1))).mul(0.79).add(vec2(0.37, 0.61));
    const c2 = Math.cos(2.1), s2 = Math.sin(2.1);
    const alt2 = vec2(base.x.mul(c2).sub(base.y.mul(s2)), base.x.mul(s2).add(base.y.mul(c2))).mul(1.23).add(vec2(0.71, 0.19));
    const w1 = smoothstep(-0.06, 0.06, mx_noise_float(positionWorld.mul(0.45)));
    const w2 = smoothstep(-0.06, 0.06, mx_noise_float(positionWorld.mul(0.27).add(vec3(31.7, 5.3, 12.9))));
    const sample = (tex: THREE.Texture) => mix(mix(texture(tex, base), texture(tex, alt1), w1), texture(tex, alt2), w2);

    const albedo = sample(map).rgb.mul(color(depth ? 0x7e99a4 : 0xffffff));
    const material = new THREE.MeshStandardNodeMaterial({ metalness: 0.48, roughness: 0.55, side });
    material.colorNode = albedo;
    material.emissiveNode = albedo.mul(depth ? 0.03 : 0.10);
    material.normalNode = normalMapNode(sample(normalTex), vec2(1, 1));
    return material;
  };

  // --- 池底(平場) ---
  const floorGeometry = new THREE.CircleGeometry(POND_OUTER + 1, 96);
  floorGeometry.rotateX(-Math.PI / 2);
  const floor = new THREE.Mesh(floorGeometry, makeSand(28, 28, THREE.FrontSide, true, true));
  floor.position.y = POND_DEPTH;
  scene.add(floor);

  // --- 外岸: なだらかに水へ下りる砂の斜面 ---
  const bankDry = new THREE.Mesh(
    new THREE.CylinderGeometry(POND_OUTER, bankWaterline, -WATER_LEVEL, 160, 1, true),
    makeSand(120, 0.48, THREE.BackSide),
  );
  bankDry.position.y = WATER_LEVEL / 2;
  scene.add(bankDry);
  const bankWet = new THREE.Mesh(
    new THREE.CylinderGeometry(bankWaterline, BANK_INNER, WATER_LEVEL - POND_DEPTH, 160, 3, true),
    makeSand(120, 1.6, THREE.BackSide, true),
  );
  bankWet.position.y = (WATER_LEVEL + POND_DEPTH) / 2;
  scene.add(bankWet);

  // --- 中島: 砂の斜面を上がった先に金の頂 ---
  const islandDry = new THREE.Mesh(
    new THREE.CylinderGeometry(ISLAND_RADIUS, islandWaterline, ISLAND_TOP - WATER_LEVEL, 96, 1, true),
    makeSand(40, 0.7 * (ISLAND_TOP - WATER_LEVEL) / 0.9), // 斜面の高さに合わせて縦の繰り返しを保つ(伸びると縞になる)
  );
  islandDry.position.y = (ISLAND_TOP + WATER_LEVEL) / 2;
  scene.add(islandDry);
  const islandWet = new THREE.Mesh(
    new THREE.CylinderGeometry(islandWaterline, ISLAND_FOOT, WATER_LEVEL - POND_DEPTH, 96, 3, true),
    makeSand(40, 1.3, THREE.FrontSide, true),
  );
  islandWet.position.y = WATER_LEVEL - 0.85;
  scene.add(islandWet);
  const islandTop = new THREE.Mesh(
    new THREE.CircleGeometry(ISLAND_RADIUS + 0.05, 64),
    new THREE.MeshStandardMaterial({ color: 0xc9a13b, metalness: 0.5, roughness: 0.5 }),
  );
  islandTop.geometry.rotateX(-Math.PI / 2);
  islandTop.position.y = ISLAND_TOP;
  scene.add(islandTop);

  // --- 八功徳水: 澄み切った水面。二重の波で穏やかに揺れる ---
  // 水面の縁は、岸と中島の斜面が水位(-0.5m)と交わる半径に合わせる
  const waterGeometry = new THREE.RingGeometry(islandWaterline - 0.05, bankWaterline + 0.05, 192, 40);
  waterGeometry.rotateX(-Math.PI / 2);
  const waterMaterial = new THREE.MeshPhysicalNodeMaterial({
    color: 0x2b93a4, transparent: true, opacity: 0.55,
    metalness: 0.0, roughness: 0.10,
    // この世界の空はベージュ色。素直に映すと水までベージュに染まるので、
    // 環境反射をほぼ断ち、瑠璃色の照りをフレネルで自前に持たせる
    envMapIntensity: 0.06,
    specularIntensity: 0.4,
    depthWrite: false,
  });
  const wave = sin(positionLocal.x.mul(0.24).add(time.mul(0.7)))
    .mul(sin(positionLocal.z.mul(0.21).add(time.mul(0.55))))
    .mul(0.16)
    .add(sin(positionLocal.x.mul(0.9).add(positionLocal.z.mul(0.75)).add(time.mul(1.2))).mul(0.045));
  waterMaterial.positionNode = positionLocal.add(vec3(0, wave, 0));
  const fresnel = normalView.dot(positionViewDirection.negate()).saturate().oneMinus().pow(3.0);
  waterMaterial.emissiveNode = vec3(0.16, 0.42, 0.50).mul(fresnel).mul(1.3);
  const water = new THREE.Mesh(waterGeometry, waterMaterial);
  water.position.y = WATER_LEVEL;
  scene.add(water);
}
