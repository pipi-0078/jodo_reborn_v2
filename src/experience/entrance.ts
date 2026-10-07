import type { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { AmbientBgm } from '../audio/bgm';

/** Keep the entry UI, browser pointer lock and music on the same lifecycle. */
export function setupEntrance(controls: PointerLockControls, lockTarget: HTMLElement): () => boolean {
  const overlay = document.getElementById('overlay')!;
  const enterButton = document.getElementById('enter') as HTMLButtonElement;
  const bgmEnabled = document.getElementById('bgm-enabled') as HTMLInputElement;
  const audioError = document.getElementById('audio-error')!;
  const bgm = new AmbientBgm(`${import.meta.env.BASE_URL}audio/celestial-resonance.mp3?v=128`, () => {
    audioError.hidden = false;
  });
  // PointerLockControls dispatches events before updating its isLocked property.
  const isInside = () => document.pointerLockElement === lockTarget;
  const updateMusic = () => bgm.setActive(isInside() && bgmEnabled.checked && !document.hidden);
  const updateEntry = () => {
    const inside = isInside();
    overlay.classList.toggle('hidden', inside);
    overlay.inert = inside;
    updateMusic();
  };

  enterButton.addEventListener('click', () => {
    audioError.hidden = true;
    // Both audio APIs must start within this gesture, before pointer lock completes.
    if (bgmEnabled.checked) bgm.prepare();
    controls.lock();
  });
  controls.addEventListener('lock', updateEntry);
  controls.addEventListener('unlock', updateEntry);
  document.addEventListener('pointerlockerror', () => bgm.setActive(false));
  document.addEventListener('visibilitychange', updateMusic);
  window.addEventListener('pagehide', () => bgm.stopImmediately());
  enterButton.disabled = false;
  enterButton.textContent = 'クリックして入場';
  return isInside;
}
