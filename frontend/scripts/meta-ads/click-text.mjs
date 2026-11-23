// Clicks visible text in the current Ads Manager tab and screenshots the result.
// Usage: node scripts/meta-ads/click-text.mjs "Some text"

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const text = process.argv.slice(2).join(' ');
if (!text) throw new Error('Pass the text to click');
const shot = path.join(os.tmpdir(), 'meta-ads-click.png');

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const page = browser
  .contexts()
  .flatMap((c) => c.pages())
  .find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\//.test(p.url()));
if (!page) throw new Error('Ads Manager page not found');

await page.bringToFront();
const loc = page.getByText(text, { exact: true }).first();
console.log(`MATCHES=${await page.getByText(text, { exact: true }).count()}`);
await loc.click();
await page.waitForTimeout(7000);

console.log(`URL=${page.url()}`);
const body = await page.evaluate(() => document.body.innerText);
console.log('BODY_START');
console.log(body.replace(/\n{2,}/g, '\n').slice(0, 5000));
console.log('BODY_END');

await page.screenshot({ path: shot });
console.log(`SCREENSHOT=${shot}`);
process.exit(0);
