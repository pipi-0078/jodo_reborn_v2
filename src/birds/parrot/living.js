import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {GLTFExporter} from 'three/addons/exporters/GLTFExporter.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {rigParrot} from './rig.js';
import {ParrotBehavior} from './behavior.js';
const scene=new T.Scene();scene.background=new T.Color('#e8e4de');
const renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=.8;renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;document.body.append(renderer.domElement);
const camera=new T.PerspectiveCamera(34,1,.01,30),controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=false;controls.target.set(0,.55,0);camera.position.set(1.15,.9,1.8);controls.update();
const pmrem=new T.PMREMGenerator(renderer),room=new RoomEnvironment();scene.environment=pmrem.fromScene(room).texture;room.dispose();pmrem.dispose();
scene.add(new T.HemisphereLight(0xffffff,0xaaa399,.7));const sun=new T.DirectionalLight(0xffffff,1.3);sun.position.set(-2,4,3);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);Object.assign(sun.shadow.camera,{left:-1.5,right:1.5,top:1.5,bottom:-1.5,near:.1,far:10});sun.shadow.normalBias=.002;scene.add(sun);
const branch=new T.Mesh(new T.CylinderGeometry(.024,.028,.8,24),new T.MeshStandardMaterial({color:'#c7ab67',metalness:.45,roughness:.65}));branch.rotation.z=Math.PI/2;branch.position.set(0,.416,.115);branch.castShadow=true;branch.receiveShadow=true;scene.add(branch);
const stand=new T.Mesh(new T.CylinderGeometry(.014,.024,.5,16),branch.material);stand.position.set(-.31,.16,.115);stand.castShadow=true;scene.add(stand);
const ground=new T.Mesh(new T.CircleGeometry(2,64),new T.MeshStandardMaterial({color:'#d9d2c2',roughness:.95}));ground.rotation.x=-Math.PI/2;ground.position.y=-.09;ground.receiveShadow=true;scene.add(ground);
let rig,paused=false,dirty=true,last=performance.now(),accum=0;const brain=new ParrotBehavior();
// Slightly livelier tempo without increasing rendering frequency.
const MOTION_SPEED = 1.5;
const labels={look:'静かに辺りを眺めています',curious:'気になるものを見つけたようです',rest:'止まり木でひと休みしています'};
function step(dt){const pose=brain.update(dt * MOTION_SPEED);rig.pose(brain.time,pose);document.querySelector('#state').textContent=labels[brain.state];dirty=true;}
async function exportModel(){
  const saved=rig.bones.map(b=>b.quaternion.clone());rig.pose(0);
  try{return await new GLTFExporter().parseAsync(rig.group,{binary:true,animations:rig.clips,onlyVisible:true});}
  finally{rig.bones.forEach((b,i)=>b.quaternion.copy(saved[i]));rig.group.updateMatrixWorld(true);rig.mesh.skeleton.update();dirty=true;}
}
try{const gltf=await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}assets/parrot/parrot.glb`);rig=rigParrot(gltf.scene);scene.add(rig.group);step(0);document.querySelector('#download').disabled=false;document.querySelector('#status').textContent='5本の骨・3種類の動作';window.__parrot={rig,brain,step,scene,camera,exportModel,pause(v=true){paused=v;dirty=true;}};window.__ready=true;}catch(e){document.querySelector('#state').textContent='読み込みに失敗しました';console.error(e)}
for(const b of document.querySelectorAll('[data-mode]'))b.onclick=()=>{brain.command(b.dataset.mode);paused=false;document.querySelector('#pause').textContent='一時停止';document.querySelectorAll('[data-mode]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));};
document.querySelector('#pause').onclick=()=>{paused=!paused;document.querySelector('#pause').textContent=paused?'再開':'一時停止';dirty=true;};
function view(v){camera.position.copy(controls.target).add(v);controls.update();dirty=true;}
document.querySelector('#front').onclick=()=>view(new T.Vector3(0,.12,2));document.querySelector('#side').onclick=()=>view(new T.Vector3(2,.12,0));
document.querySelector('#download').onclick=async()=>{const b=document.querySelector('#download');b.disabled=true;try{const data=await exportModel();const url=URL.createObjectURL(new Blob([data],{type:'model/gltf-binary'}));const a=document.createElement('a');a.href=url;a.download='parrot-rigged.glb';a.click();setTimeout(()=>URL.revokeObjectURL(url),10000);}catch(e){document.querySelector('#status').textContent='保存に失敗しました';console.error(e)}finally{b.disabled=false}};
function resize(){const narrow=innerWidth<650,left=narrow?0:285,top=narrow?230:0;const w=Math.max(1,innerWidth-left),h=Math.max(150,innerHeight-top);renderer.domElement.style.marginLeft=left+'px';renderer.domElement.style.marginTop=top+'px';renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();dirty=true;}resize();addEventListener('resize',resize);controls.addEventListener('change',()=>dirty=true);
renderer.setAnimationLoop(()=>{const now=performance.now(),dt=Math.min((now-last)/1000,.05);last=now;if(document.hidden)return;accum+=dt;if(accum<1/30)return;const elapsed=accum;accum=0;if(rig&&!paused)step(elapsed);if(dirty){renderer.render(scene,camera);dirty=false;}});
