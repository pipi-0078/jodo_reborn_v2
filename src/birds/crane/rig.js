import * as T from 'three';
export function rigCrane(source){
 source.updateMatrixWorld(true);let original;source.traverse(o=>{if(o.isMesh)original=o});
 const geometry=original.geometry.clone().applyMatrix4(original.matrixWorld),bones=[],anchors=[];
 const add=(name,a,parent=0)=>{const b=new T.Bone(),v=new T.Vector3(...a);b.name=name;b.position.copy(v);if(bones.length){b.position.sub(anchors[parent]);bones[parent].add(b)}anchors.push(v);bones.push(b);return bones.length-1;};
 add('root',[0,0,0]);const neck=add('neck',[0,.35,.10]);const head=add('head',[0,.49,.16],neck);
 const wings=[],legs=[];
 for(const s of [-1,1]){const shoulder=add(`wing_${s}`,[s*.065,.345,.02]);const elbow=add(`wingtip_${s}`,[s*.28,.40,.0],shoulder);wings.push({s,shoulder,elbow});
 const hip=new T.Vector3(s*.045,.241,.002),knee=new T.Vector3(s*.057,.133,-.024),foot=new T.Vector3(s*.099,.015,-.013);
 legs.push({s,hip,knee,foot,upper:add(`leg_${s}`,hip.toArray()),lower:add(`shin_${s}`,knee.toArray()),toe:add(`foot_${s}`,foot.toArray()),l1:hip.distanceTo(knee),l2:knee.distanceTo(foot)});}
 const p=geometry.attributes.position,ids=[],weights=[];let error=0;
 for(let i=0;i<p.count;i++){const x=p.getX(i),y=p.getY(i),z=p.getZ(i),s=x<0?-1:1;let indices=[0,0,0,0],w=[1,0,0,0];
 if(y<.25&&z>-.09&&(Math.abs(x)<.085||y<.05)){const leg=legs.find(l=>l.s===s);const upper=T.MathUtils.smoothstep(y,.215,.25),bend=T.MathUtils.smoothstep(y,.118,.149),ankle=T.MathUtils.smoothstep(y,.028,.050);indices=[0,leg.upper,leg.lower,leg.toe];w=[upper,(1-upper)*bend,(1-upper)*(1-bend)*ankle,(1-upper)*(1-bend)*(1-ankle)];}
 else if(Math.abs(x)>.07){const wing=wings.find(l=>l.s===s),a=T.MathUtils.smoothstep(Math.abs(x),.07,.14),e=T.MathUtils.smoothstep(Math.abs(x),.22,.33);indices=[0,wing.shoulder,wing.elbow,0];w=[1-a,a*(1-e),a*e,0];}
 else if(y>.35&&z>.065){const a=T.MathUtils.smoothstep(y,.35,.40),b=T.MathUtils.smoothstep(y,.47,.515);indices=[0,neck,head,0];w=[1-a,a*(1-b),a*b,0];}
 error=Math.max(error,Math.abs(w.reduce((a,b)=>a+b,0)-1));ids.push(...indices);weights.push(...w);}
 geometry.setAttribute('skinIndex',new T.Uint16BufferAttribute(ids,4));geometry.setAttribute('skinWeight',new T.Float32BufferAttribute(weights,4));
 const mesh=new T.SkinnedMesh(geometry,original.material.clone());mesh.add(bones[0]);mesh.bind(new T.Skeleton(bones));mesh.frustumCulled=false;mesh.castShadow=true;mesh.receiveShadow=true;
 const group=new T.Group();group.add(mesh);
 function pose(time,feet,fold=1,gait={}){
 for(const w of wings){bones[w.shoulder].rotation.set(-.45*fold,w.s*1.42*fold,0);bones[w.elbow].rotation.y=w.s*.18*fold;bones[w.elbow].scale.x=1-.50*fold;}
 bones[neck].rotation.y=.08*Math.sin(time*.47);bones[head].rotation.y=.06*Math.sin(time*.73);
 bones[neck].rotation.x=.024*(gait.lift||0);bones[head].rotation.x=-.020*(gait.lift||0);bones[neck].rotation.z=-(gait.roll||0)*.6;
 let reachError=0;
 legs.forEach((l,i)=>{const f=feet?.[i]??l.foot.clone(),dvec=f.clone().sub(l.hip),distance=dvec.length(),d=Math.min(l.l1+l.l2-.0001,Math.max(.001,distance)),axis=dvec.normalize();
 const a=(l.l1*l.l1-l.l2*l.l2+d*d)/(2*d),h=Math.sqrt(Math.max(0,l.l1*l.l1-a*a));let bend=new T.Vector3(0,0,-1).addScaledVector(axis,axis.z).normalize();const k=l.hip.clone().addScaledVector(axis,a).addScaledVector(bend,h);
 bones[l.upper].quaternion.setFromUnitVectors(l.knee.clone().sub(l.hip).normalize(),k.clone().sub(l.hip).normalize());bones[l.lower].position.copy(k);bones[l.lower].quaternion.setFromUnitVectors(l.foot.clone().sub(l.knee).normalize(),f.clone().sub(k).normalize());bones[l.toe].position.copy(f);bones[l.toe].rotation.set(i===gait.active?-.12*(gait.lift||0):0,0,0);reachError=Math.max(reachError,Math.max(0,distance-l.l1-l.l2));});
 group.updateMatrixWorld(true);mesh.skeleton.update();return reachError;
 }
 pose(0);return {group,mesh,bones,legs,pose,weightError:error};
}
