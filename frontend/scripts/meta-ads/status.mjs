// Reports what the dedicated Meta browser is showing and saves a screenshot.
// Usage: node scripts/meta-ads/status.mjs

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const PORT = 9222;
const shot = path.join(os.tmpdir(), 'meta-ads-status.png');

let browser;
try {
  browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`);
} catch {
  console.error('NOT_RUNNING: start it with node scripts/meta-ads/launch.mjs');
  process.exit(2);
}

const pages = browser.contexts().flatMap((c) => c.pages());
for (const p of pages) {
  let title = '';
  try {
    title = await p.title();
  } catch {}
  console.log(JSON.stringify({ url: p.url(), title }));
}

const page =
  pages.find((p) => /adsmanager\.facebook\.com\/adsmanager/.test(p.url())) ??
  pages.find((p) => /facebook\.com/.test(p.url())) ??
  pages[0];

if (page) {
  try {
    await page.screenshot({ path: shot, fullPage: false });
    console.log(`SCREENSHOT=${shot}`);
  } catch (e) {
    console.error(`screenshot failed: ${e.message}`);
  }
}

// Disconnect without closing the user's browser window.
process.exit(0);
