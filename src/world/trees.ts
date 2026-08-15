import * as THREE from 'three/webgpu';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

// 仕立て木(niwaki)風の宝樹を手続き生成する。
// 曲がりのある三段の幹から枝が張り出し、その先に平たい葉層が重なる。

interface TreeTemplate {
  wood: THREE.BufferGeometry;
  canopy: THREE.BufferGeometry;
}

// 再現性のある乱数(テンプレートの形を毎回同じにする)
function mulberry32(seed: number): () => number {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// 中心からの半径方向に凹凸をつける(共有頂点が同じ量だけ動くよう、位置から決める)
function roughen(geometry: THREE.BufferGeometry, amount: number): void {
  const position = geometry.attributes.position;
  const v = new THREE.Vector3();
  for (let i = 0; i < position.count; i++) {
    v.fromBufferAttribute(position, i);
    const n = Math.sin(v.x * 12.3 + v.y * 7.1) * Math.cos(v.z * 9.7 + v.x * 3.3);
    const s = 1 + n * amount;
    position.setXYZ(i, v.x * s, v.y * s, v.z * s);
  }
  geometry.computeVertexNormals();
}

// 2点間を結ぶ先細りの枝
function branchBetween(start: THREE.Vector3, end: THREE.Vector3, r1: number, r2: number): THREE.BufferGeometry {
  const direction = end.clone().sub(start);
  const length = direction.length();
  const geometry = new THREE.CylinderGeometry(r2, r1, length, 6, 1);
  geometry.translate(0, length / 2, 0);
  const quaternion = new THREE.Quaternion().setFromUnitVectors(
    new THREE.Vector3(0, 1, 0),
    direction.normalize(),
  );
  geometry.applyQuaternion(quaternion);
  geometry.translate(start.x, start.y, start.z);
  return geometry;
}

export function buildTreeTemplate(seed: number): TreeTemplate {
  const rand = mulberry32(seed);
  const woodParts: THREE.BufferGeometry[] = [];
  const canopyParts: THREE.BufferGeometry[] = [];

  // 幹:先細りの円柱を三段、少しずつ折りながら積む
  const radii = [0.32, 0.23, 0.16, 0.1];
  const heights = [2.2, 1.9, 1.6];
  let tip = new THREE.Vector3(0, 0, 0);
  let angle = (rand() - 0.5) * 0.2;
  let tilt = rand() * Math.PI * 2;
  for (let s = 0; s < 3; s++) {
    const rotation = new THREE.Matrix4().makeRotationAxis(
      new THREE.Vector3(Math.cos(tilt), 0, Math.sin(tilt)),
      angle,
    );
    rotation.setPosition(tip.x, tip.y, tip.z);
    const segment = new THREE.CylinderGeometry(radii[s + 1], radii[s], heights[s], 8, 1);
    segment.translate(0, heights[s] / 2, 0);
    segment.applyMatrix4(rotation);
    woodParts.push(segment);
    tip = new THREE.Vector3(0, heights[s], 0).applyMatrix4(rotation);
    angle += (rand() - 0.5) * 0.45;
    tilt += (rand() - 0.5) * 1.2;
  }

  // 枝と葉層:幹の上部から放射状に張り出す
  const padCount = 5 + Math.floor(rand() * 2);
  for (let i = 0; i < padCount; i++) {
    const theta = (i / padCount) * Math.PI * 2 + rand() * 0.9;
    const spread = 1.0 + rand() * 1.5;
    const height = tip.y - 2.1 + (i / padCount) * 2.7 + rand() * 0.35;
    const padCenter = new THREE.Vector3(Math.cos(theta) * spread, height, Math.sin(theta) * spread);
    const branchStart = new THREE.Vector3(tip.x * 0.4, height - 0.7 - rand() * 0.4, tip.z * 0.4);
    woodParts.push(branchBetween(branchStart, padCenter, 0.07, 0.035));

    const pad = new THREE.IcosahedronGeometry(0.95, 1);
    roughen(pad, 0.12);
    pad.scale(1.25 + rand() * 0.5, 0.32 + rand() * 0.08, 1.25 + rand() * 0.5);
    pad.translate(padCenter.x, padCenter.y + 0.18, padCenter.z);
    canopyParts.push(pad);
  }

  // 天辺の冠
  const crown = new THREE.IcosahedronGeometry(0.95, 1);
  roughen(crown, 0.12);
  crown.scale(1.15, 0.5, 1.15);
  crown.translate(tip.x, tip.y + 0.42, tip.z);
  canopyParts.push(crown);

  return {
    wood: mergeGeometries(woodParts),
    canopy: mergeGeometries(canopyParts),
  };
}
