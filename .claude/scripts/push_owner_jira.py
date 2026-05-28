#!/usr/bin/env python3
"""
Push the 6 Epics + 48 Stories from docs/owner/SRS_VN.md to Jira ESTY project.

Workflow:
1. Push 6 Epics, capture returned ESTY-XXX keys
2. Push 48 Stories with parent = corresponding Epic key
3. After creation, PUT update for priority + labels (omitted from initial create)
4. Transition Done/In Review stories via /transitions endpoint

Reads creds from .env at repo root.
"""
import os
import sys
import json
import time
import re
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error
import base64
from typing import Dict, Optional, Tuple, Union, List

REPO = Path(__file__).resolve().parents[2]
ENV = REPO / ".env"


def load_env():
    e = {}
    for line in ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip("'").strip('"')
        e[k.strip()] = v
    return e


ENV_VARS = load_env()
JIRA_BASE = ENV_VARS["JIRA_SERVER_URL"].rstrip("/")
JIRA_PROJECT = ENV_VARS["JIRA_PROJECT_KEY"]
JIRA_EMAIL = ENV_VARS["JIRA_USER_EMAIL"]
JIRA_KEY = ENV_VARS["JIRA_API_KEY"]
AUTH = "Basic " + base64.b64encode(f"{JIRA_EMAIL}:{JIRA_KEY}".encode()).decode()


def api(method, path, data=None):
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


def adf_from_markdown(md):
    """Very simple markdown → Atlassian Document Format converter.
    Handles paragraphs, headings (#..######), bullet lists, numbered lists.
    """
    content = []
    paragraphs = re.split(r"\n\n+", md.strip())
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        # Heading single-line
        m = re.match(r"^(#{1,6})\s+(.+)$", para)
        if m and "\n" not in para:
            content.append({
                "type": "heading",
                "attrs": {"level": len(m.group(1))},
                "content": [{"type": "text", "text": m.group(2)}],
            })
            continue
        lines = [l for l in para.split("\n") if l.strip()]
        # Bullet list
        if all(re.match(r"^\s*[-*]\s+", l) for l in lines):
            items = []
            for l in lines:
                text = re.sub(r"^\s*[-*]\s+", "", l).strip()
                items.append({
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
                })
            content.append({"type": "bulletList", "content": items})
            continue
        # Numbered list
        if all(re.match(r"^\s*\d+\.\s+", l) for l in lines):
            items = []
            for l in lines:
                text = re.sub(r"^\s*\d+\.\s+", "", l).strip()
                items.append({
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
                })
            content.append({"type": "orderedList", "content": items})
            continue
        # Default paragraph
        content.append({
            "type": "paragraph",
            "content": [{"type": "text", "text": para.replace("\n", " ")}],
        })
    if not content:
        content = [{"type": "paragraph", "content": [{"type": "text", "text": " "}]}]
    return {"type": "doc", "version": 1, "content": content}


def create_issue(
    summary, body_md, issuetype,
    parent=None, priority=None, labels=None,
):
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
    # Retry without priority if priority caused issue
    if priority and "priority" in str(data):
        fields.pop("priority", None)
        code2, data2 = api("POST", "/rest/api/3/issue", {"fields": fields})
        if code2 == 201:
            print(f"  (retried without priority) OK", file=sys.stderr)
            return data2["key"]
    return None


def get_transitions(key):
    code, data = api("GET", f"/rest/api/3/issue/{key}/transitions")
    return {t["to"]["name"]: t["id"] for t in data.get("transitions", [])} if code == 200 else {}


def transition_to(key, status_name):
    trans = get_transitions(key)
    tid = trans.get(status_name)
    if not tid:
        print(f"  no transition to {status_name}, available: {list(trans.keys())}", file=sys.stderr)
        return False
    code, _ = api("POST", f"/rest/api/3/issue/{key}/transitions", {"transition": {"id": tid}})
    return code in (204, 200)


