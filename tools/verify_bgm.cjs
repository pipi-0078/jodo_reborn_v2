const assert = require('node:assert/strict');
const fs = require('node:fs');
const { chromium } = require('playwright-core');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1100, height: 760 } });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    window.__bgmProbe = { media: [], gains: [] };
    const createMedia = AudioContext.prototype.createMediaElementSource;
    AudioContext.prototype.createMediaElementSource = function (audio) {
      window.__bgmProbe.media.push(audio);
      return createMedia.call(this, audio);
    };
    const createGain = AudioContext.prototype.createGain;
    AudioContext.prototype.createGain = function () {
      const gain = createGain.call(this);
      window.__bgmProbe.gains.push(gain);
      return gain;
    };
  });
  const state = () => page.evaluate(() => {
    const audio = window.__bgmProbe.media[0];
    return {
      count: window.__bgmProbe.media.length,
      paused: audio?.paused,
      loop: audio?.loop,
      time: audio?.currentTime,
      duration: audio?.duration,
      gain: window.__bgmProbe.gains[0]?.gain.value,
      locked: !!document.pointerLockElement,
    };
  });
  const enter = () => page.locator('#enter').click();
  const exit = () => page.evaluate(() => document.exitPointerLock());
  const results = {};
  try {
    await page.goto(process.env.BGM_BASE || 'http://127.0.0.1:8964/jodo_reborn_v2/');
    assert.match(await page.locator('#sound-notice').innerText(), /音が出ます/);
    await page.waitForFunction(() => !document.getElementById('enter').disabled, {}, { timeout: 180000 });
    assert.equal((await state()).count, 0, 'No audio graph before entry');
    await page.locator('#sound-notice').click();
    assert.equal((await state()).locked, false, 'Notice is not an entry action');
    const out = process.env.OUTPUT_DIR || '/tmp/jodo-bgm-verification';
    fs.mkdirSync(out, { recursive: true });
    await page.screenshot({ path: `${out}/entrance.png`, timeout: 60000 });

    await enter();
    await page.waitForFunction(() => document.pointerLockElement && window.__bgmProbe.media[0]?.currentTime > 0);
    await page.waitForTimeout(900);
    results.fadeIn = await state();
    assert(results.fadeIn.gain > 0 && results.fadeIn.gain < 0.18, 'Fade-in intermediate gain');
    await page.waitForTimeout(3500);
    results.playing = await state();
    assert(Math.abs(results.playing.gain - 0.18) < 0.001, 'Quiet target gain');
    assert.equal(results.playing.loop, true);
    assert.equal(results.playing.paused, false);
    assert(results.playing.duration > 299 && results.playing.duration < 301);

    // Seek through the actual MP3 end and observe the native loop restart.
    await page.evaluate(() => {
      const audio = window.__bgmProbe.media[0];
      audio.currentTime = audio.duration - 0.6;
    });
    await page.waitForFunction(() => window.__bgmProbe.media[0].currentTime < 3);
    results.loop = await state();
    assert.equal(results.loop.paused, false);

    await exit();
    await page.waitForTimeout(700);
    results.fadeOut = await state();
    assert(results.fadeOut.gain > 0 && results.fadeOut.gain < 0.18, 'Fade-out intermediate gain');
    await page.waitForTimeout(1600);
    results.stopped = await state();
    assert.equal(results.stopped.paused, true);
    assert.equal(results.stopped.gain, 0);

    await enter();
    await page.waitForTimeout(700);
    await exit();
    await page.waitForTimeout(300);
    await enter();
    await page.waitForTimeout(4300);
    results.reentry = await state();
    assert.equal(results.reentry.count, 1, 'Reentry reuses one audio element');
    assert.equal(results.reentry.paused, false, 'Old fade-out does not pause reentry');
    assert(Math.abs(results.reentry.gain - 0.18) < 0.001);

    // Exercise the same visibility event used when a browser tab is hidden.
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { configurable: true, value: true });
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await page.waitForTimeout(2300);
    results.hidden = await state();
    assert.equal(results.hidden.paused, true);
    assert.equal(results.hidden.gain, 0);
    await page.evaluate(() => {
      delete document.hidden;
      document.dispatchEvent(new Event('visibilitychange'));
    });
    await page.waitForTimeout(4300);
    results.visible = await state();
    assert.equal(results.visible.paused, false);

    await exit();
    await page.waitForTimeout(2300);
    await page.locator('#bgm-enabled').uncheck();
    await enter();
    await page.waitForTimeout(500);
    results.silentEntry = await state();
    assert.equal(results.silentEntry.locked, true);
    assert.equal(results.silentEntry.paused, true);
    assert.equal(results.silentEntry.gain, 0);
    assert.deepEqual(errors, []);
    fs.writeFileSync(`${out}/results.json`, JSON.stringify(results, null, 2));
    console.log(JSON.stringify(results, null, 2));
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
