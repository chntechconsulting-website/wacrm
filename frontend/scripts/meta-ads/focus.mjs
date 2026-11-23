// Focuses the Facebook login tab in the dedicated Meta browser and screenshots it.
// Usage: node scripts/meta-ads/focus.mjs <url-regex>

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const pattern = process.argv[2] || 'facebook\\.com/login';
const shot = path.join(os.tmpdir(), 'meta-ads-focus.png');

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const pages = browser.contexts().flatMap((c) => c.pages());
const page = pages.find((p) => new RegExp(pattern).test(p.url()));

if (!page) {
  console.log('NO_MATCH');
  for (const p of pages) console.log(p.url());
  process.exit(1);
}

await page.bringToFront();
await page.screenshot({ path: shot });
console.log(`URL=${page.url()}`);
console.log(`TITLE=${await page.title().catch(() => '')}`);
console.log(`SCREENSHOT=${shot}`);
process.exit(0);
