import * as T from 'three';

export function rigParrot(source) {
  source.updateMatrixWorld(true);
  let original;source.traverse(o=>{if(o.isMesh)original=o});
  if(!original)throw new Error('Parrot mesh missing');
  const geometry=original.geometry.clone().applyMatrix4(original.matrixWorld);
  const bones=[], anchors=[];
  function bone(name,p,parent=-1){
    const b=new T.Bone();b.name=name;const a=new T.Vector3(...p);anchors.push(a);b.position.copy(a);
    if(parent>=0){b.position.sub(anchors[parent]);bones[parent].add(b)}bones.push(b);return bones.length-1;
  }
  const root=bone('parrot_root',[0,0,0]);
  const torso=bone('parrot_torso',[0,.55,.015],root);
  const neck=bone('parrot_neck',[0,.79,.095],torso);
  const head=bone('parrot_head',[0,.925,.15],neck);
  const tail=bone('parrot_tail',[0,.45,-.13],root);
  const p=geometry.attributes.position,indices=[],weights=[];
  let maxWeightError=0,footVertices=0;
  for(let i=0;i<p.count;i++){
    const y=p.getY(i),z=p.getZ(i);
    let ids=[root,torso,neck,head], w;
    if(z<-.07&&y<.49){
      const t=(1-T.MathUtils.smoothstep(y,.36,.49))*(1-T.MathUtils.smoothstep(z,-.12,-.07));
      ids=[root,tail,0,0];w=[1-t,t,0,0];
    }else{
      const body=T.MathUtils.smoothstep(y,.49,.64);
      const n=T.MathUtils.smoothstep(y,.76,.87);
      const h=T.MathUtils.smoothstep(y,.89,.925);
      w=[1-body,body*(1-n),body*n*(1-h),body*n*h];
    }
    if(y<.49&&z>-.04)footVertices++;
    maxWeightError=Math.max(maxWeightError,Math.abs(w.reduce((a,b)=>a+b,0)-1));indices.push(...ids);weights.push(...w);
  }
  geometry.setAttribute('skinIndex',new T.Uint16BufferAttribute(indices,4));
  geometry.setAttribute('skinWeight',new T.Float32BufferAttribute(weights,4));
  const mesh=new T.SkinnedMesh(geometry,original.material.clone());mesh.name='parrot_rigged';
  mesh.add(bones[root]);mesh.bind(new T.Skeleton(bones));mesh.frustumCulled=false;mesh.castShadow=true;mesh.receiveShadow=true;
  const group=new T.Group();group.name='PureLandParrot';group.add(mesh);
  function pose(time,{yaw=0,tilt=0,rest=0}={}){
    bones[torso].rotation.x=.006*Math.sin(time*1.8);
    bones[neck].rotation.set(.075*rest,yaw*.3,tilt*.25);
    bones[head].rotation.set(.11*rest+.015*Math.sin(time*.7),yaw*.7,tilt*.75);
    bones[tail].rotation.y=.025*Math.sin(time*.75);
    bones[tail].rotation.x=.008*Math.sin(time*1.1);
    group.updateMatrixWorld(true);mesh.skeleton.update();
  }
  function makeClip(name,seconds,fn){
    const times=[],values=bones.map(()=>[]);
    for(let i=0;i<=seconds*30;i++){const t=i/30;times.push(t);const u=t/seconds;const spec=fn(u);pose(t,spec);
      // Exported loops meet exactly at both ends, including breathing and tail sway.
      bones[torso].rotation.x=.006*Math.sin(u*Math.PI*4);
      bones[head].rotation.x=.11*(spec.rest||0)+.015*Math.sin(u*Math.PI*2);
      bones[tail].rotation.set(.008*Math.sin(u*Math.PI*2),.025*Math.sin(u*Math.PI*2),0);
      bones.forEach((b,j)=>values[j].push(...b.quaternion.toArray()));}
    return new T.AnimationClip(name,seconds,bones.map((b,j)=>new T.QuaternionKeyframeTrack(`${b.name}.quaternion`,times,values[j])));
  }
  const clips=[
    makeClip('LookAround',8,u=>({yaw:.42*Math.sin(u*Math.PI*2)})),
    makeClip('CuriousTilt',6,u=>({tilt:.20*Math.sin(u*Math.PI*2),yaw:.15*Math.sin(u*Math.PI*2)})),
    makeClip('Rest',8,u=>({rest:Math.sin(u*Math.PI)**2})),
  ];
  group.animations=clips;pose(0);
  return {group,mesh,bones,pose,clips,maxWeightError,footVertices};
}
