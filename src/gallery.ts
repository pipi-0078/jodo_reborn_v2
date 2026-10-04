import * as THREE from 'three/webgpu';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { pass } from 'three/tsl';
import { bloom } from 'three/addons/tsl/display/BloomNode.js';
import { createSky } from './world/sky';
import { makeGlowSprite, makeHaloMesh, tintPetal } from './world/glow';
import { applyPureGold, createGoldEnvironment } from './world/gold';

interface GalleryItem {
  id: string;
  name: string;
  category: string;
  file: string;
  desc: string;
  credit: string;
  explanation?: string;
  sceneNote?: string;
  sources?: string[];
  preview?: string; // 行動付きアセットは専用の展示ページで確認する
  animation?: string; // GLBに収録された動作をそのまま展示する
  surfaceY?: number; // 水面に触れる動作はGLB内の接触面を展示床に合わせる
  tint?: { materialName: string; color: string };
  glow?: boolean; // 蓮など、tint の色で淡く光らせる(発光マップ+光のスプライト+床の光輪)
  attach?: string[]; // 同じ座標系の添え物(光背の後ろに坐像を置く等)。一緒に読み込んで同じ枠で見せる
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
  const { sunDirection } = createSky(scene, renderer);
  createGoldEnvironment(renderer, sunDirection);
  scene.fog = null; // 陳列室では靄をかけない

  // 展示台(小さな金の circular 台座)
  const floor = new THREE.Mesh(
    new THREE.CircleGeometry(40, 64).rotateX(-Math.PI / 2),
    new THREE.MeshStandardMaterial({ color: 0xc9a13b, metalness: 0.45, roughness: 0.55 }),
  );
  scene.add(floor);

  // 煌めき: 強い光の点(宝石や磨いた金のハイライト)だけを滲ませる。閾値を高くして床の金は滲ませない(9/4)
  const postProcessing = new THREE.PostProcessing(renderer);
  const scenePass = pass(scene, camera);
  const scenePassColor = scenePass.getTextureNode('output');
  postProcessing.outputNode = scenePassColor.add(bloom(scenePassColor, 0.6, 0.35, 1.9));

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI * 0.52;
  controls.minDistance = 1;
  controls.maxDistance = 80;

  const loader = new GLTFLoader();
  let current: THREE.Group | null = null;
  let mixer: THREE.AnimationMixer | null = null;
  let animatedFraming = false;
  let cameraFit = 1;
  let backdropDirty = true;
  let showToken = 0; // 読み込み中に別の品目へ切り替えたとき、遅れて届いた前の品目を捨てる

