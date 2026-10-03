const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright-core');

const base = process.env.KARYOBINGA_BASE || 'http://127.0.0.1:8941/jodo_reborn_v2/';
const out = process.env.OUTPUT_DIR || '/tmp/karyobinga-pair-check';
fs.mkdirSync(out, { recursive:true });
(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  const page = await browser.newPage({viewport:{width:1200,height:820}});
  const errors = [], failures = [], report = {gallery:[]};
  page.on('pageerror',e=>errors.push(e.message));
  page.on('response',r=>{if(r.status()>=400&&!r.url().includes('favicon'))failures.push([r.url(),r.status()]);});
  try {
    for (const [variant,id,closed] of [['biwa','karyobinga-biwa',2.61],['flute','karyobinga',2.7]]) {
      await page.setViewportSize({width:1200,height:820});
      await page.goto(base+'gallery.html?asset='+id);
      const iframe = await page.waitForSelector('#asset-preview');
      const frame = await iframe.contentFrame();
      await frame.waitForFunction(()=>window.__ready,{}, {timeout:120000});
      console.log('Loaded gallery',variant);
      const initial = await frame.evaluate(()=>__karyo.rig.mixer.time);
      await page.waitForTimeout(700);
      const playing = await frame.evaluate(t=>__karyo.rig.mixer.time>t,initial);
      const result = await frame.evaluate(async ({variant,closed})=>{
        const k=__karyo; k.pose(0);
        const body0=k.rig.bodyGroup.getWorldPosition(k.camera.position.clone()).toArray();
        const head=k.rig.group.getObjectByName('BiwaHead'),head0=head?.quaternion.clone();
        const mesh=k.rig.meshes.find(m=>Object.keys(m.morphTargetDictionary||{}).some(n=>/blink/i.test(n)));
        if(!mesh)throw Error('Blink mesh missing');
        const index=Object.entries(mesh.morphTargetDictionary).find(([n])=>/blink/i.test(n))[1];
        const open=mesh.morphTargetInfluences[index];k.pose(closed);const shut=mesh.morphTargetInfluences[index];k.pose(3);const reopened=mesh.morphTargetInfluences[index];
        k.pose(1.8);const headRotation=head?head.quaternion.angleTo(head0):null;const body1=k.rig.bodyGroup.getWorldPosition(k.camera.position.clone()).toArray();k.pose(0);
        const data=await fetch(document.querySelector('#download').href).then(r=>r.arrayBuffer());
        const sha256=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data)),b=>b.toString(16).padStart(2,'0')).join('');
        return {variant,headRotation,clip:k.rig.clip.name,duration:k.rig.clip.duration,meshes:k.rig.meshes.length,triangles:k.rig.meshes.reduce((n,m)=>n+m.geometry.index.count/3,0),open,shut,reopened,body0,body1,sha256,shadow:k.renderer.shadowMap.enabled&&k.rig.meshes.every(m=>m.castShadow&&m.receiveShadow)};
      },{variant,closed});
      const manifest = await page.request.get(base+'assets/'+(variant==='biwa'?'karyobinga-biwa/manifest.json':'karyobinga/manifest.json')).then(r=>r.json());
      assert.equal(result.sha256,manifest.sha256);assert.equal(result.triangles,manifest.triangles);
      assert(playing);if(variant==='biwa')assert(result.headRotation>.025,'Head must move relative to the body');assert.equal(result.open,0);assert(result.shut>.99);assert.equal(result.reopened,0);assert(result.shadow);assert(result.body0.some((v,i)=>Math.abs(v-result.body1[i])>.01));
      await page.screenshot({path:path.join(out,variant+'-gallery.png')});
      for (const view of ['face','hairback']) {
        await frame.evaluate(view=>{__karyo.view(view);__karyo.pose(0);},view);
        await page.screenshot({path:path.join(out,variant+'-'+view+'.png')});
      }
      await frame.evaluate(t=>{__karyo.view('face');__karyo.pose(t);},closed);
      await page.screenshot({path:path.join(out,variant+'-blink.png')});
      await page.setViewportSize({width:390,height:844});
      await frame.waitForFunction(()=>innerWidth===390&&Math.abs(__karyo.renderer.domElement.getBoundingClientRect().width-390)<1&&__karyo.renderer.domElement.getBoundingClientRect().top>=65);
      await frame.evaluate(()=>{__karyo.view('front');__karyo.pose(0);});
      const framing = await frame.evaluate(()=>{
        const k=__karyo;let maxX=0,maxY=0;
        for(const t of [0,1.8,5.4,10.8,16.2,21.6]){
          k.pose(t);
          for(const m of k.rig.meshes)for(let i=0;i<m.geometry.attributes.position.count;i+=29){
            const v=k.camera.position.clone();m.getVertexPosition(i,v);m.localToWorld(v);v.project(k.camera);
            maxX=Math.max(maxX,Math.abs(v.x));maxY=Math.max(maxY,Math.abs(v.y));
          }
        }k.pose(0);
        const canvas=k.renderer.domElement.getBoundingClientRect(),nav=document.querySelector('header').getBoundingClientRect();
        return {maxX,maxY,canvasTop:canvas.top,navBottom:nav.bottom};
      });
      await page.screenshot({path:path.join(out,variant+'-mobile.png')});
      assert(framing.maxX<1&&framing.maxY<1,'Mobile clips the model');
      assert(framing.canvasTop>=framing.navBottom,'Mobile controls overlap canvas');
      report.gallery.push({...result,playing,framing});
      console.log(JSON.stringify(report.gallery.at(-1)));
    }
    await page.setViewportSize({width:1280,height:850});
    await page.goto(base+'?view=karyobinga');
    await page.waitForFunction(()=>window.__worldKaryobinga&&window.__worldKaryobingaBiwa&&window.__scene&&window.__camera,{}, {timeout:180000});
    console.log('World loaded');
    await page.evaluate(()=>document.querySelector('#overlay').style.display='none');
    const before = await page.evaluate(()=>[__worldKaryobinga.mixer.time,__worldKaryobingaBiwa.mixer.time]);
    await page.waitForTimeout(1500);
    report.world = await page.evaluate(before=>{
      const playing=__worldKaryobinga.mixer.time>before[0]&&__worldKaryobingaBiwa.mixer.time>before[1];
      const actors=[__worldKaryobingaBiwa,__worldKaryobinga];
      const data=actors.map(a=>{
        a.update=()=>{};a.seek(0);
        const meshes=[];a.bird.traverse(m=>{if(m.isMesh)meshes.push(m);});
        meshes.forEach(m=>m.skeleton?.update());
        const bounds={min:[Infinity,Infinity,Infinity],max:[-Infinity,-Infinity,-Infinity]};
        for(const m of meshes)for(let i=0;i<m.geometry.attributes.position.count;i+=17){
          const v=__camera.position.clone();m.getVertexPosition(i,v);m.localToWorld(v);
          v.toArray().forEach((n,k)=>{bounds.min[k]=Math.min(bounds.min[k],n);bounds.max[k]=Math.max(bounds.max[k],n);});
        }
        const screen=a.bird.position.clone().setY(9).project(__camera).toArray();
        return {variant:a.variant,position:a.bird.position.toArray(),screen,bounds,meshes:meshes.length,shadow:meshes.every(m=>m.castShadow&&m.receiveShadow),clip:a.clip.name};
      });
      return {playing,actors:data,camera:__camera.position.toArray(),otherBirds:{shari:!!__worldShari,gumyocho:!!__worldGumyocho},before};
    },before);
    assert(report.world.actors[0].screen[0]<0&&report.world.actors[1].screen[0]>0,'Incorrect left/right');
    assert(report.world.playing);
    assert(report.world.actors.every(a=>a.shadow&&a.meshes===9));
    await page.waitForTimeout(700);
    await page.screenshot({path:path.join(out,'world-pair.png'),timeout:120000});
    console.log(JSON.stringify(report.world));
    assert.equal(errors.length,0);assert.equal(failures.length,0);
    report.passed=true;
  } finally {
    report.errors=errors;report.failures=failures;
    fs.writeFileSync(path.join(out,'report.json'),JSON.stringify(report,null,2)+'\n');
    await browser.close();
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
