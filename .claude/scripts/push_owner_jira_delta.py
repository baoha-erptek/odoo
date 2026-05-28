#!/usr/bin/env python3
"""Delta sync 2026-05-25 — transition 3 Stories to Done + create Epic 7 with 7 Stories.

Idempotent: detects existing issues by summary before creating. Run once.

Reads creds from .env at repo root.
"""
from __future__ import annotations
import os
import sys
import json
import time
import base64
import urllib.request
import urllib.error
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ENV = REPO / ".env"


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
JIRA_PROJECT = ENV_VARS["JIRA_PROJECT_KEY"]
JIRA_EMAIL = ENV_VARS["JIRA_USER_EMAIL"]
JIRA_KEY = ENV_VARS["JIRA_API_KEY"]
AUTH = "Basic " + base64.b64encode(f"{JIRA_EMAIL}:{JIRA_KEY}".encode()).decode()


def api(method: str, path: str, data: dict | None = None):
    url = f"{JIRA_BASE}{path}"
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


def adf_from_markdown(md: str) -> dict:
    """Minimal markdown -> Atlassian Document Format (paragraphs only)."""
    paragraphs = [p.strip() for p in md.strip().split("\n\n") if p.strip()]
    content = [
        {"type": "paragraph", "content": [{"type": "text", "text": p.replace("\n", " ")}]}
        for p in paragraphs
    ]
    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": " "}]}]
    return {"type": "doc", "version": 1, "content": content}


def get_transitions(key: str) -> dict:
    code, data = api("GET", f"/rest/api/3/issue/{key}/transitions")
    if code != 200:
        return {}
    return {t["to"]["name"]: t["id"] for t in data.get("transitions", [])}


def transition_to(key: str, status_name: str) -> bool:
    trans = get_transitions(key)
    tid = trans.get(status_name)
    if not tid:
        print(f"  {key}: no transition to {status_name}; available={list(trans.keys())}", file=sys.stderr)
        return False
    code, _ = api("POST", f"/rest/api/3/issue/{key}/transitions", {"transition": {"id": tid}})
    return code in (204, 200)


def find_issue_by_summary(summary: str) -> str | None:
    jql = f'project = {JIRA_PROJECT} AND summary ~ "{summary[:60]}"'
    code, data = api("GET", f"/rest/api/3/search?jql={urllib.parse.quote(jql)}&fields=summary&maxResults=20")
    if code != 200:
        return None
    for issue in data.get("issues", []):
        if issue["fields"]["summary"].strip() == summary.strip():
            return issue["key"]
    return None


def create_issue(summary: str, body_md: str, issuetype: str,
                 parent: str | None = None, priority: str | None = None,
                 labels: list[str] | None = None) -> str | None:
    fields = {
        "project": {"key": JIRA_PROJECT},
        "summary": summary[:250],
        "issuetype": {"name": issuetype},
        "description": adf_from_markdown(body_md),
    }
    if parent:
        fields["parent"] = {"key": parent}
    if priority:
        fields["priority"] = {"name": priority}
    if labels:
        fields["labels"] = labels
    code, data = api("POST", "/rest/api/3/issue", {"fields": fields})
    if code == 201:
        return data["key"]
    print(f"  FAIL ({code}): {data}", file=sys.stderr)
    if priority and "priority" in str(data):
        fields.pop("priority", None)
        code2, data2 = api("POST", "/rest/api/3/issue", {"fields": fields})
        if code2 == 201:
            print("  retried without priority OK", file=sys.stderr)
            return data2["key"]
    return None


# ---- Delta payload ----

TRANSITIONS = [
    ("ESTY-132", "Done", "1.7 Đồng bộ sản phẩm + tồn kho — go-live 2026-05-23"),
    ("ESTY-140", "Done", "2.6 Tự lưu trữ file đã in — go-live 2026-05-23"),
    ("ESTY-161", "Done", "5.4 Mail alias gom phản hồi khách — go-live 2026-05-24"),
]

import urllib.parse  # noqa: E402

