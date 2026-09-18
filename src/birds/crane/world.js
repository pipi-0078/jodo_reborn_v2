import * as T from 'three/webgpu';
import {positionLocal,positionWorld,vec3,lights} from 'three/tsl';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {rigCrane} from './rig.js';
import {pondWave,craneWaterFocus} from '../../world/waterSurface';
import {CRANE_RADIUS,CRANE_ANGLE,CRANE_SCALE,WATER_LEVEL} from '../../world/layout';
export async function createWorldCrane(scene,sunDirection){
 const rig=rigCrane((await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}assets/crane/crane.glb`)).scene),bird=rig.group;bird.name='PureLandCrane';bird.scale.setScalar(CRANE_SCALE);scene.add(bird);
 rig.mesh.material.emissive.set(0xffffff);rig.mesh.material.emissiveMap=rig.mesh.material.map;rig.mesh.material.emissiveIntensity=.10;
 const bank=scene.getObjectByName('ShallowBank');scene.updateMatrixWorld(true);const ray=new T.Raycaster();
 function bed(x,z){ray.set(new T.Vector3(x,2,z),new T.Vector3(0,-1,0));const hit=ray.intersectObject(bank,false)[0];if(!hit)throw Error('Crane outside shallow bank');return hit.point.y+.003;}
 let time=0,distance=0,velocity=0,sway=0,active=0,stepAge=0,swing=null,cursor=0,events=0,maxReach=0;
 const duration=.88,hold=.20,speed=.028*CRANE_SCALE;
 const feet=rig.legs.map(l=>l.foot.clone()),worldFeet=[];
 const ringGeo=new T.RingGeometry(.94,1,48).rotateX(-Math.PI/2),rings=[];
 for(let i=0;i<36;i++){const mat=new T.MeshBasicNodeMaterial({color:i%3===1?0xeaffef:0x245551,transparent:true,opacity:0,depthWrite:false,side:T.DoubleSide});mat.positionNode=positionLocal.add(vec3(0,pondWave(positionWorld),0));const m=new T.Mesh(ringGeo,mat);m.visible=false;m.renderOrder=5;scene.add(m);rings.push({m,age:9});}
 function ripple(p){events++;for(let j=0;j<3;j++){const r=rings[cursor++%rings.length];r.age=-j*.17;r.m.position.set(p.x,WATER_LEVEL+.006+j*.0001,p.z);}}
 function place(lift=0){const angle=CRANE_ANGLE+distance/CRANE_RADIUS,r=CRANE_RADIUS+sway;bird.rotation.set(0,-angle,sway*.35);const x=r*Math.cos(angle),z=r*Math.sin(angle);bird.position.set(x,bed(x,z)-.085+.003*lift,z);bird.updateMatrixWorld(true);}
 place();rig.legs.forEach(l=>{const p=l.foot.clone();p.x=l.s*.060;bird.localToWorld(p);p.y=bed(p.x,p.z)+.015*CRANE_SCALE;worldFeet.push(p);});
 const light=new T.DirectionalLight(0xffffff,1);light.layers.set(4);light.castShadow=true;light.shadow.camera.layers.set(4);light.shadow.mapSize.set(1024,1024);Object.assign(light.shadow.camera,{left:-2,right:2,top:2,bottom:-2,near:.1,far:90});light.shadow.camera.updateProjectionMatrix();light.shadow.normalBias=.004;light.shadow.autoUpdate=false;scene.add(light,light.target);rig.mesh.layers.enable(4);
 const sm=new T.ShadowNodeMaterial({color:0x233329,opacity:.35,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-1});sm.lightsNode=lights([light]);const receiver=new T.Mesh(bank.geometry,sm);receiver.position.copy(bank.position);receiver.receiveShadow=true;scene.add(receiver);let shadowTime=1;
 function update(dt){time+=dt;const cycle=time%18,walking=cycle<12,drive=walking?T.MathUtils.smoothstep(cycle,0,1.2)*(1-T.MathUtils.smoothstep(cycle,10.8,12)):0;velocity=T.MathUtils.lerp(velocity,speed*drive,1-Math.exp(-dt*5));distance+=velocity*dt;
 const u=swing?Math.min(1,stepAge/duration):0,lift=swing?Math.sin(Math.PI*u)**2:0,support=swing?rig.legs[1-active].s:0;sway=T.MathUtils.lerp(sway,support*.006*CRANE_SCALE*lift,1-Math.exp(-dt*9));place(lift);craneWaterFocus.value.copy(bird.position);
 if(!swing&&walking){const p=rig.legs[active].foot.clone();p.x=rig.legs[active].s*.060;p.z+=.034;bird.localToWorld(p);p.y=bed(p.x,p.z)+.015*CRANE_SCALE;swing={from:worldFeet[active].clone(),to:p};stepAge=0;}
 if(swing){stepAge+=dt;const t=Math.min(1,stepAge/duration),q=T.MathUtils.clamp((t-.10)/.78,0,1),ease=q*q*q*(q*(q*6-15)+10);worldFeet[active].lerpVectors(swing.from,swing.to,ease);worldFeet[active].y+=.033*CRANE_SCALE*Math.sin(Math.PI*t)**2;if(stepAge>=duration&&stepAge-dt<duration)ripple(swing.to);if(stepAge>=duration+hold){worldFeet[active].copy(swing.to);swing=null;active=1-active;}}
 for(let i=0;i<2;i++)feet[i].copy(bird.worldToLocal(worldFeet[i].clone()));maxReach=Math.max(maxReach,rig.pose(time,feet,1,{lift,phase:u,active,roll:sway*.35}));
 for(const r of rings){r.age+=dt;r.m.visible=r.age>=0&&r.age<2.2;if(r.m.visible){r.m.scale.setScalar((.012+r.age*.10)*CRANE_SCALE);r.m.material.opacity=.65*(1-r.age/2.2);}}
 shadowTime+=dt;if(shadowTime>.1){shadowTime%=.1;light.target.position.copy(bird.position);light.position.copy(bird.position).addScaledVector(sunDirection,30);light.shadow.needsUpdate=true;}
 }
 update(0);const actor={bird,rig,update,worldFeet,rings,bed,get stats(){return {time,events,maxReach,distance}}};window.__worldCrane=actor;return actor;
}