# ---- Data: Epics ----
EPICS = [
    {
        "id": "E1", "summary": "Epic 1 — Nhập đơn tự động",
        "labels": ["phase-1", "owner-view"],
        "priority": "Highest", "status": "In Review",
        "body": (
            "## Mục tiêu\n\n"
            "Đơn từ Etsy tự chảy vào hệ thống trong vòng 5 phút; không phải nhập tay từ Gmail. "
            "Làm sạch 17.659 đơn cũ.\n\n"
            "## Phạm vi\n\n"
            "- Kết nối Etsy API (4 quyền đã duyệt 2026-05-12)\n"
            "- Email parser dự phòng vĩnh viễn\n"
            "- Migration 17.659 đơn cũ, sửa 423 đơn $0, gộp khách trùng\n"
            "- Đồng bộ danh sách sản phẩm + tồn kho\n"
            "- Bật API cho 19 shop (pilot trước, mở rộng sau)\n\n"
            "## Tiến độ hiện tại\n\n"
            "85% — 6/9 Story đã Done, 1 In Progress, 1 Blocked (CDA bật pilot), 1 Sắp làm."
        ),
    },
    {
        "id": "E2", "summary": "Epic 2 — Duyệt thiết kế",
        "labels": ["phase-2", "owner-view"],
        "priority": "High", "status": "In Review",
        "body": (
            "## Mục tiêu\n\n"
            "File thiết kế upload 1 lần, các bộ phận xem đúng phiên bản, in được hàng loạt.\n\n"
            "## Phạm vi\n\n"
            "- Upload Google Drive, quy trình duyệt 3 trạng thái\n"
            "- Hàng đợi kanban duyệt file\n"
            "- Tự gửi file đến PD/MP/Partner\n"
            "- Bulk-download in A4 cho PD\n"
            "- Cảnh báo file thiếu trước sản xuất\n\n"
            "## Tiến độ hiện tại\n\n"
            "95% — 6/7 Story đã Done, còn auto-archive file đã in."
        ),
    },
    {
        "id": "E3", "summary": "Epic 3 — Sản xuất",
        "labels": ["phase-3", "owner-view"],
        "priority": "High", "status": "In Review",
        "body": (
            "## Mục tiêu\n\n"
            "Thấy đơn đang ở công đoạn nào, ai phụ trách, có trễ không. "
            "Cho phép cấu hình các bước sản xuất riêng cho từng dòng sản phẩm.\n\n"
            "## Phạm vi\n\n"
            "- Dashboard 17 trạng thái Việt Nam\n"
            "- Pipeline cấu hình được qua giao diện\n"
            "- Tuyến Dropship + MTO\n"
            "- Gán team phụ trách từng stage\n"
            "- Scan barcode, auto-advance MRP workorder\n\n"
            "## Tiến độ hiện tại\n\n"
            "90% — 6/7 Story đã Done, còn auto-chuyển stage khi xong MRP."
        ),
    },
    {
        "id": "E4", "summary": "Epic 4 — Vận chuyển & tracking",
        "labels": ["phase-4", "owner-view"],
        "priority": "High", "status": "In Review",
        "body": (
            "## Mục tiêu\n\n"
            "Đẩy đơn sang Gearment, nhập tracking GKE, cập nhật tracking về Etsy, duyệt đổi địa chỉ.\n\n"
            "## Phạm vi\n\n"
            "- Kết nối Gearment + nhận thông báo trạng thái tự động\n"
            "- Import Excel tracking GKE, tự nhận diện carrier\n"
            "- Đẩy tracking ngược Etsy\n"
            "- Duyệt đổi địa chỉ giao hàng (khoá Buy Label khi pending)\n"
            "- Bulk-send, xử lý hoàn/refund\n\n"
            "## Tiến độ hiện tại\n\n"
            "80% — 7/9 Story đã Done. Cần CDA cấp API key Gearment để full automation."
        ),
    },
    {
        "id": "E5", "summary": "Epic 5 — Tin nhắn khách hàng",
        "labels": ["phase-5", "owner-view"],
        "priority": "High", "status": "To Do",
        "body": (
            "## Mục tiêu\n\n"
            "Đọc và trả lời tin nhắn 19 shop ở một chỗ; tự tạo CRM lead khi cần.\n\n"
            "## Phạm vi\n\n"
            "- Hiển thị buyer message trên form đơn\n"
            "- Hub tin nhắn khách (cross-shop)\n"
            "- CRM lead từ tin nhắn\n"
            "- Mail alias gom phản hồi\n"
            "- Kéo tin nhắn Etsy qua API (sau khi Etsy duyệt conversations_r)\n\n"
            "## Tiến độ hiện tại\n\n"
            "60% — 3/6 Story đã Done. Bị chặn: chờ CDA submit lại Etsy app xin conversations_r."
        ),
    },
    {
        "id": "E6", "summary": "Epic 6 — Báo cáo & quản trị",
        "labels": ["phase-6", "owner-view"],
        "priority": "High", "status": "In Review",
        "body": (
            "## Mục tiêu\n\n"
            "Mỗi bộ phận có dashboard riêng. Audit log mọi thao tác. "
            "Việt hoá toàn bộ giao diện. Kiểm soát giá hàng ngày.\n\n"
            "## Phạm vi\n\n"
            "- Dashboard Đơn hàng, Tracking, Sản xuất (3 dashboard chính)\n"
            "- Dashboard Tài chính + Kiểm soát giá\n"
            "- Audit log mọi thao tác\n"
            "- Phân vai trò người dùng\n"
            "- Việt hoá UI Phase 1\n"
            "- Health monitoring + báo cáo email\n\n"
            "## Tiến độ hiện tại\n\n"
            "70% — 5/10 Story đã Done, 5 Sắp làm trong tháng 6-7."
        ),
    },
]


