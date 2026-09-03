import * as THREE from 'three/webgpu';

// 「青色青光 黄色黄光 赤色赤光 白色白光」— 蓮がそれぞれの色で淡く光るための共通部品。
//  1. 花弁マテリアル: 色を乗算し、同じ色で発光させる(glb の発光マップが芯→先端の薄れを持つ)
//  2. 光のスプライト: 花の芯に置く、常にカメラを向く放射状の淡い光(加算)
//  3. 水面の光輪: 花の下の水面(床)に落ちる同色の光(加算)

export const PETAL_GLOW = 0.75; // 花弁の発光係数(発光マップは根元 1.0 → 先端 0.22 なので実効 0.17〜0.75)

// 花弁マテリアルを色に染めて同色で光らせる(複製して返す。元は共有テンプレートなので触らない)
export function tintPetal(material: THREE.Material, tint: THREE.ColorRepresentation, glow = PETAL_GLOW): THREE.Material {
  const petal = (material as THREE.MeshStandardMaterial).clone();
  petal.color.set(tint);
  petal.emissive.set(tint).multiplyScalar(glow);
  return petal;
}

// 放射状に薄れる光のテクスチャ。stops は [位置, 不透明度] の並び
function radialTexture(stops: [number, number][], size = 128): THREE.Texture {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  stops.forEach(([at, alpha]) => gradient.addColorStop(at, `rgba(255,255,255,${alpha})`));
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

let haloTexture: THREE.Texture | null = null;
let glowTexture: THREE.Texture | null = null;

// 水面に落ちる光の輪
export function makeHaloTexture(): THREE.Texture {
  haloTexture ??= radialTexture([[0, 1], [0.35, 0.55], [1, 0]]);
  return haloTexture;
}

// 花の芯から広がる淡い光(中心も飛ばさない、裾の長い分布)
export function makeGlowTexture(): THREE.Texture {
  glowTexture ??= radialTexture([[0, 0.85], [0.18, 0.45], [0.45, 0.12], [1, 0]], 256);
  return glowTexture;
}

// 花の芯に置く光のスプライト。size は直径(m)
export function makeGlowSprite(tint: THREE.ColorRepresentation, size: number, opacity = 0.32): THREE.Sprite {
  const material = new THREE.SpriteMaterial({
    map: makeGlowTexture(), color: tint, transparent: true, opacity,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(size, size, 1);
  return sprite;
}

// 床(水面)に落ちる光輪。radius は半径(m)
export function makeHaloMesh(tint: THREE.ColorRepresentation, radius: number, opacity = 0.5): THREE.Mesh {
  const geometry = new THREE.CircleGeometry(1, 40);
  geometry.rotateX(-Math.PI / 2);
  const material = new THREE.MeshBasicMaterial({
    map: makeHaloTexture(), color: tint, transparent: true, opacity,
    blending: THREE.AdditiveBlending, depthWrite: false,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.scale.set(radius, 1, radius);
  return mesh;
}
