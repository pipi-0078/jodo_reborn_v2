import * as THREE from 'three/webgpu';
import { SHARI_FLIGHT_AREA, SHARI_SCALE } from '../../world/layout';
import { loadShari } from './asset';
import { sampleFlight } from './motion';

export async function createWorldShari(scene: THREE.Scene) {
  const { gltf, clip } = await loadShari();
  const bird = new THREE.Group();
  bird.name = 'WorldShari';
  bird.scale.setScalar(SHARI_SCALE);
  bird.add(gltf.scene);
  gltf.scene.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = false;
    const materials = Array.isArray(mesh.material) ? mesh.material : [mesh.material];
    for (const material of materials) {
      const surface = material as THREE.MeshStandardMaterial;
      if (!surface.isMeshStandardMaterial) continue;
      // Gentle local fill keeps the pearl feathers readable under the canopy.
      surface.emissive.copy(surface.color);
      surface.emissiveMap = surface.map;
      surface.emissiveIntensity = 0.12;
    }
  });
  const mixer = new THREE.AnimationMixer(gltf.scene);
  mixer.clipAction(clip).play();
  let time = 0;
  function place(t: number) {
    const pose = sampleFlight(t, SHARI_FLIGHT_AREA);
    bird.position.set(pose.x, pose.y, pose.z);
    bird.rotation.y = pose.yaw;
  }
  place(0);
  mixer.update(0);
  scene.add(bird);
  const actor = {
    bird, mixer, clip, area: SHARI_FLIGHT_AREA,
    update(dt: number) {
      time += dt;
      place(time);
      mixer.update(dt);
    },
  };
  (window as unknown as { __worldShari: typeof actor }).__worldShari = actor;
  return actor;
}
