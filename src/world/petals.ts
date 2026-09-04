import * as THREE from 'three/webgpu';
import { WATER_LEVEL } from './layout';

// 「昼夜六時 雨天曼陀羅華」— 天から曼陀羅華の花弁がゆっくり舞い落ちる。
// 花弁はインスタンス化した小さな板(花弁形のアルファ)。落下・横揺れ・回転を CPU で毎フレーム更新する。
// 池と中島の上空(半径 SPAWN_RADIUS、高さ 28〜48m)に湧き、水面・地面に着いたら上空へ戻す。

const COUNT = 2000;
const SPAWN_RADIUS = 60;
const SPAWN_TOP = 48;
const SPAWN_BOTTOM = 28;
const TINTS = [0xfff6ee, 0xffd6dc, 0xfff0b8, 0xdce8ff]; // 白・淡い紅・淡い金・淡い青

interface Petal {
  x: number; y: number; z: number;
  fall: number;        // 落下速度 m/s
  swayAmp: number;     // 横揺れの振幅
  swayFreq: number;    // 横揺れの周期
  phase: number;
  spin: THREE.Vector3; // 回転速度(軸ごと)
  angle: THREE.Vector3;
  size: number;
}

function makePetalTexture(): THREE.Texture {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  ctx.clearRect(0, 0, size, size);
  // 花弁: 楕円に近い形で、先がわずかに尖る。中心は白く、縁へ向けてわずかに透ける
  const gradient = ctx.createRadialGradient(size / 2, size * 0.55, 4, size / 2, size * 0.55, size * 0.5);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.7, 'rgba(255,255,255,0.95)');
  gradient.addColorStop(1, 'rgba(255,255,255,0.75)');
  ctx.fillStyle = gradient;
  ctx.beginPath();
  ctx.moveTo(size / 2, 4);
  ctx.bezierCurveTo(size * 0.95, size * 0.35, size * 0.9, size * 0.9, size / 2, size - 4);
  ctx.bezierCurveTo(size * 0.1, size * 0.9, size * 0.05, size * 0.35, size / 2, 4);
  ctx.fill();
  // 中央の筋
  ctx.strokeStyle = 'rgba(255,255,255,0.35)';
  ctx.lineWidth = 3;
  ctx.beginPath();
  ctx.moveTo(size / 2, 10);
  ctx.lineTo(size / 2, size - 10);
  ctx.stroke();
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export function createFallingFlowers(scene: THREE.Scene): { update(dt: number): void } {
  const geometry = new THREE.PlaneGeometry(0.28, 0.4);
  const material = new THREE.MeshStandardMaterial({
    map: makePetalTexture(), alphaMap: makePetalTexture(), transparent: true, alphaTest: 0.4,
    side: THREE.DoubleSide, roughness: 0.6, metalness: 0.0,
    emissive: 0xffffff, emissiveIntensity: 0.25, // 花弁は光を透かして淡く光る(ブルームが拾う)
  });
  const mesh = new THREE.InstancedMesh(geometry, material, COUNT);
  mesh.frustumCulled = false;
  const random = (a: number, b: number) => a + Math.random() * (b - a);

  const petals: Petal[] = [];
  const color = new THREE.Color();
  for (let i = 0; i < COUNT; i++) {
    const angle = Math.random() * Math.PI * 2;
    const radius = Math.sqrt(Math.random()) * SPAWN_RADIUS;
    petals.push({
      x: Math.cos(angle) * radius,
      y: random(WATER_LEVEL, SPAWN_TOP),  // 最初は空間全体に散らしておく(湧き待ちの空白を作らない)
      z: Math.sin(angle) * radius,
      fall: random(0.35, 0.7),
      swayAmp: random(0.3, 0.9),
      swayFreq: random(0.4, 0.9),
      phase: Math.random() * Math.PI * 2,
      spin: new THREE.Vector3(random(-1.2, 1.2), random(-0.8, 0.8), random(-1.2, 1.2)),
      angle: new THREE.Vector3(random(0, 6.28), random(0, 6.28), random(0, 6.28)),
      size: random(0.7, 1.4),
    });
    color.set(TINTS[i % TINTS.length]);
    mesh.setColorAt(i, color);
  }
  scene.add(mesh);

  const matrix = new THREE.Matrix4();
  const position = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  const euler = new THREE.Euler();
  const scale = new THREE.Vector3();
  let time = 0;

  function update(dt: number): void {
    time += dt;
    for (let i = 0; i < COUNT; i++) {
      const p = petals[i];
      p.y -= p.fall * dt;
      // 横揺れ: 木の葉のように左右へ滑る
      const sway = Math.sin(time * p.swayFreq + p.phase) * p.swayAmp;
      const drift = Math.cos(time * p.swayFreq * 0.7 + p.phase) * p.swayAmp * 0.5;
      p.angle.x += p.spin.x * dt;
      p.angle.y += p.spin.y * dt;
      p.angle.z += p.spin.z * dt;
      if (p.y < WATER_LEVEL - 0.5) {
        // 上空へ戻す
        const angle = Math.random() * Math.PI * 2;
        const radius = Math.sqrt(Math.random()) * SPAWN_RADIUS;
        p.x = Math.cos(angle) * radius;
        p.z = Math.sin(angle) * radius;
        p.y = random(SPAWN_BOTTOM, SPAWN_TOP);
      }
      position.set(p.x + sway, p.y, p.z + drift);
      euler.set(p.angle.x, p.angle.y, p.angle.z);
      quaternion.setFromEuler(euler);
      scale.setScalar(p.size);
      matrix.compose(position, quaternion, scale);
      mesh.setMatrixAt(i, matrix);
    }
    mesh.instanceMatrix.needsUpdate = true;
  }
  update(0);
  return { update };
}