# ---- Data: 48 Stories ----
# Format: (epic_id, summary, priority, status, labels, body_md)
# status mapping: ✅ Xong → "Done", 🟡 Đang làm → "In Review", 🟥 Bị chặn → "To Do" + "blocked" label, ⏳ Sắp làm → "To Do"
STORIES = [
    # ---- Epic 1 — Nhập đơn tự động (9) ----
    ("E1", "1.1 Kết nối tài khoản Etsy an toàn", "Highest", "Done", ["spec-005", "dev-action"],
     "## Mô tả\n\nChủ dự án vào trang cấu hình, bấm 'Connect Etsy', đăng nhập 1 lần. Hệ thống nhớ kết nối, tự gia hạn, cảnh báo trước 7 ngày khi cần kết nối lại.\n\n## Tiêu chí nghiệm thu\n\n- Đăng nhập 1 lần, không phải làm lại trong 90 ngày\n- Có thông báo trên dashboard khi sắp hết hạn\n- Có nút Test connection để kiểm tra ngay\n\n## Trạng thái\n\nĐã go-live 2026-05-12."),
    ("E1", "1.2 Tự động kéo đơn mới mỗi 5 phút", "Highest", "Done", ["spec-005", "dev-action"],
     "## Mô tả\n\nHệ thống tự lấy đơn mới và đơn bị sửa từ Etsy mỗi 5 phút. Không tạo trùng. Không ghi đè ghi chú nội bộ của Marketing.\n\n## Tiêu chí nghiệm thu\n\n- Đơn mới xuất hiện trong hệ thống trong ≤5 phút\n- Đơn bị sửa địa chỉ trên Etsy thì hệ thống cập nhật trạng thái nhưng giữ nguyên ghi chú MP\n- Trong 7 ngày không có đơn nào bị trùng"),
    ("E1", "1.3 Email parser dự phòng", "Highest", "Done", ["spec-001", "dev-action"],
     "## Mô tả\n\nNếu Etsy API gặp lỗi 3 lần liên tiếp, hệ thống tự chuyển sang đọc email Gmail để không sót đơn. Khi API khôi phục, tự chuyển ngược lại.\n\n## Tiêu chí nghiệm thu\n\n- Tự chuyển sang email trong 15 phút khi API hỏng\n- Có cảnh báo HIGH gửi cho admin khi xảy ra\n- Tự khôi phục về API sau khi API ổn 6 lần liên tiếp"),
    ("E1", "1.4 Làm sạch 17.659 đơn cũ (Migration)", "Highest", "Done", ["spec-002", "dev-action"],
     "## Mô tả\n\nĐọc file Excel lịch sử (17.659 đơn) và tạo trong hệ thống. Có thể chạy lại nếu gián đoạn. Tự nhận diện tiền tệ (USD, EUR, GBP, CAD, VND). Tách phí ship thành dòng riêng.\n\n## Tiêu chí nghiệm thu\n\n- Tổng số đơn nhập khớp tổng trong Excel\n- Tổng doanh thu khớp trong sai số $0.01/đơn\n- Báo cáo có danh sách đơn lỗi để BA xử lý tay\n- BA Lead ký xác nhận trước khi sang giai đoạn tiếp"),
    ("E1", "1.5 Sửa 423 đơn ghi giá $0", "Highest", "Done", ["spec-002", "dev-action"],
     "## Mô tả\n\nHệ thống tính lại giá cho 423 đơn ghi $0 từ nguồn gốc. Đơn không tính được sẽ liệt kê cho BA xử lý tay.\n\n## Tiêu chí nghiệm thu\n\n- ≥80% trong 423 đơn được tính lại tự động\n- Đơn không tính được có lý do rõ ràng"),
    ("E1", "1.6 Gộp khách hàng trùng có BA duyệt", "Highest", "Done", ["spec-002", "dev-action"],
     "## Mô tả\n\nHệ thống đề xuất danh sách khách trùng → xuất Excel → BA tick chọn → upload lại để gộp. KHÔNG tự gộp — phải có BA duyệt.\n\n## Tiêu chí nghiệm thu\n\n- Excel xuất ra rõ ràng (tên, email, số đơn từng khách)\n- Sau khi upload, có báo cáo gộp thành công X / lỗi Y\n- Có nút hoàn tác trong 24h"),
    ("E1", "1.7 Đồng bộ danh sách sản phẩm + tồn kho từ Etsy", "High", "In Review", ["spec-008", "dev-action"],
     "## Mô tả\n\nTải danh sách sản phẩm và số lượng tồn kho từ Etsy về hệ thống. Chỉ đọc, không sửa được.\n\n## Tiêu chí nghiệm thu\n\n- Mỗi shop xem được số sản phẩm và tồn kho hiện tại\n- Có cảnh báo khi tồn kho lệch >10% giữa Etsy và hệ thống\n\n**ETA:** tuần đầu tháng 6/2026"),
    ("E1", "1.8 Bật API cho shop pilot", "Highest", "To Do", ["crosscut", "owner-action", "blocked"],
     "## Mô tả\n\nChủ dự án chọn 1 shop để bật chế độ API (thay vì email). Theo dõi 1-2 tuần để đảm bảo không sót đơn.\n\n## Tiêu chí nghiệm thu\n\n- Shop thí điểm chạy API trong 14 ngày không sót đơn\n- Không có khiếu nại nào từ Marketing\n- Có quy trình rollback (về lại email) nếu cần\n\n**Bị chặn:** Cần CDA thao tác. ETA tuần 4 tháng 5/2026."),
    ("E1", "1.9 Bật API cho 18 shop còn lại", "Highest", "To Do", ["crosscut", "owner-action"],
     "## Mô tả\n\nSau khi shop thí điểm ổn, mở rộng ra 18 shop còn lại, mỗi đợt 2-4 shop.\n\n## Tiêu chí nghiệm thu\n\n- Tất cả 19 shop chạy API\n- Email cron tự tắt sau khi hoàn tất\n- Không có đơn nào sót trong 14 ngày sau cùng\n\n**ETA:** tháng 6-7/2026"),

    # ---- Epic 2 — Duyệt thiết kế (7) ----
    ("E2", "2.1 BA upload file thiết kế lên Google Drive", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nBA upload file lớn (vd 150MB) cho đơn. Hệ thống lưu trên Google Drive, ghi nhớ link và phiên bản. Có thể xóa và upload lại bản mới; bản cũ vẫn lưu để truy vết.\n\n## Tiêu chí nghiệm thu\n\n- File >100MB upload được trong ≤2 phút\n- Mỗi lần upload tạo 1 phiên bản mới, không ghi đè\n- Lịch sử phiên bản hiển thị rõ trên form đơn"),
    ("E2", "2.2 Quy trình duyệt 3 trạng thái", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nFile có 3 trạng thái: Chờ duyệt → Đã duyệt → Cần chỉnh lại. PD bấm duyệt hoặc chọn 'Cần chỉnh' (phải nhập lý do). Ghi nhận ai duyệt, khi nào.\n\n## Tiêu chí nghiệm thu\n\n- 3 trạng thái rõ ràng trên giao diện\n- 'Cần chỉnh lại' bắt buộc nhập lý do ≥10 ký tự\n- Lịch sử duyệt hiển thị trên form đơn"),
    ("E2", "2.3 Bảng kanban hàng đợi duyệt", "High", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nDesigner và BA thấy danh sách đang chờ duyệt theo dạng cột (3 cột tương ứng 3 trạng thái). Kéo-thả hoặc click để chuyển trạng thái.\n\n## Tiêu chí nghiệm thu\n\n- 3 cột hiển thị đúng số file\n- Cập nhật real-time khi có người duyệt"),
    ("E2", "2.4 Tự động gửi file đến các bộ phận liên quan", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nKhi BA duyệt đơn, hệ thống tự cấp quyền đọc file cho PD, MP, hoặc đối tác (Gearment) tùy đơn. Không cần BA gửi tay.\n\n## Tiêu chí nghiệm thu\n\n- Mỗi đơn duyệt → file tự gửi đến đúng người trong ≤2 phút\n- Có badge cảnh báo nếu gửi thất bại sau 2 giờ"),
    ("E2", "2.5 PD bulk-download in A4", "High", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nPD tick các file đã duyệt → bấm 'Download A4' → hệ thống tạo file PDF dàn sẵn để in. Cache 24 giờ để in lại không phải chờ.\n\n## Tiêu chí nghiệm thu\n\n- Bulk-download ≤50 file trong ≤30 giây\n- PDF in được trên máy in A4 thông thường"),
    ("E2", "2.6 Tự lưu trữ file đã in", "Medium", "To Do", ["spec-003", "dev-action"],
     "## Mô tả\n\nFile đã in xong và đơn đã giao thì tự chuyển sang trạng thái 'Đã lưu trữ' để không hiển thị trong danh sách hàng ngày, tránh rối mắt.\n\n## Tiêu chí nghiệm thu\n\n- File tự ẩn sau 30 ngày kể từ ngày đơn giao\n- Có filter 'Xem cả file đã lưu trữ' để xem lại\n\n**ETA:** cuối tháng 5/2026"),
    ("E2", "2.7 Cảnh báo file thiếu trước sản xuất", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nKhi đơn được đẩy sản xuất nhưng chưa có file thiết kế duyệt, hệ thống chặn và cảnh báo BA.\n\n## Tiêu chí nghiệm thu\n\n- Đơn không có file duyệt → không đẩy được sang PD/Gearment\n- Cảnh báo hiển thị rõ trên form đơn"),

    # ---- Epic 3 — Sản xuất (7) ----
    ("E3", "3.1 Dashboard sản xuất với 17 trạng thái Việt Nam", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nPD và BA xem đơn theo cột Trạng thái với 17 bước chuẩn (CHỜ FILE → ... → VN-Fulfilled). Đơn US và VN cùng dashboard.\n\n## Tiêu chí nghiệm thu\n\n- 17 cột hiển thị đúng số đơn\n- Click trạng thái để mở danh sách đơn\n- Tô màu khác nhau cho từng trạng thái"),
    ("E3", "3.2 Pipeline đơn cấu hình được", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nAdmin có thể tạo pipeline mới (vd cho dòng sản phẩm khác), thêm/xóa/sửa stage, đổi tên, đổi màu. Không cần lập trình.\n\n## Tiêu chí nghiệm thu\n\n- Admin tạo được pipeline mới qua giao diện\n- Đổi tên stage không ảnh hưởng đơn đang chạy\n- Audit log ghi mọi thay đổi cấu trúc"),
    ("E3", "3.3 Tuyến Dropship và Make-to-Order (MTO)", "Highest", "Done", ["spec-004", "dev-action"],
     "## Mô tả\n\nHệ thống tự quyết định đơn nào đi tuyến Dropship (gửi thẳng từ Gearment) hay MTO (sản xuất nội bộ) dựa trên loại sản phẩm.\n\n## Tiêu chí nghiệm thu\n\n- Đơn POD (Gearment) → tuyến Dropship\n- Đơn sản xuất nội bộ → tuyến MTO\n- Có thể override tay khi cần"),
    ("E3", "3.4 Gán team phụ trách cho từng stage", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nMỗi stage trong pipeline có thể gán cho một team (vd Team thêu, Team in). Đơn ở stage đó hiển thị tên team phụ trách.\n\n## Tiêu chí nghiệm thu\n\n- Mỗi stage gán được 1 team default\n- PD lead có thể override per-đơn\n- Filter theo team hoạt động"),
    ("E3", "3.5 Scan barcode để chuyển trạng thái", "High", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nPD scan barcode đơn → hệ thống tự chuyển sang stage Đã fulfilled, ghi ngày ship, ai scan.\n\n## Tiêu chí nghiệm thu\n\n- Scan 1 đơn xong trong ≤2 giây\n- Audit log ghi đúng người scan"),
    ("E3", "3.6 Tự chuyển stage khi xong workorder MRP", "High", "To Do", ["crosscut", "dev-action"],
     "## Mô tả\n\nKhi PD hoàn thành 1 công đoạn trong MRP, hệ thống tự đẩy đơn sang stage tiếp theo trong pipeline. PD không phải bấm tay 2 nơi.\n\n## Tiêu chí nghiệm thu\n\n- Hoàn thành workorder → stage pipeline đổi trong ≤5 giây\n- Có nút tắt auto-advance nếu PD muốn kiểm soát tay\n\n**ETA:** tuần 2 tháng 6/2026"),
    ("E3", "3.7 Widget thống kê sản xuất", "Medium", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nTrên dashboard sản xuất có widget hiển thị: tổng đơn đang chạy, đơn sắp trễ, đơn theo loại sản phẩm, đơn theo team.\n\n## Tiêu chí nghiệm thu\n\n- Cập nhật real-time khi có đơn mới\n- Click widget mở danh sách lọc"),

    # ---- Epic 4 — Vận chuyển & tracking (9) ----
    ("E4", "4.1 Kết nối Gearment, đẩy đơn qua API", "Highest", "Done", ["spec-004", "dev-action"],
     "## Mô tả\n\nBA bấm 'Push to Gearment' trên đơn → hệ thống gửi sang Gearment qua API, kèm file thiết kế. Theo dõi trạng thái Draft → Quote → Confirm.\n\n## Tiêu chí nghiệm thu\n\n- Push thành công trong ≤10 giây\n- Đơn lên Gearment với đúng SKU và địa chỉ\n- File thiết kế đính kèm đúng"),
    ("E4", "4.2 Nhận thông báo trạng thái từ Gearment", "Highest", "Done", ["spec-004", "dev-action"],
     "## Mô tả\n\nKhi Gearment update đơn (vd: đang sản xuất, đã ship, có tracking), hệ thống nhận tự động. Không cần BA bấm refresh.\n\n## Tiêu chí nghiệm thu\n\n- Cập nhật trong ≤5 giây\n- Đơn update đúng trạng thái\n- Có cơ chế hỏi lại Gearment mỗi 5 phút nếu thông báo bị bỏ lỡ"),
    ("E4", "4.3 Import tracking từ file Excel GKE", "Highest", "Done", ["spec-004a", "dev-action"],
     "## Mô tả\n\nBA upload file Excel GKE → hệ thống đọc, khớp Order ID, tự điền tracking + carrier. Hàng không khớp được liệt kê cho BA xử lý tay.\n\n## Tiêu chí nghiệm thu\n\n- File Excel chuẩn GKE đọc đúng 100%\n- Báo cáo matched / unmatched rõ ràng\n- Có lịch tự đọc file mới upload lên Google Drive"),
    ("E4", "4.4 Tự nhận diện carrier từ mã tracking", "Highest", "Done", ["spec-004a", "dev-action"],
     "## Mô tả\n\nHệ thống tự đoán carrier (USPS / UniUni / YunExpress / Other) từ format mã tracking. BA không phải chọn tay.\n\n## Tiêu chí nghiệm thu\n\n- ≥95% mã tracking nhận đúng carrier\n- Mã không nhận được → carrier = Other"),
    ("E4", "4.5 Đẩy tracking ngược về Etsy", "Highest", "Done", ["spec-005", "dev-action"],
     "## Mô tả\n\nKhi tracking vào hệ thống, tự đẩy lên Etsy trong ≤5 phút (theo cài đặt từng shop).\n\n## Tiêu chí nghiệm thu\n\n- Tracking lên Etsy trong ≤5 phút\n- Marketing có công tắc Auto-push bật/tắt từng shop\n- Có thử lại tối đa 3 lần nếu Etsy fail"),
    ("E4", "4.6 Duyệt đổi địa chỉ giao hàng", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nMarketing không sửa địa chỉ trực tiếp được. Phải tạo Yêu cầu đổi địa chỉ → BA duyệt/từ chối → mới sửa. Trong khi chờ duyệt, không cho mua label.\n\n## Tiêu chí nghiệm thu\n\n- MP không có quyền sửa địa chỉ trực tiếp\n- Yêu cầu duyệt xử lý trong ≤24h\n- Đơn đang chờ duyệt địa chỉ → nút Buy Label bị khóa\n- Có badge cảnh báo trên dashboard"),
    ("E4", "4.7 Bulk-action gửi đơn đã duyệt sang Gearment", "High", "To Do", ["spec-004", "dev-action"],
     "## Mô tả\n\nBA tick nhiều đơn → bấm 'Send approved to Gearment' để đẩy hàng loạt thay vì từng đơn.\n\n## Tiêu chí nghiệm thu\n\n- Đẩy được ≤50 đơn/lần\n- Báo cáo: thành công X / lỗi Y\n- Đơn lỗi không chặn các đơn khác\n\n**ETA:** cuối tháng 5/2026"),
    ("E4", "4.8 Xử lý đơn hoàn / refund", "High", "To Do", ["spec-004", "dev-action"],
     "## Mô tả\n\nCó form tạo ticket replace / refund / discount trên đơn. MP nhập lý do + ảnh → BA duyệt → hệ thống tự xử lý (refund → credit note; replace → đơn mới link đơn gốc).\n\n## Tiêu chí nghiệm thu\n\n- Tạo ticket trong ≤3 phút\n- BA duyệt → tự xử lý không sai\n- Có lịch sử ticket trên form đơn\n\n**ETA:** tháng 7/2026"),
    ("E4", "4.9 Hiển thị trạng thái tracking (In-transit / Delivered / Returned)", "High", "Done", ["spec-004a", "dev-action"],
     "## Mô tả\n\nHệ thống nhận thông báo từ carrier (USPS, UniUni, YunExpress) và hiển thị trạng thái real-time trên dashboard Tracking.\n\n## Tiêu chí nghiệm thu\n\n- Trạng thái cập nhật trong ≤5 phút sau khi carrier báo\n- Dashboard tô màu khác nhau cho từng trạng thái"),

    # ---- Epic 5 — Tin nhắn khách hàng (6) ----
    ("E5", "5.1 Hiển thị buyer message trên form đơn", "Highest", "Done", ["spec-005", "dev-action"],
     "## Mô tả\n\nKhi khách ghi chú khi đặt đơn (vd custom name, gift message), nội dung này hiển thị nổi bật trên form đơn để MP và PD không bỏ sót.\n\n## Tiêu chí nghiệm thu\n\n- Buyer message hiển thị trên top form đơn\n- PD thấy nội dung custom trước khi sản xuất"),
    ("E5", "5.2 Hub tin nhắn khách (Customer Message Hub)", "High", "Done", ["spec-007", "dev-action"],
     "## Mô tả\n\nMột trang duy nhất hiển thị tin nhắn khách của 19 shop. Có search, filter theo shop, theo ngày.\n\n## Tiêu chí nghiệm thu\n\n- Hiển thị tin nhắn của tất cả shop đã connect API\n- Search hoạt động trên nội dung và tên khách"),
    ("E5", "5.3 Tạo CRM lead từ tin nhắn khách", "High", "Done", ["spec-007", "dev-action"],
     "## Mô tả\n\nKhi tin nhắn khách chứa câu hỏi mua hàng (vd hỏi giá custom), MP có nút tạo CRM lead trực tiếp. BA theo dõi lead trên dashboard CRM.\n\n## Tiêu chí nghiệm thu\n\n- Tạo lead trong ≤1 click\n- Lead link với tin nhắn gốc\n- Có dashboard CRM lead riêng"),
    ("E5", "5.4 Mail alias gom phản hồi khách", "Medium", "To Do", ["spec-007", "dev-action"],
     "## Mô tả\n\nTạo email alias riêng cho từng shop. Khi khách trả lời, hệ thống tự gom vào CRM lead tương ứng.\n\n## Tiêu chí nghiệm thu\n\n- Email reply gom đúng lead\n- Không trùng (1 email = 1 entry)\n\n**ETA:** tháng 7/2026"),
    ("E5", "5.5 Re-submit Etsy app xin quyền conversations_r", "High", "To Do", ["crosscut", "owner-action", "blocked"],
     "## Mô tả\n\nEtsy hiện chỉ duyệt 4/5 quyền truy cập; thiếu quyền conversations_r (đọc tin nhắn Etsy đầy đủ). Cần submit lại đơn đăng ký.\n\n## Tiêu chí nghiệm thu\n\n- CDA submit đơn đăng ký lại với justification rõ\n- Etsy phản hồi duyệt\n- Hệ thống bật module đọc tin nhắn đầy đủ\n\n**Bị chặn:** Cần CDA thao tác. ETA: tuần này → chờ Etsy 3-8 tuần."),
    ("E5", "5.6 Kéo tin nhắn Etsy qua API (sau khi được duyệt)", "High", "To Do", ["spec-007", "dev-action", "blocked"],
     "## Mô tả\n\nSau khi Etsy duyệt conversations_r, hệ thống tự kéo toàn bộ tin nhắn về Hub. Không phải xem từng shop.\n\n## Tiêu chí nghiệm thu\n\n- Tin nhắn mới về Hub trong ≤5 phút\n- Không trùng với tin nhắn đã có\n\n**Bị chặn:** chờ Story 5.5."),

    # ---- Epic 6 — Báo cáo & quản trị (10) ----
    ("E6", "6.1 Dashboard Đơn hàng (BA + Marketing)", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nBảng đơn 10 cột cốt lõi: Shop, Order ID, Tracking, Ảnh, Ngày, Tình trạng, SL, Shipping, Quốc gia, Tổng giá. Inline edit. Tô màu theo loại đơn.\n\n## Tiêu chí nghiệm thu\n\n- Hiển thị đủ 10 cột\n- Search hoạt động trên Shop + Order ID\n- Inline edit cho Tracking, Carrier, Label state, Note\n- Đơn qty≥2 → cam; đơn Push → đỏ; đơn quá hạn → vàng"),
    ("E6", "6.2 Dashboard Tracking (BA)", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nTrang riêng cho tracking, 13 cột (Order ID, Tracking, Carrier, Tình trạng, ... Quốc gia). Export Excel. Bulk chuyển label state.\n\n## Tiêu chí nghiệm thu\n\n- 13 cột hiển thị đúng\n- Export Excel theo filter hiện tại\n- Bulk action: chọn nhiều → đổi label state 1 click"),
    ("E6", "6.3 Dashboard Sản xuất (PD + BA)", "Highest", "Done", ["spec-003", "dev-action"],
     "## Mô tả\n\nXem mô tả tại Story 3.1 (Dashboard sản xuất 17 trạng thái VN).\n\n## Tiêu chí nghiệm thu\n\nĐồng bộ với Story 3.1."),
    ("E6", "6.4 Dashboard Tài chính", "High", "To Do", ["spec-003", "dev-action"],
     "## Mô tả\n\nTổng doanh thu, chi phí, lợi nhuận theo shop / tháng / quý. Xuất Excel cho kế toán.\n\n## Tiêu chí nghiệm thu\n\n- Doanh thu tổng khớp với báo cáo Etsy trong sai số 1%\n- Filter theo shop / khoảng ngày\n- Export Excel cho kế toán\n\n**ETA:** tháng 6/2026"),
    ("E6", "6.5 Dashboard Kiểm soát giá (Pricing Audit)", "High", "To Do", ["spec-004", "dev-action"],
     "## Mô tả\n\n25 cột (A-F nhập tay, G-T tự lấy từ đơn). Quy đổi đa tiền tệ về EUR. Tô màu chênh lệch giá so với catalog. Tự động mỗi sáng list đơn vượt ngưỡng.\n\n## Tiêu chí nghiệm thu\n\n- 25 cột hiển thị đúng\n- Tô màu đỏ (thấp) / vàng (bằng) / tím (cao) so với catalog\n- Hệ thống mỗi 7h sáng gửi danh sách đơn lệch giá cho RD\n\n**ETA:** tháng 7/2026"),
    ("E6", "6.6 Audit log mọi thao tác", "Highest", "Done", ["crosscut", "dev-action"],
     "## Mô tả\n\nMọi thay đổi trên đơn (đổi tracking, đổi địa chỉ, đổi trạng thái, duyệt file) đều ghi: ai, khi nào, từ giá trị nào sang giá trị nào.\n\n## Tiêu chí nghiệm thu\n\n- Mỗi đơn có tab Lịch sử hiển thị đầy đủ\n- Search theo người sửa, theo loại thao tác"),
    ("E6", "6.7 Phân vai trò người dùng", "Highest", "Done", ["crosscut", "dev-action"],
     "## Mô tả\n\nPhân quyền theo bộ phận (Chủ dự án / BA / MP / PD / RD). Mỗi vai trò chỉ thấy menu và dữ liệu của mình.\n\n## Tiêu chí nghiệm thu\n\n- Đăng nhập tài khoản PD → chỉ thấy Dashboard Sản xuất\n- Đăng nhập tài khoản MP → không sửa được địa chỉ\n- Admin có thể override khi cần"),
    ("E6", "6.8 Việt hoá toàn bộ giao diện", "High", "To Do", ["crosscut", "dev-action"],
     "## Mô tả\n\nTất cả nhãn, nút, thông báo trên giao diện chuyển sang tiếng Việt. Người dùng không cần biết tiếng Anh.\n\n## Tiêu chí nghiệm thu\n\n- 100% nhãn hệ thống Việt hoá (trừ tên riêng Etsy/Gearment/SKU)\n- Người mới vào hiểu được mà không cần đào tạo tiếng Anh\n\n**ETA:** tháng 6/2026"),
    ("E6", "6.9 Kiểm tra sức khỏe hệ thống (Health Monitoring)", "Medium", "To Do", ["crosscut", "dev-action"],
     "## Mô tả\n\nDashboard chuyên dụng hiển thị: API Etsy ổn không, Gearment ổn không, Google Drive ổn không, lịch tự động có chạy không, có job nào fail không.\n\n## Tiêu chí nghiệm thu\n\n- 5 tile xanh/vàng/đỏ rõ ràng\n- Admin click tile để xem chi tiết lỗi\n\n**ETA:** tháng 7/2026"),
    ("E6", "6.10 Báo cáo định kỳ qua email", "Medium", "To Do", ["crosscut", "dev-action"],
     "## Mô tả\n\nHàng sáng 7h, gửi email cho Chủ dự án: tổng đơn hôm qua, doanh thu, đơn lỗi, cảnh báo đặc biệt.\n\n## Tiêu chí nghiệm thu\n\n- Email gửi đúng 7h sáng mỗi ngày\n- Nội dung đúng format CDA duyệt\n\n**ETA:** tháng 7-8/2026"),
]


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--dry-run":
        print(f"Would create {len(EPICS)} Epics + {len(STORIES)} Stories = {len(EPICS)+len(STORIES)} issues")
        for e in EPICS:
            print(f"  Epic {e['id']}: {e['summary']}")
        for s in STORIES:
            print(f"  Story [{s[0]}]: {s[1]} ({s[3]}, {s[2]})")
        return

    # 1) Push Epics
    print("=== Pushing 6 Epics ===")
    epic_keys = {}
    for e in EPICS:
        key = create_issue(
            summary=e["summary"], body_md=e["body"], issuetype="Epic",
            priority=e["priority"], labels=e["labels"],
        )
        if key:
            epic_keys[e["id"]] = key
            print(f"  {e['id']} → {key}: {e['summary']}")
            # Transition if needed (default new = To Do)
            if e["status"] != "To Do":
                if transition_to(key, e["status"]):
                    print(f"    transitioned to {e['status']}")
            time.sleep(0.3)
        else:
            print(f"  FAILED to create {e['id']}: {e['summary']}", file=sys.stderr)
    print(f"Created {len(epic_keys)}/6 Epics")
    print()

    # 2) Push Stories
    print(f"=== Pushing {len(STORIES)} Stories ===")
    story_keys = []
    for idx, (eid, summary, prio, status, labels, body) in enumerate(STORIES, 1):
        parent_key = epic_keys.get(eid)
        if not parent_key:
            print(f"  SKIP Story #{idx} {summary}: no Epic for {eid}", file=sys.stderr)
            continue
        key = create_issue(
            summary=summary, body_md=body, issuetype="Story",
            parent=parent_key, priority=prio, labels=labels,
        )
        if key:
            story_keys.append((key, status, summary))
            print(f"  [{idx:2d}/{len(STORIES)}] {key} ({status}, {prio}): {summary[:60]}")
            time.sleep(0.25)
        else:
            print(f"  FAILED Story #{idx}: {summary}", file=sys.stderr)
    print(f"Created {len(story_keys)}/{len(STORIES)} Stories")
    print()

    # 3) Transition Stories that aren't "To Do"
    print("=== Transitioning Stories ===")
    transitioned = 0
    for key, status, summary in story_keys:
        if status == "To Do":
            continue
        if transition_to(key, status):
            transitioned += 1
        time.sleep(0.15)
    print(f"Transitioned {transitioned} Stories")

    # 4) Save mapping
    out = {
        "epics": epic_keys,
        "stories": [
            {"key": k, "status": s, "summary": summ}
            for k, s, summ in story_keys
        ],
    }
    out_path = REPO / ".docs/tasks/_owner_sync_2026-05-21.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"\nMapping saved to {out_path}")


if __name__ == "__main__":
    main()
