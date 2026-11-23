// Launches a dedicated Chrome profile with remote debugging so the Meta Ads
// Manager session can be driven across script runs without touching your
// normal Chrome profile or handling credentials.
//
// Usage: node scripts/meta-ads/launch.mjs
// The window stays open; log in to Meta yourself (password + 2FA).

import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const PORT = 9222;
const PROFILE = path.join(process.env.LOCALAPPDATA || os.homedir(), 'WaCRM', 'meta-ads-profile');
const URL = 'https://adsmanager.facebook.com/adsmanager/manage/campaigns';
const CHROME = process.env.META_CHROME || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

async function cdpUp() {
  try {
    const res = await fetch(`http://127.0.0.1:${PORT}/json/version`, { signal: AbortSignal.timeout(1500) });
    return res.ok;
  } catch {
    return false;
  }
}

if (await cdpUp()) {
  console.log(`ALREADY_RUNNING http://127.0.0.1:${PORT}`);
  process.exit(0);
}

if (!fs.existsSync(CHROME)) {
  console.error(`Chrome not found at ${CHROME}. Set META_CHROME to chrome.exe.`);
  process.exit(1);
}

fs.mkdirSync(PROFILE, { recursive: true });

const child = spawn(
  CHROME,
  [
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${PROFILE}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--start-maximized',
    '--disable-blink-features=AutomationControlled',
    URL,
  ],
  { detached: true, stdio: 'ignore' }
);
child.unref();

for (let i = 0; i < 40; i++) {
  await new Promise((r) => setTimeout(r, 500));
  if (await cdpUp()) break;
}

if (!(await cdpUp())) {
  console.error('Chrome started but the debugging port never opened.');
  process.exit(1);
}

console.log(`LAUNCHED pid=${child.pid}`);
console.log(`PROFILE=${PROFILE}`);
console.log(`CDP=http://127.0.0.1:${PORT}`);
console.log('Log in to Meta in the window that just opened (password + 2FA are yours to type).');
