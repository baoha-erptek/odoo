#!/usr/bin/env python3
"""Push docs/owner Markdown files to Confluence Cloud space HEP.

Idempotent: detects existing pages by title (within the space) and updates them.
Uses same Atlassian Cloud token as JIRA_API_KEY (tenant-wide).

Pages pushed (5):
  README.md            -> "Tài liệu Chủ dự án — Index"           (root, parent of others)
  BRD_VN.md            -> "BRD — Hệ thống quản lý đơn hàng Etsy đa kênh"
  SRS_VN.md            -> "SRS — 7 Epic / 55 Story"
  STATUS_VN.md         -> "Dashboard tình hình dự án"
  JIRA_SYNC_REPORT.md  -> "Báo cáo sync Jira"

Reads creds from .env at repo root.
"""
from __future__ import annotations
import os
import re
import sys
import json
import time
import base64
import html
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENV = REPO / ".env"
DOCS = REPO / "docs/owner"


def load_env() -> dict:
    env = {}
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("'").strip('"')
    return env


ENV_VARS = load_env()
JIRA_BASE = ENV_VARS["JIRA_SERVER_URL"].rstrip("/")
CONFLUENCE_BASE = ENV_VARS.get("CONFLUENCE_BASE_URL", f"{JIRA_BASE}/wiki").rstrip("/")
SPACE_KEY = ENV_VARS.get("CONFLUENCE_SPACE_KEY", "HEP")
JIRA_EMAIL = ENV_VARS["JIRA_USER_EMAIL"]
JIRA_KEY = ENV_VARS["JIRA_API_KEY"]
AUTH = "Basic " + base64.b64encode(f"{JIRA_EMAIL}:{JIRA_KEY}".encode()).decode()


def api(method: str, path: str, data: dict | None = None, base: str | None = None):
    url = f"{base or CONFLUENCE_BASE}{path}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": AUTH,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as resp:
            text = resp.read().decode() or "{}"
            try:
                return resp.status, json.loads(text)
            except json.JSONDecodeError:
                return resp.status, text
    except urllib.error.HTTPError as e:
        text = e.read().decode()
        try:
            return e.code, json.loads(text)
        except json.JSONDecodeError:
            return e.code, text


# ----- Markdown -> Confluence storage (XHTML) -----

_INLINE_CODE = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(text: str) -> str:
    """Apply inline markdown formatting after HTML escape."""
    out = html.escape(text, quote=False)
    out = _INLINE_CODE.sub(lambda m: f"<code>{m.group(1)}</code>", out)
    out = _BOLD.sub(lambda m: f"<strong>{m.group(1)}</strong>", out)
    out = _ITALIC.sub(lambda m: f"<em>{m.group(1)}</em>", out)
    out = _LINK.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', out)
    return out


