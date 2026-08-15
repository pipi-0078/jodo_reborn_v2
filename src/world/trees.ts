import * as THREE from 'three/webgpu';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

// 円錐の葉を段重ねにした宝樹(針葉樹・クリスマスツリー型)。
// 裾は波打たせて垂らし、頂に宝珠、枝先に宝玉の飾りを付ける。

export interface TreeTemplate {
  wood: THREE.BufferGeometry; // 幹
  canopy: THREE.BufferGeometry; // 円錐の葉(四宝の色が乗る)
  jewels: THREE.BufferGeometry; // 宝珠・宝玉(発光)
}

function mulberry32(seed: number): () => number {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// 円錐の裾を波打たせ、端をわずかに垂らす(滑らかな法線を保つ)
function ruffleCone(geometry: THREE.BufferGeometry, maxRadius: number, phase: number): void {
  const position = geometry.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i < position.count; i++) {
    v.fromBufferAttribute(position, i);
    const radius = Math.hypot(v.x, v.z);
    if (radius < 1e-4) continue;
    const fraction = radius / maxRadius;
    const theta = Math.atan2(v.z, v.x);
    const wobble = 1 + 0.055 * Math.sin(theta * 7 + phase) * fraction;
    const droop = 0.22 * fraction * fraction;
    position.setXYZ(i, v.x * wobble, v.y - droop, v.z * wobble);
  }
  geometry.computeVertexNormals();
}

export function buildTreeTemplate(seed: number): TreeTemplate {
  const rand = mulberry32(seed);
  const woodParts: THREE.BufferGeometry[] = [];
  const canopyParts: THREE.BufferGeometry[] = [];
  const jewelParts: THREE.BufferGeometry[] = [];

  // 幹:根元だけ見える短い円柱
  const trunk = new THREE.CylinderGeometry(0.14, 0.24, 1.4, 12);
  trunk.translate(0, 0.7, 0);
  woodParts.push(trunk);

  // 葉:円錐を4〜5段、上へいくほど小さく重ねる
  const tiers = 4 + Math.floor(rand() * 2);
  const baseRadius = 2.0 + rand() * 0.4;
  const totalHeight = 5.2 + rand() * 0.9;
  let tierTopY = 0;
  for (let i = 0; i < tiers; i++) {
    const t = i / (tiers - 1);
    const radius = THREE.MathUtils.lerp(baseRadius, 0.62, t);
    const height = THREE.MathUtils.lerp(2.15, 1.25, t);
    const baseY = 0.95 + t * (totalHeight - 2.75);
    const cone = new THREE.ConeGeometry(radius, height, 26, 3, true);
    cone.translate(0, height / 2, 0);
    ruffleCone(cone, radius, rand() * Math.PI * 2);
    cone.translate(0, baseY, 0);
    canopyParts.push(cone);
    tierTopY = baseY + height;

    // 段の縁に宝玉の飾り(小さな多面体)
    const ornamentCount = 3 - Math.floor(t * 2);
    for (let j = 0; j < ornamentCount; j++) {
      const theta = rand() * Math.PI * 2;
      const ornament = new THREE.IcosahedronGeometry(0.1 + rand() * 0.04, 0);
      ornament.translate(
        Math.cos(theta) * radius * 0.92,
        baseY + 0.08,
        Math.sin(theta) * radius * 0.92,
      );
      jewelParts.push(ornament);
    }
  }

  // 頂の宝珠(ほうじゅ)。多面体と結合するためインデックスを外す
  const finial = new THREE.SphereGeometry(0.22, 16, 12).toNonIndexed();
  finial.scale(1, 1.35, 1);
  finial.translate(0, tierTopY + 0.18, 0);
  jewelParts.push(finial);

  return {
    wood: mergeGeometries(woodParts),
    canopy: mergeGeometries(canopyParts),
    jewels: mergeGeometries(jewelParts),
  };
}
