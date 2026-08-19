import * as THREE from 'three/webgpu';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import {
  BRIDGE_CENTER, CAUSEWAY_HALF_WIDTH, POND_INNER, POND_OUTER, TREE_RINGS, WATER_LEVEL,
} from './layout';

const LOTUS_TINTS = [0x6f8cf5, 0xf2c452, 0xf07a7a, 0xf7faff]; // 青・黄・赤・白
const TREE_SPACING = 20;

// 決定的な擬似乱数(毎回同じ配置になるように)
function makeRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
}

async function load(file: string): Promise<THREE.Group> {
  const gltf = await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}assets/${file}`);
  gltf.scene.updateMatrixWorld(true);
  return gltf.scene;
}

// 四方に架かる金の反橋(全長22m、中島と岸を結ぶ)
async function placeBridges(scene: THREE.Scene): Promise<void> {
  const source = await load('bridge_long.glb');
  for (let i = 0; i < 4; i++) {
    const theta = (i * Math.PI) / 2;
    const bridge = source.clone(true);
    bridge.position.set(Math.cos(theta) * BRIDGE_CENTER, 0, Math.sin(theta) * BRIDGE_CENTER);
    bridge.rotation.y = -theta;
    scene.add(bridge);
  }
}

// 「池中蓮華大如車輪 青色青光…」満開と蕾を四色で散らす
async function placeLotuses(scene: THREE.Scene): Promise<void> {
  const [bloom, bud] = await Promise.all([load('lotus.glb'), load('lotus_bud.glb')]);
  const random = makeRandom(2026);
  const petalTints = LOTUS_TINTS.map((color) => new THREE.Color(color));

  for (let i = 0; i < 46; i++) {
    const isBud = i % 4 === 3;
    const flower = (isBud ? bud : bloom).clone(true);
    const tint = petalTints[i % 4];
    flower.traverse((object) => {
      if (object instanceof THREE.Mesh && (object.material as THREE.Material).name === 'petal') {
        const material = (object.material as THREE.MeshStandardMaterial).clone();
        material.color.copy(tint);
        material.emissive.copy(tint).multiplyScalar(0.18); // それぞれの色で内から光る
        object.material = material;
      }
    });
    // 橋の通り道を避けて池面に散らす
    let x = 0;
    let z = 0;
    for (let attempt = 0; attempt < 24; attempt++) {
      const angle = random() * Math.PI * 2;
      const radius = POND_INNER + 2 + random() * (POND_OUTER - POND_INNER - 4);
      x = Math.cos(angle) * radius;
      z = Math.sin(angle) * radius;
      if (Math.abs(x) > CAUSEWAY_HALF_WIDTH + 2.5 && Math.abs(z) > CAUSEWAY_HALF_WIDTH + 2.5) break;
    }
    flower.position.set(x, WATER_LEVEL - (isBud ? 0.5 : 0.06), z);
    flower.rotation.y = random() * Math.PI * 2;
    flower.scale.setScalar(0.85 + random() * 0.4);
    scene.add(flower);
  }
}

// 七重行樹(軽量版をインスタンシングで植える)
async function placeTrees(scene: THREE.Scene): Promise<void> {
  const source = await load('tree_lod.glb');
  const parts: { geometry: THREE.BufferGeometry; material: THREE.Material }[] = [];
  source.traverse((object) => {
    if (!(object instanceof THREE.Mesh)) return;
    const material = (object.material as THREE.MeshStandardMaterial).clone();
    if (material.name === 'foliage') {
      // 「七重行樹 皆是四宝」— 葉を金色に染める
      material.color.set(0xe8b445);
      material.metalness = 0.85;
      material.roughness = 0.35;
      material.emissive.set(0x6a4a10);
      material.emissiveIntensity = 0.25;
    }
    parts.push({
      geometry: (object.geometry as THREE.BufferGeometry).clone().applyMatrix4(object.matrixWorld),
      material,
    });
  });

  const random = makeRandom(77);
  const matrices: THREE.Matrix4[] = [];
  const position = new THREE.Vector3();
  const quaternion = new THREE.Quaternion();
  const up = new THREE.Vector3(0, 1, 0);
  for (const radius of TREE_RINGS) {
    const count = Math.floor((2 * Math.PI * radius) / TREE_SPACING);
    for (let i = 0; i < count; i++) {
      const angle = (i / count) * Math.PI * 2 + random() * 0.2;
      const x = Math.cos(angle) * radius;
      const z = Math.sin(angle) * radius;
      if (Math.abs(x) < 3 || Math.abs(z) < 3) continue; // 四方の見通しを残す
      position.set(x, 0, z);
      quaternion.setFromAxisAngle(up, random() * Math.PI * 2);
      const scale = 0.9 + random() * 0.35;
      matrices.push(new THREE.Matrix4().compose(position, quaternion, new THREE.Vector3(scale, scale, scale)));
    }
  }

  for (const part of parts) {
    const instanced = new THREE.InstancedMesh(part.geometry, part.material, matrices.length);
    matrices.forEach((matrix, i) => instanced.setMatrixAt(i, matrix));
    scene.add(instanced);
  }
}

export async function createProps(scene: THREE.Scene): Promise<void> {
  await Promise.all([placeBridges(scene), placeLotuses(scene), placeTrees(scene)]);
}
