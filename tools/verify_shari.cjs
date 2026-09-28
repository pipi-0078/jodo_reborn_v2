const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright-core');
(async () => {
  const out = process.env.OUTPUT_DIR || '/tmp/shari-world-verification';
  fs.mkdirSync(out, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const errors = [], failures = [];
  const base = process.env.SHARI_BASE || 'http://127.0.0.1:8946/jodo_reborn_v2/';
  function monitor(page) {
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error' && !m.text().includes('favicon') && !m.location().url.includes('favicon')) errors.push(m.text()); });
    page.on('response', r => { if (r.status() >= 400 && !r.url().includes('favicon')) failures.push({ url: r.url(), status: r.status() }); });
  }
  try {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    monitor(page);
    await page.goto(base + 'gallery.html?asset=shari');
    const frame = await (await page.waitForSelector('#asset-preview')).contentFrame();
    await frame.waitForFunction(() => window.__ready && window.__shari, {}, { timeout: 90000 });
    const gallery = await frame.evaluate(async () => {
      __shari.pose(1.8);
      const eyes = [];
      __shari.group.traverse(m => {
        if (m.morphTargetDictionary?.Blink !== undefined) eyes.push(m.morphTargetInfluences[m.morphTargetDictionary.Blink]);
      });
      const data = await (await fetch(document.querySelector('#download').href)).arrayBuffer();
      const hash = await crypto.subtle.digest('SHA-256', data);
      return { clip: __shari.clip.name, duration: __shari.clip.duration, eyes,
        sha256: Array.from(new Uint8Array(hash), v => v.toString(16).padStart(2, '0')).join('') };
    });
    const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '../public/assets/shari/manifest.json')));
    if (gallery.clip !== 'Living flight' || gallery.duration !== 12 || gallery.eyes.length !== 1 || gallery.eyes[0] < 0.99 || gallery.sha256 !== manifest.sha256) throw Error('Gallery mismatch: ' + JSON.stringify(gallery));
    await frame.evaluate(() => __shari.pose(0.2));
    await page.screenshot({ path: path.join(out, 'gallery.png'), timeout: 120000 });
    await page.setViewportSize({ width: 390, height: 844 });
    await frame.click('#side');
    await page.screenshot({ path: path.join(out, 'gallery-mobile.png'), timeout: 120000 });
    console.log('Gallery verified:', gallery);
    await page.close();

    const world = await browser.newPage({ viewport: { width: 1100, height: 760 } });
    monitor(world);
    await world.goto(base + 'index.html?view=shari');
    await world.waitForFunction(() => window.__worldShari && window.__scene && window.__camera, {}, { timeout: 180000 });
    await world.evaluate(() => document.querySelector('#overlay').classList.add('hidden'));
    const before = await world.evaluate(() => __worldShari.bird.position.toArray());
    await world.waitForTimeout(2500);
    const after = await world.evaluate(() => __worldShari.bird.position.toArray());
    if (Math.hypot(...after.map((v, i) => v - before[i])) < 0.05) throw Error('Shari is not moving through the world');
    await world.screenshot({ path: path.join(out, 'world.png'), timeout: 180000 });
    const flight = await world.evaluate(() => {
      const a = __worldShari;
      const bounds = { minRadius: Infinity, maxRadius: -Infinity, minHeight: Infinity, maxHeight: -Infinity, minHeadingDot: 1 };
      for (let i = 0; i < 6000; i++) {
        const before = a.bird.position.clone();
        a.update(0.1);
        const p = a.bird.position;
        const radius = Math.hypot(p.x, p.z);
        bounds.minRadius = Math.min(bounds.minRadius, radius);
        bounds.maxRadius = Math.max(bounds.maxRadius, radius);
        bounds.minHeight = Math.min(bounds.minHeight, p.y);
        bounds.maxHeight = Math.max(bounds.maxHeight, p.y);
        const dx = p.x - before.x, dz = p.z - before.z;
        const dot = (Math.cos(a.bird.rotation.y) * dx - Math.sin(a.bird.rotation.y) * dz) / Math.hypot(dx, dz);
        bounds.minHeadingDot = Math.min(bounds.minHeadingDot, dot);
        if (a.bird.rotation.x !== 0 || a.bird.rotation.z !== 0) throw Error('Flight body tilts');
      }
      return { ...bounds, clip: a.clip.name, scale: a.bird.scale.x, area: a.area };
    });
    if (flight.minRadius < flight.area.radius - flight.area.radialRange - 0.001 ||
        flight.maxRadius > flight.area.radius + flight.area.radialRange + 0.001 ||
        flight.minHeadingDot < 0.999) throw Error('Flight route mismatch: ' + JSON.stringify(flight));
    if (errors.length || failures.length) throw Error(JSON.stringify({ errors, failures }));
    const report = { gallery, flight, errors, failures };
    fs.writeFileSync(path.join(out, 'report.json'), JSON.stringify(report, null, 2));
    console.log('World verified:', flight);
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
