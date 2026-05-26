import { execSync } from 'child_process';
import path from 'path';
import fs from 'fs';
import { CONFIG } from './env';

const REPO_ROOT = CONFIG.REPO_ROOT;
const SEED_SCRIPT = path.join(__dirname, 'seed_ba_user.py');
const STATE_FILE = path.join(__dirname, '..', 'artifacts', '_seed_state.json');

async function preflight(): Promise<void> {
  console.log(`\n[globalSetup] Preflight ${CONFIG.BASE_URL} ...`);
  try {
    const out = execSync(`curl -sI --max-time 10 ${CONFIG.BASE_URL}/web/login | head -1`, {
      encoding: 'utf8',
    });
    if (!/HTTP\/[12]\.?[01]?\s+200/i.test(out)) {
      throw new Error(`Preflight non-200: ${out.trim()}`);
    }
    console.log(`[globalSetup] Preflight OK: ${out.trim()}`);
  } catch (e) {
    throw new Error(
      `Cannot reach ${CONFIG.BASE_URL}. Check network / VPN. Detail: ${(e as Error).message}`
    );
  }
}

async function seedBaUser(): Promise<void> {
  if (!CONFIG.ADMIN_PASSWORD) {
    console.warn(
      `[globalSetup] STAGING_ADMIN_PASSWORD not set — skipping BA User seed. ` +
      `TC-006/TC-007 will fail if BA_USER_PASSWORD env var is also empty.`
    );
    return;
  }
  console.log(`[globalSetup] Seeding BA User on db=${CONFIG.DB} ...`);
  try {
    const result = execSync(
      `python3 ${SEED_SCRIPT} --base-url "${CONFIG.BASE_URL}" --db "${CONFIG.DB}"`,
      {
        encoding: 'utf8',
        env: {
          ...process.env,
          STAGING_ADMIN_LOGIN: CONFIG.ADMIN_LOGIN,
          STAGING_ADMIN_PASSWORD: CONFIG.ADMIN_PASSWORD,
        },
      }
    );
    console.log(result);
    // The script prints a final line: BA_USER_PASSWORD=<value>
    const m = result.match(/^BA_USER_PASSWORD=(\S+)$/m);
    if (m) {
      const generated = m[1];
      // Persist for tests to read via env
      process.env.STAGING_BA_USER_PASSWORD = generated;
      fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
      fs.writeFileSync(STATE_FILE, JSON.stringify({ ba_user_password: generated }, null, 2));
      console.log(`[globalSetup] BA User seeded; password persisted to ${STATE_FILE}`);
    } else {
      console.warn(`[globalSetup] seed script did not output BA_USER_PASSWORD line; check seed_ba_user.py output above`);
    }
  } catch (e) {
    throw new Error(`seed_ba_user.py failed: ${(e as Error).message}`);
  }
}

export default async function globalSetup() {
  console.log('===========================================');
  console.log('Odoo19-Esty UAT — globalSetup');
  console.log(`  Base URL : ${CONFIG.BASE_URL}`);
  console.log(`  Database : ${CONFIG.DB}`);
  console.log(`  REPO_ROOT: ${CONFIG.REPO_ROOT}`);
  console.log('===========================================');

  await preflight();
  await seedBaUser();
}
