import * as THREE from 'three/webgpu';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import {
  BRIDGE_CENTER, BRIDGE_HALF, ISLAND_TOP, PAVILION_CLEARANCE, PAVILION_RADIUS,
  POND_INNER, POND_OUTER, TREE_RINGS, WATER_LEVEL,
} from './layout';

// 完成予想図(docs/reference_concept.png)に沿って、承認済みアセットを据える。
// 阿弥陀如来坐像は別途(蓮華座だけ先に中島へ置く)。

const LOTUS_TINTS = [0x6f8cf5, 0xf2c452, 0xf07a7a, 0xf7faff]; // 青・黄・赤・白
const BUD_TINT = 0xf2a8c0;
const GOLD_LEAF = 0xf0c050;
const BRIDGE_ANGLES = [0, Math.PI / 2, Math.PI, Math.PI * 1.5]; // 東・南・西・北
const PAVILION_ANGLES = [Math.PI / 4, Math.PI * 0.75, Math.PI * 1.25, Math.PI * 1.75];
const SIGHT_LANE = 5; // 四方の階道の延長線上に空ける半幅

interface Part {
  geometry: THREE.BufferGeometry;
  material: THREE.Material;
}

interface Template {
  parts: Part[];
  height: number;
}

// 決定的な擬似乱数(毎回同じ配置になるように)
function makeRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
}

const loader = new GLTFLoader();

// glbを読み、ノードの変換を頂点に焼き込み、マテリアルごとに1メッシュへまとめる。
// floor: 最下点を y=0 に揃える(木や台座)。recenter: 原点から外れたモデルを中心へ寄せる
async function loadTemplate(file: string, options: { floor?: boolean; recenter?: boolean } = {}): Promise<Template> {
  const gltf = await loader.loadAsync(`${import.meta.env.BASE_URL}assets/${file}`);
  gltf.scene.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(gltf.scene, true);
  const center = box.getCenter(new THREE.Vector3());
  const shift = new THREE.Vector3(
    options.recenter ? -center.x : 0,
    options.floor ? -box.min.y : 0,
    options.recenter ? -center.z : 0,
  );

  const byMaterial = new Map<THREE.Material, THREE.BufferGeometry[]>();
  gltf.scene.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    const geometry = (object.geometry as THREE.BufferGeometry).clone().applyMatrix4(object.matrixWorld);
    geometry.translate(shift.x, shift.y, shift.z);
    const material = object.material as THREE.Material;
    const list = byMaterial.get(material) ?? [];
    list.push(geometry);
    byMaterial.set(material, list);
  });

  const parts: Part[] = [];
  for (const [material, geometries] of byMaterial) {
    // 属性構成が揃っているものだけ結合(揃わなければ個別に描く)
    const signature = (g: THREE.BufferGeometry) => Object.keys(g.attributes).sort().join() + (g.index ? '#i' : '');
    const mergeable = geometries.every((g) => signature(g) === signature(geometries[0]));
    const merged = mergeable && geometries.length > 1 ? mergeGeometries(geometries) : null;
    if (merged) parts.push({ geometry: merged, material });
    else geometries.forEach((geometry) => parts.push({ geometry, material }));
  }
  return { parts, height: box.max.y - box.min.y };
}

// テンプレートを行列の数だけインスタンス描画する。materialFor でパーツ別に差し替え可
function instance(
  scene: THREE.Scene, template: Template, matrices: THREE.Matrix4[],
  materialFor?: (material: THREE.Material) => THREE.Material,
): void {
  if (matrices.length === 0) return;
  for (const part of template.parts) {
    const material = materialFor ? materialFor(part.material) : part.material;
    const mesh = new THREE.InstancedMesh(part.geometry, material, matrices.length);
    matrices.forEach((matrix, i) => mesh.setMatrixAt(i, matrix));
    scene.add(mesh);
  }
}

function compose(x: number, y: number, z: number, rotationY: number, scale: number, rotationZ = 0): THREE.Matrix4 {
  return new THREE.Matrix4().compose(
    new THREE.Vector3(x, y, z),
    new THREE.Quaternion().setFromEuler(new THREE.Euler(0, rotationY, rotationZ)),
    new THREE.Vector3(scale, scale, scale),
  );
}

