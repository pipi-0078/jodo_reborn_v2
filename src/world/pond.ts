import * as THREE from 'three/webgpu';
import { positionLocal, time, sin, vec3 } from 'three/tsl';
import { POND_INNER, POND_OUTER, WATER_LEVEL, POND_DEPTH, ISLAND_RADIUS, ISLAND_TOP } from './layout';

// 「七宝池 八功徳水充満其中 池底純以金沙布地」
// 渡りは props.ts の反橋が担うので、ここは水と地形だけを組む。
export function createPond(scene: THREE.Scene): void {
  // 池底の金砂
  const floorGeometry = new THREE.CircleGeometry(POND_OUTER + 1, 96);
  floorGeometry.rotateX(-Math.PI / 2);
  const floor = new THREE.Mesh(floorGeometry, new THREE.MeshStandardMaterial({
    color: 0xd8b545, metalness: 0.6, roughness: 0.4,
    emissive: 0x8a6a18, emissiveIntensity: 0.55, // 水越しでも金砂がほの明るく見えるように
  }));
  floor.position.y = POND_DEPTH;
  scene.add(floor);

  // 八功徳水: 澄んだ水面。TSLの頂点変位で穏やかに揺らす
  const waterGeometry = new THREE.RingGeometry(POND_INNER - 1, POND_OUTER + 0.5, 128, 24);
  waterGeometry.rotateX(-Math.PI / 2);
  const waterMaterial = new THREE.MeshPhysicalNodeMaterial({
    color: 0x4fb5b5, transparent: true, opacity: 0.42, metalness: 0.0, roughness: 0.04,
  });
  const wave = sin(positionLocal.x.mul(0.55).add(time.mul(0.9)))
    .mul(sin(positionLocal.z.mul(0.47).add(time.mul(0.7))))
    .mul(0.06);
  waterMaterial.positionNode = positionLocal.add(vec3(0, wave, 0));
  const water = new THREE.Mesh(waterGeometry, waterMaterial);
  water.position.y = WATER_LEVEL;
  scene.add(water);

  // 中島(阿弥陀如来を安置する場所)
  const island = new THREE.Mesh(
    new THREE.CylinderGeometry(ISLAND_RADIUS, ISLAND_RADIUS + 2.5, ISLAND_TOP - POND_DEPTH, 64),
    new THREE.MeshStandardMaterial({ color: 0xc9a13b, metalness: 0.5, roughness: 0.5 }),
  );
  island.position.y = (ISLAND_TOP + POND_DEPTH) / 2;
  scene.add(island);
}
