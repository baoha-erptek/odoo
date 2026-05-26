import { execSync } from 'child_process';
import path from 'path';
import { CONFIG } from './env';

const CLEANUP_SCRIPT = path.join(__dirname, 'cleanup_uat_data.py');

export default async function globalTeardown() {
  if (!CONFIG.ADMIN_PASSWORD) {
    console.warn('[globalTeardown] STAGING_ADMIN_PASSWORD not set — skipping cleanup');
    return;
  }
  console.log('\n[globalTeardown] Cleaning up UAT products + archiving BA User ...');
  try {
    const out = execSync(
      `python3 ${CLEANUP_SCRIPT} --base-url "${CONFIG.BASE_URL}" --db "${CONFIG.DB}"`,
      {
        encoding: 'utf8',
        env: {
          ...process.env,
          STAGING_ADMIN_LOGIN: CONFIG.ADMIN_LOGIN,
          STAGING_ADMIN_PASSWORD: CONFIG.ADMIN_PASSWORD,
        },
      }
    );
    console.log(out);
  } catch (e) {
    console.warn(`[globalTeardown] cleanup_uat_data.py failed (non-fatal): ${(e as Error).message}`);
  }
}
