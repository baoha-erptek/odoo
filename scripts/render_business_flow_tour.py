"""Render docs/owner/business-flows/*.md to *.rendered.html for the owner tour.

Pipeline: python-markdown with codehilite + tables + fenced_code + toc.
CSS: Crimson Pro (serif) + JetBrains Mono (mono), paper/ink palette.

Usage (re-render all 5 flows + README + tour index):
    python3 scripts/render_business_flow_tour.py

Usage (one file):
    python3 scripts/render_business_flow_tour.py docs/owner/business-flows/flow-1-tao-san-pham.md

Output file is sibling of input with `.rendered.html` suffix. Relative image
paths (`./screenshots/flow-1/01-form-general.png`) are preserved — the browser
resolves them against the rendered file's directory, which is the same as the
source MD, so screenshots committed under `screenshots/flow-X/` Just Work.
"""
from __future__ import annotations

import sys
from pathlib import Path

import markdown

REPO_ROOT = Path(__file__).resolve().parent.parent
FLOWS_DIR = REPO_ROOT / "docs" / "owner" / "business-flows"

CSS = """
:root {
  --ink: #1a1814;
  --paper: #faf8f3;
  --rule: #d8d2c5;
  --accent: #8b3a1f;
  --muted: #6b665c;
  --code-bg: #f1ede4;
}
* { box-sizing: border-box; }
body {
  font-family: 'Crimson Pro', Georgia, 'Times New Roman', serif;
  font-size: 18px;
  line-height: 1.65;
  color: var(--ink);
  background: var(--paper);
  margin: 0;
  padding: 2.5rem 1.5rem 4rem;
}
main {
  max-width: 760px;
  margin: 0 auto;
}
h1, h2, h3, h4 {
  font-weight: 600;
  letter-spacing: -0.01em;
  margin-top: 2rem;
  line-height: 1.25;
}
h1 { font-size: 2.2rem; border-bottom: 1px solid var(--rule); padding-bottom: 0.5rem; }
h2 { font-size: 1.6rem; color: var(--accent); }
h3 { font-size: 1.25rem; }
a { color: var(--accent); text-decoration: underline; text-decoration-thickness: 1px; }
hr { border: 0; border-top: 1px solid var(--rule); margin: 2rem 0; }
blockquote {
  margin: 1.2rem 0;
  padding: 0.6rem 1.2rem;
  border-left: 3px solid var(--accent);
  background: rgba(139, 58, 31, 0.04);
  color: var(--muted);
}
blockquote img { border: 1px solid var(--rule); border-radius: 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
img { max-width: 100%; height: auto; }
code, pre, kbd, samp {
  font-family: 'JetBrains Mono', 'SFMono-Regular', Menlo, Consolas, monospace;
  font-size: 0.88em;
}
code { background: var(--code-bg); padding: 0.1em 0.35em; border-radius: 3px; }
pre {
  background: var(--code-bg);
  padding: 1rem;
  overflow-x: auto;
  border-radius: 4px;
  border: 1px solid var(--rule);
}
pre code { background: transparent; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 1.2rem 0; }
th, td { padding: 0.5rem 0.8rem; border-bottom: 1px solid var(--rule); text-align: left; }
th { font-weight: 600; color: var(--accent); }
ul, ol { padding-left: 1.5rem; }
li { margin: 0.25rem 0; }
"""

HEAD = """<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Crimson+Pro:wght@400;600&family=JetBrains+Mono:wght@400;500&display=swap">
<style>{css}</style>
</head>
<body><main>
"""
FOOT = "</main></body></html>\n"

EXTENSIONS = ["extra", "tables", "fenced_code", "toc", "sane_lists"]


def render_one(src: Path) -> Path:
    text = src.read_text(encoding="utf-8")
    title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), src.stem)
    body_html = markdown.markdown(text, extensions=EXTENSIONS, output_format="html5")
    out = src.with_suffix(".rendered.html")
    out.write_text(HEAD.format(title=title, css=CSS) + body_html + FOOT, encoding="utf-8")
    return out


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        targets = [Path(p) for p in argv[1:]]
    else:
        targets = sorted(FLOWS_DIR.glob("flow-*.md")) + [FLOWS_DIR / "README.md"]
    for src in targets:
        if not src.exists():
            print(f"skip: {src} (not found)")
            continue
        out = render_one(src)
        print(f"rendered: {src.name} -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
