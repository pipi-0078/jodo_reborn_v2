import * as T from 'three';
const smooth=(a,b,x)=>{const t=T.MathUtils.clamp((x-a)/(b-a),0,1);return t*t*(3-2*t);};

// Add a small neck articulation; keep all original positions, morphs and textures.
export function addNaturalMotion(rig){
  const root=new T.Bone();root.name='BiwaMotionRoot';
  const neck=new T.Bone();neck.name='BiwaNeck';neck.position.set(.002,.805,.31);
  const head=new T.Bone();head.name='BiwaHead';head.position.set(0,.043,.005);
  root.add(neck);neck.add(head);rig.bodyGroup.add(root);
  const skeleton=new T.Skeleton([root,neck,head]);
  rig.neutral();rig.bodyGroup.updateMatrixWorld(true);skeleton.calculateInverses();
  const replacements=new Map();
  for(const old of rig.meshes){
    const g=old.geometry,p=g.attributes.position,count=p.count;
    const indices=new Uint16Array(count*4),weights=new Float32Array(count*4);
    const headPart=old.name.startsWith('Floating_Rebuilt_head_');
    for(let i=0;i<count;i++){
      const x=p.getX(i),y=p.getY(i),z=p.getZ(i);
      // A common smooth field on the neck and rear hair connects the moving head to the torso.
      const height=smooth(.76,.855,y);
      // Shared field across all original surfaces: material boundaries must not open.
      const region=(1-smooth(.09,.17,Math.abs(x-.002)))*smooth(.15,.22,z)*(1-smooth(.35,.375,z));
      let influence=height*region;
      // Above the grafted neck, the approved head and crown move as one rigid shape.
      if(headPart)influence=T.MathUtils.lerp(influence,height,smooth(.824,.856,y));
      const upper=smooth(.802,.847,y),wHead=influence*upper,wNeck=influence-wHead;
      indices.set([0,1,2,0],i*4);weights.set([1-influence,wNeck,wHead,0],i*4);
    }
    g.setAttribute('skinIndex',new T.Uint16BufferAttribute(indices,4));
    g.setAttribute('skinWeight',new T.Float32BufferAttribute(weights,4));
    const mesh=new T.SkinnedMesh(g,old.material);mesh.name=old.name;
    mesh.castShadow=old.castShadow;mesh.receiveShadow=old.receiveShadow;mesh.frustumCulled=false;
    old.parent.add(mesh);mesh.updateMatrixWorld(true);mesh.bind(skeleton,mesh.matrixWorld);
    mesh.morphTargetInfluences?.fill(0);old.removeFromParent();replacements.set(old,mesh);
  }
  rig.meshes=rig.meshes.map(m=>replacements.get(m));
  rig.blinkMeshes=rig.blinkMeshes.map(m=>replacements.get(m));
  rig.windMeshes=rig.windMeshes.map(m=>replacements.get(m));
  const ts=[],neckQ=[],headQ=[],bodyQ=[],bodyY=[],duration=rig.clip.duration;
  for(let i=0;i<=648;i++){
    const t=duration*i/648,p=2*Math.PI*t/7.2,q=2*Math.PI*t/10.8,b=2*Math.PI*t/5.4;
    ts.push(t);bodyY.push(0,-.5+.0025*Math.sin(b),0);
    const rotations=[
      [new T.Euler(.012*Math.sin(p-.25),.012*Math.sin(q-.2),.006*Math.sin(p+.15)),neckQ],
      [new T.Euler(.022*Math.sin(p-.55)+.006*Math.sin(q),.035*Math.sin(q-.45),.009*Math.sin(p+.45)),headQ],
      [new T.Euler(.009*Math.sin(b-.2),0,.006*Math.sin(q)),bodyQ],
    ];
    for(const [e,values]of rotations)values.push(...new T.Quaternion().setFromEuler(e).toArray());
  }
  const clip=new T.AnimationClip('BiwaFloatingIdle',duration,[...rig.clip.tracks,
    new T.QuaternionKeyframeTrack('BiwaNeck.quaternion',ts,neckQ),
    new T.QuaternionKeyframeTrack('BiwaHead.quaternion',ts,headQ),
    new T.QuaternionKeyframeTrack('BiwaBody.quaternion',ts,bodyQ),
    new T.VectorKeyframeTrack('BiwaBody.position',ts,bodyY),
  ]);
  rig.mixer.stopAllAction();rig.mixer.uncacheRoot(rig.group);
  rig.clip=clip;rig.mixer=new T.AnimationMixer(rig.group);rig.mixer.clipAction(clip).play();
  rig.bones={root,neck,head};rig.skeleton=skeleton;
  rig.pose=t=>{rig.mixer.setTime(t);rig.group.updateMatrixWorld(true);skeleton.update();};
  rig.neutral=()=>{
    rig.mixer.stopAllAction();rig.group.position.set(0,1.025,0);rig.group.quaternion.identity();
    rig.bodyGroup.position.set(0,-.5,0);rig.bodyGroup.quaternion.identity();
    neck.quaternion.identity();head.quaternion.identity();
    for(const mesh of rig.meshes)mesh.morphTargetInfluences?.fill(0);
    rig.group.updateMatrixWorld(true);skeleton.update();
  };
  rig.pose(0);return rig;
}
