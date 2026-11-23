// Lists campaigns in the current ad account without clicking anything.
// Usage: node scripts/meta-ads/list-campaigns.mjs

import { chromium } from 'playwright';

const browser = await chromium.connectOverCDP('http://127.0.0.1:9222');
const page = browser
  .contexts()
  .flatMap((c) => c.pages())
  .find((p) => /adsmanager\.facebook\.com\/adsmanager\/manage\/campaigns/.test(p.url()));
if (!page) throw new Error('Campaigns page not found');

await page.bringToFront();
const rows = await page.evaluate(() => {
  const out = [];
  for (const row of document.querySelectorAll('[role="row"]')) {
    const text = (row.innerText || '').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const links = [...row.querySelectorAll('a')].map((a) => ({ text: (a.innerText || '').trim(), href: a.href }));
    out.push({ text, links });
  }
  return out;
});
console.log(JSON.stringify({ url: page.url(), rows }, null, 2));
process.exit(0);
