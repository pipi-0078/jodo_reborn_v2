import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

export async function loadShari() {
  const response = await fetch(`${import.meta.env.BASE_URL}assets/shari/shari-flight.glb.gz`);
  if (!response.ok) throw new Error(`Shari HTTP ${response.status}`);
  const packed = await response.arrayBuffer();
  const bytes = new Uint8Array(packed);
  const data = bytes[0] === 0x1f && bytes[1] === 0x8b
    ? await new Response(new Blob([packed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()
    : packed;
  const gltf = await new GLTFLoader().parseAsync(data, '');
  const clip = gltf.animations.find(animation => animation.name === 'Living flight');
  if (!clip) throw new Error('Shari Living flight animation is missing');
  return { gltf, clip, data };
}
