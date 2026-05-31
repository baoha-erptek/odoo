import { execSync } from 'child_process';
import path from 'path';
import fs from 'fs';
import { CONFIG } from './env';

const REPO_ROOT = CONFIG.REPO_ROOT;
const SEED_SCRIPT = path.join(__dirname, 'seed_ba_user.py');
const PREFLIGHT_SCRIPT = path.join(__dirname, 'preflight_check.py');
const ASSET_BUILDER_SCRIPT = path.join(__dirname, 'assets', 'build_uat_assets.py');
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

/**
 * Phase C — run preflight_check.py for env + module + cron + shop-default +
 * real-order-anchor parity. Soft-fail (warn) by default: setting
 * UAT_PREFLIGHT_STRICT=1 promotes to a hard error that aborts the suite.
 */
async function preflightStaging(): Promise<void> {
  if (!CONFIG.ADMIN_PASSWORD) {
    console.warn('[globalSetup] STAGING_ADMIN_PASSWORD unset — skipping Phase-C preflight');
    return;
  }
  console.log(`[globalSetup] Phase-C preflight (env+cron+shop+anchor) ...`);
  try {
    const out = execSync(
      `python3 ${PREFLIGHT_SCRIPT} --base-url "${CONFIG.BASE_URL}" --db "${CONFIG.DB}"`,
      {
        encoding: 'utf8',
        env: {
          ...process.env,
          STAGING_ADMIN_LOGIN: CONFIG.ADMIN_LOGIN,
          STAGING_ADMIN_PASSWORD: CONFIG.ADMIN_PASSWORD,
        },
      },
    );
    console.log(out);
  } catch (e) {
    const detail = (e as Error).message;
    if (process.env.UAT_PREFLIGHT_STRICT === '1') {
      throw new Error(`[globalSetup] Phase-C preflight FAILED (strict mode): ${detail}`);
    }
    console.warn(
      `[globalSetup] Phase-C preflight produced warnings (non-strict): ${detail}\n` +
      `[globalSetup] Set UAT_PREFLIGHT_STRICT=1 to make this a hard failure.`,
    );
  }
}

/**
 * Idempotent fixture-asset builder. Generates the GKE XLSX files at
 * fixtures/assets/ if missing. Files are .gitignored so a fresh checkout
 * always rebuilds them on first run.
 */
