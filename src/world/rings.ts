import * as THREE from 'three/webgpu';
import { TREE_RINGS, CAUSEWAY_HALF_WIDTH, makeTreasureMaterials } from './layout';

const TREE_SPACING = 16; // 並木の間隔(m)
const GATE_HALF_ANGLE = 0.09; // 欄楯の四方の門の半角(rad)

// 「七重欄楯 七重羅網 七重行樹 皆是四宝周匝囲繞」のうち欄楯と行樹
export function createRings(scene: THREE.Scene): void {
  createTrees(scene);
  createRailings(scene);
}

// 七重行樹:金の幹に四宝の梢
function createTrees(scene: THREE.Scene): void {
  const treasures = makeTreasureMaterials();

  // 配置を先に計算する(リングごとに四宝を巡回)
  const placements: { position: THREE.Vector3; scale: number; treasure: number }[] = [];
  for (let ring = 0; ring < TREE_RINGS.length; ring++) {
    const radius = TREE_RINGS[ring];
    const count = Math.floor((2 * Math.PI * radius) / TREE_SPACING);
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2 + ring * 0.35;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      // 階道の延長線上は空けて、四方の視線と動線を通す
      if (Math.abs(x) < CAUSEWAY_HALF_WIDTH + 2 || Math.abs(z) < CAUSEWAY_HALF_WIDTH + 2) continue;
      const scale = 0.85 + ((i * 7 + ring * 13) % 10) * 0.035;
      placements.push({ position: new THREE.Vector3(x, 0, z), scale, treasure: (ring + i) % 4 });
    }
  }

  // 幹:全て共通の金
  const trunkGeometry = new THREE.CylinderGeometry(0.32, 0.55, 4.4, 7);
  trunkGeometry.translate(0, 2.2, 0);
  const trunkMaterial = new THREE.MeshStandardMaterial({ color: 0x9a7422, metalness: 0.85, roughness: 0.45 });
  const trunks = new THREE.InstancedMesh(trunkGeometry, trunkMaterial, placements.length);

  const matrix = new THREE.Matrix4();
  placements.forEach((p, i) => {
    matrix.compose(p.position, new THREE.Quaternion(), new THREE.Vector3(p.scale, p.scale, p.scale));
    trunks.setMatrixAt(i, matrix);
  });
  scene.add(trunks);

  // 梢:四宝ごとにInstancedMeshを分ける
  const crownGeometry = new THREE.IcosahedronGeometry(2.3, 1);
  crownGeometry.translate(0, 5.4, 0);
  for (let t = 0; t < 4; t++) {
    const subset = placements.filter((p) => p.treasure === t);
    const crowns = new THREE.InstancedMesh(crownGeometry, treasures[t], subset.length);
    subset.forEach((p, i) => {
      const s = p.scale;
      matrix.compose(p.position, new THREE.Quaternion(), new THREE.Vector3(s * 1.1, s, s * 1.1));
      crowns.setMatrixAt(i, matrix);
    });
    scene.add(crowns);
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
