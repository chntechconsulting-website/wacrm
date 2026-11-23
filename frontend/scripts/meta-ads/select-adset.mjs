// Selects an ad set row (checkbox) then opens the toolbar Edit pane.
// Usage: node scripts/meta-ads/select-adset.mjs "New Leads Ad Set"

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const name = process.argv.slice(2).join(' ') || 'New Leads Ad Set';
const shot = path.join(os.tmpdir(), 'meta-ads-adset-editor.png');
const URL =
  'https://adsmanager.facebook.com/adsmanager/manage/adsets?act=1612414910426125&business_id=1611991997000422&global_scope_id=1611991997000422&selected_campaign_ids=120252639644700627';

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const page = browser
  .contexts()
  .flatMap((c) => c.pages())
  .find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\//.test(p.url()));
if (!page) throw new Error('Ads Manager page not found');

await page.bringToFront();
await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 });
await page.waitForTimeout(7000);

const nameLoc = page.getByText(name, { exact: true }).first();
await nameLoc.waitFor({ state: 'visible', timeout: 30000 });

const cb = await page.evaluate((target) => {
  const node = [...document.querySelectorAll('*')].find(
    (e) => e.childElementCount === 0 && e.textContent.trim() === target
  );
  let el = node;
  for (let i = 0; i < 14 && el; i++, el = el.parentElement) {
    const box = el.querySelector('[role="checkbox"], input[type="checkbox"]');
    if (box) {
      const r = box.getBoundingClientRect();
      if (r.width && r.height) {
        return { x: r.x + r.width / 2, y: r.y + r.height / 2, text: (el.innerText || '').slice(0, 120) };
      }
    }
  }
  return null;
}, name);
console.log(`CHECKBOX=${JSON.stringify(cb)}`);
if (!cb) throw new Error('Checkbox not found near ad set');

await page.mouse.click(cb.x, cb.y);
await page.waitForTimeout(1500);

const edits = page.getByRole('button', { name: 'Edit', exact: true });
const n = await edits.count();
for (let i = 0; i < n; i++) {
  console.log(
    `EDIT[${i}] disabled=${await edits.nth(i).getAttribute('aria-disabled')} box=${JSON.stringify(
      await edits.nth(i).boundingBox()
    )}`
  );
}
let target = null;
for (let i = 0; i < n; i++) {
  if ((await edits.nth(i).getAttribute('aria-disabled')) !== 'true' && (await edits.nth(i).isVisible())) {
    target = edits.nth(i);
    break;
  }
}
if (!target) throw new Error('Enabled Edit button not found');
await target.click();
await page.waitForTimeout(10000);

console.log(`EDITOR_URL=${page.url()}`);
const body = await page.evaluate(() => document.body.innerText);
console.log('BODY_START');
console.log(body.replace(/\n{2,}/g, '\n').slice(0, 8000));
console.log('BODY_END');
await page.screenshot({ path: shot });
console.log(`SCREENSHOT=${shot}`);
process.exit(0);
