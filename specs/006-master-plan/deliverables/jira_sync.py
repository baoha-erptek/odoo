"""Sync owner catalog (build_owner_docs.CATALOG_RAW) to JIRA project ESTY.

Topology:
  - 12 Epics  : one per `Nhóm hạng mục` group (GROUPS[0..11])
  - 100 Stories: one per work-item row, parent-linked to its group's Epic

Workflow:
  1. write_epic_drafts()  -> 12 .docs/tasks/ESTY-DRAFT-mp006-epic-*/progress-tracker.md
  2. push_epics()         -> calls push_to_jira.sh per draft; writes epic_key_map.json
  3. write_story_drafts() -> 100 .docs/tasks/ESTY-DRAFT-mp006-story-*/progress-tracker.md
  4. push_stories()       -> calls push_to_jira.sh per draft; writes jira_keys.json
  5. sync_status()        -> transitions stories: Hoàn thành -> Done, Đang làm -> In Progress
  6. rename_drafts()      -> ESTY-DRAFT-mp006-* dirs -> ESTY-<NNN>/

Idempotent: re-running skips drafts already pushed (frontmatter jira_key non-empty).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent
REPO_ROOT = OUT_DIR.parents[2]
TASKS_DIR = REPO_ROOT / ".docs" / "tasks"
PUSH_SCRIPT = REPO_ROOT / ".claude" / "skills" / "jira-create" / "scripts" / "push_to_jira.sh"

JIRA_KEYS_PATH = OUT_DIR / "jira_keys.json"
EPIC_KEY_MAP_PATH = OUT_DIR / "epic_key_map.json"
STATUS_OVERRIDES_PATH = OUT_DIR / "status_overrides.json"

PRIORITY_MAP = {"Cao": "Highest", "Trung bình": "Medium", "Thấp": "Low"}
PHASE_LABEL_MAP = {
    "Giai đoạn 1": "giai-doan-1",
    "Giai đoạn 2": "giai-doan-2",
    "Giai đoạn 3": "giai-doan-3",
}
PUSH_SLEEP_SECONDS = 0.3
TRANSITION_TARGETS = {"Hoàn thành": "Done", "Đang làm": "In Progress"}
TODAY = "2026-05-10"

sys.path.insert(0, str(OUT_DIR))
from build_owner_docs import build_catalog, GROUPS  # noqa: E402


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _strip_diacritics(text: str) -> str:
    nkfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nkfd if not unicodedata.combining(c)).replace("đ", "d").replace("Đ", "D")


def slugify(text: str, max_len: int = 50) -> str:
    s = _strip_diacritics(text).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len].rstrip("-") or "item"


def _strip_group_prefix(group: str) -> str:
    return re.sub(r"^\d+\.\s*", "", group).strip()


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_frontmatter(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.index("---", 3)
    fm_block = text[3:end].strip()
    out = {}
    for line in fm_block.split("\n"):
        if ":" in line:
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip("\"'")
    return out


def _env() -> dict:
    """Load .env into a dict for direct API calls (transitions)."""
    env = {}
    for line in (REPO_ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip().strip("\"'")
    return env


def _curl(method: str, path: str, payload: dict | None = None) -> tuple[int, dict]:
    """Authenticated JIRA REST call. Returns (status_code, response_json)."""
    env = _env()
    base = env["JIRA_SERVER_URL"].rstrip("/")
    user = env["JIRA_USER_EMAIL"]
    token = env["JIRA_API_KEY"]
    args = [
        "curl", "-s", "-w", "\n%{http_code}",
        "-X", method,
        "-u", f"{user}:{token}",
        "-H", "Content-Type: application/json",
    ]
    if payload is not None:
        args += ["-d", json.dumps(payload)]
    args.append(f"{base}{path}")
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    out = result.stdout.rstrip("\n")
    code_idx = out.rfind("\n")
    code = int(out[code_idx + 1:])
    body = out[:code_idx] if code_idx > 0 else ""
    try:
        return code, (json.loads(body) if body else {})
    except json.JSONDecodeError:
        return code, {"_raw": body}


# --------------------------------------------------------------------------
# Stage 1 : Write 12 Epic drafts
# --------------------------------------------------------------------------

def _epic_dir(group_idx: int, group: str) -> Path:
    clean = _strip_group_prefix(group)
    slug = slugify(clean)
    return TASKS_DIR / f"ESTY-DRAFT-mp006-epic-{group_idx:02d}-{slug}"


def write_epic_drafts(catalog: list[dict]) -> None:
    """Write one epic draft per GROUPS entry."""
    rows_by_group: dict[str, list[dict]] = {g: [] for g in GROUPS}
    for item in catalog:
        rows_by_group[item["nhom"]].append(item)

    for idx, group in enumerate(GROUPS, start=1):
        clean = _strip_group_prefix(group)
        rows = rows_by_group[group]
        epic_dir = _epic_dir(idx, group)
        # Skip if already pushed
        progress_md = epic_dir / "progress-tracker.md"
        if progress_md.exists():
            fm = _read_frontmatter(progress_md)
            if fm.get("jira_key"):
                print(f"  [skip] epic {idx:02d} already pushed: {fm['jira_key']}")
                continue
        epic_dir.mkdir(parents=True, exist_ok=True)

        # Body
        story_lines = "\n".join(
            f"- {r['ten_ngan']} ({r['giai_doan']}, {r['muc_uu_tien']}, {r['phong_ban']})"
            for r in rows
        )
        body = f"""# {clean}

