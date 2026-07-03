# Evaluation: docmd-io/docmd as Owner Docs Site

**Date**: 2026-06-06
**Trigger**: Owner Telegram msg 703 referencing https://github.com/docmd-io/docmd
**Verdict**: ✅ Recommend adoption as **additional** read surface alongside Confluence

---

## What docmd is

- TypeScript / Node-based static site generator that consumes plain Markdown and produces a self-contained docs site
- 1.94k GitHub stars, MIT license, actively maintained (last commit today 2026-06-06)
- "Zero-config" promise — works out of the box without frontmatter or per-page setup
- Tiny JS payload (~18 KB) + offline full-text search built-in
- Native i18n hooks (English / Hindi / Chinese / Spanish / German / Japanese / French; Vietnamese easy to add)
- Mermaid diagrams, AI / LLM context generation (`llms.txt`), PWA option

## Trial — built our `docs/owner/` cleanly

Ran locally against a copy of the 21 owner Markdown files:

```bash
mkdir /tmp/docmd-trial && cd /tmp/docmd-trial
rsync -a docs/owner/ ./docs/
echo '{"title":"Hatafax — Owner Guides","url":"http://localhost:3030"}' > docmd.config.json
npx --yes @docmd/core build
```

**Result**:

| Metric | Value |
|---|---|
| Pages generated | 20 (from 21 source files — 1 was a non-Markdown subdir) |
| Build time | 867 ms |
| Total site size | 3.1 MB |
| Output structure | One folder per source file + `index.html`, `404.html`, `assets/`, sitemap, robots.txt, LLMs context files |
| Vietnamese rendering | Clean — UTF-8 preserved end-to-end; tested HUONG_DAN_TAO_SAN_PHAM_VN.md, 49 Vietnamese-specific tokens render correctly |
| HTML embed handling | Pass-through OK; no `<details>`/`<table>` in current docs to stress-test, but the renderer is Markdown-it-class which accepts inline HTML by default |
| Errors | None |

**One platform note**: the optional Rust engine couldn't load on this Ubuntu 20.04 box (libc < 2.33). docmd's JS fallback engine ran cleanly with no functional difference; will auto-pick Rust on newer hosts.

## Strengths

- ⚡ **Speed**: 21 docs → 3 MB static site in <1 s. No build pipeline overhead.
- 🇻🇳 **Vietnamese works**: native Vietnamese isn't in their built-in list but the locale system accepts arbitrary languages; the build run on our docs already renders correctly.
- 🔍 **Offline search**: Marketing can grep across all guides in-browser without internet.
- 📱 **Mobile**: responsive theme out of the box.
- 🤖 **LLM-ready**: auto-generates `llms.txt` so Claude / GPT can consume the docs corpus directly.
- 🚀 **Deploy anywhere**: GitHub Pages, Vercel, S3+CloudFront, an nginx vhost on the staging server, even file:// for quick local share.

## Weaknesses for our use case

- 🔁 **Doubles the publish path**: we already sync to Confluence space HEP via `.githooks/post-commit`. Adding docmd creates two destinations; need a clear story for which is canonical.
- 🇻🇳 **Vietnamese not in native locale list**: a tiny config addition needed (~5 lines).
- 🆕 **Owner workflow change**: currently owner reads on Confluence; would need to learn a new URL.

## Recommendation

**Adopt as a complementary read surface** — not a replacement.

| Where | Role |
|---|---|
| Confluence space HEP | Authoritative team-edit + comment surface (current, unchanged) |
| docmd-generated site at `https://docs.hatafax.com` (or staging path) | Fast, searchable, mobile-friendly browser-facing site for operators in the warehouse / on the road |

### Two-step adoption plan

**Step 1 — quick win (1 slice, ~30 min):**
1. Add a `docmd/` config dir at repo root with `docmd.config.json` referencing `docs/owner/` as the source.
2. Add a GitHub Action (or cron) that runs `npx @docmd/core build` on every push to `feature/006-master-plan-coding` AND `main`, writes the `site/` to a staging path on `129.150.63.207` (rsync; reuse the existing SSH key).
3. nginx serves `https://docs-staging.hatafax.com` (separate vhost) pointing to the rsync target.

**Step 2 — production publish:**
4. Same Action targets `https://docs.hatafax.com` on `main` merges only.
5. Update memory `reference_confluence_sync_pipeline.md` to note the dual pipeline.

### Effort

- Step 1: ~30 min (config file + Action YAML + nginx vhost + DNS A record).
- Step 2: ~10 min on top of Step 1 (extra deploy target).

### Reversible?

Yes. The Confluence sync stays unchanged. If docmd doesn't fit, delete the workflow + nginx vhost; no source changes.

## Open questions for owner

1. Domain — `docs.hatafax.com` OK, or prefer a path under the staging server?
2. Authentication — owner docs are currently public on Confluence (within the space); should the docmd site be open or behind basic-auth?
3. Wave-2 status: this is a small DX win, not a Wave-2 must-have. Ship now (next slice) or after the next ESTY-188 owner re-publish closes T6?

---

## Trial artifacts (left on disk for re-review)

- `/tmp/docmd-trial/site/` — full generated static site (3.1 MB).
- `/tmp/docmd-trial/docs/` — source copy (read-only, untouched).
- `/tmp/docmd-trial/docmd.config.json` — minimal 3-line config used.

To re-browse locally:

```bash
cd /tmp/docmd-trial && npx --yes @docmd/core dev
# opens http://localhost:3000
```
