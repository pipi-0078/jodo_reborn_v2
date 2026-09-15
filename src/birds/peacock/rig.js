import * as T from 'three';

// Initial gallery rig for this specific, normalized generated body.
// Bind-space geometry is preserved; wings/flight are intentionally not rigged.
export function rigBody(source) {
  source.updateMatrixWorld(true);
  let original;
  source.traverse(o=>{if(o.isMesh)original=o;});
  if(!original)throw new Error('Body mesh missing');
  const geometry=original.geometry.clone().applyMatrix4(original.matrixWorld);
  const material=original.material.clone();
  const bones=[],anchors=[];
  function bone(name,position,parentIndex=-1){
    const b=new T.Bone();b.name=name;
    const p=new T.Vector3(...position);anchors.push(p);
    b.position.copy(p);if(parentIndex>=0){b.position.sub(anchors[parentIndex]);bones[parentIndex].add(b);}
    bones.push(b);return bones.length-1;
  }
  const root=bone('body',[0,0,0]);
  const neck=bone('neck',[-.18,.62,0],root);
  const head=bone('head',[-.19,.855,0],neck);
  const legs=[];
  for(const sign of [-1,1]){
    const hip=bone(`hip_${sign}`,[-.05,.30,sign*.065],root);
    const hock=bone(`hock_${sign}`,[-.055,.16,sign*.073],hip);
    const foot=bone(`foot_${sign}`,[-.070,.035,sign*.084],hock);
    legs.push({hip,hock,foot,sign});
  }
  const positions=geometry.attributes.position,indices=[],weights=[];
  let maxWeightError=0;
  for(let i=0;i<positions.count;i++){
    const x=positions.getX(i),y=positions.getY(i),z=positions.getZ(i);
    let ids=[root,0,0,0],ws=[1,0,0,0];
    if(y>.60){
      const nw=T.MathUtils.smoothstep(y,.60,.73),hw=T.MathUtils.smoothstep(y,.80,.86);
      ids=[root,neck,head,0];ws=[1-nw,nw*(1-hw),nw*hw,0];
    }else if(y<.32 && x<.025){
      const leg=legs[z<0?0:1];
      const mask=(1-T.MathUtils.smoothstep(y,.235,.315))*(1-T.MathUtils.smoothstep(x,-.025,.025));
      const fw=1-T.MathUtils.smoothstep(y,.035,.075);
      const hw=(1-fw)*(1-T.MathUtils.smoothstep(y,.13,.21));
      const tw=1-fw-hw;
      ids=[root,leg.hip,leg.hock,leg.foot];ws=[1-mask,mask*tw,mask*hw,mask*fw];
    }
    maxWeightError=Math.max(maxWeightError,Math.abs(ws.reduce((a,b)=>a+b,0)-1));
    indices.push(...ids);weights.push(...ws);
  }
  geometry.setAttribute('skinIndex',new T.Uint16BufferAttribute(indices,4));
  geometry.setAttribute('skinWeight',new T.Float32BufferAttribute(weights,4));
  const mesh=new T.SkinnedMesh(geometry,material);mesh.name='peacock_rigged_body';
  mesh.add(bones[root]);mesh.bind(new T.Skeleton(bones));mesh.frustumCulled=false;
  mesh.castShadow=true;mesh.receiveShadow=true;
  const group=new T.Group();group.add(mesh);
  function solveLeg(leg,x,y){
    const a=anchors[leg.hip],b=anchors[leg.hock],c=anchors[leg.foot];
    const l1=Math.hypot(b.x-a.x,b.y-a.y),l2=Math.hypot(c.x-b.x,c.y-b.y);
    let dx=x-a.x,dy=y-a.y,d=Math.hypot(dx,dy);
    d=T.MathUtils.clamp(d,Math.abs(l1-l2)+.00001,l1+l2-.00001);
    const ux=dx/Math.hypot(dx,dy),uy=dy/Math.hypot(dx,dy);
    const along=(l1*l1-l2*l2+d*d)/(2*d),out=Math.sqrt(Math.max(0,l1*l1-along*along));
    const jointX=a.x+ux*along-uy*out,jointY=a.y+uy*along+ux*out;
    const upper=Math.atan2(jointY-a.y,jointX-a.x)-Math.atan2(b.y-a.y,b.x-a.x);
    const lower=Math.atan2(y-jointY,x-jointX)-Math.atan2(c.y-b.y,c.x-b.x)-upper;
    bones[leg.hip].rotation.z=upper;bones[leg.hock].rotation.z=lower;
    bones[leg.foot].rotation.z=-upper-lower;
  }
  let gait=0,look=0,nod=0,walkBlend=0;
  function update(dt,{distance=0,moving=false,lookYaw=0,resting=false,time=0}={}){
    gait+=distance/.085*.62;
    walkBlend=T.MathUtils.damp(walkBlend,moving?1:0,8,dt);
    for(let i=0;i<legs.length;i++){
      const leg=legs[i],phase=(gait+i*.5)%1;
      let step,lift;
      if(phase<.62){step=-.0425+.085*phase/.62;lift=0;}
      else{const u=(phase-.62)/.38;step=.0425-.085*T.MathUtils.smoothstep(u,0,1);lift=.032*Math.sin(Math.PI*u);}
      solveLeg(leg,anchors[leg.foot].x+step*walkBlend,anchors[leg.foot].y+lift*walkBlend);
    }
    look=T.MathUtils.damp(look,T.MathUtils.clamp(lookYaw,-.55,.55),3,dt);
    nod=T.MathUtils.damp(nod,resting?-.09:0,2,dt);
    bones[neck].rotation.y=look*.35;
    bones[head].rotation.y=look*.65;
    bones[neck].rotation.z=nod+.018*Math.sin(time*1.3)*walkBlend;
    bones[head].rotation.z=-nod*.35+.012*Math.sin(time*.9);
    return {gait,walkBlend};
  }
  return {group,mesh,update,bones,anchors,maxWeightError};
}
