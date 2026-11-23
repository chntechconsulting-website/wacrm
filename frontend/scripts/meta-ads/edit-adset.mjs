// Navigates to the ad-set view and opens the editor for a given ad set.
// Usage: node scripts/meta-ads/edit-adset.mjs "New Leads Ad Set"

import { chromium } from 'playwright';
import os from 'node:os';
import path from 'node:path';

const name = process.argv.slice(2).join(' ') || 'New Leads Ad Set';
const shot = path.join(os.tmpdir(), 'meta-ads-adset-edit.png');
const URL =
  'https://adsmanager.facebook.com/adsmanager/manage/adsets?act=1612414910426125&business_id=1611991997000422&global_scope_id=1611991997000422&selected_campaign_ids=120252639644700627';

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const pages = browser.contexts().flatMap((c) => c.pages());
const page = pages.find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\//.test(p.url()));
if (!page) throw new Error('Ads Manager page not found');

await page.bringToFront();
await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 90000 });
await page.waitForTimeout(7000);
console.log(`URL=${page.url()}`);

const nameLoc = page.getByText(name, { exact: true }).first();
await nameLoc.waitFor({ state: 'visible', timeout: 30000 });
const nameBox = await nameLoc.boundingBox();
console.log(`NAME_BOX=${JSON.stringify(nameBox)}`);

const edits = page.getByRole('button', { name: 'Edit', exact: true });
const count = await edits.count();
console.log(`EDIT_BUTTONS=${count}`);
let best = null;
for (let i = 0; i < count; i++) {
  const b = edits.nth(i);
  const box = await b.boundingBox();
  const vis = await b.isVisible().catch(() => false);
  console.log(`EDIT[${i}] visible=${vis} box=${JSON.stringify(box)}`);
  if (!vis || !box || !nameBox) continue;
  const dy = Math.abs(box.y + box.height / 2 - (nameBox.y + nameBox.height / 2));
  if (!best || dy < best.dy) best = { i, dy };
}
if (!best) throw new Error('No Edit button found on the ad set row');
console.log(`CLICK_EDIT_INDEX=${best.i} dy=${best.dy}`);
await edits.nth(best.i).click();
await page.waitForTimeout(9000);

console.log(`EDITOR_URL=${page.url()}`);
const body = await page.evaluate(() => document.body.innerText);
console.log('BODY_START');
console.log(body.replace(/\n{2,}/g, '\n').slice(0, 7000));
console.log('BODY_END');
await page.screenshot({ path: shot });
console.log(`SCREENSHOT=${shot}`);
process.exit(0);
