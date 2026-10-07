const fs = require('node:fs');
const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1100, height: 760 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  // Test-only instrumentation: no profiling globals or counters in the published bundle.
  await page.route('**/src/main.ts*', async route => {
    const response = await route.fetch();
    const source = await response.text();
    const marker = 'await renderer.init();';
    if (!source.includes(marker)) throw new Error('Profiling injection point not found');
    await route.fulfill({ response, body: source.replace(marker, `${marker}
      window.__profileRenderer = renderer;
      window.__profileFrames = [];
      const setLoop = renderer.setAnimationLoop.bind(renderer);
      renderer.setAnimationLoop = (callback) => setLoop(callback && ((...args) => {
        const calls = renderer.info.render.calls;
        const start = performance.now();
        callback(...args);
        if (renderer.info.render.calls > calls) window.__profileFrames.push(performance.now() - start);
      }));
    `) });
  });
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  async function sample() {
    await page.evaluate(() => { window.__profileFrames = []; });
    const before = await cdp.send('Performance.getMetrics');
    await page.waitForTimeout(6000);
    const after = await cdp.send('Performance.getMetrics');
    const metrics = data => Object.fromEntries(data.metrics.map(item => [item.name, item.value]));
    const a = metrics(before), b = metrics(after);
    return page.evaluate(({ a, b }) => {
      const frames = window.__profileFrames;
      const renderer = window.__profileRenderer;
      return {
        seconds: b.Timestamp - a.Timestamp,
        renderedFrames: frames.length,
        fps: frames.length / (b.Timestamp - a.Timestamp),
        frameCpuMs: frames.reduce((sum, ms) => sum + ms, 0) / frames.length,
        taskCpuSeconds: b.TaskDuration - a.TaskDuration,
        heapBytes: b.JSHeapUsedSize,
        gpuMemory: renderer.info.memory,
        drawCalls: renderer.info.render.drawCalls,
        triangles: renderer.info.render.triangles,
      };
    }, { a, b });
  }
  try {
    const start = Date.now();
    await page.goto(process.env.WORLD_BASE || 'http://127.0.0.1:8965/jodo_reborn_v2/');
    await page.waitForFunction(() => !document.getElementById('enter').disabled && window.__scene && window.__profileRenderer, {}, { timeout: 180000 });
    const readyMs = Date.now() - start;
    await page.waitForTimeout(5000);
    const entrance = await sample();
    await page.locator('#bgm-enabled').uncheck();
    await page.locator('#enter').click();
    await page.waitForFunction(() => !!document.pointerLockElement);
    await page.waitForTimeout(2000);
    const walking = await sample();
    const resources = await page.evaluate(() => {
      const entries = performance.getEntriesByType('resource');
      const assets = entries.filter(item => /\.(glb|gz|png|jpg)(\?|$)/.test(item.name));
      const textures = new Set();
      window.__scene.traverse(object => {
        for (const material of [object.material].flat().filter(Boolean)) {
          for (const value of Object.values(material)) if (value?.isTexture) textures.add(value.uuid);
        }
      });
      return { assetTransferBytes: assets.reduce((sum, item) => sum + item.encodedBodySize, 0), textureObjects: textures.size, assets: assets.map(item => ({ url: item.name.split('/jodo_reborn_v2/')[1], bytes: item.encodedBodySize })) };
    });
    const out = process.env.PROFILE_OUT || '/tmp/jodo-world-profile.json';
    const result = { readyMs, entrance, walking, resources, errors };
    fs.writeFileSync(out, JSON.stringify(result, null, 2));
    console.log(JSON.stringify({ ...result, resources: { ...resources, assets: undefined } }, null, 2));
    if (errors.length) process.exitCode = 1;
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
