// Build runtime copies; approved source models are never overwritten.
// node tools/prepare-karyobinga.mjs <source.glb> <output.glb.gz>
import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import { gzipSync } from 'node:zlib';
import { spawnSync } from 'node:child_process';
import { MeshoptSimplifier } from 'three/examples/jsm/libs/meshopt_simplifier.module.js';

const [source, destination] = process.argv.slice(2);
if (!source || !destination) throw Error('Expected source.glb and output.glb.gz');
const original = fs.readFileSync(source);
const jsonSize = original.readUInt32LE(12);
const doc = JSON.parse(original.subarray(20, 20 + jsonSize));
const bin = original.subarray(28 + jsonSize);
if (doc.extensionsUsed?.length) throw Error('Review extensions before optimizing');
const width = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT4: 16 };
const constructors = {5120: Int8Array, 5121: Uint8Array, 5122: Int16Array, 5123: Uint16Array, 5125: Uint32Array, 5126: Float32Array};
function readAccessor(id) {
  const a = doc.accessors[id], v = doc.bufferViews[a.bufferView];
  if (a.sparse || !v) throw Error('Unsupported accessor');
  const C = constructors[a.componentType], size = width[a.type] * C.BYTES_PER_ELEMENT;
  const data = Buffer.alloc(a.count * size), start = (v.byteOffset || 0) + (a.byteOffset || 0);
  for (let i = 0; i < a.count; i++) bin.copy(data, i * size, start + i * (v.byteStride || size), start + i * (v.byteStride || size) + size);
  return new C(data.buffer, data.byteOffset, a.count * width[a.type]);
}
const pending = new Map();
function newAccessor(old, data) {
  const a = structuredClone(doc.accessors[old]);
  delete a.bufferView; delete a.byteOffset;
  a.count = data.length / width[a.type];
  if (a.min || a.max) {
    a.min = Array(width[a.type]).fill(Infinity); a.max = a.min.map(() => -Infinity);
    for (let i = 0; i < data.length; i++) { const k = i % a.min.length; a.min[k] = Math.min(a.min[k], data[i]); a.max[k] = Math.max(a.max[k], data[i]); }
  }
  const id = doc.accessors.push(a) - 1;
  pending.set(id, data); return id;
}
await MeshoptSimplifier.ready;
const meshes = [];
for (let mi = 0; mi < doc.meshes.length; mi++) {
  for (const p of doc.meshes[mi].primitives) {
    const index = new Uint32Array(readAccessor(p.indices)), positions = readAccessor(p.attributes.POSITION);
    let result = index, error = 0;
    // Only the body and wings are decimated. Face, crown, hair and fine fibers remain exact.
    if (mi === 0) {
      const normals = readAccessor(p.attributes.NORMAL), uv = readAccessor(p.attributes.TEXCOORD_0);
      const morphs = (p.targets || []).map(t => readAccessor(t.POSITION));
      const skin = p.attributes.WEIGHTS_0 === undefined ? null : readAccessor(p.attributes.WEIGHTS_0);
      const stride = 5 + morphs.length * 3 + (skin ? 4 : 0), attributes = new Float32Array(positions.length / 3 * stride);
      const weights = [1, 1, 1, 1, 1, ...morphs.flatMap(() => [8, 8, 8]), ...(skin ? [2, 2, 2, 2] : [])];
      for (let i = 0; i < positions.length / 3; i++) {
        let off = i * stride;
        attributes.set(normals.subarray(i * 3, i * 3 + 3), off); off += 3;
        attributes.set(uv.subarray(i * 2, i * 2 + 2), off); off += 2;
        for (const m of morphs) { attributes.set(m.subarray(i * 3, i * 3 + 3), off); off += 3; }
        if (skin) attributes.set(skin.subarray(i * 4, i * 4 + 4), off);
      }
      [result, error] = MeshoptSimplifier.simplifyWithAttributes(index, positions, 3, attributes, stride, weights, null, Math.floor(index.length * .22 / 3) * 3, .002, ['LockBorder']);
    }
    const oldIds = [], map = new Map();
    const compact = new Uint32Array(result.length);
    for (let i = 0; i < result.length; i++) {
      const id = result[i]; if (!map.has(id)) { map.set(id, oldIds.length); oldIds.push(id); }
      compact[i] = map.get(id);
    }
    // Preserve every retained attribute/morph value byte-for-byte, including skinning.
    const remap = id => {
      const array = readAccessor(id), n = width[doc.accessors[id].type], next = new array.constructor(oldIds.length * n);
      for (let i = 0; i < oldIds.length; i++) next.set(array.subarray(oldIds[i] * n, (oldIds[i] + 1) * n), i * n);
      return newAccessor(id, next);
    };
    const oldIndex = p.indices;
    p.indices = newAccessor(oldIndex, compact);
    doc.accessors[p.indices].componentType = 5125;
    for (const key of Object.keys(p.attributes)) p.attributes[key] = remap(p.attributes[key]);
    for (const t of p.targets || []) for (const key of Object.keys(t)) t[key] = remap(t[key]);
    const name = doc.nodes.find(n => n.mesh === mi)?.name;
    meshes.push({ name, sourceTriangles:index.length / 3, triangles:result.length / 3, vertices:oldIds.length, error, topologyPreserved:mi !== 0 });
  }
}
const chunks = [], views = [], accessors = [], accessorMap = new Map(); let offset = 0;
function addView(data, target) {
  const padding = (4 - offset % 4) % 4;
  if (padding) { chunks.push(Buffer.alloc(padding)); offset += padding; }
  const buffer = Buffer.from(data.buffer, data.byteOffset, data.byteLength);
  const id = views.push({ buffer:0, byteOffset:offset, byteLength:buffer.length, ...(target ? { target } : {}) }) - 1;
  chunks.push(buffer); offset += buffer.length; return id;
}
function saveAccessor(id, target) {
  if (accessorMap.has(id)) return accessorMap.get(id);
  const a = structuredClone(doc.accessors[id]), array = pending.get(id) || readAccessor(id);
  a.bufferView = addView(array, target); a.byteOffset = 0;
  const next = accessors.push(a) - 1; accessorMap.set(id,next); return next;
}
for (const m of doc.meshes) for (const p of m.primitives) {
  p.indices = saveAccessor(p.indices, 34963);
  for (const key of Object.keys(p.attributes)) p.attributes[key] = saveAccessor(p.attributes[key],34962);
  for (const t of p.targets || []) for (const key of Object.keys(t)) t[key] = saveAccessor(t[key],34962);
}
for (const s of doc.skins || []) s.inverseBindMatrices = saveAccessor(s.inverseBindMatrices);
const trackHashes = [];
for (const animation of doc.animations || []) for (const s of animation.samplers) {
  for (const key of ['input','output']) {
    const data = readAccessor(s[key]);
    trackHashes.push(crypto.createHash('sha256').update(Buffer.from(data.buffer,data.byteOffset,data.byteLength)).digest('hex'));
    s[key] = saveAccessor(s[key]);
  }
}
// Preserve the approved face/hair colour and individual fiber texture at full resolution.
// Only surface-detail maps and body textures are reduced; their alpha is unused by materials.
const headImages = new Set([3, 4]);
const images = [];
for (let i = 0; i < doc.images.length; i++) {
  const image = doc.images[i], v = doc.bufferViews[image.bufferView];
  let bytes = bin.subarray(v.byteOffset || 0, (v.byteOffset || 0) + v.byteLength); const before = bytes.length;
  if (!headImages.has(i)) {
    const resized = spawnSync('python3', ['-c', 'from PIL import Image; import sys,io; im=Image.open(io.BytesIO(sys.stdin.buffer.read())); im.thumbnail((2048,2048),Image.Resampling.LANCZOS); im.convert("RGB").save(sys.stdout.buffer,format="JPEG",quality=95,subsampling=0,optimize=True)'], {input:bytes,maxBuffer:64*1024*1024});
    if (resized.status !== 0) throw Error(resized.stderr.toString());
    bytes = resized.stdout; image.mimeType = 'image/jpeg';
  }
  image.bufferView = addView(bytes);
  images.push({index:i,originalBytes:before,bytes:bytes.length,preserved:headImages.has(i)});
}
doc.bufferViews = views; doc.accessors = accessors;
const tailPadding = (4 - offset % 4) % 4;
if (tailPadding) chunks.push(Buffer.alloc(tailPadding));
const newBin = Buffer.concat(chunks); doc.buffers = [{byteLength:newBin.length}];
doc.asset.generator = 'Jodo runtime preparation; approved face/hair and animation preserved';
const json = Buffer.from(JSON.stringify(doc)), paddedJSON = Buffer.concat([json,Buffer.alloc((4-json.length%4)%4,32)]);
const header = Buffer.alloc(20); header.writeUInt32LE(0x46546c67);header.writeUInt32LE(2,4);header.writeUInt32LE(28+paddedJSON.length+newBin.length,8);header.writeUInt32LE(paddedJSON.length,12);header.writeUInt32LE(0x4e4f534a,16);
const binHeader = Buffer.alloc(8);binHeader.writeUInt32LE(newBin.length);binHeader.writeUInt32LE(0x004e4942,4);
const output = Buffer.concat([header,paddedJSON,binHeader,newBin]), packed = gzipSync(output,{level:9});
fs.mkdirSync(path.dirname(destination),{recursive:true});fs.writeFileSync(destination,packed);
const report = {source:path.basename(source),sourceSha256:crypto.createHash('sha256').update(original).digest('hex'),file:path.basename(destination),sourceBytes:original.length,bytes:output.length,gzipBytes:packed.length,sha256:crypto.createHash('sha256').update(output).digest('hex'),triangles:meshes.reduce((n,m)=>n+m.triangles,0),sourceTriangles:meshes.reduce((n,m)=>n+m.sourceTriangles,0),meshes,images,animationTracksSha256:trackHashes,animations:doc.animations.map(a=>a.name)};
fs.writeFileSync(path.join(path.dirname(destination),'manifest.json'),JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,animationTracksSha256:undefined,images:undefined,meshes:meshes.map(m=>({name:m.name,triangles:m.triangles,error:m.error}))},null,2));
