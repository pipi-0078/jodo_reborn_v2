import * as THREE from 'three/webgpu';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';

const EYE_HEIGHT = 1.6;
const WALK_SPEED = 14;
const DAMPING = 8;
const BOUNDARY = 960; // 大地の縁の手前で止める

export class FirstPersonWalker {
  readonly controls: PointerLockControls;
  private readonly velocity = new THREE.Vector3();
  private readonly direction = new THREE.Vector3();
  private readonly keys = { forward: false, back: false, left: false, right: false };

  constructor(camera: THREE.PerspectiveCamera, domElement: HTMLElement, overlay: HTMLElement) {
    camera.position.set(120, EYE_HEIGHT, 0); // 東端にスポーン
    camera.lookAt(0, EYE_HEIGHT, 0); // 西方(阿弥陀仏の方角)を向く

    this.controls = new PointerLockControls(camera, domElement);

    overlay.addEventListener('click', () => this.controls.lock());
    this.controls.addEventListener('lock', () => overlay.classList.add('hidden'));
    this.controls.addEventListener('unlock', () => overlay.classList.remove('hidden'));

    document.addEventListener('keydown', (e) => this.setKey(e.code, true));
    document.addEventListener('keyup', (e) => this.setKey(e.code, false));
  }

  private setKey(code: string, pressed: boolean): void {
    switch (code) {
      case 'KeyW': case 'ArrowUp': this.keys.forward = pressed; break;
      case 'KeyS': case 'ArrowDown': this.keys.back = pressed; break;
      case 'KeyA': case 'ArrowLeft': this.keys.left = pressed; break;
      case 'KeyD': case 'ArrowRight': this.keys.right = pressed; break;
    }
  }

  update(dt: number): void {
    if (!this.controls.isLocked) return;

    const { velocity, direction, keys } = this;
    velocity.x -= velocity.x * DAMPING * dt;
    velocity.z -= velocity.z * DAMPING * dt;

    direction.z = Number(keys.forward) - Number(keys.back);
    direction.x = Number(keys.right) - Number(keys.left);
    direction.normalize();

    if (keys.forward || keys.back) velocity.z -= direction.z * WALK_SPEED * DAMPING * dt;
    if (keys.left || keys.right) velocity.x -= direction.x * WALK_SPEED * DAMPING * dt;

    this.controls.moveRight(-velocity.x * dt);
    this.controls.moveForward(-velocity.z * dt);

    const position = this.controls.object.position;
    position.y = EYE_HEIGHT;
    const radius = Math.hypot(position.x, position.z);
    if (radius > BOUNDARY) {
      position.x *= BOUNDARY / radius;
      position.z *= BOUNDARY / radius;
    }
  }
}
