// Closes the create modal, opens the ad-account switcher, and lists accounts.
// Usage: node scripts/meta-ads/list-accounts.mjs

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const shot = path.join(os.tmpdir(), 'meta-ads-accounts.png');

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const page = browser
  .contexts()
  .flatMap((c) => c.pages())
  .find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\/campaigns/.test(p.url()));
if (!page) throw new Error('Campaigns page not found');

await page.bringToFront();

const cancel = page.getByRole('button', { name: 'Cancel' });
if (await cancel.isVisible().catch(() => false)) await cancel.click();
await page.waitForTimeout(1000);

const accountText = page.getByText('923516884887001', { exact: false });
console.log(`ACCOUNT_TEXT_MATCHES=${await accountText.count()}`);
await accountText.first().click();
await page.waitForTimeout(2500);

// Dump visible text from any open listbox/dialog/menu to identify account names.
const visibleText = await page.evaluate(() => {
  const nodes = [...document.querySelectorAll('[role="dialog"], [role="listbox"], [role="menu"]')];
  return nodes.map((n) => (n.innerText || '').trim()).filter(Boolean).join('\n---\n');
});
console.log('VISIBLE_TEXT_START');
console.log(visibleText.slice(0, 4000));
console.log('VISIBLE_TEXT_END');

await page.screenshot({ path: shot });
console.log(`SCREENSHOT=${shot}`);
process.exit(0);