Mục tiêu: cung cấp đầy đủ năng lực thuộc nhóm '{clean}' cho hệ thống quản lý đơn hàng đa kênh.

## Phạm vi

### Trong phạm vi

- Tất cả hạng mục công việc thuộc nhóm này (xem danh sách bên dưới).
- Bao trùm cả các cấu hình, dữ liệu mẫu và quy trình thao tác liên quan.

### Ngoài phạm vi

- Các nhóm hạng mục khác (đã có epic riêng).

## Tiêu chí nghiệm thu

- [ ] Tất cả story con đạt trạng thái Done.
- [ ] BA Lead nghiệm thu trên môi trường demo.
- [ ] Hồ sơ đào tạo người dùng đã cập nhật cho nhóm này.

## Danh sách hạng mục

{story_lines}
"""

        frontmatter = f"""---
type: epic
project: ESTY
summary: "MP006 — {clean}"
status: draft
jira_key:
parent:
labels: [mp006]
priority: Medium
created: {TODAY}
---

"""
        progress_md.write_text(frontmatter + body, encoding="utf-8")
        print(f"  [write] epic {idx:02d}: {clean}")


# --------------------------------------------------------------------------
# Stage 2 : Push Epics
# --------------------------------------------------------------------------

def _md_body(md_path: Path) -> str:
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return text
    end = text.index("---", 3) + 3
    return text[end:].strip()


def _body_to_adf(body: str) -> dict:
    """Convert markdown body to Atlassian Document Format."""
    paragraphs = re.split(r"\n\n+", body.strip())
    content = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Heading
        m = re.match(r"^(#{1,6})\s+(.+)$", para)
        if m and "\n" not in para:
            content.append({
                "type": "heading",
                "attrs": {"level": len(m.group(1))},
                "content": [{"type": "text", "text": m.group(2)}],
            })
            continue
        # Bullet list
        lines = [l.rstrip() for l in para.split("\n") if l.strip()]
        if lines and all(re.match(r"^[-*]\s+", l) for l in lines):
            items = []
            for line in lines:
                text_ = re.sub(r"^[-*]\s+(\[[ x]\]\s+)?", "", line)
                items.append({
                    "type": "listItem",
                    "content": [{"type": "paragraph",
                                 "content": [{"type": "text", "text": text_}]}],
                })
            content.append({"type": "bulletList", "content": items})
            continue
        # Default paragraph
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": para}],
        })
    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": " "}]}]
    return {"type": "doc", "version": 1, "content": content}


def _set_frontmatter_field(md_path: Path, field: str, value: str) -> None:
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return
    end = text.index("---", 3)
    fm_lines = text[3:end].strip().split("\n")
    body = text[end:]
    found = False
    new_lines = []
    for line in fm_lines:
        if line.startswith(f"{field}:"):
            new_lines.append(f"{field}: {value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{field}: {value}")
    md_path.write_text("---\n" + "\n".join(new_lines) + "\n" + body, encoding="utf-8")


def _push_md(md_path: Path) -> str | None:
    """Create JIRA issue from draft .md. Returns ESTY-NNN key or None on failure."""
    fm = _read_frontmatter(md_path)
    if fm.get("jira_key"):
        return fm["jira_key"]
    issue_type_map = {"epic": "Epic", "story": "Story", "bug": "Bug", "task": "Task"}
    issue_type = issue_type_map.get(fm.get("type", ""), "Task")
    body = _md_body(md_path)
    payload = {
        "fields": {
            "project": {"key": fm.get("project", "ESTY")},
            "summary": fm.get("summary", "").strip('"').strip("'"),
            "issuetype": {"name": issue_type},
            "description": _body_to_adf(body),
        }
    }
    parent = fm.get("parent", "").strip()
    if parent:
        payload["fields"]["parent"] = {"key": parent}
    # Labels — parse [a, b, c] form
    labels_raw = fm.get("labels", "").strip()
    if labels_raw.startswith("[") and labels_raw.endswith("]"):
        labels = [l.strip() for l in labels_raw[1:-1].split(",") if l.strip()]
        if labels:
            payload["fields"]["labels"] = labels
    # Priority
    priority = fm.get("priority", "").strip()
    if priority:
        payload["fields"]["priority"] = {"name": priority}

    code, response = _curl("POST", "/rest/api/3/issue", payload)
    if code != 201:
        print(f"  [FAIL] {md_path.parent.name}: HTTP {code}\n    {response}")
        return None
    key = response.get("key")
    if key:
        _set_frontmatter_field(md_path, "jira_key", key)
        _set_frontmatter_field(md_path, "status", "pushed")
    return key


def push_epics() -> dict[str, str]:
    """Push each epic draft. Return mapping {nhom -> ESTY-NNN}."""
    epic_map = _read_json(EPIC_KEY_MAP_PATH)
    for idx, group in enumerate(GROUPS, start=1):
        if epic_map.get(group):
            print(f"  [skip] {group} already mapped to {epic_map[group]}")
            continue
        epic_dir = _epic_dir(idx, group)
        md = epic_dir / "progress-tracker.md"
        if not md.exists():
            print(f"  [WARN] missing draft: {md}")
            continue
        key = _push_md(md)
        if key:
            epic_map[group] = key
            _write_json(EPIC_KEY_MAP_PATH, epic_map)
            print(f"  [push] epic {idx:02d} {group[:30]:30} -> {key}")
        time.sleep(PUSH_SLEEP_SECONDS)
    return epic_map


# --------------------------------------------------------------------------
# Stage 3 : Write 100 Story drafts (with parent linkage)
# --------------------------------------------------------------------------

def _story_dir(stt: int, ten_ngan: str) -> Path:
    return TASKS_DIR / f"ESTY-DRAFT-mp006-story-{stt:03d}-{slugify(ten_ngan, 40)}"


def write_story_drafts(catalog: list[dict], epic_map: dict[str, str]) -> None:
    for item in catalog:
        story_dir = _story_dir(item["stt"], item["ten_ngan"])
        progress_md = story_dir / "progress-tracker.md"
        if progress_md.exists():
            fm = _read_frontmatter(progress_md)
            if fm.get("jira_key"):
                continue  # already pushed
        story_dir.mkdir(parents=True, exist_ok=True)
        parent_key = epic_map.get(item["nhom"], "")
        priority = PRIORITY_MAP.get(item["muc_uu_tien"], "Medium")
        phase_label = PHASE_LABEL_MAP.get(item["giai_doan"], "")
        labels = ["mp006"]
        if phase_label:
            labels.append(phase_label)
        labels_yaml = ", ".join(labels)

        body_parts = [
            f"# {item['ten_ngan']}",
            "",
            "## Mô tả ngắn",
            "",
            item["mo_ta"],
            "",
            "## Thông tin nghiệp vụ",
            "",
            f"- Phòng ban đề xuất: {item['phong_ban']}",
            f"- Mức ưu tiên: {item['muc_uu_tien']}",
            f"- Giai đoạn: {item['giai_doan']}",
            f"- Trạng thái hiện tại: {item['trang_thai']}",
        ]
        if item["ghi_chu"]:
            body_parts.append(f"- Ghi chú: {item['ghi_chu']}")
        body_parts += [
            "",
            "## Tiêu chí nghiệm thu",
            "",
            "- [ ] BA Lead xác nhận hạng mục hoạt động đúng trên môi trường demo.",
            "- [ ] Hồ sơ đào tạo / hướng dẫn sử dụng đã cập nhật.",
        ]
        body = "\n".join(body_parts) + "\n"

        # Clean summary — must not contain double quotes inside
        safe_summary = item["ten_ngan"].replace('"', "'")
        frontmatter = f"""---
