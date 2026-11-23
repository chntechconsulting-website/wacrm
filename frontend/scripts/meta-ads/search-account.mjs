// Searches the ad-account switcher for a query and screenshots the results.
// Usage: node scripts/meta-ads/search-account.mjs [query]

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const query = process.argv[2] || 'wahrms';
const shot = path.join(os.tmpdir(), 'meta-ads-account-search.png');

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const page = browser
  .contexts()
  .flatMap((c) => c.pages())
  .find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\/campaigns/.test(p.url()));
if (!page) throw new Error('Campaigns page not found');

await page.bringToFront();

const search = page.getByPlaceholder('Search for an ad account');
if (!(await search.isVisible().catch(() => false))) {
  await page.getByText('923516884887001', { exact: false }).first().click();
  await page.waitForTimeout(1000);
}
await search.fill(query);
await page.waitForTimeout(3000);

const bodyText = await page.evaluate(() => document.body.innerText);
const lines = bodyText
  .split('\n')
  .map((l) => l.trim())
  .filter((l) => /wahrms|923516|act_|account/i.test(l));
console.log('MATCHES_START');
console.log(lines.join('\n'));
console.log('MATCHES_END');

await page.screenshot({ path: shot });
console.log(`SCREENSHOT=${shot}`);
process.exit(0);