EPIC7 = {
    "summary": "Epic 7 — Trung tâm sản phẩm + xuất kênh",
    "priority": "High",
    "status": "In Review",
    "labels": ["phase-7", "owner-view"],
    "body": (
        "## Mục tiêu\n\n"
        "Đảo ngược trạng thái 'chỉ đọc' của các kênh bán. Đưa Odoo lên thành bản gốc duy nhất "
        "của danh mục sản phẩm đa kênh. Kênh đầu tiên xuất ra: Etsy. Amazon + Website chờ Phase 5.\n\n"
        "## Phạm vi\n\n"
        "- Mô hình sản phẩm thống nhất + SKU v2 song song SKU cũ\n"
        "- Wizard tạo sản phẩm (BA-gate)\n"
        "- Wizard chuẩn hoá SKU + drift review\n"
        "- Backfill listing Etsy hiện có (read-only)\n"
        "- Form sản phẩm: tab Kênh + nút Đăng lên Etsy\n"
        "- Đồng bộ Excel danh mục định kỳ\n"
        "- Xuất bản listing Etsy (4 bước: draft → ảnh → inventory → publish)\n\n"
        "## Tiến độ hiện tại\n\n"
        "86% — 6/7 Story xong, 1 Đang triển khai (Story 7.6 Excel sync).\n\n"
        "**Pilot live publish Etsy JaHandmadeArt thành công 2026-05-25.**"
    ),
}

STORIES7 = [
    ("7.1 Mô hình sản phẩm thống nhất", "Highest", "Done", ["spec-009", "dev-action"],
     "Bản gốc sản phẩm có trường 'Các kênh áp dụng'. Mỗi cặp (sản phẩm, kênh) có một dòng "
     "trạng thái riêng. Mã SKU đang dùng + Mã chuẩn v2 + Trạng thái drift hiển thị rõ. "
     "Danh sách 3 kênh (Etsy bật, Amazon + Website tắt chờ Phase 5)."),
    ("7.2 Wizard tạo sản phẩm", "Highest", "Done", ["spec-009", "dev-action"],
     "Wizard có gate BA, bắt buộc Tên + SKU + Nhóm + Giá > 0 + ≥1 kênh. Hiển thị preview "
     "mã SKU chuẩn + chế độ sản xuất trước khi lưu."),
    ("7.3 Wizard chuẩn hoá SKU", "High", "Done", ["spec-009", "dev-action"],
     "BA xem danh sách sản phẩm có mã SKU không khớp v2 → chọn 'Giữ mã cũ' (pin) hoặc "
     "'Chấp nhận mã chuẩn' (đổi mã + lưu trữ mã cũ + tự gửi cập nhật lên Etsy với rollback)."),
    ("7.4 Backfill listing Etsy hiện có", "High", "Done", ["spec-009", "dev-action"],
     "Đọc các listing Etsy đã có + tạo bản sản phẩm + dòng trạng thái kênh cho từng variant "
     "đã match SKU. Variant chưa match → liệt kê để BA quyết định. Chạy lại 2 lần không tạo trùng."),
    ("7.5 Tab Kênh + nút Đăng lên Etsy", "High", "Done", ["spec-009", "dev-action"],
     "Form sản phẩm thêm tab 'Kênh' (M2M kênh áp dụng + danh sách dòng trạng thái) + tab "
     "'Drift mã SKU' + nút 'Đăng lên Etsy' trên header (BA-only)."),
    ("7.6 Đồng bộ định kỳ từ file Excel", "Highest", "In Review", ["spec-010", "dev-action"],
     "File Excel danh mục đặt lên Google Drive → hệ thống đọc + đối chiếu hàng đêm (mặc định 02h). "
     "Excel thắng các trường Tên/Mô tả/Nhóm/Giá/SKU; Odoo thắng 'Các kênh áp dụng'. "
     "Mỗi sheet có vân tay cột; thay đổi cột bất ngờ → cần admin duyệt trước.\n\n"
     "Trạng thái hiện tại: mô hình dữ liệu staging + upsert đã xong; parser openpyxl + cron + "
     "tải ảnh đang triển khai."),
    ("7.7 Xuất lên Etsy (Outbound Publish)", "Highest", "Done", ["spec-009", "dev-action"],
     "Wizard 'Đăng lên Etsy' thực hiện chuỗi 4 bước: tạo draft → upload ảnh → đẩy inventory → "
     "publish. BA-only. Resumable: nếu publish thất bại ở bước 2, lần chạy lại bỏ qua bước 1 "
     "+ tiếp tục từ bước 2. Tự rollback nếu Etsy báo lỗi.\n\n"
     "Smoke test trên shop JaHandmadeArt thành công 2026-05-25 — tạo được listing thật trên Etsy, "
     "đã sửa 7 lỗi đường biên Etsy 2025 API (readiness_state_id mandatory, int4 overflow trên "
     "shipping/taxonomy/return policy IDs, XML-RPC int32 overflow trên listing_id)."),
]