function pavilionPositions(): THREE.Vector2[] {
  return PAVILION_ANGLES.map((a) => new THREE.Vector2(Math.cos(a) * PAVILION_RADIUS, Math.sin(a) * PAVILION_RADIUS));
}

// 木を植えてよい場所か(階道の見通しと楼閣の周囲を空ける)
function plantable(x: number, z: number, pavilions: THREE.Vector2[]): boolean {
  if (Math.abs(x) < SIGHT_LANE || Math.abs(z) < SIGHT_LANE) return false;
  return pavilions.every((p) => Math.hypot(p.x - x, p.y - z) > PAVILION_CLEARANCE);
}

// 四方に架かる金の反橋(全長29m)。中島側の袂は島の高さ(0.4)、岸側は地表(0)に着ける
async function placeBridges(scene: THREE.Scene): Promise<void> {
  const template = await loadTemplate('bridge_long.glb');
  const tilt = Math.atan2(ISLAND_TOP, BRIDGE_HALF * 2);
  const matrices = BRIDGE_ANGLES.map((theta) => compose(
    Math.cos(theta) * BRIDGE_CENTER, ISLAND_TOP / 2, Math.sin(theta) * BRIDGE_CENTER, -theta, 1, -tilt,
  ));
  instance(scene, template, matrices);
}

// 中島の蓮華座(如来を迎える前に台座だけ据える)
async function placePedestal(scene: THREE.Scene): Promise<void> {
  const template = await loadTemplate('rengeza.glb', { floor: true });
  instance(scene, template, [compose(0, ISLAND_TOP, 0, 0, 3)]);
}

// 楼閣: 近景(東側)の二隅に七宝楼閣、如来の背後(西側)の二隅に黄金八角楼。いずれも正面を池へ向ける
async function placePavilions(scene: THREE.Scene): Promise<void> {
  const [rect, octagon] = await Promise.all([loadTemplate('pavilion.glb'), loadTemplate('pavilion_b.glb')]);
  const rectMatrices: THREE.Matrix4[] = [];
  const octMatrices: THREE.Matrix4[] = [];
  PAVILION_ANGLES.forEach((theta) => {
    const x = Math.cos(theta) * PAVILION_RADIUS;
    const z = Math.sin(theta) * PAVILION_RADIUS;
    const east = Math.cos(theta) > 0;
    // 七宝楼閣の正面は -x、八角楼の正面は +x
    if (east) rectMatrices.push(compose(x, 0, z, -theta, 1));
    else octMatrices.push(compose(x, 0, z, -theta + Math.PI, 1));
  });
  instance(scene, rect, rectMatrices);
  instance(scene, octagon, octMatrices);
}

// 葉の色を四宝の金に染める(名木・軽量宝樹)
function goldFoliage(name: string): (material: THREE.Material) => THREE.Material {
  return (material) => {
    if (material.name !== name) return material;
    const gold = (material as THREE.MeshStandardMaterial).clone();
    gold.color.set(GOLD_LEAF);
    gold.emissive.set(GOLD_LEAF).multiplyScalar(0.18);
    return gold;
  };
}

