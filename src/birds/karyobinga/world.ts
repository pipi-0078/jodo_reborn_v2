import * as THREE from 'three/webgpu';
import { KARYOBINGA_HOME, KARYOBINGA_BIWA_HOME, KARYOBINGA_SCALE } from '../../world/layout';
import { loadKaryobinga, type KaryobingaVariant } from './asset';

export async function createWorldKaryobinga(scene: THREE.Scene, variant: KaryobingaVariant = 'flute') {
  const { gltf, clip } = await loadKaryobinga(variant);
  const home = variant === 'biwa' ? KARYOBINGA_BIWA_HOME : KARYOBINGA_HOME;
  // Keep placement outside the animated hierarchy so hover tracks retain their original pose.
  const bird = new THREE.Group();
  bird.name = variant === 'biwa' ? 'WorldKaryobingaBiwa' : 'WorldKaryobinga';
  bird.position.set(home.x, home.y, home.z);
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
  mixer.setTime(variant === 'biwa' ? 3.6 : 0);
  bird.updateMatrixWorld(true);
  scene.add(bird);
  let elapsed = 0;
  const actor = { bird, mixer, clip, variant, seek(time: number) {
    mixer.setTime(time);
    bird.updateMatrixWorld(true);
  }, update(dt: number) {
    elapsed += dt;
    if (elapsed < 1 / 30) return;
    mixer.update(elapsed);
    elapsed = 0;
  } };
  const key = variant === 'biwa' ? '__worldKaryobingaBiwa' : '__worldKaryobinga';
  (window as unknown as Record<string, typeof actor>)[key] = actor;
  return actor;
}
