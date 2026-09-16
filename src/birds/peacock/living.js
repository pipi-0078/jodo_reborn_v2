import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
import {createTrain} from './train.js';
import {rigBody} from './rig.js';
import {PeacockBehavior} from './behavior.js';

const embedded=new URLSearchParams(location.search).has('embedded');
if(embedded)document.body.classList.add('embedded');
const scene=new T.Scene();scene.background=new T.Color('#e8e3d7');scene.fog=new T.Fog('#e8e3d7',10,25);
const renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.setSize(innerWidth,innerHeight);
renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=.75;renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;document.body.append(renderer.domElement);
const camera=new T.PerspectiveCamera(36,innerWidth/innerHeight,.01,40);
function resize(){
  const mobile=innerWidth<600,left=mobile?0:(embedded?260:330),top=mobile?(embedded?180:360):0;
  const w=Math.max(1,innerWidth-left),h=Math.max(180,innerHeight-top);
  renderer.domElement.style.marginLeft=`${left}px`;renderer.domElement.style.marginTop=`${top}px`;
  camera.aspect=w/h;camera.updateProjectionMatrix();renderer.setSize(w,h);
}
resize();
camera.position.set(-3.6,2.1,-4.5);
const controls=new OrbitControls(camera,renderer.domElement);controls.target.set(0,.55,0);controls.enableDamping=true;controls.maxPolarAngle=Math.PI*.48;controls.minDistance=1.8;controls.maxDistance=12;controls.update();
const pmrem=new T.PMREMGenerator(renderer),room=new RoomEnvironment();scene.environment=pmrem.fromScene(room).texture;room.dispose();pmrem.dispose();
scene.add(new T.HemisphereLight(0xffffff,0xab956c,.8));
const sun=new T.DirectionalLight(0xffffff,1);sun.position.set(-3,6,-4);sun.castShadow=true;sun.shadow.mapSize.set(2048,2048);sun.shadow.camera.left=-4;sun.shadow.camera.right=4;sun.shadow.camera.top=4;sun.shadow.camera.bottom=-4;sun.shadow.normalBias=.005;scene.add(sun);
const ground=new T.Mesh(new T.CircleGeometry(3.4,128),new T.MeshStandardMaterial({color:'#d7c49b',roughness:.95}));ground.rotation.x=-Math.PI/2;ground.position.y=-.003;ground.receiveShadow=true;scene.add(ground);
const rim=new T.Mesh(new T.RingGeometry(3.38,3.43,128),new T.MeshStandardMaterial({color:'#b7a17b',roughness:.9}));rim.rotation.x=-Math.PI/2;rim.position.y=-.002;scene.add(rim);
const bird=new T.Group();scene.add(bird);const brain=new PeacockBehavior();
let rig,train,paused=false,ready=false,lastState='',lastPosition=new T.Vector3();
const labels={look:['周囲を眺めています','少し立ち止まり、辺りの様子を見ています。'],walk:['庭を歩いています','行き先を決めて、ゆっくり向かっています。'],rest:['ひと休みしています','次に動き出すまで、静かに過ごします。'],display:['飾り羽を広げています','立ち止まって、羽をゆっくり開閉します。']};
function update(dt){
  const motion=brain.update(dt);
  bird.position.set(brain.position.x,0,brain.position.z);bird.rotation.y=brain.heading;
  rig.update(dt,motion);train.update(brain.openness,brain.time);
  if(document.querySelector('#follow').checked){const delta=bird.position.clone().sub(lastPosition);camera.position.add(delta);controls.target.add(delta);}
  lastPosition.copy(bird.position);
  if(lastState!==brain.state){lastState=brain.state;document.querySelector('#state').textContent=labels[brain.state][0];document.querySelector('#reason').textContent=labels[brain.state][1];}
  bird.updateMatrixWorld(true);
}
try{
  const gltf=await new GLTFLoader().loadAsync(`${import.meta.env.BASE_URL}assets/peacock/peacock-body.glb`);
  rig=rigBody(gltf.scene);bird.add(rig.group);
  train=await createTrain(rig.group);bird.add(train.root);
  // Train is attached to the same actor, so navigation cannot leave it behind.
  ready=true;document.querySelector('#loading').remove();document.querySelectorAll('[data-mode],#pause').forEach(b=>b.disabled=false);
  update(0);
  window.__living={brain,rig,train,bird,scene,camera,controls,step:update,pause(value=true){paused=value;},ready:true};
  window.__ready=true;
}catch(e){document.querySelector('#loading').textContent='読み込みに失敗しました。再読み込みしてください。';console.error(e);}
for(const button of document.querySelectorAll('[data-mode]'))button.onclick=()=>{
  brain.command(button.dataset.mode);paused=false;document.querySelector('#pause').textContent='一時停止';
  document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));
};
document.querySelector('#pause').onclick=()=>{paused=!paused;document.querySelector('#pause').textContent=paused?'再開':'一時停止';};
function view(offset){controls.target.copy(bird.position).add(new T.Vector3(0,.65,0));camera.position.copy(controls.target).add(offset.applyAxisAngle(new T.Vector3(0,1,0),bird.rotation.y));controls.update();}
document.querySelector('#front').onclick=()=>view(new T.Vector3(-4.8,.4,0));
document.querySelector('#side').onclick=()=>view(new T.Vector3(0,.5,-4.8));
document.querySelector('#overview').onclick=()=>{document.querySelector('#follow').checked=false;controls.target.set(0,0,0);camera.position.set(-5,5,-6);controls.update();};
let last=performance.now();renderer.setAnimationLoop(()=>{const now=performance.now(),dt=Math.min((now-last)/1000,.04);last=now;if(document.hidden)return;if(ready&&!paused&&!document.hidden)update(dt);controls.update();renderer.render(scene,camera);});
addEventListener('resize',resize);
