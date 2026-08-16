import * as THREE from 'three/webgpu';
import { POND_OUTER } from './layout';

export const WORLD_RADIUS = 1000;

// 「黄金為地」— 大地は黄金。
// 歩行時の視差が生まれるよう、ラフネスにゆらぎを持たせて表面の変化をつくる
export function createGround(scene: THREE.Scene, withPondHole = false): void {
  const geometry = withPondHole
    ? new THREE.RingGeometry(POND_OUTER, WORLD_RADIUS, 128, 8)
    : new THREE.CircleGeometry(WORLD_RADIUS, 128);
  geometry.rotateX(-Math.PI / 2);

  const material = new THREE.MeshStandardMaterial({
    color: 0xc9a13b,
    metalness: 0.45,
    roughness: 0.55,
    roughnessMap: makeNoiseTexture(),
  });

  const ground = new THREE.Mesh(geometry, material);
  scene.add(ground);
}

function makeNoiseTexture(): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const image = ctx.createImageData(size, size);
  for (let i = 0; i < image.data.length; i += 4) {
    const v = 150 + Math.floor(Math.random() * 90);
    image.data[i] = image.data[i + 1] = image.data[i + 2] = v;
    image.data[i + 3] = 255;
  }
  ctx.putImageData(image, 0, 0);

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
  texture.repeat.set(120, 120);
  return texture;
}
