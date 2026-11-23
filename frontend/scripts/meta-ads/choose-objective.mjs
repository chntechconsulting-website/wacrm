// Selects the Leads objective in the create-campaign modal and continues.
// Usage: node scripts/meta-ads/choose-objective.mjs

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const shot = path.join(os.tmpdir(), 'meta-ads-objective.png');

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const page = browser
  .contexts()
  .flatMap((c) => c.pages())
  .find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\/campaigns/.test(p.url()));
if (!page) throw new Error('Campaigns page not found');

await page.bringToFront();
const dialog = page.getByRole('dialog');
console.log(`DIALOGS=${await dialog.count()}`);

const scope = (await dialog.count()) > 0 ? dialog.first() : page;
await scope.getByText('Leads', { exact: true }).click();
await page.waitForTimeout(500);
await scope.getByRole('button', { name: 'Continue' }).click();
await page.waitForTimeout(8000);

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
  pages.find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\/campaigns/.test(p.url())) ??
  page;
await active.bringToFront();
await active.screenshot({ path: shot });
console.log(`ACTIVE=${active.url()}`);
console.log(`SCREENSHOT=${shot}`);
process.exit(0);
