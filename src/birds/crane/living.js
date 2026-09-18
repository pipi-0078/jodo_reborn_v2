import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {Water} from 'three/addons/objects/Water.js';
import {rigCrane} from './rig.js';
const scene=new T.Scene();scene.background=new T.Color('#dce6df');scene.fog=new T.Fog('#dce6df',3,8);
const renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.3));renderer.setSize(innerWidth,innerHeight);renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=.85;renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;document.body.append(renderer.domElement);
const camera=new T.PerspectiveCamera(38,innerWidth/innerHeight,.01,20);camera.position.set(1.6,1.15,1.9);const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,.22,0);controls.maxPolarAngle=Math.PI*.48;controls.minDistance=.5;controls.maxDistance=6;controls.update();
const pmrem=new T.PMREMGenerator(renderer),room=new RoomEnvironment();scene.environment=pmrem.fromScene(room).texture;room.dispose();pmrem.dispose();scene.add(new T.HemisphereLight('#fff8e9','#7b9a93',1.5));const sun=new T.DirectionalLight('#fff0cf',2.0);sun.position.set(-1.8,3,2);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);Object.assign(sun.shadow.camera,{left:-2,right:2,top:2,bottom:-2,near:.1,far:8});sun.shadow.normalBias=.002;scene.add(sun);
const bed=new T.Mesh(new T.CircleGeometry(4,80),new T.MeshStandardMaterial({color:'#c4b68a',roughness:.95}));bed.rotation.x=-Math.PI/2;bed.position.y=-.002;bed.receiveShadow=true;scene.add(bed);
const data=new Uint8Array(64*64*4);for(let y=0;y<64;y++)for(let x=0;x<64;x++){const i=(y*64+x)*4;data[i]=128+8*Math.sin(x*.5+y*.7);data[i+1]=128+8*Math.cos(y*.6-x*.4);data[i+2]=255;data[i+3]=255;}const normal=new T.DataTexture(data,64,64);normal.wrapS=normal.wrapT=T.RepeatWrapping;normal.needsUpdate=true;
const level=.027,water=new Water(new T.CircleGeometry(2.5,80),{textureWidth:512,textureHeight:512,waterNormals:normal,alpha:.52,sunDirection:sun.position.clone().normalize(),sunColor:0xfff2d8,waterColor:0x479e9a,distortionScale:.025});water.rotation.x=-Math.PI/2;water.position.y=level;water.material.transparent=true;water.material.depthWrite=false;water.renderOrder=2;scene.add(water);
const rings=[];let cursor=0;const ringGeo=new T.RingGeometry(.94,1,64);ringGeo.rotateX(-Math.PI/2);
for(let i=0;i<36;i++){const m=new T.Mesh(ringGeo,new T.MeshBasicMaterial({color:'#f5ffec',transparent:true,opacity:0,depthWrite:false,side:T.DoubleSide}));m.renderOrder=3;m.visible=false;scene.add(m);rings.push({m,age:9,delay:0});}
let events=0;
function ripple(p){events++;for(let j=0;j<3;j++){const r=rings[cursor++%rings.length];r.age=-j*.17;r.m.position.set(p.x,level+.001+j*.0001,p.z);r.m.visible=false;}}
// A few shoreline stones give scale without obscuring the feet.
for(let i=0;i<12;i++){const a=i*2.399,rad=1.5+(i%3)*.13,m=new T.Mesh(new T.SphereGeometry(1,12,8),new T.MeshStandardMaterial({color:i%2?'#b4b6a5':'#ccc7b0',roughness:1}));m.position.set(Math.cos(a)*rad,.006,Math.sin(a)*rad);m.scale.set(.09,.035,.06);m.castShadow=true;scene.add(m);}
const rig=rigCrane((await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}assets/crane/crane.glb`)).scene);scene.add(rig.group);
let time=0,walkTime=0,paused=false,close=false,dirty=true,velocity=0,sway=0,active=0,stepAge=0,swing=null,maxReach=0;const feet=rig.legs.map(l=>l.foot.clone()),worldFeet=feet.map(p=>p.clone());
const duration=.88,hold=.20,speed=.028;rig.group.position.set(-.45,-.004,0);worldFeet.forEach(p=>p.x-=.45);let heading=0;
function step(dt){time+=dt;const walking=time%18<12;
 // Ease into and out of a walk; keep moving feet planted in world space.
 const cycle=time%18,drive=walking?T.MathUtils.smoothstep(cycle,0,1.2)*(1-T.MathUtils.smoothstep(cycle,10.8,12)):0;
 velocity=T.MathUtils.lerp(velocity,speed*drive,1-Math.exp(-dt*5));walkTime+=velocity*dt;heading=walkTime/.45;
 const u=swing?Math.min(1,stepAge/duration):0,lift=swing?Math.sin(Math.PI*u)**2:0;
 const support=swing?rig.legs[1-active].s:0;sway=T.MathUtils.lerp(sway,support*.006*lift,1-Math.exp(-dt*9));
 rig.group.rotation.set(0,heading,-sway*.8);rig.group.position.set(-.45*Math.cos(heading)+Math.cos(heading)*sway,-.006+.0015*lift,.45*Math.sin(heading)-Math.sin(heading)*sway);

 rig.group.updateMatrixWorld(true);
 if(!swing&&walking){const target=rig.legs[active].foot.clone();target.z+=.034;rig.group.localToWorld(target);target.y=.015;swing={from:worldFeet[active].clone(),to:target};stepAge=0;}
 if(swing){stepAge+=dt;const u=Math.min(1,stepAge/duration),q=T.MathUtils.clamp((u-.10)/.78,0,1),ease=q*q*q*(q*(q*6-15)+10);worldFeet[active].lerpVectors(swing.from,swing.to,ease);worldFeet[active].y=.015+.033*Math.sin(Math.PI*u)**2;
 if(stepAge>=duration&&stepAge-dt<duration)ripple(swing.to);
 if(stepAge>=duration+hold){worldFeet[active].copy(swing.to);swing=null;active=1-active;}}
 for(let i=0;i<2;i++)feet[i].copy(rig.group.worldToLocal(worldFeet[i].clone()));maxReach=Math.max(maxReach,rig.pose(time,feet,1,{lift,phase:u,active,roll:-sway*.8}));
 water.material.uniforms.time.value=time*.15;
 for(const r of rings){r.age+=dt;r.m.visible=r.age>=0&&r.age<2.2;if(r.m.visible){const radius=.012+r.age*.10;r.m.scale.setScalar(radius);r.m.material.opacity=.4*(1-r.age/2.2);}}
 if(close){const target=rig.group.position.clone().add(new T.Vector3(0,.27,0)),delta=target.clone().sub(controls.target);camera.position.add(delta);controls.target.copy(target);controls.update();}
 document.querySelector('#state').textContent=walking?'浅瀬をゆっくり歩いています':'立ち止まって辺りを眺めています';
}
step(0);document.querySelector('#status').textContent='浅瀬の歩行試作';
window.__crane={rig,scene,camera,controls,water,rings,step,worldFeet,get stats(){return {time,events,maxReach,weightError:rig.weightError}},pause(v=true){paused=v;dirty=true;}};window.__ready=true;
document.querySelector('#pause').onclick=()=>{paused=!paused;dirty=true;document.querySelector('#pause').textContent=paused?'再開':'一時停止';};
document.querySelector('#close').onclick=()=>{close=true;controls.target.copy(rig.group.position).add(new T.Vector3(0,.26,0));camera.position.copy(controls.target).add(new T.Vector3(.85,.27,.9));controls.update();};document.querySelector('#wide').onclick=()=>{close=false;controls.target.set(0,.2,.1);camera.position.set(1.6,1.15,1.9);controls.update();};
controls.addEventListener('change',()=>dirty=true);
let last=performance.now(),accum=0;renderer.setAnimationLoop(()=>{const now=performance.now(),dt=Math.min((now-last)/1000,.05);last=now;if(document.hidden)return;accum+=dt;if(accum<1/30)return;if(!paused){step(accum);dirty=true;}accum=0;if(dirty){renderer.render(scene,camera);dirty=false;}});
addEventListener('resize',()=>{camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();renderer.setSize(innerWidth,innerHeight);dirty=true;});
