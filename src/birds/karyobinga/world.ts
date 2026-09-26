import * as THREE from 'three/webgpu';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { KARYOBINGA_HOME, KARYOBINGA_SCALE } from '../../world/layout';

export async function createWorldKaryobinga(scene: THREE.Scene) {
  const response = await fetch(`${import.meta.env.BASE_URL}assets/karyobinga/karyobinga-floating.glb.gz`);
  if (!response.ok) throw new Error(`Karyobinga HTTP ${response.status}`);
  const packed = await response.arrayBuffer();
  const bytes = new Uint8Array(packed);
  const data = bytes[0] === 0x1f && bytes[1] === 0x8b
    ? await new Response(new Blob([packed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()
    : packed;
  const gltf = await new GLTFLoader().parseAsync(data, '');
  const clip = gltf.animations.find(a => a.name === 'FloatingIdle');
  if (!clip) throw new Error('Karyobinga FloatingIdle animation is missing');
  // Keep placement outside the animated hierarchy so hover tracks retain their original pose.
  const bird = new THREE.Group();
  bird.name = 'WorldKaryobinga';
  bird.position.set(KARYOBINGA_HOME.x, KARYOBINGA_HOME.y, KARYOBINGA_HOME.z);
  bird.scale.setScalar(KARYOBINGA_SCALE);
  bird.rotation.y = Math.PI / 2;
  bird.add(gltf.scene);
  gltf.scene.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    // Bounds of the original pose do not cover the moving wings and hover.
    mesh.frustumCulled = false;
    // The western sun and overhead garlands otherwise obscure the coloured feathers.
    // Keep this gentle fill local to the bird, including the approved face textures.
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const material of materials) {
      const surface = material as THREE.MeshStandardMaterial;
      if (!surface.isMeshStandardMaterial || surface.emissive.getHex() !== 0) continue;
      surface.emissive.copy(surface.color);
      surface.emissiveMap = surface.map;
      surface.emissiveIntensity = 0.18;
    }
  });
  const mixer = new THREE.AnimationMixer(gltf.scene);
  mixer.clipAction(clip).play();
  mixer.update(0);
  scene.add(bird);
  let elapsed = 0;
  const actor = { bird, mixer, clip, update(dt: number) {
    elapsed += dt;
    if (elapsed < 1 / 30) return;
    mixer.update(elapsed);
    elapsed = 0;
  } };
  (window as unknown as { __worldKaryobinga: typeof actor }).__worldKaryobinga = actor;
  return actor;
}
