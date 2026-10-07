import { loadGltfAssetWithData } from '../../assets/loadGltf';

export async function loadShari() {
  const { gltf, data } = await loadGltfAssetWithData(`${import.meta.env.BASE_URL}assets/shari/shari-flight.glb.gz`);
  const clip = gltf.animations.find(animation => animation.name === 'Living flight');
  if (!clip) throw new Error('Shari Living flight animation is missing');
  return { gltf, clip, data };
}