async function buildUatAssets(): Promise<void> {
  const happy = path.join(path.dirname(ASSET_BUILDER_SCRIPT), 'gke_excel_sample.xlsx');
  const broken = path.join(path.dirname(ASSET_BUILDER_SCRIPT), 'gke_excel_broken_schema.xlsx');
  if (fs.existsSync(happy) && fs.existsSync(broken)) {
    console.log('[globalSetup] UAT asset XLSX files already present — skip rebuild');
    return;
  }
  console.log('[globalSetup] Building UAT asset XLSX files via openpyxl ...');
  try {
    const out = execSync(`python3 ${ASSET_BUILDER_SCRIPT}`, { encoding: 'utf8' });
    console.log(out);
  } catch (e) {
    console.warn(
      `[globalSetup] asset builder failed (continuing — Flow-3 GKE TCs will skip): ` +
      `${(e as Error).message}`,
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
      },
    );
    // SECURITY: do NOT echo `result` — it contains `<ROLE>_PASSWORD=<value>` lines
    // for every seeded role and would leak generated passwords into CI logs.
    // Print only the non-credential lines (everything before the first PASSWORD= line).
    const safeLog = result.replace(/^[A-Z_]+_PASSWORD=\S+$/gm, '<REDACTED_PASSWORD_LINE>');
    console.log(safeLog);
    // Parse all role lines `<ROLE>_PASSWORD=<value>` (seed_ba_user.py emits
    // one per provisioned role: BA_USER, BA_LEAD, BA_SHIPPING, BA_SHIPPING_MGR).
    const lineRe = /^([A-Z_]+)_PASSWORD=(\S+)$/gm;
    const seedState: Record<string, string> = {};
    let match: RegExpExecArray | null;
    while ((match = lineRe.exec(result)) !== null) {
      const role = match[1];
      const pwd = match[2];
      // SECURITY/CORRECTNESS: do NOT overwrite process.env.STAGING_BA_LEAD_PASSWORD —
      // that env var is reserved for the owner-provided legacy BA Lead (often
      // the staging admin user) and is consumed by env.ts STATIC_CONFIG
      // BA_LEAD_PASSWORD → loginAsBaLead(). Overwriting it with the auto-seeded
      // uat_ba_lead@hatafax.demo password breaks every spec that calls
      // loginAsBaLead, because the login + password pair becomes mismatched
      // (admin user × uat_ba_lead's 16-char password → AccessDenied).
      // The auto-seeded BA Lead password is recoverable from seedState via the
      // BA_LEAD_AUTO_PASSWORD getter in env.ts (reads from _seed_state.json).
      if (role !== 'BA_LEAD') {
        process.env[`STAGING_${role}_PASSWORD`] = pwd;
      }
      // Persist with legacy key name for the original BA_USER (env.ts dereferences
      // it via getter); other roles persisted under snake-case for lookup parity.
      seedState[role === 'BA_USER' ? 'ba_user_password' : `${role.toLowerCase()}_password`] = pwd;
    }
    if (Object.keys(seedState).length === 0) {
      console.warn(
        `[globalSetup] seed script did not output any <ROLE>_PASSWORD lines; ` +
        `check seed_ba_user.py output above`,
      );
    } else {
      fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
      fs.writeFileSync(STATE_FILE, JSON.stringify(seedState, null, 2));
      console.log(
        `[globalSetup] seeded roles: ${Object.keys(seedState).join(', ')} → ${STATE_FILE}`,
      );
    }
  } catch (e) {
    throw new Error(`seed_ba_user.py failed: ${(e as Error).message}`);
  }
}

async function seedUatData(): Promise<void> {
  console.log(`[globalSetup] Seeding UAT data (categories/legacy product/tags) on db=${CONFIG.DB} ...`);
  try {
    const out = execSync(
      `python3 ${path.join(__dirname, 'seed_uat_data.py')} --base-url "${CONFIG.BASE_URL}" --db "${CONFIG.DB}"`,
      { encoding: 'utf8' },
    );
    console.log(out);
  } catch (e) {
    // Non-fatal: form-only TCs that don't need the seed can still run; the
    // seed-dependent TCs skip themselves. Surface the error for visibility.
    console.warn(`[globalSetup] seed_uat_data.py failed (continuing): ${(e as Error).message}`);
  }
}

/**
 * Phase D residual #1 — fire the Etsy receipts cron once so Flow-2 TC-003
 * has a fresh etsy.api.log row to assert on. Best-effort: cron failures
 * surface in the spec itself, not here.
 */
async function triggerStagingCrons(): Promise<void> {
  if (!CONFIG.ADMIN_PASSWORD) {
    console.warn('[globalSetup] STAGING_ADMIN_PASSWORD not set — skipping cron trigger');
    return;
  }
  console.log(`[globalSetup] Triggering staging crons (etsy.api.log freshness) ...`);
  try {
    const out = execSync(
      `python3 ${path.join(__dirname, 'trigger_crons.py')} --base-url "${CONFIG.BASE_URL}" --db "${CONFIG.DB}"`,
      {
        encoding: 'utf8',
        env: {
          ...process.env,
          STAGING_ADMIN_LOGIN: CONFIG.ADMIN_LOGIN,
          STAGING_ADMIN_PASSWORD: CONFIG.ADMIN_PASSWORD,
        },
      },
    );
    console.log(out);
  } catch (e) {
    console.warn(`[globalSetup] trigger_crons.py failed (continuing): ${(e as Error).message}`);
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
  await preflightStaging();
  await seedBaUser();
  await seedUatData();
  await triggerStagingCrons();
  await buildUatAssets();
}
