const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright-core');

(async () => {
  const out = process.env.OUTPUT_DIR || '/tmp/gumyocho-world-verification';
  const base = process.env.GUMYOCHO_BASE || 'http://127.0.0.1:8952/jodo_reborn_v2/';
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const errors = [], failures = [];
  const page = await browser.newPage({ viewport: { width: 1100, height: 760 } });
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error' && !m.text().includes('favicon') && !m.location().url.includes('favicon')) errors.push({message:m.text(),url:m.location().url}); });
  page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon')) failures.push({ url: r.url(), status: r.status() }); });
  try {
    await page.goto(base + 'index.html?view=gumyocho');
    await page.waitForFunction(() => window.__worldGumyocho && window.__scene && window.__camera, {}, { timeout: 180000 });
    console.log('World loaded');
    const initialTime = await page.evaluate(() => __worldGumyocho.mixer.time);
    await page.waitForTimeout(1500);
    const playing = await page.evaluate(before => __worldGumyocho.mixer.time > before, initialTime);
    const geometry = await page.evaluate(() => {
      const a = __worldGumyocho;
      a.update = () => {};
      a.seek(0);
      let mesh;
      a.bird.traverse(n => { if (n.isSkinnedMesh) mesh = n; });
      if (!mesh) throw Error('No animated bird mesh');
      function point(index) {
        const v = mesh.position.clone().fromBufferAttribute(mesh.geometry.attributes.position, index);
        mesh.skeleton.update();
        mesh.applyBoneTransform(index, v);
        return mesh.localToWorld(v);
      }
      const footIndices = [32198, 55139];
      const feet = footIndices.map(point);
      let footMotion = 0;
      for (let t = 0; t < 36; t += .25) {
        a.seek(t);
        footIndices.forEach((index, i) => { footMotion = Math.max(footMotion, point(index).distanceTo(feet[i])); });
      }
      const drinks = [[5,3822],[21,33007]].map(([t,index]) => {
        a.seek(t);
        const p = point(index);
        return { time:t, position:p.toArray(), waterClearance:p.y-a.placement.waterY, radiusFromLotus:Math.hypot(p.x-a.perch.position.x,p.z-a.perch.position.z) };
      });
      a.seek(0);
      const spanRest = point(24287).distanceTo(point(58164));
      a.seek(33.5);
      const spanSpread = point(24287).distanceTo(point(58164));
      const pod = a.lotus.getObjectByName('Lotus_pod');
      // Ray/triangle intersection in pod coordinates, independent of the scene renderer.
      function podGap(worldPoint) {
        const origin = pod.worldToLocal(worldPoint.clone().add(mesh.position.clone().set(0,1,0)));
        const down = pod.worldToLocal(worldPoint.clone().add(mesh.position.clone().set(0,-1,0))).sub(origin).normalize();
        const positions=pod.geometry.attributes.position, indices=pod.geometry.index;
        let closest=Infinity;
        for(let i=0;i<indices.count;i+=3){
          const v0=origin.clone().fromBufferAttribute(positions,indices.getX(i));
          const v1=origin.clone().fromBufferAttribute(positions,indices.getX(i+1));
          const v2=origin.clone().fromBufferAttribute(positions,indices.getX(i+2));
          const e1=v1.sub(v0),e2=v2.sub(v0),h=down.clone().cross(e2),det=e1.dot(h);
          if(Math.abs(det)<1e-9) continue;
          const s=origin.clone().sub(v0),u=s.dot(h)/det;
          if(u<0||u>1)continue;
          const q=s.clone().cross(e1),v=down.dot(q)/det;
          if(v<0||u+v>1)continue;
          const t=e2.dot(q)/det;
          if(t>=0)closest=Math.min(closest,t);
        }
        if(!Number.isFinite(closest)) return null;
        const hit=pod.localToWorld(origin.addScaledVector(down,closest));
        return worldPoint.y-hit.y;
      }
      const footGaps = feet.map(podGap);
      const petal = a.lotus.getObjectByName('Lotus_petal');
      const lotusPosition = a.lotus.getWorldPosition(mesh.position.clone());
      const lotusScale = a.lotus.getWorldScale(mesh.position.clone());
      const originalPosition=a.placement.originalLotusPosition;
      const originError=Math.hypot(...lotusPosition.toArray().map((n,i)=>n-originalPosition[i]));
      const whiteFlowerCounts=[];
      __scene.traverse(n=>{if(n.isInstancedMesh&&n.material?.name==='petal')whiteFlowerCounts.push({count:n.count,color:n.material.color.getHexString()});});
      return { placement:a.placement, footMotion, footGaps, drinks, spanRest, spanSpread, originError, lotusPosition:lotusPosition.toArray(),lotusScale:lotusScale.toArray(), petalColor:petal.material.color.getHexString(),whiteFlowerCounts,camera:__camera.position.toArray(),clip:a.clip.name,duration:a.clip.duration };
    });
    console.log('Geometry checked', JSON.stringify(geometry));
    await page.evaluate(() => { document.querySelector('#overlay').style.display='none'; __worldGumyocho.seek(0); });
    await page.waitForTimeout(700);
    await page.screenshot({path:path.join(out,'world-rest.png'),timeout:180000});
    for (const [name,time] of [['drink',5],['spread',33.5]]) {
      await page.evaluate(t=>__worldGumyocho.seek(t),time);
      await page.waitForTimeout(400);
      await page.screenshot({path:path.join(out,`world-${name}.png`),timeout:180000});
    }
    console.log('World screenshots saved');
    await page.goto(base+'gallery.html?asset=gumyocho');
    await page.waitForFunction(()=>window.__model&&__model.getObjectByName('Bird_seated_on_receptacle'),{}, {timeout:120000});
    const sample=()=>page.evaluate(()=>{
      let mesh; __model.traverse(n=>{if(n.isSkinnedMesh)mesh=n;});
      return mesh.skeleton.bones.map(b=>b.quaternion.toArray()).flat();
    });
    const before=await sample();
    await page.waitForTimeout(2000);
    const after=await sample();
    const galleryMoving=after.some((n,i)=>Math.abs(n-before[i])>1e-5);
    await page.screenshot({path:path.join(out,'gallery.png'),timeout:180000});
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(300);
    const galleryFrame=await page.evaluate(()=>{
      const canvas=document.querySelector('canvas').getBoundingClientRect();
      const list=document.querySelector('#list').getBoundingClientRect();
      const caption=document.querySelector('#caption').getBoundingClientRect();
      let mesh;__model.traverse(n=>{if(n.isSkinnedMesh)mesh=n;});
      mesh.skeleton.update();
      let maxNdc=0;
      for(let i=0;i<mesh.geometry.attributes.position.count;i++){
        const p=mesh.position.clone().fromBufferAttribute(mesh.geometry.attributes.position,i);
        mesh.applyBoneTransform(i,p);mesh.localToWorld(p);p.project(__camera);
        maxNdc=Math.max(maxNdc,Math.abs(p.x),Math.abs(p.y));
      }
      return {top:canvas.top,bottom:canvas.bottom,listBottom:list.bottom,captionTop:caption.top,maxNdc};
    });
    await page.screenshot({path:path.join(out,'gallery-mobile.png'),timeout:180000});
    const checks={playing,galleryMoving,footFixed:geometry.footMotion<1e-6,feetOnPod:geometry.footGaps.every(n=>n!==null&&n>=-1e-5&&n<.006),
      waterContact:geometry.drinks.every(d=>d.waterClearance<0&&d.waterClearance>-.035&&d.radiusFromLotus<2.5),spread:geometry.spanSpread>geometry.spanRest*1.3,
      originalLotus:geometry.originError<1e-9,white:geometry.petalColor==='f7faff',singleWhiteReplaced:geometry.whiteFlowerCounts.filter(p=>p.color==='f7faff').every(p=>p.count===12),
      galleryFrame:galleryFrame.top>=galleryFrame.listBottom-1&&galleryFrame.bottom<=galleryFrame.captionTop+1&&galleryFrame.maxNdc<1,
      duration:geometry.duration===36,errors:errors.length===0&&failures.length===0};
    const passed=Object.values(checks).every(Boolean);
    fs.writeFileSync(path.join(out,'report.json'),JSON.stringify({passed,checks,geometry,galleryFrame,errors,failures},null,2));
    console.log(JSON.stringify({passed,checks,errors,failures}));
    if(!passed)process.exitCode=1;
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