// 七重行樹。内から: 宝樹(最内周)→名木・柳→針葉樹・広葉樹・枝垂れ→軽量宝樹4周
async function placeTrees(scene: THREE.Scene): Promise<void> {
  const [takara, meiboku, yanagi, conifer, broadleaf, weeping, lod] = await Promise.all([
    loadTemplate('takara_tree.glb', { floor: true, recenter: true }),
    loadTemplate('tree_meiboku.glb', { floor: true }),
    loadTemplate('tree_yanagi.glb', { floor: true }),
    loadTemplate('tree_conifer.glb', { floor: true }),
    loadTemplate('tree_broadleaf.glb', { floor: true }),
    loadTemplate('tree_weeping.glb', { floor: true }),
    loadTemplate('tree_lod.glb', { floor: true }),
  ]);
  const pavilions = pavilionPositions();
  const random = makeRandom(77);

  // 最内周: 宝樹8本を四方の橋を避けた斜め位置に(四宝の葉色を巡回)
  const tints = [0xf0c050, 0xe2eaf2, 0x6488f5, 0xf2fbff]; // 金・銀・瑠璃・玻璃
  const heroByTint: THREE.Matrix4[][] = [[], [], [], []];
  for (let i = 0; i < 8; i++) {
    const theta = Math.PI / 8 + (i / 8) * Math.PI * 2;
    const scale = 0.55 * (0.92 + (i % 3) * 0.07); // 原形15.8m → 約8.7m
    heroByTint[i % 4].push(compose(Math.cos(theta) * TREE_RINGS[0], 0, Math.sin(theta) * TREE_RINGS[0], i * 2.399, scale));
  }
  tints.forEach((tint, t) => {
    instance(scene, takara, heroByTint[t], (material) => {
      if (material.name !== 'material_1') return material;
      const leaf = (material as THREE.MeshStandardMaterial).clone();
      leaf.color.set(tint);
      leaf.metalness = 0.4;
      leaf.roughness = 0.45;
      leaf.side = THREE.DoubleSide;
      leaf.emissive.set(tint).multiplyScalar(0.22);
      leaf.emissiveMap = leaf.map;
      return leaf;
    });
  });

  // リングに沿った植え位置を返す(見通しと楼閣を避ける)
  const ringSlots = (radius: number, spacing: number, jitter: number): { x: number; z: number }[] => {
    const count = Math.floor((2 * Math.PI * radius) / spacing);
    const slots: { x: number; z: number }[] = [];
    for (let i = 0; i < count; i++) {
      const angle = ((i + 0.5) / count) * Math.PI * 2 + (random() - 0.5) * jitter;
      const r = radius + (random() - 0.5) * 2;
      const x = Math.cos(angle) * r;
      const z = Math.sin(angle) * r;
      if (plantable(x, z, pavilions)) slots.push({ x, z });
    }
    return slots;
  };

  // 第2周: 名木(金の葉)と柳を交互に
  const ring1: THREE.Matrix4[][] = [[], []];
  ringSlots(TREE_RINGS[1], 14, 0.08).forEach((s, i) => {
    const kind = i % 2;
    ring1[kind].push(compose(s.x, 0, s.z, random() * Math.PI * 2, (kind === 0 ? 1.0 : 1.3) * (0.9 + random() * 0.2)));
  });
  instance(scene, meiboku, ring1[0], goldFoliage('foliage'));
  instance(scene, yanagi, ring1[1]);

  // 第3周: 針葉樹・広葉樹・枝垂れを巡回
  const ring2: THREE.Matrix4[][] = [[], [], []];
  const ring2Scale = [1.1, 1.3, 1.4];
  ringSlots(TREE_RINGS[2], 13, 0.08).forEach((s, i) => {
    const kind = i % 3;
    ring2[kind].push(compose(s.x, 0, s.z, random() * Math.PI * 2, ring2Scale[kind] * (0.9 + random() * 0.2)));
  });
  instance(scene, conifer, ring2[0]);
  instance(scene, broadleaf, ring2[1]);
  instance(scene, weeping, ring2[2]);

  // 第4〜7周: 軽量宝樹(金の葉)。外周ほどわずかに大きく
  const outer: THREE.Matrix4[] = [];
  for (let ring = 3; ring < TREE_RINGS.length; ring++) {
    ringSlots(TREE_RINGS[ring], 12, 0.1).forEach((s) => {
      outer.push(compose(s.x, 0, s.z, random() * Math.PI * 2, (1 + (ring - 3) * 0.08) * (0.9 + random() * 0.3)));
    });
  }
  instance(scene, lod, outer, goldFoliage('foliage'));
}

