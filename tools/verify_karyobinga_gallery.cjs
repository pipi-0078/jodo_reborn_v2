const fs=require('fs'),path=require('path');const {chromium}=require('playwright-core');
(async()=>{const out=process.env.OUTPUT_DIR||'/tmp/karyobinga-gallery-verification';fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({channel:'chrome',headless:true});try{
const page=await browser.newPage({viewport:{width:1280,height:1000}}),errors=[],failures=[];
page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!m.text().includes('favicon')&&!m.location().url?.includes('favicon'))errors.push(m.text())});page.on('response',r=>{if(r.status()>=400&&!r.url().includes('favicon'))failures.push({url:r.url(),status:r.status()});});
const base=process.env.GALLERY_BASE||'http://127.0.0.1:8941/jodo_reborn_v2/';
await page.goto(base+'gallery.html?asset=karyobinga');const el=await page.waitForSelector('#asset-preview');let frame=await el.contentFrame();await frame.waitForFunction(()=>window.__ready,{},{timeout:60000});
const state=await frame.evaluate(()=>{__karyo.pose(2.7);const r=__karyo.rig,meshes=r.meshes;return {clip:r.clip.name,tracks:r.clip.tracks.length,meshes:meshes.length,hover:r.group.getObjectByName('HoverMotion').position.toArray(),blink:meshes.filter(m=>m.morphTargetDictionary?.Blink!==undefined).map(m=>m.morphTargetInfluences[m.morphTargetDictionary.Blink]),hand:meshes.find(m=>m.morphTargetDictionary?.HandsLift!==undefined)?.morphTargetInfluences[2],download:document.querySelector('#download').href};});
if(state.clip!=='FloatingIdle'||state.meshes!==6||state.blink.some(v=>v<.99)||!state.download.startsWith('blob:'))throw Error('Invalid animation '+JSON.stringify(state));
await page.screenshot({path:path.join(out,'gallery.png')});await frame.click('#side');await frame.evaluate(()=>__karyo.pose(1.8));await page.screenshot({path:path.join(out,'side.png')});
await frame.click('#face');await frame.evaluate(()=>__karyo.pose(0));await page.screenshot({path:path.join(out,'face.png')});
// Verify that the downloadable GLB is byte-identical to the approved source.
const download=await frame.evaluate(async()=>{const b=await(await fetch(document.querySelector('#download').href)).arrayBuffer();const hash=await crypto.subtle.digest('SHA-256',b);return {bytes:b.byteLength,sha256:Array.from(new Uint8Array(hash),v=>v.toString(16).padStart(2,'0')).join('')};});
const manifest=JSON.parse(fs.readFileSync(path.join(__dirname,'../public/assets/karyobinga/manifest.json')));if(download.sha256!==manifest.sha256)throw Error('Decoded GLB differs');
await page.evaluate(()=>__show('parrot'));await page.waitForFunction(()=>document.querySelector('#asset-preview').src.includes('parrot.html'));await page.evaluate(()=>__show('karyobinga'));frame=await(await page.$('#asset-preview')).contentFrame();await frame.waitForFunction(()=>window.__ready&&!!window.__karyo,{},{timeout:60000});
await page.setViewportSize({width:390,height:844});await frame.click('#front');await frame.evaluate(()=>__karyo.pose(1.8));await page.screenshot({path:path.join(out,'mobile.png')});
if(errors.length||failures.length)throw Error(JSON.stringify({errors,failures}));fs.writeFileSync(path.join(out,'checks.json'),JSON.stringify({state,download,errors,failures},null,2));console.log(JSON.stringify({state,download,errors,failures}));
}finally{await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
