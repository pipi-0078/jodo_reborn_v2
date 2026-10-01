import * as THREE from 'three/webgpu';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { tintPetal } from '../../world/glow';
import { applyPureGold } from '../../world/gold';
import { GUMYOCHO_PERCH, WATER_LEVEL } from '../../world/layout';
import { gumyochoWaterFocus } from '../../world/waterSurface';

// Preserve the approved bird/lotus contact and all animation tracks inside their original hierarchy.
export async function createWorldGumyocho(scene: THREE.Scene, originalLotusMatrix: THREE.Matrix4) {
  const gltf = await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}assets/gumyocho-on-lotus.glb`);
  const clip = gltf.animations.find(animation => animation.name === 'Everyday life');
  const bird = gltf.scene.getObjectByName('Bird_seated_on_receptacle');
  const lotus = gltf.scene.getObjectByName('Existing_lotus_in_bloom');
  if (!clip || !bird || !lotus) throw new Error('Gumyocho animation or lotus assembly is missing');

  const position = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  const scale = new THREE.Vector3();
  originalLotusMatrix.decompose(position, quaternion, scale);
  const perch = new THREE.Group();
  perch.name = 'WorldGumyochoOnWhiteLotus';
  perch.scale.copy(scale).divideScalar(lotus.scale.y);
  perch.quaternion.copy(quaternion);
  // The combined GLB has its lotus root at -0.398 m and scale 2. Match the old root exactly.
  const lotusOffset = lotus.position.clone().multiply(perch.scale).applyQuaternion(quaternion);
  perch.position.copy(position).sub(lotusOffset);
  perch.add(gltf.scene);

  const tinted = new Map<THREE.Material, THREE.Material>();
  lotus.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (!mesh.isMesh) return;
    const adjust = (material: THREE.Material): THREE.Material => {
      if (material.name !== 'petal') {
        applyPureGold(material);
        return material;
      }
      if (!tinted.has(material)) tinted.set(material, tintPetal(material, GUMYOCHO_PERCH.tint));
      return tinted.get(material)!;
    };
    mesh.material = Array.isArray(mesh.material) ? mesh.material.map(adjust) : adjust(mesh.material);
  });
  gltf.scene.traverse(object => {
    const mesh = object as THREE.Mesh;
    if (!mesh.isMesh) return;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.frustumCulled = false;
  });

  const mixer = new THREE.AnimationMixer(gltf.scene);
  mixer.clipAction(clip).play();
  mixer.update(0);
  scene.add(perch);
  perch.updateMatrixWorld(true);
  gumyochoWaterFocus.value.copy(perch.position);
  const placement = {
    ...GUMYOCHO_PERCH,
    originalLotusMatrix: originalLotusMatrix.toArray(),
    originalLotusPosition: position.toArray(),
    originalLotusScale: scale.x,
    assemblyPosition: perch.position.toArray(),
    assemblyScale: perch.scale.x,
    waterY: WATER_LEVEL,
  };
  const actor = {
    bird, lotus, perch, mixer, clip, placement,
    update(dt: number) { mixer.update(dt); },
    seek(time: number) {
      mixer.setTime(THREE.MathUtils.euclideanModulo(time, clip.duration));
      perch.updateMatrixWorld(true);
    },
  };
  (window as unknown as { __worldGumyocho: typeof actor }).__worldGumyocho = actor;
  return actor;
}