// 放射状に薄れる光の輪のテクスチャ
function makeHaloTexture(): THREE.Texture {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.35, 'rgba(255,255,255,0.55)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

// 「池中蓮華大如車輪 青色青光 黄色黄光 赤色赤光 白色白光」
async function placeLotuses(scene: THREE.Scene): Promise<void> {
  const [bloom, bud] = await Promise.all([loadTemplate('lotus.glb'), loadTemplate('lotus_bud.glb')]);
  const random = makeRandom(2026);
  const bankWaterline = POND_OUTER - (-WATER_LEVEL) * 3.5 / 2.2;

  // 橋の通り道を避けて池面に置ける座標を探す
  const spot = (rMin: number, rMax: number, angleCenter?: number, angleSpread = Math.PI): { x: number; z: number } => {
    for (let attempt = 0; attempt < 40; attempt++) {
      const angle = angleCenter === undefined ? random() * Math.PI * 2 : angleCenter + (random() - 0.5) * angleSpread * 2;
      const r = rMin + random() * (rMax - rMin);
      const x = Math.cos(angle) * r;
      const z = Math.sin(angle) * r;
      if (Math.abs(x) > 4.5 && Math.abs(z) > 4.5) return { x, z };
    }
    return { x: rMin + 6, z: rMin + 6 };
  };

  // 花弁は自らの色でやさしく光る(青色青光・黄色黄光・赤色赤光・白色白光)
  const petalTint = (tint: number) => (material: THREE.Material) => {
    if (material.name !== 'petal') return material;
    const petal = (material as THREE.MeshStandardMaterial).clone();
    petal.color.set(tint);
    petal.emissive.set(tint).multiplyScalar(0.42);
    return petal;
  };

  // 水面に落ちる光の輪(加算合成の放射グラデーション)
  const haloTexture = makeHaloTexture();
  const haloGeometry = new THREE.CircleGeometry(1, 40);
  haloGeometry.rotateX(-Math.PI / 2);
  const halo = (tint: number, matrices: THREE.Matrix4[], radiusOf: (i: number) => number) => {
    const material = new THREE.MeshBasicMaterial({
      map: haloTexture, color: tint, transparent: true, opacity: 0.5,
      blending: THREE.AdditiveBlending, depthWrite: false,
    });
    const mesh = new THREE.InstancedMesh(haloGeometry, material, matrices.length);
    const position = new THREE.Vector3();
    const quaternion = new THREE.Quaternion();
    const scale = new THREE.Vector3();
    matrices.forEach((m, i) => {
      m.decompose(position, quaternion, scale);
      mesh.setMatrixAt(i, compose(position.x, WATER_LEVEL + 0.03, position.z, 0, radiusOf(i)));
    });
    scene.add(mesh);
  };

  // 満開: 四色×13株。車輪ほどの大きさ(直径0.8〜1.1m)。東岸の手前には四色一株ずつやや大きめに
  LOTUS_TINTS.forEach((tint) => {
    const matrices: THREE.Matrix4[] = [];
    const scales: number[] = [];
    for (let i = 0; i < 13; i++) {
      const giant = i === 12;
      const p = giant ? spot(29, bankWaterline - 3, 0, Math.PI / 3) : spot(POND_INNER + 3.5, bankWaterline - 2.5);
      const scale = giant ? 2.7 + random() * 0.3 : 1.8 + random() * 0.7;
      matrices.push(compose(p.x, WATER_LEVEL - 0.03 * scale, p.z, random() * Math.PI * 2, scale));
      scales.push(scale);
    }
    instance(scene, bloom, matrices, petalTint(tint));
    halo(tint, matrices, (i) => scales[i] * 1.35);
  });

  // 蕾: 茎を水中に下ろして水面から立ち上げる
  const buds: THREE.Matrix4[] = [];
  for (let i = 0; i < 14; i++) {
    const p = spot(POND_INNER + 3.5, bankWaterline - 2.5);
    buds.push(compose(p.x, WATER_LEVEL + 0.02, p.z, random() * Math.PI * 2, 1.7 + random() * 0.8));
  }
  instance(scene, bud, buds, petalTint(BUD_TINT));
}

export async function createProps(scene: THREE.Scene): Promise<void> {
  await Promise.all([
    placeBridges(scene), placePedestal(scene), placePavilions(scene), placeTrees(scene), placeLotuses(scene),
  ]);
}
