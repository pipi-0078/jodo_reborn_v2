import * as THREE from 'three/webgpu';
import { lights } from 'three/tsl';

// A local shadow pass resolves the bird's fine silhouette independently of the distant scenery.
export function createPeacockShadow(scene: THREE.Scene, bird: THREE.Object3D, direction: THREE.Vector3) {
  const layer = 2;
  bird.traverse(object => {
    if ((object as THREE.Mesh).isMesh) { object.layers.enable(layer); object.castShadow = true; }
  });
  const light = new THREE.DirectionalLight(0xffffff, 1);
  light.layers.set(layer);
  light.castShadow = true;
  light.shadow.mapSize.set(1024, 1024);
  Object.assign(light.shadow.camera, { left: -3, right: 3, top: 3, bottom: -3, near: 0.1, far: 80 });
  light.shadow.camera.layers.set(layer);
  light.shadow.camera.updateProjectionMatrix();
  light.shadow.bias = -0.00001;
  light.shadow.normalBias = 0.005;
  light.shadow.autoUpdate = false;
  light.shadow.needsUpdate = true;
  scene.add(light, light.target);
  const material = new THREE.ShadowNodeMaterial({ color: 0x302614, opacity: 0.42, depthWrite: false });
  material.lightsNode = lights([light]);
  const receiver = new THREE.Mesh(new THREE.PlaneGeometry(40, 12).rotateX(-Math.PI / 2), material);
  receiver.name = 'PeacockShadowReceiver';
  receiver.receiveShadow = true;
  scene.add(receiver);
  let elapsed = 0.1;
  function update(dt = 0) {
    elapsed += dt;
    if (elapsed < 0.1) return;
    elapsed %= 0.1;
    light.shadow.needsUpdate = true;
    light.target.position.copy(bird.position);
    light.position.copy(bird.position).addScaledVector(direction, 30);
    receiver.position.copy(bird.position);
    receiver.position.x += 10;
    receiver.position.y += 0.012;
  }
  update();
  return { update };
}
