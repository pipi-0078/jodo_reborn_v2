import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {rigBody} from './rig.js';
import {createTrain} from './train.js';
import {PeacockBehavior} from './behavior.js';
import {PEACOCK_HOME, PEACOCK_SCALE, sampleGround} from '../../world/layout';

export async function createWorldPeacock(scene) {
  const gltf = await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}assets/peacock/peacock-body.glb`);
  const bird = new T.Group();
  bird.name = 'PureLandPeacock';
  const rig = rigBody(gltf.scene);
  bird.add(rig.group);
  // Construct the train in model coordinates before placing the entire actor.
  const train = await createTrain(rig.group);
  bird.add(train.root);
  // A gentle pearlescent fill preserves the approved colors in the western backlight.
  const materials = new Set();
  bird.traverse(node => { if (node.isMesh) materials.add(node.material); });
  for (const material of materials) {
    material.emissive.set(0xffffff);
    material.emissiveMap = material.map;
    material.emissiveIntensity = 0.22;
  }
  bird.scale.setScalar(PEACOCK_SCALE);
  const brain = new PeacockBehavior();
  brain.heading = Math.PI;
  function update(dt) {
    const motion = brain.update(dt);
    const x = PEACOCK_HOME.x + brain.position.x * PEACOCK_SCALE;
    const z = PEACOCK_HOME.z + brain.position.z * PEACOCK_SCALE;
    const ground = sampleGround(x, z);
    bird.position.set(x, ground.y, z);
    bird.rotation.y = brain.heading;
    rig.update(dt, motion);
    train.update(brain.openness, brain.time);
  }
  update(0);
  scene.add(bird);
  const actor = {update, bird, brain, rig, train};
  window.__peacock = actor;
  return actor;
}
