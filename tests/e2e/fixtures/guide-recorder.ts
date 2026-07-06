import fs from 'fs';
import path from 'path';
import { Page } from '@playwright/test';

/**
 * Helpers for recording silent user-guide videos with Vietnamese caption
 * overlays (GUIDE_RECORDING=1 mode — see playwright.config.ts).
 *
 * Everything injected here is INTENTIONALLY visible in the recording:
 * caption bar, chapter title cards, and a cursor highlight dot. Pattern from
 * digitalsamba/claude-code-video-toolkit playwright-recording skill (MIT).
 *
 * Captions do not survive navigation — call showCaption() again after goto().
 * The cursor highlight uses addInitScript so it re-installs on every page.
 */

const CAPTION_ID = 'guide-caption-bar';
// NOT under artifacts/ — Playwright cleans outputDir at every run start, and
// this state must survive across per-chapter invocations.
const STATE_FILE = path.join(__dirname, '..', '.guide-state.json');

/** Install a cursor-follow highlight dot on every document of this page. */
export async function installCursorHighlight(page: Page): Promise<void> {
  await page.addInitScript(() => {
    const install = () => {
      if (document.getElementById('guide-cursor-dot')) return;
      const dot = document.createElement('div');
      dot.id = 'guide-cursor-dot';
      dot.style.cssText = [
        'position:fixed', 'z-index:2147483646', 'width:26px', 'height:26px',
        'border-radius:50%', 'background:rgba(255,80,80,0.35)',
        'border:2px solid rgba(255,60,60,0.9)', 'pointer-events:none',
        'transform:translate(-50%,-50%)', 'left:-100px', 'top:-100px',
        'transition:left 60ms linear, top 60ms linear',
      ].join(';');
      document.body.appendChild(dot);
      document.addEventListener('mousemove', (e) => {
        dot.style.left = `${e.clientX}px`;
        dot.style.top = `${e.clientY}px`;
      }, { passive: true });
      document.addEventListener('mousedown', () => {
        dot.style.background = 'rgba(255,80,80,0.7)';
        setTimeout(() => { dot.style.background = 'rgba(255,80,80,0.35)'; }, 250);
      });
    };
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', install);
    } else {
      install();
    }
  });
}

/**
 * Show/update the bottom caption bar, then hold so viewers can read.
 * holdMs default keys off text length (~reading speed), min 2.2s.
 */
export async function showCaption(page: Page, text: string, holdMs?: number): Promise<void> {
  await page.evaluate(({ id, text: t }) => {
    let bar = document.getElementById(id);
    if (!bar) {
      bar = document.createElement('div');
      bar.id = id;
      bar.style.cssText = [
        'position:fixed', 'left:50%', 'bottom:28px', 'transform:translateX(-50%)',
        'z-index:2147483647', 'max-width:72%', 'padding:14px 28px',
        'background:rgba(20,20,28,0.88)', 'color:#fff', 'border-radius:10px',
        'font:600 24px/1.4 "Segoe UI",Roboto,Arial,sans-serif',
        'text-align:center', 'pointer-events:none',
        'box-shadow:0 4px 18px rgba(0,0,0,0.45)',
      ].join(';');
      document.body.appendChild(bar);
    }
    bar.textContent = t;
  }, { id: CAPTION_ID, text });
  const hold = holdMs ?? Math.max(2200, Math.min(5000, text.length * 55));
  await page.waitForTimeout(hold);
}

/** Remove the caption bar (before screenshots of clean UI, or at chapter end). */
export async function hideCaption(page: Page): Promise<void> {
  await page.evaluate((id) => document.getElementById(id)?.remove(), CAPTION_ID);
}

/** Full-screen chapter title card, shown for ~3s then removed. */
export async function titleCard(page: Page, title: string, subtitle = ''): Promise<void> {
  await page.evaluate(({ title: t, subtitle: s }) => {
    const card = document.createElement('div');
    card.id = 'guide-title-card';
    card.style.cssText = [
      'position:fixed', 'inset:0', 'z-index:2147483647',
      'background:linear-gradient(135deg,#1a1c2c 0%,#28304d 100%)',
      'display:flex', 'flex-direction:column', 'align-items:center',
      'justify-content:center', 'color:#fff', 'pointer-events:none',
    ].join(';');
    const h = document.createElement('div');
    h.textContent = t;
    h.style.cssText = 'font:700 52px/1.3 "Segoe UI",Roboto,Arial,sans-serif;max-width:80%;text-align:center';
    card.appendChild(h);
    if (s) {
      const sub = document.createElement('div');
      sub.textContent = s;
      sub.style.cssText = 'font:400 28px/1.5 "Segoe UI",Roboto,Arial,sans-serif;margin-top:24px;opacity:0.85;max-width:75%;text-align:center';
      card.appendChild(sub);
    }
    document.body.appendChild(card);
  }, { title, subtitle });
  await page.waitForTimeout(3200);
  await page.evaluate(() => document.getElementById('guide-title-card')?.remove());
}

/** Slow, visible settle pause between actions. */
export async function pause(page: Page, ms = 1800): Promise<void> {
  await page.waitForTimeout(ms);
}

// --- cross-chapter state (product id, order name, listing id, ...) ---------

export function readGuideState(): Record<string, unknown> {
  try {
    return JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  } catch {
    return {};
  }
}

export function writeGuideState(patch: Record<string, unknown>): void {
  const merged = { ...readGuideState(), ...patch };
  fs.mkdirSync(path.dirname(STATE_FILE), { recursive: true });
  fs.writeFileSync(STATE_FILE, JSON.stringify(merged, null, 2));
}

// --- session login (off-camera) ---------------------------------------------

