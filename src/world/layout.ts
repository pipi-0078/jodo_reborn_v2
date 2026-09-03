import * as THREE from 'three/webgpu';

// 空間の寸法定義(七重の同心円レイアウトの中心)
export const ISLAND_RADIUS = 10; // 中島(阿弥陀如来を安置する場所)
export const POND_INNER = ISLAND_RADIUS;
export const POND_OUTER = 38; // 七宝池の外周
export const WATER_LEVEL = -0.5;
export const POND_DEPTH = -2.2;
export const CAUSEWAY_HALF_WIDTH = 1.5; // 橋の通行帯の半幅
export const BRIDGE_RISE = 2.2; // 橋の反り高(3.2 → 2.2 に緩めた 9/3)
export const BRIDGE_CENTER = (POND_INNER + POND_OUTER) / 2;
export const BRIDGE_HALF = 14.5; // 全長29mの半分(中島r=9.5 → 岸r=38.5)
export const BRIDGE_DECK = 0.09; // デッキ板の厚み(反りの弧の上に載る)
export const ISLAND_TOP = 2.4; // 中島の頂の高さ(0.4 → 2.4。岸のスタート地点からも金の頂と蓮華座が見えるように 9/3)
export const ISLAND_SLOPE = 6.0; // 中島の砂斜面の水平幅(頂 r=10 から池底 r=16 へ、勾配約37°)
export const ISLAND_FOOT = ISLAND_RADIUS + ISLAND_SLOPE; // 斜面が池底に達する半径
export const ISLAND_WATERLINE = ISLAND_RADIUS + ISLAND_SLOPE * (ISLAND_TOP - WATER_LEVEL) / (ISLAND_TOP - POND_DEPTH); // 斜面と水位の交点
export const BANK_INNER = 34.5; // 外岸の砂斜面が池底の平場に達する半径
export const WALK_LIMIT = 37.4; // 岸を下りて水際に立てる限界(これより先は入水)

// 七重行樹のリング半径(欄楯はその内側に添える)
export const TREE_RINGS = [44, 54, 64, 74, 84, 94, 104];

// 楼閣の据え付け(岸の外、四隅の斜め方向)
export const PAVILION_RADIUS = 52;
export const PAVILION_CLEARANCE = 15; // 楼閣の周囲で木を植えない半径

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
export function onCauseway(x: number, z: number): boolean {
  return Math.abs(z) < CAUSEWAY_HALF_WIDTH || Math.abs(x) < CAUSEWAY_HALF_WIDTH;
}

export interface GroundSample {
  y: number;
  blocked: boolean;
}

// 橋の上の足元高さ。中島側の袂(r=9.5)は島の高さ ISLAND_TOP、岸側の袂(r=38.5)は0に着く
export function bridgeHeight(r: number): number {
  const u = THREE.MathUtils.clamp((r - BRIDGE_CENTER) / BRIDGE_HALF, -1, 1);
  const foot = THREE.MathUtils.lerp(ISLAND_TOP, 0, (u + 1) / 2);
  return foot + BRIDGE_DECK + BRIDGE_RISE * (1 - u * u);
}

// 足元の高さと進入可否。中島・四方の反橋・岸の砂斜面は歩けるが、水へは入れない。
export function sampleGround(x: number, z: number): GroundSample {
  const r = Math.hypot(x, z);
  if (r < POND_INNER) return { y: ISLAND_TOP, blocked: false };
  if (r < POND_OUTER + 0.6 && onCauseway(x, z)) return { y: bridgeHeight(r), blocked: false };
  if (r < WALK_LIMIT) return { y: WATER_LEVEL, blocked: true };
  if (r < POND_OUTER) {
    // 外岸の斜面: r=POND_OUTER で地表0、内へ向かって池底へ下る
    const y = POND_DEPTH * (POND_OUTER - r) / (POND_OUTER - BANK_INNER);
    return { y, blocked: false };
  }
  return { y: 0, blocked: false };
}
