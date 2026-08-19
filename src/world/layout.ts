import * as THREE from 'three/webgpu';

// 空間の寸法定義(七重の同心円レイアウトの中心)
export const ISLAND_RADIUS = 10; // 中島(阿弥陀如来を安置する場所)
export const POND_INNER = ISLAND_RADIUS;
export const POND_OUTER = 30; // 七宝池の外周
export const WATER_LEVEL = -0.5;
export const POND_DEPTH = -2.2;
export const CAUSEWAY_HALF_WIDTH = 1.5; // 橋の通行帯の半幅
export const BRIDGE_RISE = 2.6; // 橋の反り高
export const BRIDGE_CENTER = (POND_INNER + POND_OUTER) / 2;
export const BRIDGE_HALF = 11; // 全長22mの半分
export const ISLAND_TOP = 0.4;

// 七重行樹のリング半径(欄楯はその内側に添える)
export const TREE_RINGS = [38, 48, 58, 68, 78, 88, 98];

// 四宝のマテリアル(金・銀・瑠璃・玻璃)
export function makeTreasureMaterials(): THREE.MeshStandardMaterial[] {
  return [
    new THREE.MeshStandardMaterial({ color: 0xd9a832, metalness: 0.9, roughness: 0.32 }), // 金
    new THREE.MeshStandardMaterial({ color: 0xd8dee6, metalness: 0.95, roughness: 0.22 }), // 銀
    new THREE.MeshStandardMaterial({ color: 0x2a4fc9, metalness: 0.3, roughness: 0.25, emissive: 0x0a1c5a, emissiveIntensity: 0.35 }), // 瑠璃
    new THREE.MeshStandardMaterial({ color: 0xeef6ff, metalness: 0.1, roughness: 0.08 }), // 玻璃
  ];
}

// 四辺階道の軸上(東西南北)にいるか
function onCauseway(x: number, z: number): boolean {
  return Math.abs(z) < CAUSEWAY_HALF_WIDTH || Math.abs(x) < CAUSEWAY_HALF_WIDTH;
}

export interface GroundSample {
  y: number;
  blocked: boolean;
}

// 足元の高さと進入可否。池の水面へは降りられない(階道と中島だけ歩ける)
export function sampleGround(x: number, z: number): GroundSample {
  const r = Math.hypot(x, z);
  if (r < POND_INNER) return { y: ISLAND_TOP, blocked: false };
  if (r < POND_OUTER) {
    if (onCauseway(x, z)) {
      // 橋の反り(放物線)に沿って昇降する
      const u = THREE.MathUtils.clamp((r - BRIDGE_CENTER) / BRIDGE_HALF, -1, 1);
      return { y: BRIDGE_RISE * (1 - u * u), blocked: false };
    }
    return { y: WATER_LEVEL, blocked: true };
  }
  return { y: 0, blocked: false };
}