/**
 * Authenticate the page's context via /web/session/authenticate — no login UI
 * frames in the recording. Only chapter 1 shows the login form on camera.
 */
export async function apiLogin(page: Page, login: string, password: string, db: string): Promise<void> {
  const res = await page.request.post('/web/session/authenticate', {
    data: { jsonrpc: '2.0', params: { db, login, password } },
  });
  const body = await res.json();
  if (body.error || !body.result?.uid) {
    throw new Error(`apiLogin failed for ${login}: ${JSON.stringify(body.error || body)}`);
  }
}

// --- Gearment live catalog (for a REAL quotable variant_id + artwork URL) ---

function readDotEnv(): Record<string, string> {
  const envFile = path.resolve(__dirname, '../../..', '.env');
  const out: Record<string, string> = {};
  if (!fs.existsSync(envFile)) return out;
  for (const line of fs.readFileSync(envFile, 'utf8').split('\n')) {
    const t = line.trim();
    if (!t || t.startsWith('#')) continue;
    const eq = t.indexOf('=');
    if (eq < 0) continue;
    out[t.slice(0, eq).trim()] = t.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
  }
  return out;
}

/**
 * Pick the first in-stock catalog item: the GM-prefixed variant_id goes into
 * x_gearment_sku (draft line items key off it — Defect-2026-05-10-02) and the
 * public artwork URL feeds the approved design.file (draft push 400s without
 * a printing option). Mirrors scripts/e2e_flow3b_dropship.py section_0.
 */
export async function fetchGearmentCatalogPick(): Promise<{
  variantId: string; artworkUrl: string; productName: string;
}> {
  const env = readDotEnv();
  const base = (process.env.GEARMENT_API_BASE_URL || env.GEARMENT_API_BASE_URL || '').replace(/\/$/, '');
  const key = process.env.GEARMENT_API_KEY || env.GEARMENT_API_KEY || '';
  const secret = process.env.GEARMENT_API_SECRET || env.GEARMENT_API_SECRET || '';
  if (!base || !key || !secret) throw new Error('GEARMENT_API_* missing from env/.env');
  const res = await fetch(`${base}/api/v3/catalog?limit=1`, {
    headers: { 'X-Gearment-Client-Key': key, 'X-Gearment-Client-Secret': secret },
  });
  if (!res.ok) throw new Error(`Gearment catalog fetch ${res.status}`);
  const item = ((await res.json()).data || [{}])[0];
  const variantId = String(item?.variants?.[0]?.variant_id || '');
  const artworkUrl = String(item?.product_avatar_url || '');
  if (!variantId || !artworkUrl) throw new Error(`catalog item unusable: ${JSON.stringify(item).slice(0, 200)}`);
  return { variantId, artworkUrl, productName: String(item?.product_name || '?') };
}

// --- Etsy publish wizard (on-camera, hardened for slowMo) -------------------

/**
 * Drive the "Publish to Etsy" wizard from an open product form and run
 * draft-only publish. The wizard renders the LEGACY ui-autocomplete dropdown
 * whose open menu intercepts pointer events over the submit button, and
 * fill()'s debounced search RE-OPENS the menu after the option click — wait
 * the debounce out, then Escape closes the menu without clearing selection.
 */
export async function publishDraftOnlyGuide(page: Page, shopName = 'JaHandmadeArt'): Promise<void> {
  await page.locator('button[name="action_open_etsy_publish_wizard"]').first().click();
  const modal = page.locator('.modal-dialog', {
    has: page.locator('.modal-title:has-text("Publish to Etsy")'),
  }).first();
  await modal.waitFor({ state: 'visible', timeout: 10000 });
  await showCaption(page,
    'Cửa sổ đăng bài: chọn Shop rồi nhấn Publish Draft Only — listing sẽ ở dạng Nháp trên Etsy', 4500);
  const shopInput = modal.locator('[name="shop_id"] input').first();
  if ((await shopInput.inputValue()).trim() === '') {
    await shopInput.click();
    await shopInput.fill(shopName);
    const opt = page.locator('a.ui-menu-item-wrapper', { hasText: shopName }).first();
    await opt.waitFor({ state: 'visible', timeout: 8000 });
    await opt.click();
    await page.waitForTimeout(1500);
    const dd = page.locator('.ui-menu-item-wrapper, .o-autocomplete--dropdown-item').first();
    if (await dd.isVisible().catch(() => false)) {
      await shopInput.press('Escape');
      await page.waitForTimeout(300);
    }
    if ((await shopInput.inputValue()).trim() === '') {
      throw new Error('publishDraftOnlyGuide: shop not selected');
    }
  }
  await modal.locator('button[name="action_run_publish_draft_only"]').click();
  await modal.waitFor({ state: 'hidden', timeout: 60000 }); // live Etsy API
}

// --- off-camera RPC through the logged-in browser session ------------------

/**
 * call_kw through the page's authenticated session (same trick as
 * product_form.ts _displayNameInSessionLang). Used for OFF-CAMERA fixture
 * setup between chapters (e.g. seeding the demo incoming order) — never for
 * actions the video is supposed to demonstrate.
 */
export async function callKw<T = unknown>(
  page: Page, model: string, method: string, args: unknown[], kwargs: object = {},
): Promise<T> {
  const res = await page.request.post(`/web/dataset/call_kw/${model}/${method}`, {
    data: { jsonrpc: '2.0', params: { model, method, args, kwargs } },
  });
  const body = await res.json();
  if (body.error) {
    throw new Error(`callKw ${model}.${method}: ${JSON.stringify(body.error.data?.message || body.error)}`);
  }
  return body.result as T;
}
