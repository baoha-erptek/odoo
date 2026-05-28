import fs from 'fs';
import path from 'path';

const REPO_ROOT = path.resolve(__dirname, '../../..');
const ENV_FILE = path.join(REPO_ROOT, '.env');

function parseDotEnv(): Record<string, string> {
  if (!fs.existsSync(ENV_FILE)) return {};
  const out: Record<string, string> = {};
  for (const line of fs.readFileSync(ENV_FILE, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq < 0) continue;
    const k = trimmed.slice(0, eq).trim();
    let v = trimmed.slice(eq + 1).trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    out[k] = v;
  }
  return out;
}

const dotenv = parseDotEnv();

function readEnv(key: string, fallback?: string): string {
  return process.env[key] ?? dotenv[key] ?? fallback ?? '';
}

// Static values read at module load time
const STATIC_CONFIG = {
  REPO_ROOT,
  BASE_URL: readEnv('STAGING_BASE_URL', 'https://odoo.hatafax.com'),
  DB: readEnv('STAGING_DB', 'esty_odoo19'),
  ADMIN_LOGIN: readEnv('STAGING_ADMIN_LOGIN', 'admin'),
  ADMIN_PASSWORD: readEnv('STAGING_ADMIN_PASSWORD'),
  BA_LEAD_LOGIN: readEnv('STAGING_BA_LEAD_LOGIN', readEnv('STAGING_BA_LOGIN')),
  BA_LEAD_PASSWORD: readEnv('STAGING_BA_LEAD_PASSWORD', readEnv('STAGING_BA_PASSWORD')),
  BA_USER_LOGIN: 'uat_ba_user@hatafax.demo',
};

// CONFIG uses getter for BA_USER_PASSWORD so that globalSetup (which sets
// process.env.STAGING_BA_USER_PASSWORD after seed_ba_user.py runs) is observed
// at the time the tests dereference it, not at module-load time.
export const CONFIG = {
  ...STATIC_CONFIG,
  get BA_USER_PASSWORD(): string {
    return process.env.STAGING_BA_USER_PASSWORD || readSeedStateFile();
  },
};

function readSeedStateFile(): string {
  // Fallback: globalSetup persisted to artifacts/_seed_state.json — read it
  // if process.env didn't propagate (Playwright workers re-spawn the process).
  const stateFile = path.join(REPO_ROOT, 'tests', 'e2e', 'artifacts', '_seed_state.json');
  try {
    if (fs.existsSync(stateFile)) {
      const j = JSON.parse(fs.readFileSync(stateFile, 'utf8'));
      return j.ba_user_password || '';
    }
  } catch {
    /* ignore */
  }
  return '';
}

export function requireEnv(name: keyof typeof CONFIG): string {
  const v = (CONFIG as Record<string, unknown>)[name];
  if (!v || typeof v !== 'string') {
    throw new Error(
      `Missing env var for ${String(name)}. ` +
      `Set STAGING_* in .env or export before running. ` +
      `Required: STAGING_ADMIN_PASSWORD, STAGING_BA_LEAD_LOGIN, STAGING_BA_LEAD_PASSWORD.`
    );
  }
  return v;
}
