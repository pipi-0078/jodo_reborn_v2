import * as THREE from 'three/webgpu';
import { positionLocal, time, sin, vec3 } from 'three/tsl';
import {
  POND_INNER, POND_OUTER, WATER_LEVEL, POND_DEPTH,
  ISLAND_RADIUS, ISLAND_TOP, CAUSEWAY_HALF_WIDTH, DECK_HEIGHT,
  makeTreasureMaterials,
} from './layout';

// 「七宝池 八功徳水充満其中 池底純以金沙布地」
export function createPond(scene: THREE.Scene): void {
  scene.add(makePondFloor());
  scene.add(makeWater());
  scene.add(makeIsland());
  makeCauseways(scene);
}

// 池底の金砂
function makePondFloor(): THREE.Mesh {
  const geometry = new THREE.CircleGeometry(POND_OUTER + 1, 96);
  geometry.rotateX(-Math.PI / 2);
  const material = new THREE.MeshStandardMaterial({
    color: 0xd8b545,
    metalness: 0.6,
    roughness: 0.4,
    emissive: 0x8a6a18,
    emissiveIntensity: 0.55, // 水越しでも金砂がほの明るく見えるように
  });
  const floor = new THREE.Mesh(geometry, material);
  floor.position.y = POND_DEPTH;
  return floor;
}

// 八功徳水:澄んだ水面。TSLの頂点変位で穏やかに揺らす
function makeWater(): THREE.Mesh {
  const geometry = new THREE.RingGeometry(POND_INNER - 1, POND_OUTER + 0.5, 128, 24);
  geometry.rotateX(-Math.PI / 2);

  const material = new THREE.MeshPhysicalNodeMaterial({
    color: 0x7fc9c9,
    transparent: true,
    opacity: 0.32,
    metalness: 0.0,
    roughness: 0.04,
  });
  const wave = sin(positionLocal.x.mul(0.55).add(time.mul(0.9)))
    .mul(sin(positionLocal.z.mul(0.47).add(time.mul(0.7))))
    .mul(0.06);
  material.positionNode = positionLocal.add(vec3(0, wave, 0));

  const water = new THREE.Mesh(geometry, material);
  water.position.y = WATER_LEVEL;
  return water;
}

// 中島(阿弥陀如来を安置する場所)
function makeIsland(): THREE.Mesh {
  const geometry = new THREE.CylinderGeometry(ISLAND_RADIUS, ISLAND_RADIUS + 2.5, ISLAND_TOP - POND_DEPTH, 64);
  const material = new THREE.MeshStandardMaterial({ color: 0xc9a13b, metalness: 0.5, roughness: 0.5 });
  const island = new THREE.Mesh(geometry, material);
  island.position.y = (ISLAND_TOP + POND_DEPTH) / 2;
  return island;
}

// 「四辺階道 金銀瑠璃玻璃合成」— 東西南北の四本の渡り道
function makeCauseways(scene: THREE.Scene): void {
  const [gold, silver, lapis, crystal] = makeTreasureMaterials();
  const materials = [gold, silver, lapis, crystal]; // 東・北・西・南の順
  const span = POND_OUTER - ISLAND_RADIUS + 6;
  const mid = (POND_OUTER + ISLAND_RADIUS) / 2;

  for (let i = 0; i < 4; i++) {
    const deck = new THREE.Mesh(
      new THREE.BoxGeometry(span, 0.9, CAUSEWAY_HALF_WIDTH * 2),
      materials[i],
    );
    const angle = (i * Math.PI) / 2; // 0=東(+X), π/2=北(-Z)…
    deck.position.set(Math.cos(angle) * mid, DECK_HEIGHT - 0.45, -Math.sin(angle) * mid);
    deck.rotation.y = angle;
    scene.add(deck);

    // 両端の浅い段差(階道らしさの演出)
    for (const [offset, width] of [[span / 2 + 0.6, 1.2], [span / 2 + 1.6, 1.0]] as const) {
      for (const sign of [1, -1]) {
        const step = new THREE.Mesh(
          new THREE.BoxGeometry(width, 0.18, CAUSEWAY_HALF_WIDTH * 2 + 0.6),
          materials[i],
        );
        const d = mid + sign * offset;
        step.position.set(Math.cos(angle) * d, sign > 0 ? 0.09 : ISLAND_TOP - 0.09, -Math.sin(angle) * d);
        step.rotation.y = angle;
        scene.add(step);
      }
    }
  }
}
