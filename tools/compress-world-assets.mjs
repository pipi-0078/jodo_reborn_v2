import { readFile, writeFile } from 'node:fs/promises';
import { gzipSync, gunzipSync } from 'node:zlib';

// Only assets used in the main world. Raw GLBs remain available to the gallery.
const files = [
  'bridge_long.glb',
  'island_dais.glb',
  'amida_hitem3d_eighth.glb',
  'pavilion.glb',
  'pavilion_b.glb',
  'houju_takara.glb',
  'houju_tree.glb',
  'houju_yanagi.glb',
  'houju_conifer.glb',
  'houju_broadleaf.glb',
  'houju_lod.glb',
  'lotus.glb',
  'lotus_bud.glb',
  'ramou.glb',
  'ramou_short.glb',
  'parrot/parrot.glb',
  'peacock/peacock-body.glb',
  'crane/crane.glb',
  'gumyocho-on-lotus.glb',
];

let originalBytes = 0;
let compressedBytes = 0;
for (const file of files) {
  const source = new URL(`../public/assets/${file}`, import.meta.url);
  const original = await readFile(source);
  const compressed = gzipSync(original, { level: 9 });
  if (!gunzipSync(compressed).equals(original)) throw new Error(`Gzip verification failed: ${file}`);
  await writeFile(new URL(`${source.href}.gz`), compressed);
  originalBytes += original.length;
  compressedBytes += compressed.length;
}

const mib = bytes => (bytes / 1024 ** 2).toFixed(1);
console.log(`Prepared ${files.length} world assets: ${mib(originalBytes)} → ${mib(compressedBytes)} MiB (verified lossless).`);
