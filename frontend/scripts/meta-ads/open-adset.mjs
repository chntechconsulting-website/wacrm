// Opens an ad set by name and screenshots the editor.
// Usage: node scripts/meta-ads/open-adset.mjs "Ad set name"

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const name = process.argv.slice(2).join(' ') || 'New Leads Ad Set';
const shot = path.join(os.tmpdir(), 'meta-ads-adset.png');

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const page = browser
  .contexts()
  .flatMap((c) => c.pages())
  .find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\/adsets/.test(p.url()));
if (!page) throw new Error('Ad sets page not found');

await page.bringToFront();
const link = page.getByText(name, { exact: true }).first();
console.log(`MATCHES=${await page.getByText(name, { exact: true }).count()}`);
await link.click();
await page.waitForTimeout(8000);

console.log(`URL=${page.url()}`);
const text = await page.evaluate(() => document.body.innerText);
console.log('BODY_START');
console.log(text.replace(/\n{2,}/g, '\n').slice(0, 5000));
console.log('BODY_END');

await page.screenshot({ path: shot });
console.log(`SCREENSHOT=${shot}`);
process.exit(0);
