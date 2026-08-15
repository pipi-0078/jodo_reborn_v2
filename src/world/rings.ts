import * as THREE from 'three/webgpu';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { TREE_RINGS, CAUSEWAY_HALF_WIDTH, makeTreasureMaterials } from './layout';
import { buildTreeTemplate } from './trees';

const TREE_SPACING = 15; // 並木の間隔(m)
const GATE_HALF_ANGLE = 0.09; // 欄楯の四方の門の半角(rad)
const TREE_VARIANTS = 3; // 宝樹テンプレートの種類数
const HERO_TREE_COUNT = 8; // 最内周の主役の木の本数
const HERO_TREE_SCALE = 0.55; // 原形約15.7m → 約8.6m

// 「七重欄楯 七重羅網 七重行樹 皆是四宝周匝囲繞」のうち欄楯と行樹
export async function createRings(scene: THREE.Scene): Promise<void> {
  createConiferRings(scene);
  createRailings(scene);
  await createHeroTrees(scene);
}

// 最内周:提供モデル「tesuto tree」(CC-BY-4.0)による主役の木。
// 池を囲んで8本、四宝の彩色で立てる
async function createHeroTrees(scene: THREE.Scene): Promise<void> {
  const gltf = await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}assets/takara_tree.glb`);
  gltf.scene.updateMatrixWorld(true);

  const trunkGeometries: THREE.BufferGeometry[] = [];
  const leafGeometries: THREE.BufferGeometry[] = [];
  let trunkMaterial: THREE.Material | null = null;
  let leafTexture: THREE.Texture | null = null;
  gltf.scene.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    const geometry = (object.geometry as THREE.BufferGeometry).clone().applyMatrix4(object.matrixWorld);
    const material = object.material as THREE.MeshStandardMaterial;
    if (material.name === 'material_1') {
      leafGeometries.push(geometry);
      leafTexture = material.map;
    } else {
      trunkGeometries.push(geometry);
      trunkMaterial = material;
    }
  });
  const trunk = trunkGeometries.length > 1 ? mergeGeometries(trunkGeometries) : trunkGeometries[0];
  const leaves = leafGeometries.length > 1 ? mergeGeometries(leafGeometries) : leafGeometries[0];

  // 接地と中心合わせ(元データは原点からずれている)
  trunk.computeBoundingBox();
  leaves.computeBoundingBox();
  const box = trunk.boundingBox!.clone().union(leaves.boundingBox!);
  const center = box.getCenter(new THREE.Vector3());
  for (const geometry of [trunk, leaves]) {
    geometry.translate(-center.x, -box.min.y, -center.z);
  }

  // 葉はグレースケール化済みなので、四宝の色をそのまま乗せられる
  const tints = [0xf0c050, 0xe2eaf2, 0x6488f5, 0xf2fbff]; // 金・銀・瑠璃・玻璃
  const leafMaterials = tints.map((color) => {
    const material = new THREE.MeshStandardMaterial({
      map: leafTexture, color, metalness: 0.4, roughness: 0.45, side: THREE.DoubleSide,
    });
    material.emissive.set(color).multiplyScalar(0.22); // 遠目でも彩度が沈まないように
    material.emissiveMap = leafTexture;
    return material;
  });

  const radius = TREE_RINGS[0];
  for (let i = 0; i < HERO_TREE_COUNT; i++) {
    // 四方の階道を避けて斜め45度の位置から等間隔に
    const angle = Math.PI / HERO_TREE_COUNT + (i / HERO_TREE_COUNT) * Math.PI * 2;
    const group = new THREE.Group();
    group.add(new THREE.Mesh(trunk, trunkMaterial!));
    group.add(new THREE.Mesh(leaves, leafMaterials[i % 4]));
    group.position.set(Math.cos(angle) * radius, 0, Math.sin(angle) * radius);
    group.rotation.y = i * 2.399; // 黄金角で向きをばらす
    group.scale.setScalar(HERO_TREE_SCALE * (0.92 + (i % 3) * 0.07));
    scene.add(group);
  }
}

// 外側6リング:円錐段重ねの宝樹(インスタンシング)
function createConiferRings(scene: THREE.Scene): void {
  const treasures = makeTreasureMaterials();
  const templates = Array.from({ length: TREE_VARIANTS }, (_, i) => buildTreeTemplate(1000 + i * 77));

  // 配置を先に計算する(リングごとに四宝を巡回、形と向きにも揺らぎ)
  interface Placement { matrix: THREE.Matrix4; treasure: number; variant: number }
  const placements: Placement[] = [];
  const position = new THREE.Vector3();
  const rotation = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);

  for (let ring = 1; ring < TREE_RINGS.length; ring++) {
    const radius = TREE_RINGS[ring];
    const count = Math.floor((2 * Math.PI * radius) / TREE_SPACING);
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2 + ring * 0.35;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      // 階道の延長線上は空けて、四方の視線と動線を通す
      if (Math.abs(x) < CAUSEWAY_HALF_WIDTH + 2.4 || Math.abs(z) < CAUSEWAY_HALF_WIDTH + 2.4) continue;
      const hash = (i * 7 + ring * 13) % 10;
      const scale = (0.9 + hash * 0.04) * (1 + ring * 0.025); // 外周ほどわずかに大きく
      position.set(x, 0, z);
      rotation.setFromAxisAngle(up, ((i * 37 + ring * 91) % 24) * (Math.PI / 12));
      const matrix = new THREE.Matrix4().compose(position, rotation, new THREE.Vector3(scale, scale, scale));
      placements.push({ matrix, treasure: (ring + i) % 4, variant: (i + ring) % TREE_VARIANTS });
    }
  }

  // 幹:テンプレートごとにまとめて描く
  const woodMaterial = new THREE.MeshStandardMaterial({ color: 0x8a6420, metalness: 0.7, roughness: 0.5 });
  // 宝玉・宝珠:淡く発光する金
  const jewelMaterial = new THREE.MeshStandardMaterial({
    color: 0xffe9b0, metalness: 0.9, roughness: 0.15,
    emissive: 0xffd98a, emissiveIntensity: 0.35,
  });
  for (let v = 0; v < TREE_VARIANTS; v++) {
    const subset = placements.filter((p) => p.variant === v);
    const wood = new THREE.InstancedMesh(templates[v].wood, woodMaterial, subset.length);
    const jewels = new THREE.InstancedMesh(templates[v].jewels, jewelMaterial, subset.length);
    subset.forEach((p, i) => {
      wood.setMatrixAt(i, p.matrix);
      jewels.setMatrixAt(i, p.matrix);
    });
    scene.add(wood, jewels);
  }

  // 葉:四宝×テンプレートの組ごとにまとめて描く
  for (let t = 0; t < 4; t++) {
    for (let v = 0; v < TREE_VARIANTS; v++) {
      const subset = placements.filter((p) => p.treasure === t && p.variant === v);
      if (subset.length === 0) continue;
      const canopy = new THREE.InstancedMesh(templates[v].canopy, treasures[t], subset.length);
      subset.forEach((p, i) => canopy.setMatrixAt(i, p.matrix));
      scene.add(canopy);
    }
  }
}

// 七重欄楯:各リングの内側に低い欄干。四方に門(切れ目)を残す
function createRailings(scene: THREE.Scene): void {
  const treasures = makeTreasureMaterials();
  const postGeometry = new THREE.CylinderGeometry(0.09, 0.11, 1.1, 6);
  postGeometry.translate(0, 0.55, 0);

  const postPlacements: { position: THREE.Vector3; treasure: number }[] = [];

  for (let ring = 0; ring < TREE_RINGS.length; ring++) {
    const radius = TREE_RINGS[ring] - 4;
    const material = treasures[ring % 4];

    // 手すり:四方の門を避けた4つの弧
    for (let q = 0; q < 4; q++) {
      const start = q * (Math.PI / 2) + GATE_HALF_ANGLE;
      const arcLength = Math.PI / 2 - GATE_HALF_ANGLE * 2;
      const railGeometry = new THREE.TorusGeometry(radius, 0.07, 6, 96, arcLength);
      const rail = new THREE.Mesh(railGeometry, material);
      rail.rotation.x = -Math.PI / 2;
      rail.rotation.z = start;
      rail.position.y = 1.05;
      scene.add(rail);
    }

    // 支柱
    const count = Math.floor((2 * Math.PI * radius) / 2.4);
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2;
      const gateDistance = Math.abs(((angle + Math.PI / 4) % (Math.PI / 2)) - Math.PI / 4);
      if (gateDistance < GATE_HALF_ANGLE) continue;
      postPlacements.push({
        position: new THREE.Vector3(Math.cos(angle) * radius, 0, Math.sin(angle) * radius),
        treasure: ring % 4,
      });
    }
  }

  const matrix = new THREE.Matrix4();
  for (let t = 0; t < 4; t++) {
    const subset = postPlacements.filter((p) => p.treasure === t);
    if (subset.length === 0) continue;
    const posts = new THREE.InstancedMesh(postGeometry, treasures[t], subset.length);
    subset.forEach((p, i) => {
      matrix.setPosition(p.position);
      posts.setMatrixAt(i, matrix);
    });
    scene.add(posts);
  }
}
