import * as THREE from 'three/webgpu';
import { lights } from 'three/tsl';
import { POND_OUTER } from './layout';

export function createParrotShadow(scene: THREE.Scene, bird: THREE.Object3D, direction: THREE.Vector3) {
  const layer = 3;
  bird.traverse(object => { if ((object as THREE.Mesh).isMesh) { object.layers.enable(layer); object.castShadow = true; } });
  const light = new THREE.DirectionalLight(0xffffff, 1);
  light.layers.set(layer); light.castShadow = true;
  light.shadow.mapSize.set(1024, 1024);
  Object.assign(light.shadow.camera, { left: -2, right: 2, top: 2, bottom: -2, near: .1, far: 80 });
  light.shadow.camera.layers.set(layer);light.shadow.camera.updateProjectionMatrix();
  light.shadow.bias = -.00001;light.shadow.normalBias = .003;
  light.shadow.autoUpdate = false; light.shadow.needsUpdate = true;
  scene.add(light, light.target);
  const material = new THREE.ShadowNodeMaterial({ color: 0x302614, opacity: .42, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -1, polygonOffsetUnits: -1 });
  material.lightsNode = lights([light]);
  // Receive the bird silhouette on the actual curved eastern bridge, not a flat plane over the pond.
  for (const original of [...scene.children]) {
    if (original.name !== 'BridgeAsset') continue;
    const source = original as THREE.InstancedMesh;
    const receiver = new THREE.Mesh(source.geometry, material);
    source.getMatrixAt(0, receiver.matrix);receiver.matrix.premultiply(source.matrixWorld);
    receiver.matrixAutoUpdate = false;receiver.receiveShadow = true;receiver.renderOrder = 5;receiver.name = 'ParrotBridgeShadowReceiver';scene.add(receiver);
  }
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(35, 8).rotateX(-Math.PI/2), material);
  ground.position.set(POND_OUTER + 17.5, .014, bird.position.z);ground.receiveShadow = true;ground.renderOrder = 5;ground.name = 'ParrotShoreShadowReceiver';scene.add(ground);
  light.target.position.copy(bird.position);light.position.copy(bird.position).addScaledVector(direction,30);
  let elapsed = 0;
  return { update(dt: number) { elapsed += dt; if (elapsed >= .1) { light.shadow.needsUpdate = true;elapsed %= .1; } } };
}
