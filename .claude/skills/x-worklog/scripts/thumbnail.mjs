// X投稿用サムネイル撮影スクリプト
// 使い方: node .claude/skills/x-worklog/scripts/thumbnail.mjs "タイトル" 出力パス.png
// 事前に npm run build 済みであること。カメラは CAMERA 定数で毎回構図を調整する。
import { chromium } from 'playwright-core';
import { spawn } from 'node:child_process';
import { mkdirSync, symlinkSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';

const TITLE = process.argv[2] ?? '極楽浄土を、歩ける場所にする';
const OUTPUT = resolve(process.argv[3] ?? 'thumbnail.png');
const PORT = 8933;

// その日いちばん見せたいものへ向ける(毎回調整すること)
// ギャラリーの一品を主役にする日は ITEM にidを入れる(メイン世界を撮る日は null)
const ITEM = 'pavilion';
const CAMERA = {
  position: [16.5, 6.2, 9.5],
  lookAt: [2.2, 5.0, -1.2],
};

// dist/ を /jodo_reborn_v2/ ベースパスで配信するための仮ルート
const serveRoot = join(tmpdir(), 'thumb-serve-root');
mkdirSync(serveRoot, { recursive: true });
const link = join(serveRoot, 'jodo_reborn_v2');
if (!existsSync(link)) symlinkSync(resolve('dist'), link);
const server = spawn('python3', ['-m', 'http.server', String(PORT), '--directory', serveRoot], { stdio: 'ignore' });
await new Promise((r) => setTimeout(r, 1200));

try {
  const executablePath = process.env.PLAYWRIGHT_CHROMIUM ?? '/opt/pw-browsers/chromium';
  const browser = await chromium.launch({ executablePath, args: ['--use-angle=swiftshader'] });
  const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
  page.on('pageerror', (e) => console.error('[pageerror]', e.message));
  await page.goto(`http://localhost:${PORT}/jodo_reborn_v2/${ITEM ? 'gallery.html' : ''}`);
  await page.waitForTimeout(6000); // アセット読み込みとフォールバック初期化を待つ
  if (ITEM) {
    await page.evaluate((id) => {
      window.__show(id);
      // 陳列棚のUIは伏せて、部材そのものを見せる
      ['list', 'back', 'caption', 'loading'].forEach((id) => {
        const el = document.getElementById(id);
        if (el) el.style.display = 'none';
      });
    }, ITEM);
    await page.waitForTimeout(2500);
  }

  await page.evaluate(({ position, lookAt }) => {
    const ov = document.getElementById('overlay');
    if (ov) ov.style.display = 'none';
    const camera = window.__camera;
    camera.aspect = 1600 / 900;
    camera.updateProjectionMatrix();
    camera.position.set(...position);
    camera.lookAt(...lookAt);
  }, CAMERA);
  await page.waitForTimeout(1000);

  await page.evaluate((title) => {
    const d = document.createElement('div');
    d.innerHTML = `
    <div style="position:fixed;inset:0;pointer-events:none;
      background:linear-gradient(to left, rgba(24,16,4,0.62) 0%, rgba(24,16,4,0.18) 26%, transparent 48%),
                 linear-gradient(to top, rgba(24,16,4,0.45) 0%, transparent 26%);"></div>
    <div style="position:fixed;top:64px;right:64px;pointer-events:none;
      writing-mode:vertical-rl;color:#f5dc9e;font-family:'IPAGothic',sans-serif;
      font-size:58px;letter-spacing:0.3em;font-weight:bold;line-height:1.5;
      text-shadow:0 0 16px rgba(0,0,0,0.6), 0 0 44px rgba(0,0,0,0.4);">${title.replace('、', '、<br>')}</div>
    <div style="position:fixed;left:56px;bottom:48px;pointer-events:none;
      color:#eed9a4;font-family:'IPAGothic',sans-serif;font-size:25px;letter-spacing:0.22em;
      text-shadow:0 1px 10px rgba(0,0,0,0.65);">『仏説阿弥陀経』3D再現プロジェクト ── 浄土再現</div>`;
    document.body.appendChild(d);
  }, TITLE);
  await page.waitForTimeout(400);

  await page.screenshot({ path: OUTPUT });
  await browser.close();
  console.log('saved:', OUTPUT);
} finally {
  server.kill();
}