type: story
project: ESTY
summary: "{safe_summary}"
status: draft
jira_key:
parent: {parent_key}
labels: [{labels_yaml}]
priority: {priority}
created: {TODAY}
---

"""
        progress_md.write_text(frontmatter + body, encoding="utf-8")


# --------------------------------------------------------------------------
# Stage 4 : Push Stories
# --------------------------------------------------------------------------

def push_stories(catalog: list[dict]) -> dict[str, str]:
    """Push each story draft. Update jira_keys.json (ten_ngan -> ESTY-NNN)."""
    keys = _read_json(JIRA_KEYS_PATH)
    for item in catalog:
        if keys.get(item["ten_ngan"]):
            continue
        story_dir = _story_dir(item["stt"], item["ten_ngan"])
        md = story_dir / "progress-tracker.md"
        if not md.exists():
            print(f"  [WARN] missing draft: {md}")
            continue
        key = _push_md(md)
        if key:
            keys[item["ten_ngan"]] = key
            _write_json(JIRA_KEYS_PATH, keys)
            print(f"  [push] story {item['stt']:03d} {item['ten_ngan'][:35]:35} -> {key}")
        time.sleep(PUSH_SLEEP_SECONDS)
    return keys


# --------------------------------------------------------------------------
# Stage 5 : Status sync (Hoàn thành -> Done, Đang làm -> In Progress)
# --------------------------------------------------------------------------

def _get_transitions(issue_key: str) -> list[dict]:
    code, body = _curl("GET", f"/rest/api/3/issue/{issue_key}/transitions")
    if code != 200:
        return []
    return body.get("transitions", [])


def sync_status(catalog: list[dict], story_keys: dict[str, str]) -> None:
    """Move each pushed story to its target status if not already there."""
    for item in catalog:
        target_status = TRANSITION_TARGETS.get(item["trang_thai"])
        if not target_status:
            continue
        issue_key = story_keys.get(item["ten_ngan"])
        if not issue_key:
            continue
        # Get current status
        code, body = _curl("GET", f"/rest/api/3/issue/{issue_key}?fields=status")
        if code != 200:
            print(f"  [WARN] cannot read {issue_key}: HTTP {code}")
            continue
        current = body.get("fields", {}).get("status", {}).get("name", "")
        if current == target_status:
            continue
        # Find transition
        transitions = _get_transitions(issue_key)
        match = next(
            (t for t in transitions if t.get("to", {}).get("name") == target_status),
            None,
        )
        if not match:
            print(f"  [WARN] no transition to {target_status!r} for {issue_key} (current={current})")
            continue
        code, _ = _curl(
            "POST",
            f"/rest/api/3/issue/{issue_key}/transitions",
            {"transition": {"id": match["id"]}},
        )
        if code in (200, 204):
            print(f"  [transition] {issue_key} {current} -> {target_status}")
        else:
            print(f"  [FAIL] transition {issue_key}: HTTP {code}")
        time.sleep(PUSH_SLEEP_SECONDS)


# --------------------------------------------------------------------------
# Stage 6 : Rename ESTY-DRAFT-* directories to ESTY-<KEY>/
# --------------------------------------------------------------------------

def rename_drafts() -> None:
    """Rename pushed ESTY-DRAFT-mp006-* directories to ESTY-<NNN>/."""
    for d in sorted(TASKS_DIR.glob("ESTY-DRAFT-mp006-*")):
        if not d.is_dir():
            continue
        md = d / "progress-tracker.md"
        if not md.exists():
            continue
        fm = _read_frontmatter(md)
        key = fm.get("jira_key")
        if not key:
            continue
        target = TASKS_DIR / key
        if target.exists():
            print(f"  [skip] target exists: {target.name}")
            continue
        d.rename(target)
        print(f"  [rename] {d.name} -> {target.name}")


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main() -> int:
    catalog = build_catalog()
    print(f"Catalog rows: {len(catalog)}")
    print(f"Groups (epics): {len(GROUPS)}")

    print("\n[1/6] Writing epic drafts ...")
    write_epic_drafts(catalog)

    print("\n[2/6] Pushing epics ...")
    epic_map = push_epics()
    print(f"  epic_map: {len(epic_map)}/{len(GROUPS)} groups mapped")

    print("\n[3/6] Writing story drafts ...")
    write_story_drafts(catalog, epic_map)

    print("\n[4/6] Pushing stories ...")
    story_keys = push_stories(catalog)
    print(f"  story_keys: {len(story_keys)}/{len(catalog)} stories mapped")

    print("\n[5/6] Syncing status (Hoàn thành -> Done, Đang làm -> In Progress) ...")
    sync_status(catalog, story_keys)

    print("\n[6/6] Renaming draft directories ...")
    rename_drafts()

    print("\nDone. Re-run python3 build_owner_docs.py to materialize JIRA keys in xlsx col J.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
