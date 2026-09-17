import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {rigParrot} from './rig.js';
import {ParrotBehavior} from './behavior.js';
import {PARROT_PERCH,PARROT_SCALE} from '../../world/layout';

export async function createWorldParrot(scene){
  const gltf=await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}assets/parrot/parrot.glb`);
  const rig=rigParrot(gltf.scene),bird=rig.group,brain=new ParrotBehavior();
  scene.updateMatrixWorld(true);
  const bridges=scene.children.filter(o=>o.name==='BridgeAsset');
  const ray=new T.Raycaster();
  function railTop(x){
    ray.set(new T.Vector3(x,15,PARROT_PERCH.z),new T.Vector3(0,-1,0));
    const hit=ray.intersectObjects(bridges,false)[0];
    if(!hit)throw new Error('Parrot perch did not intersect bridge rail');
    return hit.point.y;
  }
  // Avoid finials: both feet must sit on a continuous stretch of handrail.
  const span=.08*PARROT_SCALE;
  let x=PARROT_PERCH.x;
  const candidates=Array.from({length:21},(_,i)=>PARROT_PERCH.x+(i%2?1:-1)*Math.ceil(i/2)*.1);
  const safe=candidates.find(px=>{
    const a=railTop(px-span*2),b=railTop(px-span),c=railTop(px),d=railTop(px+span),e=railTop(px+span*2);
    return Math.abs(e-a)/(4*span)<.65&&Math.max(Math.abs(a-2*b+c),Math.abs(b-2*c+d),Math.abs(c-2*d+e))<.012;
  });
  if(safe===undefined)throw new Error('No continuous bridge rail found for parrot feet');
  x=safe;
  const y=railTop(x);
  const slope=Math.atan2(railTop(x+span)-railTop(x-span),2*span);
  bird.scale.setScalar(PARROT_SCALE);bird.rotation.z=slope;
  // Match the reference perch's top (0.440) and depth (0.115) to the real rail.
  const anchor=new T.Vector3(0,.440,.115).multiplyScalar(PARROT_SCALE).applyAxisAngle(new T.Vector3(0,0,1),slope);
  bird.position.set(x,y,PARROT_PERCH.z).sub(anchor);
  rig.mesh.material.emissive.set(0xffffff);rig.mesh.material.emissiveMap=rig.mesh.material.map;rig.mesh.material.emissiveIntensity=.12;
  scene.add(bird);
  function update(dt){const pose=brain.update(dt*1.5);rig.pose(brain.time,pose);}
  update(0);
  const actor={bird,brain,rig,update,perch:{x,y,z:PARROT_PERCH.z,slope}};
  window.__worldParrot=actor;
  return actor;
}
