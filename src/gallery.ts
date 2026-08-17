import * as THREE from 'three/webgpu';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { createSky } from './world/sky';

interface GalleryItem {
  id: string;
  name: string;
  file: string;
  desc: string;
  credit: string;
  tint?: { materialName: string; color: string };
}

async function main(): Promise<void> {
  const renderer = new THREE.WebGPURenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 0.9;
  document.body.appendChild(renderer.domElement);
  await renderer.init();

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.05, 3000);
  createSky(scene, renderer);
  scene.fog = null; // 陳列室では靄をかけない

  // 展示台(小さな金の circular 台座)
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(40, 64).rotateX(-Math.PI / 2),
    new THREE.MeshStandardMaterial({ color: 0xc9a13b, metalness: 0.45, roughness: 0.55 }),
  );
  scene.add(floor);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.52;
  controls.minDistance = 1;
  controls.maxDistance = 80;

  const loader = new GLTFLoader();
  let current: THREE.Group | null = null;

  const loading = document.getElementById('loading')!;
  const captionName = document.querySelector('#caption .name')!;
  const captionDesc = document.querySelector('#caption .desc')!;
  const captionCredit = document.querySelector('#caption .credit')!;

  async function show(item: GalleryItem): Promise<void> {
    loading.classList.remove('hidden');
    if (current) {
      scene.remove(current);
      current = null;
    }
    const gltf = await loader.loadAsync(`${import.meta.env.BASE_URL}assets/${item.file}`);
    const model = gltf.scene;

    if (item.tint) {
      const color = new THREE.Color(item.tint.color);
      model.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          const material = object.material as THREE.MeshStandardMaterial;
          if (material.name === item.tint!.materialName) {
            material.color.copy(color);
            // 「青色青光」— それぞれの色で内側からほのかに光らせる
            material.emissive.copy(color).multiplyScalar(0.18);
          }
        }
      });
    }

    // 接地・中心合わせ・カメラフレーミング
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    model.position.set(-center.x, -box.min.y, -center.z);
    scene.add(model);
    current = model;

    const radius = Math.max(size.x, size.y, size.z) / 2;
    controls.target.set(0, size.y * 0.45, 0);
    camera.position.set(radius * 1.6, size.y * 0.55, radius * 2.4);
    controls.update();

    captionName.textContent = item.name;
    captionDesc.textContent = item.desc;
    captionCredit.textContent = item.credit;
    loading.classList.add('hidden');
  }

  const manifest = await fetch(`${import.meta.env.BASE_URL}assets/gallery.json`).then((r) => r.json());
  const items: GalleryItem[] = manifest.items;
  const list = document.getElementById('list')!;
  items.forEach((item, index) => {
    const button = document.createElement('button');
    button.textContent = item.name;
    button.addEventListener('click', () => {
      list.querySelectorAll('button').forEach((b) => b.classList.remove('active'));
      button.classList.add('active');
      void show(item);
    });
    list.appendChild(button);
    if (index === 0) button.click();
  });

  // 動作検証用フック
  (window as unknown as { __camera?: THREE.PerspectiveCamera; __show?: (id: string) => void }).__camera = camera;
  (window as unknown as { __show?: (id: string) => void }).__show = (id: string) => {
    const item = items.find((i) => i.id === id);
    if (item) void show(item);
  };

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  renderer.setAnimationLoop(() => {
    controls.update();
    renderer.render(scene, camera);
  });
}

main().catch((error) => console.error('ギャラリーの起動に失敗:', error));
