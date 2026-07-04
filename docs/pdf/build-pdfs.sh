#!/usr/bin/env bash
#
# Build docs/pdf/docs_sds.pdf and docs/pdf/docs_srs.pdf with rendered mermaid diagrams.
#
# Why this exists: make-pdf (gstack) has no mermaid support and passes HTML *inline*
# to the browser, so ```mermaid fences render as raw code and relative/file:// image
# paths don't resolve. This script pre-renders each mermaid block to SVG with mmdc,
# then inlines every SVG as a base64 data-URI inside a <figure> (so make-pdf's
# `figure img { max-width:100% }` rule keeps it on the page). SVG uses htmlLabels:false
# so text is <text> (not <foreignObject>), which renders reliably inside an <img>.
#
# Usage: bash docs/pdf/build-pdfs.sh
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
DOCS="$ROOT/docs"
OUT="$DOCS/pdf"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT

# --- resolve make-pdf binary (same order as the skill) ---
P="${MAKE_PDF_BIN:-}"
[ -z "$P" ] && [ -x "$ROOT/.claude/skills/gstack/make-pdf/dist/pdf" ] && P="$ROOT/.claude/skills/gstack/make-pdf/dist/pdf"
[ -z "$P" ] && P="$HOME/.claude/skills/gstack/make-pdf/dist/pdf"
[ -x "$P" ] || { echo "ERROR: make-pdf binary not found (run ./setup in the gstack repo)"; exit 1; }

# --- chrome for mmdc's puppeteer + no-sandbox (headless server) ---
export PUPPETEER_EXECUTABLE_PATH="${PUPPETEER_EXECUTABLE_PATH:-$(command -v google-chrome-stable || command -v google-chrome || echo /snap/bin/chromium)}"
printf '{"args":["--no-sandbox","--disable-gpu"]}\n' > "$BUILD/puppeteer.json"
# htmlLabels:false -> SVG <text> (renders inside <img>); useMaxWidth keeps diagrams responsive.
printf '{"flowchart":{"htmlLabels":false,"useMaxWidth":true},"er":{"useMaxWidth":true},"sequence":{"useMaxWidth":true,"htmlLabels":false}}\n' > "$BUILD/mermaid.json"

build_set() {
  local name="$1"; shift
  local files=("$@")
  local src="$BUILD/$name.md"
  : > "$src"
  for f in "${files[@]}"; do
    cat "$DOCS/$name/$f" >> "$src"
    printf '\n\n' >> "$src"
  done

  echo ">> [$name] rendering mermaid with mmdc ..."
  npx --no-install @mermaid-js/mermaid-cli \
      -i "$src" -o "$BUILD/$name.rendered.md" \
      -e svg -b transparent \
      -p "$BUILD/puppeteer.json" -c "$BUILD/mermaid.json"

  echo ">> [$name] inlining SVGs as data-URIs (wide diagrams -> landscape pages) ..."
  python3 - "$BUILD/$name.rendered.md" <<'PY'
import base64, os, re, sys
md_path = sys.argv[1]
base = os.path.dirname(md_path)
text = open(md_path, encoding="utf-8").read()

# Diagrams wider than this (width/height) read too small in a portrait column,
# so they go on their own landscape page (10in usable width vs 6.5in portrait).
WIDE_ASPECT = 2.4

# mmdc emits: ![diagram](name.rendered-1.svg)  (path relative to the output md)
img_re = re.compile(r'!\[[^\]]*\]\(([^)]+\.svg)\)')

def svg_aspect(svg_text):
    m = re.search(r'viewBox="[\d.\-]+ [\d.\-]+ ([\d.]+) ([\d.]+)"', svg_text[:4000])
    if m:
        w, h = float(m.group(1)), float(m.group(2))
        return (w / h) if h else 1.0
    return 1.0

n_wide = 0
def repl(m):
    global n_wide
    rel = m.group(1)
    svg_path = rel if os.path.isabs(rel) else os.path.join(base, rel)
    svg = open(svg_path, encoding="utf-8").read()
    b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    cls = ""
    if svg_aspect(svg) >= WIDE_ASPECT:
        cls = ' class="wide"'
        n_wide += 1
    return (f'<figure{cls}><img alt="diagram" '
            f'src="data:image/svg+xml;base64,{b64}"></figure>')

new, n = img_re.subn(repl, text)

# Named landscape page for wide figures. make-pdf runs Paged.js, which honors
# named @page rules; its HTML sanitizer keeps <style> (only strips script/etc).
# Keep this block quote-free so smartypants/entity-decoding can't mangle the CSS.
style = (
    "<style>\n"
    "@page landscapeFig { size: letter landscape; margin: 0.5in; }\n"
    "figure { margin: 12pt 0; }\n"
    "figure img { display:block; max-width:100%; max-height:8.7in; height:auto; margin:0 auto; }\n"
    "figure.wide { page: landscapeFig; break-before: page; }\n"
    "figure.wide img { max-height:6.7in; }\n"
    "</style>\n\n"
)
open(md_path, "w", encoding="utf-8").write(style + new)
print(f"   inlined {n} diagram(s); {n_wide} routed to landscape pages")
PY

  echo ">> [$name] generating PDF ..."
  # NOTE: options MUST come after positionals — make-pdf's parser treats
  # `--toc <next>` greedily and would eat the input path as --toc's value.
  "$P" generate "$BUILD/$name.rendered.md" "$OUT/docs_$name.pdf" --toc
  echo ">> [$name] done -> $OUT/docs_$name.pdf"
}

# Order per docs/<set>/README.md (README index files are excluded).
build_set sds 01-architecture.md 02a-data-model.md 02b-data-model.md 03-integrations.md 04a-sequence-flows.md 04b-sequence-flows.md 05-security.md
build_set srs 01-overview.md 02-channel-etsy.md 03-orders-fulfillment.md 04-catalog-listings.md 05-operations-admin.md

echo "All PDFs rebuilt."
