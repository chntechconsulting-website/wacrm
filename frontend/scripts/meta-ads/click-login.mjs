// Brings the dedicated Meta window forward and opens the Facebook login form.
// Usage: node scripts/meta-ads/click-login.mjs

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const shot = path.join(os.tmpdir(), 'meta-ads-login.png');

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const pages = browser.contexts().flatMap((c) => c.pages());
const page = pages.find((p) => /business\.facebook\.com\/business\/loginpage/.test(p.url())) ?? pages[0];

await page.bringToFront();

if (/loginpage/.test(page.url())) {
  const fb = page.getByText('Continue with Facebook', { exact: false }).first();
  if (await fb.isVisible().catch(() => false)) {
    await fb.click().catch((e) => console.error(`click failed: ${e.message}`));
    await page.waitForTimeout(3000);
  }
}

await page.screenshot({ path: shot });
console.log(`URL=${page.url()}`);
console.log(`SCREENSHOT=${shot}`);

process.exit(0);
