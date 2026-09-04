import * as THREE from 'three/webgpu';
import {
  positionLocal, positionWorld, time, sin, vec2, vec3, color, uv, texture, mix, smoothstep,
  mx_noise_float, normalMap as normalMapNode, normalView, positionViewDirection, reflector, cos,
} from 'three/tsl';
import { NO_REFLECT_LAYER } from './layout';
import {
  POND_OUTER, WATER_LEVEL, POND_DEPTH, ISLAND_RADIUS, ISLAND_TOP, ISLAND_FOOT, ISLAND_WATERLINE, BANK_INNER,
} from './layout';
import { applyPureGold } from './gold';

// 「七宝池 八功徳水充満其中 池底純以金沙布地」
// 池底には四宝(金・銀・瑠璃・玻璃)の砂が吹き溜まりを作って敷かれる。
export function createPond(scene: THREE.Scene, camera: THREE.Camera): void {
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
  const islandTopMaterial = new THREE.MeshStandardMaterial({ name: 'gold_island', color: 0xc9a13b, metalness: 0.5, roughness: 0.5 });
  applyPureGold(islandTopMaterial);
  islandTopMaterial.roughness = 0.45;
  const islandTop = new THREE.Mesh(new THREE.CircleGeometry(ISLAND_RADIUS + 0.05, 64), islandTopMaterial);
  islandTop.geometry.rotateX(-Math.PI / 2);
  islandTop.position.y = ISLAND_TOP;
  scene.add(islandTop);

  // --- 八功徳水: 澄み切った水面。二重の波で穏やかに揺れる ---
  // 水面の縁は、岸と中島の斜面が水位(-0.5m)と交わる半径に合わせる
  const waterGeometry = new THREE.RingGeometry(islandWaterline - 0.05, bankWaterline + 0.05, 192, 40);
  waterGeometry.rotateX(-Math.PI / 2);
  // 水面は照明を受けない素材にして、鏡面反射(reflector)で中島・宝樹・如来を映す(9/3)。
  // 発光チャンネルに反射を載せるとブルームで水面全体が滲むので、colorNode に置く
  const waterMaterial = new THREE.MeshBasicNodeMaterial({ transparent: true, depthWrite: false });
  const wave = sin(positionLocal.x.mul(0.24).add(time.mul(0.7)))
    .mul(sin(positionLocal.z.mul(0.21).add(time.mul(0.55))))
    .mul(0.16)
    .add(sin(positionLocal.x.mul(0.9).add(positionLocal.z.mul(0.75)).add(time.mul(1.2))).mul(0.045));
  waterMaterial.positionNode = positionLocal.add(vec3(0, wave, 0));
  const fresnel = normalView.dot(positionViewDirection.negate()).saturate().oneMinus().pow(3.0);

  // 鏡面反射: 水面の平面で世界を映し、波でわずかに歪ませる。見下ろすほど水色が勝ち、
  // 遠くを見るほど鏡になる(フレネル)。反射は照明を受けない emissive に乗せる
  const mirror = reflector({ resolutionScale: 0.4 });
  // 遠くの並木(第2周以降)は水面に映さない(軽量化 9/4)。反射用の仮想カメラから NO_REFLECT_LAYER を外す
  mirror.reflector.getVirtualCamera(camera).layers.disable(NO_REFLECT_LAYER);
  const distortion = vec2(
    sin(positionWorld.x.mul(0.9).add(positionWorld.z.mul(0.75)).add(time.mul(1.2))),
    cos(positionWorld.z.mul(0.8).sub(positionWorld.x.mul(0.6)).add(time.mul(0.9))),
  ).mul(0.006);
  mirror.uvNode = mirror.uvNode!.add(distortion);
  const reflectance = fresnel.mul(0.5).add(0.45); // 蓮の光が水に映るよう、見下ろしても反射を残す
  const waterColor = vec3(0.10, 0.40, 0.46);
  waterMaterial.colorNode = mix(waterColor, mirror.rgb, reflectance).add(vec3(0.16, 0.42, 0.50).mul(fresnel).mul(0.35));
  waterMaterial.opacityNode = fresnel.mul(0.4).add(0.6);
  const water = new THREE.Mesh(waterGeometry, waterMaterial);
  water.position.y = WATER_LEVEL;
  mirror.target.rotateX(-Math.PI / 2); // 反射面の法線(target の +Z)を上に向ける
  water.add(mirror.target);
  scene.add(water);
}
