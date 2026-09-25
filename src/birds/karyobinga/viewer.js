import * as T from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {OrbitControls} from 'three/addons/controls/OrbitControls.js';
import {RoomEnvironment} from 'three/addons/environments/RoomEnvironment.js';
const embedded=new URLSearchParams(location.search).get('embedded')==='1';document.body.classList.toggle('embedded',embedded);
const scene=new T.Scene();scene.background=new T.Color('#e8edf1');
const renderer=new T.WebGLRenderer({antialias:true});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.toneMapping=T.ACESFilmicToneMapping;renderer.toneMappingExposure=.75;renderer.shadowMap.enabled=true;renderer.shadowMap.type=T.PCFSoftShadowMap;document.body.append(renderer.domElement);
const camera=new T.PerspectiveCamera(36,1,.005,20),controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=false;controls.minDistance=.13;controls.maxDistance=8;
const pmrem=new T.PMREMGenerator(renderer),room=new RoomEnvironment();scene.environment=pmrem.fromScene(room).texture;room.dispose();pmrem.dispose();scene.add(new T.HemisphereLight(0xffffff,0xaaa399,.6));
const sun=new T.DirectionalLight(0xffffff,.8);sun.position.set(2,4,3);sun.castShadow=true;sun.shadow.mapSize.set(1024,1024);Object.assign(sun.shadow.camera,{left:-1.3,right:1.3,top:1.3,bottom:-1.3,near:.1,far:8});sun.shadow.normalBias=.0015;sun.shadow.bias=-.0001;scene.add(sun);
const ground=new T.Mesh(new T.PlaneGeometry(200,200),new T.MeshStandardMaterial({color:'#e8edf1',roughness:1}));ground.rotation.x=-Math.PI/2;ground.position.y=-.003;ground.receiveShadow=true;scene.add(ground);
let rig,time=0,paused=matchMedia('(prefers-reduced-motion: reduce)').matches,dirty=true,viewName='front',last=performance.now(),accum=0;
function faceTarget(){return rig?rig.bodyGroup.localToWorld(new T.Vector3(0,.823,.14)):new T.Vector3(0,1.33,.20);}
function view(name){viewName=name;if(name==='face'){const target=faceTarget();controls.target.copy(target);camera.position.copy(target).add(new T.Vector3(0,.01,.40));}else{const span=Math.max(1.8,1.8/camera.aspect);const d=span/(2*Math.tan(T.MathUtils.degToRad(camera.fov/2)));controls.target.set(0,.84,0);camera.position.set(name==='side'?d+.65:name==='front'?.55:0,.92,name==='back'?-d:name==='side'?0:d);}controls.update();dirty=true;}
function syncPause(){const b=document.querySelector('#pause');b.textContent=paused?'再開':'一時停止';b.setAttribute('aria-pressed',String(paused));}
for(const name of ['front','face','side','back'])document.querySelector('#'+name).onclick=()=>view(name);
document.querySelector('#pause').onclick=()=>{paused=!paused;syncPause();dirty=true;};syncPause();
function resize(){const top=innerWidth<650?(embedded?65:160):0;const h=Math.max(200,innerHeight-top);renderer.domElement.style.marginTop=top+'px';renderer.setSize(innerWidth,h);camera.aspect=innerWidth/h;camera.updateProjectionMatrix();view(viewName);}resize();addEventListener('resize',resize);controls.addEventListener('change',()=>dirty=true);
try{
  const url=`${import.meta.env.BASE_URL}assets/karyobinga/karyobinga-floating.glb.gz`;
  const response=await fetch(url);if(!response.ok)throw Error(`Model HTTP ${response.status}`);
  const packed=await response.arrayBuffer();
  // Some hosts transparently decode .gz; detect the magic bytes before inflating.
  const bytes=new Uint8Array(packed);
  const data=bytes[0]===0x1f&&bytes[1]===0x8b
    ?await new Response(new Blob([packed]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer():packed;
  const gltf=await new GLTFLoader().parseAsync(data,'');
  const group=gltf.scene,bodyGroup=group.getObjectByName('KaryobingaIdle');
  const clip=gltf.animations.find(a=>a.name==='FloatingIdle');
  if(!bodyGroup||!clip)throw Error('Floating model structure is missing');
  const mixer=new T.AnimationMixer(group);mixer.clipAction(clip).play();
  const meshes=[];group.traverse(o=>{if(o.isMesh){o.castShadow=true;o.receiveShadow=true;o.frustumCulled=false;meshes.push(o);}});
  rig={group,bodyGroup,meshes,clip,mixer,pose(t){mixer.setTime(t);group.updateMatrixWorld(true);meshes.forEach(m=>m.skeleton?.update());}};
  scene.add(group);rig.pose(0);view(viewName);
  document.querySelector('#status').textContent='空中をゆっくり漂っています';
  window.__karyo={rig,scene,camera,renderer,controls,pose(t){paused=true;syncPause();time=t;rig.pose(t);renderer.render(scene,camera);},pause(v=true){paused=v;syncPause();}};
  const downloadURL=URL.createObjectURL(new Blob([data],{type:'model/gltf-binary'}));
  const link=document.querySelector('#download');link.href=downloadURL;link.hidden=false;
  addEventListener('pagehide',()=>URL.revokeObjectURL(downloadURL),{once:true});
  window.__ready=true;
}catch(e){document.querySelector('#status').textContent='読み込みに失敗しました。再読み込みしてください。';console.error(e);}
renderer.setAnimationLoop(()=>{const now=performance.now(),dt=Math.min((now-last)/1000,.05);last=now;if(document.hidden)return;accum+=dt;if(accum<1/30)return;const elapsed=accum;accum=0;if(rig&&!paused){const before=viewName==='face'?faceTarget():null;time+=elapsed;rig.pose(time);if(before){const delta=faceTarget().sub(before);camera.position.add(delta);controls.target.add(delta);controls.update();}dirty=true;}if(dirty){renderer.render(scene,camera);dirty=false;}});