  const loading = document.getElementById('loading')!;
  const captionName = document.querySelector('#caption .name')!;
  const captionDesc = document.querySelector('#caption .desc')!;
  const captionExplanation = document.querySelector('#caption .explanation')!;
  const captionScene = document.querySelector<HTMLElement>('#caption .scene-note')!;
  const captionSources = document.querySelector('#caption .sources')!;
  const captionDetails = document.querySelector<HTMLDetailsElement>('#caption details')!;
  let sources: Record<string, { label: string; url: string }> = {};
  const captionCredit = document.querySelector('#caption .credit')!;
  const preview = document.createElement('iframe');
  preview.id = 'asset-preview';
  preview.hidden = true;
  document.body.appendChild(preview);
  const browseElement = document.getElementById('browse')!;
  const captionElement = document.getElementById('caption')!;
  const fitPreview = (): void => {
    backdropDirty = true;
    const top = browseElement.getBoundingClientRect().bottom;
    const bottom = captionElement.getBoundingClientRect().height;
    const availableHeight = Math.max(1, window.innerHeight - top - bottom);
    preview.style.top = `${top}px`;
    preview.style.bottom = `${bottom}px`;
    preview.style.height = `${availableHeight}px`;
    // Keep every model above the explanation panel, including on portrait screens.
    const height = availableHeight;
    renderer.domElement.style.position = 'fixed';
    renderer.domElement.style.top = `${top}px`;
    camera.aspect = window.innerWidth / height;
    const nextFit = (animatedFraming ? 1.3 : 1.15) * Math.max(1, 1 / camera.aspect);
    camera.position.sub(controls.target).multiplyScalar(nextFit / cameraFit).add(controls.target);
    cameraFit = nextFit;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, height);
  };
  window.addEventListener('message', (event) => {
    if (event.origin !== location.origin || event.source !== preview.contentWindow || preview.hidden) return;
    const data = event.data;
    if (data?.type !== 'gallery-backdrop-camera') return;
    const { position, quaternion, fov, viewport } = data;
    if (!Array.isArray(position) || position.length !== 3 || !position.every(Number.isFinite)
      || !Array.isArray(quaternion) || quaternion.length !== 4 || !quaternion.every(Number.isFinite)
      || !Number.isFinite(fov) || fov <= 0 || fov >= 180 || !viewport
      || ![viewport.left, viewport.top, viewport.width, viewport.height].every(Number.isFinite)
      || viewport.width <= 0 || viewport.height <= 0) return;
    camera.position.fromArray(position);
    camera.quaternion.fromArray(quaternion);
    camera.fov = fov;
    // Extend the bird's view across its toolbar margins without shifting the horizon.
    camera.setViewOffset(viewport.width, viewport.height, -viewport.left, -viewport.top,
      preview.clientWidth, preview.clientHeight);
    camera.updateProjectionMatrix();
    backdropDirty = true;
  });
  new ResizeObserver(fitPreview).observe(browseElement);
  new ResizeObserver(fitPreview).observe(captionElement);

  async function show(item: GalleryItem): Promise<void> {
    captionName.textContent = item.name;
    captionExplanation.textContent = item.explanation ?? item.desc;
    captionScene.textContent = item.sceneNote ?? '';
    captionScene.hidden = !item.sceneNote;
    captionDesc.textContent = item.desc;
    captionCredit.textContent = item.credit;
    captionDetails.open = false;
    captionSources.replaceChildren();
    for (const id of item.sources ?? []) {
      const source = sources[id];
      if (!source) continue;
      const li = document.createElement('li');
      const link = document.createElement('a');
      link.textContent = source.label;
      link.href = source.url;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      li.appendChild(link);
      captionSources.appendChild(li);
    }
    captionElement.scrollTop = 0;
    loading.classList.remove('hidden');
    mixer?.stopAllAction();
    mixer = null;
    animatedFraming = !!item.animation;
    if (current) {
      scene.remove(current);
      current = null;
    }
    const token = ++showToken;
    preview.hidden = true;
    camera.clearViewOffset();
    camera.fov = 45;
    preview.removeAttribute('src'); // 他の品目では孔雀の描画・行動を停止
    renderer.domElement.style.display = '';
    fitPreview();
    if (item.preview) {
      preview.title = `${item.name}の動作展示`;
      preview.src = `${import.meta.env.BASE_URL}${item.preview}?embedded=1&backdrop=gallery`;
      preview.hidden = false;
      // Draw the statue's sky and golden floor behind the transparent bird viewer.
      backdropDirty = true;
      fitPreview();
      loading.classList.add('hidden');
      (window as unknown as { __model?: unknown }).__model = null;
      return;
    }
    const gltf = await loader.loadAsync(`${import.meta.env.BASE_URL}assets/${item.file}`);
    if (token !== showToken) return;
    const model = gltf.scene;
    for (const file of item.attach ?? []) {
      const extra = await loader.loadAsync(`${import.meta.env.BASE_URL}assets/${file}`);
      if (token !== showToken) return;
      model.add(extra.scene);
    }
    model.traverse((object) => {
      if (object instanceof THREE.Mesh) applyPureGold(object.material as THREE.Material); // 金の部材は純金の反射に
    });

    if (item.tint) {
      const color = new THREE.Color(item.tint.color);
      model.traverse((object) => {
        if (object instanceof THREE.Mesh) {
          const material = object.material as THREE.MeshStandardMaterial;
          if (material.name === item.tint!.materialName) {
            if (item.glow) {
              // 「青色青光」— それぞれの色で内側から淡く光らせる(空間と同じ係数)
              object.material = tintPetal(material, color);
            } else {
              material.color.copy(color);
              material.emissive.copy(color).multiplyScalar(0.18);
            }
          }
        }
      });
    }

    // 接地・中心合わせ・カメラフレーミング
    const box = new THREE.Box3().setFromObject(model);
    const size = box.getSize(new THREE.Vector3());
    const center = box.getCenter(new THREE.Vector3());
    model.position.set(-center.x, -(item.surfaceY ?? box.min.y), -center.z);
    if (item.tint && item.glow) {
      // 花の芯の光と、展示台に落ちる光輪
      const radius = Math.max(size.x, size.z) / 2;
      const sprite = makeGlowSprite(item.tint.color, radius * 1.7, 0.2);
      sprite.position.set(0, Math.min(size.y * 0.35, 0.2), 0);
      model.add(sprite);
      const halo = makeHaloMesh(item.tint.color, radius * 1.35, 0.5);
      halo.position.y = (item.surfaceY ?? 0) + 0.02;
      model.add(halo);
    }
    scene.add(model);
    (window as unknown as { __model?: unknown }).__model = model; // ヘッドレス検品用
    current = model;
    if (item.animation) {
      const clip = gltf.animations.find(animation => animation.name === item.animation);
      if (clip) {
        mixer = new THREE.AnimationMixer(model);
        mixer.clipAction(clip).play();
        model.traverse(object => {
          if ((object as THREE.SkinnedMesh).isSkinnedMesh) object.frustumCulled = false;
        });
      }
    }

    const radius = Math.max(size.x, size.y, size.z) / 2;
    const visibleHeight = box.max.y + model.position.y;
    controls.target.set(0, visibleHeight * 0.45, 0);
    camera.position.set(radius * 1.6, visibleHeight * 0.55, radius * 2.4);
    // Leave room for the open wings and forward drinking pose on portrait screens.
    cameraFit = (animatedFraming ? 1.3 : 1.15) * Math.max(1, 1 / camera.aspect);
    camera.position.sub(controls.target).multiplyScalar(cameraFit).add(controls.target);
    controls.update();

    loading.classList.add('hidden');
  }

  // no-cacheで毎回サーバに確認する(GitHub Pagesのキャッシュで新作が見えなくなるのを防ぐ)
  const manifest = await fetch(`${import.meta.env.BASE_URL}assets/gallery.json`, { cache: 'no-cache' })
    .then((r) => r.json());
  sources = manifest.sources ?? {};
  const items: GalleryItem[] = manifest.items;
  const list = document.getElementById('list')!;
  const categoryList = document.getElementById('categories')!;
  const categories: { id: string; name: string }[] = [
    { id: 'all', name: 'すべて' }, ...(manifest.categories ?? []),
  ];
  const params = new URLSearchParams(location.search);
  const initialItem = items.find(item => item.id === params.get('asset'));
  const requestedCategory = params.get('category');
  let activeCategory = categories.some(category => category.id === requestedCategory)
    ? requestedCategory! : initialItem?.category ?? 'all';
  let selectedId: string | undefined;
  const itemButtons = new Map<string, HTMLButtonElement>();
  const categoryButtons = new Map<string, HTMLButtonElement>();

  function selectItem(item: GalleryItem): void {
    itemButtons.forEach((button, id) => {
      button.classList.toggle('active', id === item.id);
      button.setAttribute('aria-pressed', String(id === item.id));
    });
    const url = new URL(location.href);
    url.searchParams.set('asset', item.id);
    url.searchParams.set('category', activeCategory);
    history.replaceState(null, '', url);
    if (selectedId !== item.id) {
      selectedId = item.id;
      void show(item);
    }
  }

  function selectCategory(id: string, preferredId = selectedId): void {
    activeCategory = id;
    const visible = items.filter(item => id === 'all' || item.category === id);
    const visibleIds = new Set(visible.map(item => item.id));
    itemButtons.forEach((button, itemId) => { button.hidden = !visibleIds.has(itemId); });
    categoryButtons.forEach((button, categoryId) => {
      button.setAttribute('aria-pressed', String(categoryId === id));
    });
    list.scrollTop = 0;
    const next = visible.find(item => item.id === preferredId) ?? visible[0];
    if (next) {
      selectItem(next);
      itemButtons.get(next.id)?.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    }
    fitPreview();
  }

  items.forEach(item => {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = item.name;
    button.dataset.asset = item.id;
    button.addEventListener('click', () => selectItem(item));
    list.appendChild(button);
    itemButtons.set(item.id, button);
  });
  categories.forEach(category => {
    const count = items.filter(item => category.id === 'all' || item.category === category.id).length;
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = `${category.name} ${count}`;
    button.dataset.category = category.id;
    button.setAttribute('aria-controls', 'list');
    button.addEventListener('click', () => selectCategory(category.id));
    categoryList.appendChild(button);
    categoryButtons.set(category.id, button);
  });
  selectCategory(activeCategory, initialItem?.id);

  // 動作検証用フック
  (window as unknown as { __camera?: THREE.PerspectiveCamera; __show?: (id: string) => void }).__camera = camera;
  (window as unknown as { __controls?: unknown }).__controls = controls; // ヘッドレス検品で注視点を動かす用
  (window as unknown as { __show?: (id: string) => void }).__show = (id: string) => {
    const item = items.find((i) => i.id === id);
    if (item) selectCategory(activeCategory === 'all' ? 'all' : item.category, item.id);
  };

  window.addEventListener('resize', () => {
    fitPreview();
  });

  const timer = new THREE.Timer();
  renderer.setAnimationLoop(() => {
    timer.update();
    if (document.hidden) return;
    if (!preview.hidden) {
      if (backdropDirty) postProcessing.render();
      backdropDirty = false;
      return;
    }
    mixer?.update(Math.min(timer.getDelta(), 0.05));
    controls.update();
    postProcessing.render();
  });
}

main().catch((error) => console.error('ギャラリーの起動に失敗:', error));
