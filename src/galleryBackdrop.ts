import type { Object3D, PerspectiveCamera, Scene, WebGLRenderer } from 'three';
import type { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Embedded bird viewers supply only the actor; gallery.ts draws the same stage as the statue.
export const usesGalleryBackdrop = window.parent !== window
  && new URLSearchParams(location.search).get('backdrop') === 'gallery';

export function useGalleryBackdrop(
  scene: Scene, renderer: WebGLRenderer, camera: PerspectiveCamera, controls: OrbitControls,
  groundY = 0, scenery: Object3D[] = [],
): void {
  if (!usesGalleryBackdrop) return;
  scene.background = null;
  scene.fog = null;
  scenery.forEach(object => object.removeFromParent());
  renderer.setClearColor(0x000000, 0);
  document.documentElement.style.background = 'transparent';
  document.body.style.background = 'transparent';
  document.body.style.overflow = 'hidden';
  // Keep the shared stage visible on small screens; all existing controls remain available.
  const toolbar = document.querySelector<HTMLElement>('aside, header');
  if (toolbar) {
    const panel = document.createElement('details');
    panel.className = 'gallery-tools';
    const summary = document.createElement('summary');
    summary.textContent = '操作';
    panel.append(summary, toolbar);
    document.body.appendChild(panel);
    toolbar.style.cssText += ';position:static;width:auto;max-width:none;margin:0;padding:8px;background:transparent;border:0';
    const style = document.createElement('style');
    style.textContent = `
      .gallery-tools { position:absolute; top:8px; left:8px; z-index:10; max-width:calc(100% - 16px);
        max-height:calc(100% - 16px); overflow:auto; box-sizing:border-box; border-radius:8px;
        color:#493f32; background:#fcfaf3ed; font:13px/1.6 system-ui; }
      .gallery-tools > summary { cursor:pointer; padding:6px 12px; }
      .gallery-tools[open] { width:280px; }
      .gallery-tools button { font-size:12px; padding:5px 8px; }
      .gallery-tools h1 { display:none; }
    `;
    document.head.appendChild(style);
  }
  const update = (): void => {
    const rect = renderer.domElement.getBoundingClientRect();
    window.parent.postMessage({
      type: 'gallery-backdrop-camera',
      position: [camera.position.x, camera.position.y - groundY, camera.position.z],
      quaternion: camera.quaternion.toArray(), fov: camera.fov,
      viewport: { left: rect.left, top: rect.top, width: rect.width, height: rect.height },
    }, location.origin);
  };
  controls.addEventListener('change', update);
  new ResizeObserver(update).observe(renderer.domElement);
  window.addEventListener('resize', update);
  update();
}
