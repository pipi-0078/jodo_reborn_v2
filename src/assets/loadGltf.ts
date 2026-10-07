import { LoaderUtils } from 'three';
import { GLTFLoader, type GLTF } from 'three/addons/loaders/GLTFLoader.js';

const loader = new GLTFLoader();

/** Keep the decoded GLB available for viewers that offer an original-file download. */
export async function loadGltfAssetWithData(url: string): Promise<{ gltf: GLTF; data: ArrayBuffer }> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`GLTF ${url}: HTTP ${response.status}`);
  const packed = await response.arrayBuffer();
  const bytes = new Uint8Array(packed);
  // Hosts may already decode .gz responses via Content-Encoding.
  const data = bytes[0] === 0x1f && bytes[1] === 0x8b
    ? await new Response(new Blob([packed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()
    : packed;
  const resourcePath = LoaderUtils.extractUrlBase(response.url || url);
  const gltf = await loader.parseAsync(data, resourcePath);
  return { gltf, data };
}

export async function loadGltfAsset(url: string): Promise<GLTF> {
  if (/\.gz(?:[?#]|$)/.test(url)) return (await loadGltfAssetWithData(url)).gltf;
  return loader.loadAsync(url);
}
