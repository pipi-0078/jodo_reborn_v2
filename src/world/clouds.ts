import * as THREE from 'three/webgpu';

// 紫雲(しうん): 来迎図に描かれる紫金の雲。西の地平(阿弥陀の方角)の空に、
// 太陽側の縁が金に光り、内側が紫に沈む柔らかい雲を何層にも重ねる。ゆっくり流れる。
// 雲はカメラを向くスプライト(放射状のぼかしを重ねた雲形のテクスチャ)。靄の外側に置くので fog は切る

const CLOUD_COUNT = 34;
const DISTANCE = 1100;          // 雲までの距離(空のドーム 1800m の内側)

interface Cloud {
  sprite: THREE.Sprite;
  azimuth: number;   // 西(π)を中心とした方位
  elevation: number; // 仰角(rad)
  speed: number;     // 方位方向の流れ(rad/s)
}

// 雲形のテクスチャ: 楕円の中に柔らかい玉を重ね、上辺はもくもく、下辺は平らに
function makeCloudTexture(seed: number): THREE.Texture {
  const size = 512;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  ctx.clearRect(0, 0, size, size);
  let s = seed;
  const random = () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
  ctx.globalCompositeOperation = 'lighter';
  const puffs = 34;
  for (let i = 0; i < puffs; i++) {
    const t = i / puffs;
    const x = size * (0.15 + 0.7 * random());
    // 上辺は盛り上がり、下辺は平らに寄せる
    const y = size * (0.62 - 0.3 * Math.pow(random(), 1.6) + 0.06 * Math.sin(t * 9));
    const r = size * (0.09 + 0.14 * random());
    const gradient = ctx.createRadialGradient(x, y, 0, x, y, r);
    gradient.addColorStop(0, 'rgba(255,255,255,0.5)');
    gradient.addColorStop(0.5, 'rgba(255,255,255,0.22)');
    gradient.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, size, size);
  }
  // 全体を楕円で切って輪郭をまとめる
  ctx.globalCompositeOperation = 'destination-in';
  const mask = ctx.createRadialGradient(size / 2, size * 0.58, size * 0.1, size / 2, size * 0.58, size * 0.5);
  mask.addColorStop(0, 'rgba(0,0,0,1)');
  mask.addColorStop(0.75, 'rgba(0,0,0,1)');
  mask.addColorStop(1, 'rgba(0,0,0,0)');
  ctx.fillStyle = mask;
  ctx.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export function createPurpleClouds(scene: THREE.Scene, sunDirection: THREE.Vector3): { update(dt: number): void } {
  const textures = [makeCloudTexture(11), makeCloudTexture(23), makeCloudTexture(37)];
  const sunAzimuth = Math.atan2(sunDirection.z, sunDirection.x);
  const clouds: Cloud[] = [];
  let seed = 5;
  const random = () => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed / 0x7fffffff;
  };
  const gold = new THREE.Color(0xffd9a4);
  const violet = new THREE.Color(0xd9c2e6); // 薄紫(9/4「紫が濃すぎる」→ 淡く)
  const deep = new THREE.Color(0xb59ccb);

  for (let i = 0; i < CLOUD_COUNT; i++) {
    // 西を中心に ±55° の範囲。太陽に近いほど金、離れるほど紫
    const offset = (random() - 0.5) * 2 * THREE.MathUtils.degToRad(55);
    const elevation = THREE.MathUtils.degToRad(5 + Math.pow(random(), 1.4) * 20);
    const near = 1 - Math.min(1, Math.abs(offset) / THREE.MathUtils.degToRad(35));
    const tint = new THREE.Color().copy(violet).lerp(gold, near * near * 0.85);
    if (random() < 0.35) tint.lerp(deep, 0.4); // 手前のやや濃い層
    const material = new THREE.SpriteMaterial({
      map: textures[i % textures.length], color: tint, transparent: true,
      opacity: 0.7 + random() * 0.2, depthWrite: false, fog: false,
    });
    const sprite = new THREE.Sprite(material);
    const width = 260 + random() * 420;
    sprite.scale.set(width, width * (0.38 + random() * 0.2), 1);
    scene.add(sprite);
    clouds.push({ sprite, azimuth: sunAzimuth + offset, elevation, speed: (0.0006 + random() * 0.0012) * (random() < 0.5 ? 1 : -1) });
  }

  function place(cloud: Cloud): void {
    const { sprite, azimuth, elevation } = cloud;
    sprite.position.set(
      Math.cos(azimuth) * Math.cos(elevation) * DISTANCE,
      Math.sin(elevation) * DISTANCE,
      Math.sin(azimuth) * Math.cos(elevation) * DISTANCE,
    );
  }
  clouds.forEach(place);

  function update(dt: number): void {
    for (const cloud of clouds) {
      cloud.azimuth += cloud.speed * dt;
      place(cloud);
    }
  }
  return { update };
}
