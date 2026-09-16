import * as THREE from 'three/webgpu';
import { NO_REFLECT_LAYER, TREE_RINGS, POND_OUTER, ISLAND_RADIUS, ISLAND_TOP } from './layout';

// One shared western sun shadow map, covering every planted ring.
export function createWorldShadows(
  scene: THREE.Scene, renderer: THREE.WebGPURenderer, sun: THREE.DirectionalLight,
): { update(dt: number): void } {
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFShadowMap;
  sun.castShadow = true;
  const extent = TREE_RINGS[TREE_RINGS.length - 1] + 20;
  const shadow = sun.shadow;
  shadow.mapSize.set(4096, 4096);
  Object.assign(shadow.camera, {
    left: -extent, right: extent, top: extent, bottom: -extent, near: 1, far: 600,
  });
  shadow.camera.layers.enable(NO_REFLECT_LAYER);
  shadow.camera.updateProjectionMatrix();
  shadow.normalBias = 0.035;
  shadow.bias = -0.00015;
  shadow.intensity = 0.65;
  shadow.autoUpdate = false;
  shadow.needsUpdate = true;
  scene.traverse(object => {
    if (!(object instanceof THREE.Mesh)) return;
    const materials = Array.isArray(object.material) ? object.material : [object.material];
    // Sky, light halos and the reflective water are not solid occluders.
    if (!materials.some(material => (material as THREE.MeshStandardMaterial).isMeshStandardMaterial)) return;
    object.castShadow = true;
    object.receiveShadow = true;
  });
  // Environment reflections on pure gold are not attenuated by direct-light shadows.
  // A transparent receiver adds gentle contact contrast without changing the gold.
  const catcherMaterial = new THREE.ShadowNodeMaterial({
    color: 0x392b18, opacity: 0.28, transparent: true, depthWrite: false,
  });
  for (const [geometry, height] of [
    [new THREE.RingGeometry(POND_OUTER, extent * 3, 128), 0],
    [new THREE.CircleGeometry(ISLAND_RADIUS, 64), ISLAND_TOP],
  ] as const) {
    geometry.rotateX(-Math.PI / 2);
    const catcher = new THREE.Mesh(geometry, catcherMaterial);
    catcher.name = 'GoldenGroundShadowReceiver';
    catcher.position.y = height + 0.008;
    catcher.receiveShadow = true;
    scene.add(catcher);
  }
  let elapsed = 0;
  return { update(dt) {
    elapsed += dt;
    // Animate bird/petal shadows at 10 Hz; reuse the map on intervening frames.
    if (elapsed >= 0.1) { shadow.needsUpdate = true; elapsed %= 0.1; }
  } };
}
