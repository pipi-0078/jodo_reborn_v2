import { loadGltfAssetWithData } from '../../assets/loadGltf';

export const KARYOBINGA_ASSETS = {
  flute: {
    file: 'karyobinga/karyobinga-flute-v11.glb.gz',
    clip: 'FloatingIdle', body: 'KaryobingaIdle',
    face: [0, 0.823, 0.14], hair: [0, 0.77, 0.06],
    span: 1.8, frontOffset: 0.55,
  },
  biwa: {
    file: 'karyobinga-biwa/karyobinga-biwa-floating-v2.glb.gz',
    clip: 'BiwaFloatingIdle', body: 'BiwaBody',
    face: [0, 0.884, 0.385], hair: [0, 0.79, 0.24],
    span: 1.75, frontOffset: 0.20,
  },
} as const;
export type KaryobingaVariant = keyof typeof KARYOBINGA_ASSETS;

export async function loadKaryobinga(variant: KaryobingaVariant) {
  const config = KARYOBINGA_ASSETS[variant];
  const { gltf, data } = await loadGltfAssetWithData(`${import.meta.env.BASE_URL}assets/${config.file}`);
  const clip = gltf.animations.find(a => a.name === config.clip);
  const body = gltf.scene.getObjectByName(config.body);
  if (!clip || !body) throw new Error(`Karyobinga ${variant}: missing animation or body`);
  return { gltf, clip, body, data, config };
}
