// Opens the Ads Manager campaign creation flow and screenshots the first step.
// Usage: node scripts/meta-ads/open-create.mjs

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const shot = path.join(os.tmpdir(), 'meta-ads-create.png');

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const before = browser.contexts().flatMap((c) => c.pages());
const page = before.find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\/campaigns/.test(p.url()));
if (!page) {
  console.error('Campaigns page not found');
  process.exit(1);
}

await page.bringToFront();
const create = page.getByRole('button', { name: /^Create$/ }).first();
console.log(`CREATE_BUTTONS=${await page.getByRole('button', { name: /^Create$/ }).count()}`);
await create.click();

await page.waitForTimeout(7000);

const pages = browser.contexts().flatMap((c) => c.pages());
for (const p of pages) {
  let title = '';
  try {
    title = await p.title();
  } catch {}
  console.log(JSON.stringify({ url: p.url(), title }));
}

const active =
  pages.find((p) => /adsmanager\.facebook\.com\/adsmanager\/create/.test(p.url())) ??
  pages.find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage/.test(p.url())) ??
  page;

await active.bringToFront();
await active.screenshot({ path: shot });
console.log(`ACTIVE=${active.url()}`);
console.log(`SCREENSHOT=${shot}`);
process.exit(0);