def md_to_storage(md: str) -> str:
    """Convert markdown to Confluence storage-format XHTML.

    Supports: H1-H6, paragraphs, bullet/ordered lists, tables, hr, blockquotes, code blocks.
    """
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Blank line
        if not stripped:
            i += 1
            continue

        # Horizontal rule
        if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", stripped):
            out.append("<hr/>")
            i += 1
            continue

        # Headings
        m = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{_inline(m.group(2).strip())}</h{level}>")
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            buf: list[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            body = "\n".join(buf)
            esc = html.escape(body)
            if lang:
                out.append(
                    f'<ac:structured-macro ac:name="code">'
                    f'<ac:parameter ac:name="language">{html.escape(lang)}</ac:parameter>'
                    f'<ac:plain-text-body><![CDATA[{body}]]></ac:plain-text-body>'
                    f'</ac:structured-macro>'
                )
            else:
                out.append(f"<pre><code>{esc}</code></pre>")
            continue

        # Blockquote
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f"<blockquote><p>{_inline(' '.join(buf))}</p></blockquote>")
            continue

        # Table (pipe-separated). Header row followed by separator |---|---|
        if "|" in stripped and i + 1 < n and re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", lines[i + 1]):
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # skip header + separator
            rows = []
            while i < n and "|" in lines[i].strip() and lines[i].strip():
                row_cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                rows.append(row_cells)
                i += 1
            ths = "".join(f"<th>{_inline(c)}</th>" for c in header_cells)
            trs = "".join(
                "<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in row) + "</tr>"
                for row in rows
            )
            out.append(f"<table><thead><tr>{ths}</tr></thead><tbody>{trs}</tbody></table>")
            continue

        # Bullet list
        if re.match(r"^\s*[-*+]\s+", line):
            items = []
            while i < n and re.match(r"^\s*[-*+]\s+", lines[i]):
                content = re.sub(r"^\s*[-*+]\s+", "", lines[i]).strip()
                items.append(f"<li>{_inline(content)}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Numbered list
        if re.match(r"^\s*\d+\.\s+", line):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                content = re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip()
                items.append(f"<li>{_inline(content)}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Paragraph (gather consecutive non-blank, non-special lines)
        para: list[str] = [stripped]
        i += 1
        while i < n:
            ln = lines[i]
            s = ln.strip()
            if not s:
                break
            if re.match(r"^#{1,6}\s+", s):
                break
            if s.startswith("```") or s.startswith(">"):
                break
            if re.match(r"^\s*[-*+]\s+", ln) or re.match(r"^\s*\d+\.\s+", ln):
                break
            if "|" in s and i + 1 < n and re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", lines[i + 1]):
                break
            if re.fullmatch(r"-{3,}|\*{3,}|_{3,}", s):
                break
            para.append(s)
            i += 1
        out.append(f"<p>{_inline(' '.join(para))}</p>")

    return "\n".join(out)


# ----- Confluence operations -----

def get_space_id(key: str) -> str | None:
    code, data = api("GET", f"/api/v2/spaces?keys={key}")
    if code != 200 or not data.get("results"):
        print(f"  !! space lookup failed: {code} {data}", file=sys.stderr)
        return None
    return data["results"][0]["id"]


def find_page(space_id: str, title: str) -> dict | None:
    """Return page dict {id, version.number, title} if found, else None."""
    q = urllib.parse.quote(title)
    code, data = api("GET", f"/api/v2/spaces/{space_id}/pages?title={q}&body-format=storage&limit=10")
    if code != 200:
        return None
    for p in data.get("results", []):
        if p.get("title", "").strip() == title.strip():
            return p
    return None


def create_page(space_id: str, title: str, xhtml: str, parent_id: str | None = None) -> dict | None:
    payload = {
        "spaceId": space_id,
        "status": "current",
        "title": title,
        "body": {"representation": "storage", "value": xhtml},
    }
    if parent_id:
        payload["parentId"] = parent_id
    code, data = api("POST", "/api/v2/pages", payload)
    if code in (200, 201):
        return data
    print(f"  !! create failed ({code}): {str(data)[:500]}", file=sys.stderr)
    return None


def update_page(page_id: str, title: str, xhtml: str, current_version: int) -> dict | None:
    payload = {
        "id": page_id,
        "status": "current",
        "title": title,
        "body": {"representation": "storage", "value": xhtml},
        "version": {"number": current_version + 1, "message": "Delta sync 2026-05-25"},
    }
    code, data = api("PUT", f"/api/v2/pages/{page_id}", payload)
    if code in (200, 201):
        return data
    print(f"  !! update failed ({code}): {str(data)[:500]}", file=sys.stderr)
    return None


# ----- Page manifest -----

PAGES = [
    # (filename, title, is_root)
    ("README.md", "Tài liệu Chủ dự án — Index", True),
    ("BRD_VN.md", "BRD — Hệ thống quản lý đơn hàng Etsy đa kênh", False),
    ("SRS_VN.md", "SRS — 7 Epic / 55 Story", False),
    ("STATUS_VN.md", "Dashboard tình hình dự án", False),
    ("JIRA_SYNC_REPORT.md", "Báo cáo sync Jira", False),
]


def main():
    dry_run = "--dry-run" in sys.argv
    print("=" * 60)
    print(f"Confluence sync → space {SPACE_KEY}")
    print(f"Base: {CONFLUENCE_BASE}")
    print("=" * 60)

    if dry_run:
        for fname, title, is_root in PAGES:
            path = DOCS / fname
            md = path.read_text()
            xhtml = md_to_storage(md)
            print(f"\n--- {fname} → '{title}' ({'root' if is_root else 'child'}) ---")
            print(f"  md bytes:    {len(md)}")
            print(f"  xhtml bytes: {len(xhtml)}")
            print(f"  xhtml head:  {xhtml[:200]!r}")
        return

    space_id = get_space_id(SPACE_KEY)
    if not space_id:
        print(f"!! cannot find space {SPACE_KEY}; aborting", file=sys.stderr)
        sys.exit(2)
    print(f"Space {SPACE_KEY} → id {space_id}")

    results = {"space_id": space_id, "pages": []}
    root_id: str | None = None

    for fname, title, is_root in PAGES:
        path = DOCS / fname
        if not path.exists():
            print(f"  !! missing: {path}", file=sys.stderr)
            continue
        md = path.read_text()
        xhtml = md_to_storage(md)
        print(f"\n--- {fname} → '{title}'  ({len(xhtml)} bytes XHTML) ---")
        existing = find_page(space_id, title)
        if existing:
            page_id = existing["id"]
            ver = existing.get("version", {}).get("number", 1)
            updated = update_page(page_id, title, xhtml, ver)
            if updated:
                print(f"  updated {page_id} → v{ver+1}")
                if is_root:
                    root_id = page_id
                results["pages"].append({
                    "file": fname, "title": title, "id": page_id,
                    "version": ver + 1, "action": "updated",
                    "url": f"{CONFLUENCE_BASE}/spaces/{SPACE_KEY}/pages/{page_id}",
                })
        else:
            parent_id = root_id if (not is_root and root_id) else None
            created = create_page(space_id, title, xhtml, parent_id)
            if created:
                page_id = created["id"]
                print(f"  created {page_id}  (parent={parent_id or 'space root'})")
                if is_root:
                    root_id = page_id
                results["pages"].append({
                    "file": fname, "title": title, "id": page_id,
                    "version": 1, "action": "created",
                    "url": f"{CONFLUENCE_BASE}/spaces/{SPACE_KEY}/pages/{page_id}",
                })
        time.sleep(0.3)

    out_path = REPO / ".docs/tasks/_owner_confluence_2026-05-25.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nMapping saved to {out_path}")

    print("\nPage URLs:")
    for p in results["pages"]:
        print(f"  {p['file']:25s} → {p['url']}")

    print("\nDONE.")


if __name__ == "__main__":
    main()