def main():
    dry_run = "--dry-run" in sys.argv
    results = {"transitions": [], "epic": None, "stories": []}

    print("=" * 60)
    print("DELTA SYNC 2026-05-25")
    print("=" * 60)

    # 1) Transitions
    print("\n--- Step 1: Transition 3 Stories to Done ---")
    for key, status, note in TRANSITIONS:
        print(f"  {key} → {status}  ({note})")
        if dry_run:
            results["transitions"].append({"key": key, "status": status, "ok": "dry-run"})
            continue
        ok = transition_to(key, status)
        results["transitions"].append({"key": key, "status": status, "ok": ok})
        if not ok:
            print(f"    !! transition failed for {key}", file=sys.stderr)
        time.sleep(0.2)

    # 2) Create Epic 7 (idempotent — check by summary first)
    print("\n--- Step 2: Create Epic 7 ---")
    existing = find_issue_by_summary(EPIC7["summary"]) if not dry_run else None
    if existing:
        print(f"  Epic 7 already exists: {existing} (skipping create)")
        epic_key = existing
    elif dry_run:
        print(f"  Would create Epic: {EPIC7['summary']}")
        epic_key = "ESTY-XXX (dry-run)"
    else:
        epic_key = create_issue(
            summary=EPIC7["summary"], body_md=EPIC7["body"], issuetype="Epic",
            priority=EPIC7["priority"], labels=EPIC7["labels"],
        )
        if epic_key:
            print(f"  Created Epic: {epic_key}")
            if EPIC7["status"] != "To Do":
                if transition_to(epic_key, EPIC7["status"]):
                    print(f"    transitioned to {EPIC7['status']}")
            time.sleep(0.3)
        else:
            print("  !! Epic 7 creation failed; aborting", file=sys.stderr)
            sys.exit(1)
    results["epic"] = epic_key

    # 3) Create 7 Stories under Epic 7
    print("\n--- Step 3: Create 7 Stories under Epic 7 ---")
    for idx, (summary, prio, status, labels, body) in enumerate(STORIES7, 1):
        print(f"  [{idx}/7] {summary}  ({status}, {prio})")
        if dry_run:
            results["stories"].append({"summary": summary, "status": status, "key": "dry-run"})
            continue
        # idempotent
        existing_story = find_issue_by_summary(summary)
        if existing_story:
            print(f"    already exists: {existing_story}")
            results["stories"].append({"summary": summary, "status": status, "key": existing_story, "skipped": True})
            continue
        story_key = create_issue(
            summary=summary, body_md=body, issuetype="Story",
            parent=epic_key, priority=prio, labels=labels,
        )
        if not story_key:
            print(f"    !! create failed", file=sys.stderr)
            results["stories"].append({"summary": summary, "ok": False})
            continue
        print(f"    created {story_key}")
        if status != "To Do":
            if transition_to(story_key, status):
                print(f"    transitioned to {status}")
        results["stories"].append({"summary": summary, "status": status, "key": story_key})
        time.sleep(0.25)

    # 4) Save mapping
    if not dry_run:
        out_path = REPO / ".docs/tasks/_owner_sync_2026-05-25.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
        print(f"\nMapping saved to {out_path}")

    print("\nDONE.")


if __name__ == "__main__":
    main()
