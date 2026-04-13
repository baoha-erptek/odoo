"""Build SRS_Multichannel_Hub_VN.xlsx v2 — simplified, Etsy API only.

Phiên bản này được viết lại hoàn toàn cho khách hàng nghiệp vụ (không có
background phần mềm). So với v1:
- Bỏ toàn bộ luồng email ingestion — Etsy API là nguồn đồng bộ đơn duy nhất.
- Giảm 24 sheet → 12 sheet.
- Giảm 128 req → ~65 req, tập trung vào những gì phòng ban đã đề xuất.
- Văn phong Tiếng Việt đời thường, không Odoo jargon.

Run: python3 specs/006-master-plan/build_srs.py
"""

from __future__ import annotations

import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation


OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(OUTPUT_DIR, "SRS_Multichannel_Hub_VN.xlsx")

DOC_TITLE = "SRS — Hệ thống quản lý đơn hàng Etsy"
DOC_VERSION = "v2.0 (bản đơn giản hoá cho nghiệp vụ)"
DOC_DATE = "2026-04-13"
DOC_OWNER = "Chủ dự án Etsy Shop"

# --- Styles ----------------------------------------------------------------

FONT_TITLE = Font(name="Calibri", size=18, bold=True, color="1F3864")
FONT_H1 = Font(name="Calibri", size=14, bold=True, color="1F3864")
FONT_H2 = Font(name="Calibri", size=12, bold=True, color="2E75B6")
FONT_HEADER = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
FONT_BODY = Font(name="Calibri", size=11)
FONT_BODY_B = Font(name="Calibri", size=11, bold=True)
FONT_SMALL = Font(name="Calibri", size=10, italic=True, color="595959")
FONT_LINK = Font(name="Calibri", size=11, color="0563C1", underline="single")

FILL_HEADER = PatternFill("solid", fgColor="2E75B6")
FILL_P0 = PatternFill("solid", fgColor="F8CBAD")  # bắt buộc — đỏ cam
FILL_P1 = PatternFill("solid", fgColor="FFE699")  # rất cần — vàng
FILL_P2 = PatternFill("solid", fgColor="C6E0B4")  # có cũng được — xanh
FILL_SECTION = PatternFill("solid", fgColor="DEEBF7")

THIN = Side(style="thin", color="BFBFBF")
BORDER_ALL = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

ALIGN_WRAP_TOP = Alignment(wrap_text=True, vertical="top", horizontal="left")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


def style_header_row(ws, row, ncols):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = BORDER_ALL
    ws.row_dimensions[row].height = 30


def apply_priority_fill(row_cells, priority):
    m = {"P0": FILL_P0, "P1": FILL_P1, "P2": FILL_P2}
    fill = m.get(priority)
    if fill:
        for cell in row_cells:
            cell.fill = fill


# --- Requirement sheet renderer -------------------------------------------

REQ_HEADERS = [
    ("Mã YC", 14),
    ("Tên yêu cầu", 36),
    ("Mô tả", 65),
    ("Ai đề xuất", 22),
    ("Ưu tiên", 10),
    ("Giai đoạn", 14),
]

PRIORITY_OPTIONS = '"P0,P1,P2"'
PHASE_OPTIONS = '"Giai đoạn 1,Giai đoạn 2,Giai đoạn 3"'


def build_req_sheet(wb, sheet_name, title_vn, intro, requirements):
    ws = wb.create_sheet(title=sheet_name)

    ws.merge_cells("A1:F1")
    ws["A1"] = title_vn
    ws["A1"].font = FONT_H1
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 26

    ws.merge_cells("A2:F2")
    ws["A2"] = intro
    ws["A2"].font = FONT_SMALL
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 40

    header_row = 4
    for col_idx, (header, width) in enumerate(REQ_HEADERS, start=1):
        ws.cell(row=header_row, column=col_idx, value=header)
        ws.column_dimensions[get_column_letter(col_idx)].width = width
    style_header_row(ws, header_row, len(REQ_HEADERS))

    data_start = header_row + 1
    for i, req in enumerate(requirements):
        r = data_start + i
        values = [req["id"], req["ten"], req["mota"], req["ai_yc"], req["priority"], req["phase"]]
        row_cells = []
        for c, val in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=val)
            cell.font = FONT_BODY_B if c == 2 else FONT_BODY
            cell.alignment = ALIGN_WRAP_TOP if c != 5 and c != 6 else ALIGN_CENTER
            cell.border = BORDER_ALL
            row_cells.append(cell)
        apply_priority_fill(row_cells, req["priority"])
        ws.row_dimensions[r].height = max(42, min(120, 18 + len(req["mota"]) // 4))

    ws.freeze_panes = f"A{data_start}"
    ws.auto_filter.ref = (
        f"A{header_row}:F{data_start + len(requirements) - 1}"
    )

    dv_pri = DataValidation(type="list", formula1=PRIORITY_OPTIONS, allow_blank=True)
    dv_phase = DataValidation(type="list", formula1=PHASE_OPTIONS, allow_blank=True)
    ws.add_data_validation(dv_pri)
    ws.add_data_validation(dv_phase)
    if requirements:
        dv_pri.add(f"E{data_start}:E{data_start + len(requirements) - 1}")
        dv_phase.add(f"F{data_start}:F{data_start + len(requirements) - 1}")

    return ws


# --- Sheet list for TOC ---------------------------------------------------

SHEETS = [
    ("00_Bia_MucLuc", "Bìa & Mục lục"),
    ("01_Tong_Quan_Lo_Trinh", "Tổng quan & Lộ trình 3 giai đoạn"),
    ("02_Vai_Tro_Nguoi_Dung", "Ai dùng hệ thống (các phòng ban)"),
    ("03_Dong_Bo_Don_Etsy", "Đồng bộ đơn từ Etsy (qua API)"),
    ("04_Chuan_Hoa_Du_Lieu_Cu", "Chuẩn hoá 17.659 đơn cũ"),
    ("05_Dashboard_Don_Hang", "Dashboard Đơn hàng (BA + Marketing)"),
    ("06_Dashboard_Tracking", "Dashboard Tracking (BA)"),
    ("07_Dashboard_San_Xuat", "Dashboard Sản xuất (PD)"),
    ("08_Quy_Trinh_Duyet", "Quy trình duyệt (file thiết kế / địa chỉ / ticket)"),
    ("09_Tracking_Va_Fulfillment", "Nhập tracking & đẩy đơn sản xuất"),
    ("10_Tinh_Nang_Mo_Rong", "Tính năng mở rộng (giai đoạn sau)"),
    ("11_Phe_Duyet", "Phê duyệt & chữ ký"),
]


# --- Cover -----------------------------------------------------------------

def build_cover(wb):
    ws = wb.create_sheet(title="00_Bia_MucLuc")
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 38
    ws.column_dimensions["C"].width = 70

    ws.merge_cells("A1:C1")
    ws["A1"] = DOC_TITLE
    ws["A1"].font = FONT_TITLE
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 42

    ws.merge_cells("A2:C2")
    ws["A2"] = "Tài liệu mô tả yêu cầu — viết cho nghiệp vụ đọc và phê duyệt"
    ws["A2"].font = FONT_H2
    ws["A2"].alignment = Alignment(horizontal="center")
    ws.row_dimensions[2].height = 22

    meta = [
        ("Phiên bản", DOC_VERSION),
        ("Ngày phát hành", DOC_DATE),
        ("Chủ dự án", DOC_OWNER),
        ("Trạng thái", "Bản nháp chờ các phòng ban duyệt"),
        (
            "Phạm vi",
            "Hệ thống quản lý đơn hàng Etsy tập trung: lấy đơn qua Etsy API, "
            "quản lý trên 3 dashboard, đưa đơn sang sản xuất hoặc đối tác.",
        ),
        (
            "Nguồn yêu cầu",
            "Feedback của Phòng BA, Phòng Marketing, Phòng Sản xuất (PD), "
            "Phòng Kiểm soát giá (Sales Audit) + đề xuất hệ thống mẫu.",
        ),
        (
            "Thay đổi so với bản v1 (2026-04-11)",
            "1. Không còn lấy đơn qua email — chỉ qua Etsy API.\n"
            "2. Giảm từ 24 xuống 12 sheet, tập trung nhu cầu thực tế.\n"
            "3. Viết lại bằng văn phong đời thường, bỏ thuật ngữ kỹ thuật.",
        ),
    ]
    row = 4
    for k, v in meta:
        ws.cell(row=row, column=2, value=k).font = FONT_BODY_B
        ws.cell(row=row, column=2).alignment = Alignment(vertical="top")
        ws.cell(row=row, column=3, value=v).font = FONT_BODY
        ws.cell(row=row, column=3).alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[row].height = 35 + v.count("\n") * 16
        row += 1

    # TOC
    row += 2
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    ws.cell(row=row, column=1, value="MỤC LỤC").font = FONT_H1
    ws.cell(row=row, column=1).alignment = Alignment(horizontal="center")
    ws.row_dimensions[row].height = 26
    row += 1

    for i, h in enumerate(["STT", "Sheet", "Nội dung"], start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font = FONT_HEADER
        c.fill = FILL_HEADER
        c.alignment = ALIGN_CENTER
        c.border = BORDER_ALL
    ws.row_dimensions[row].height = 24
    row += 1

    for idx, (sheet, desc) in enumerate(SHEETS, start=1):
        ws.cell(row=row, column=1, value=idx).alignment = ALIGN_CENTER
        link = ws.cell(row=row, column=2, value=sheet)
        link.hyperlink = f"#'{sheet}'!A1"
        link.font = FONT_LINK
        ws.cell(row=row, column=3, value=desc).alignment = Alignment(
            wrap_text=True, vertical="top"
        )
        for col in range(1, 4):
            ws.cell(row=row, column=col).border = BORDER_ALL
        row += 1

    row += 1
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
    note = (
        "Cách đọc: Mỗi sheet từ 03 đến 10 liệt kê các yêu cầu cụ thể, có cột "
        "'Ưu tiên' và 'Giai đoạn'. Ưu tiên P0 (nền cam) = bắt buộc làm trước; "
        "P1 (nền vàng) = rất cần; P2 (nền xanh) = có thể làm sau. Giai đoạn "
        "1/2/3 tương ứng với 3 đợt triển khai — xem chi tiết trong sheet "
        "'01_Tong_Quan_Lo_Trinh'."
    )
    c = ws.cell(row=row, column=1, value=note)
    c.font = FONT_SMALL
    c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[row].height = 70


# --- Overview + Roadmap ---------------------------------------------------

def build_overview(wb):
    ws = wb.create_sheet(title="01_Tong_Quan_Lo_Trinh")
    ws.column_dimensions["A"].width = 26
    ws.column_dimensions["B"].width = 90

    ws.merge_cells("A1:B1")
    ws["A1"] = "Tổng quan & Lộ trình 3 giai đoạn"
    ws["A1"].font = FONT_H1
    ws.row_dimensions[1].height = 28

    sections = [
        (
            "Hệ thống này làm gì?",
            "1. Tự động lấy đơn hàng mới từ Etsy (qua kết nối API).\n"
            "2. Hiển thị đơn trên 3 màn hình chuyên dụng cho BA, Marketing, "
            "Sản xuất.\n"
            "3. Cho đội thiết kế upload file in và đội PD duyệt file.\n"
            "4. Đưa đơn đã duyệt sang xưởng nội bộ hoặc đối tác Gearment, "
            "rồi cập nhật tracking ngược lên Etsy.",
        ),
        (
            "Ai sẽ dùng?",
            "Phòng BA (điều phối chính) — Phòng Marketing (quản store, trả "
            "khách) — Phòng Sản xuất PD (làm hàng, quản NVL) — Phòng Kiểm "
            "soát giá Sales Audit (kiểm tra giá bán) — Chủ dự án (duyệt "
            "pha).",
        ),
        (
            "Quyết định chiến lược",
            "• Chỉ dùng Etsy API để đồng bộ đơn, không dùng email.\n"
            "• Vận hành trên Odoo 19 (bản miễn phí, không mua Enterprise).\n"
            "• Tiếng Việt là ngôn ngữ giao diện mặc định.\n"
            "• Gearment là đối tác fulfillment chính ở giai đoạn 2.",
        ),
    ]

    row = 3
    for title, content in sections:
        ws.cell(row=row, column=1, value=title).font = FONT_BODY_B
        ws.cell(row=row, column=1).fill = FILL_SECTION
        ws.cell(row=row, column=1).alignment = Alignment(vertical="top")
        ws.cell(row=row, column=2, value=content).font = FONT_BODY
        ws.cell(row=row, column=2).alignment = Alignment(wrap_text=True, vertical="top")
        for col in range(1, 3):
            ws.cell(row=row, column=col).border = BORDER_ALL
        ws.row_dimensions[row].height = 40 + content.count("\n") * 18
        row += 1

    # Roadmap table
    row += 2
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=2)
    ws.cell(row=row, column=1, value="Lộ trình 3 giai đoạn").font = FONT_H1
    ws.cell(row=row, column=1).alignment = Alignment(horizontal="left")
    ws.row_dimensions[row].height = 26
    row += 1

    roadmap_headers = ["Giai đoạn", "Nội dung & điều kiện nghiệm thu"]
    for i, h in enumerate(roadmap_headers, start=1):
        ws.cell(row=row, column=i, value=h)
    style_header_row(ws, row, 2)
    row += 1

    phases = [
        (
            "Giai đoạn 1 — MVP (khoảng 3-4 tháng)",
            "• Kết nối Etsy API và tự lấy đơn mới.\n"
            "• Chuẩn hoá 17.659 đơn cũ (sửa 423 đơn giá 0, gán tiền tệ, gộp "
            "khách trùng có BA duyệt).\n"
            "• 3 dashboard: Đơn hàng, Tracking, Sản xuất.\n"
            "• Duyệt file thiết kế và duyệt đổi địa chỉ.\n"
            "• Nhập tracking từ file Excel GKE Logistics.\n"
            "ĐIỀU KIỆN KÝ NHẬN: BA Lead ký đối chiếu dữ liệu cũ; các phòng "
            "ban chạy Odoo thay thế Google Sheet 1 tháng, sai lệch <1%.",
        ),
        (
            "Giai đoạn 2 — Mở rộng (khoảng 3-4 tháng)",
            "• Đẩy đơn sang Gearment qua API và nhận tracking về.\n"
            "• Hệ thống ticket cho yêu cầu replace/refund (BA duyệt).\n"
            "• Dashboard kiểm soát giá (Pricing Audit) với quy đổi EUR.\n"
            "• Xuất lịch sử tin nhắn Etsy ra file Excel.\n"
            "ĐIỀU KIỆN KÝ NHẬN: đơn Gearment đi live không lỗi 2 tuần liên "
            "tiếp; phòng Sales Audit nghiệm thu dashboard.",
        ),
        (
            "Giai đoạn 3 — Tương lai (khoảng 4-6 tháng)",
            "• Quản lý tồn kho nguyên vật liệu + dự báo 1/3/12 tháng.\n"
            "• Catalog Dashboard cho từng sản phẩm (template, mockup, đơn "
            "đã bán).\n"
            "• Scan sheet barcode cho PD.\n"
            "• Mở thêm kênh Amazon và Website.\n"
            "ĐIỀU KIỆN KÝ NHẬN: quyết định chi tiết đưa ra khi kết thúc Giai "
            "đoạn 2, dựa trên feedback thực tế.",
        ),
    ]
    for phase, content in phases:
        ws.cell(row=row, column=1, value=phase).font = FONT_BODY_B
        ws.cell(row=row, column=1).alignment = Alignment(wrap_text=True, vertical="top")
        ws.cell(row=row, column=1).fill = FILL_P0 if "1" in phase else FILL_P1 if "2" in phase else FILL_P2
        ws.cell(row=row, column=2, value=content).font = FONT_BODY
        ws.cell(row=row, column=2).alignment = Alignment(wrap_text=True, vertical="top")
        for col in range(1, 3):
            ws.cell(row=row, column=col).border = BORDER_ALL
        ws.row_dimensions[row].height = 130
        row += 1


# --- Actors ---------------------------------------------------------------

def build_actors(wb):
    ws = wb.create_sheet(title="02_Vai_Tro_Nguoi_Dung")
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 26
    ws.column_dimensions["C"].width = 45
    ws.column_dimensions["D"].width = 45

    ws.merge_cells("A1:D1")
    ws["A1"] = "Ai dùng hệ thống"
    ws["A1"].font = FONT_H1
    ws.row_dimensions[1].height = 28

    for i, h in enumerate(["STT", "Phòng ban / Vai trò", "Công việc chính", "Màn hình họ dùng nhiều nhất"], start=1):
        ws.cell(row=3, column=i, value=h)
    style_header_row(ws, 3, 4)

    actors = [
        (
            "Chủ dự án",
            "Quyết định chiến lược, ký duyệt từng giai đoạn, theo dõi tiến độ "
            "và kết quả tổng.",
            "Bản tóm tắt chỉ số hằng tuần; tất cả các dashboard (đọc).",
        ),
        (
            "Phòng BA",
            "Điều phối chính: rà soát đơn khó, duyệt đổi địa chỉ, duyệt "
            "ticket replace/refund, đảm bảo chất lượng dữ liệu, đối chiếu "
            "với Google Sheet cũ.",
            "Dashboard Đơn hàng, Dashboard Tracking, Duyệt đổi địa chỉ, "
            "Ticket.",
        ),
        (
            "Phòng Marketing (MP)",
            "Quản lý các store Etsy, push đơn ưu tiên, trả lời khách, gửi "
            "yêu cầu đổi địa chỉ, bật/tắt tự động đẩy tracking.",
            "Dashboard Đơn hàng, form chi tiết đơn, popup thông báo.",
        ),
        (
            "Phòng Sản xuất (PD)",
            "Làm hàng thực tế: in, thêu, khắc, ép nhiệt; scan hàng khi xong, "
            "quản tồn kho nguyên vật liệu.",
            "Dashboard Sản xuất, Scan sheet, màn hình tồn kho NVL.",
        ),
        (
            "Phòng Kiểm soát giá (Sales Audit)",
            "Đảm bảo đơn được bán đúng giá chính sách, phát hiện đơn lệch "
            "giá, báo cáo đa tiền tệ.",
            "Dashboard Kiểm soát giá (Pricing Audit).",
        ),
    ]

    for i, (role, work, screens) in enumerate(actors, start=1):
        r = 3 + i
        ws.cell(row=r, column=1, value=i).alignment = ALIGN_CENTER
        ws.cell(row=r, column=2, value=role).font = FONT_BODY_B
        ws.cell(row=r, column=3, value=work).font = FONT_BODY
        ws.cell(row=r, column=4, value=screens).font = FONT_BODY
        for col in range(1, 5):
            cell = ws.cell(row=r, column=col)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = BORDER_ALL
        ws.row_dimensions[r].height = 70

    ws.freeze_panes = "A4"


# --- Requirements data ----------------------------------------------------

def reqs_etsy_sync():
    return [
        {
            "id": "REQ-SYN-01",
            "ten": "Kết nối tài khoản Etsy an toàn",
            "mota": (
                "Chủ shop vào menu Cài đặt, bấm 'Kết nối Etsy' và đăng "
                "nhập một lần. Hệ thống nhớ kết nối và tự gia hạn khi "
                "gần hết hạn. Admin nhận cảnh báo trước 7 ngày khi phải "
                "đăng nhập lại."
            ),
            "ai_yc": "Chủ dự án",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-SYN-02",
            "ten": "Tự động lấy đơn mới từ Etsy mỗi 5 phút",
            "mota": (
                "Hệ thống tự kéo đơn mới hoặc đơn bị sửa từ Etsy về Odoo "
                "mỗi 5 phút. Đơn đã có thì không bị tạo trùng. Sau 5 "
                "phút, đơn mới trên Etsy xuất hiện trên dashboard."
            ),
            "ai_yc": "Phòng BA, Marketing",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-SYN-03",
            "ten": "Không ghi đè dữ liệu do nghiệp vụ nhập",
            "mota": (
                "Khi Etsy báo cập nhật một đơn đã có, hệ thống chỉ cập "
                "nhật trạng thái thanh toán/vận chuyển từ Etsy, giữ "
                "nguyên note MP, người phụ trách, trạng thái duyệt file "
                "đã nhập bởi các phòng ban."
            ),
            "ai_yc": "Phòng BA",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-SYN-04",
            "ten": "Đẩy tracking về Etsy tự động",
            "mota": (
                "Khi BA nhập tracking + đơn vị vận chuyển, hệ thống gửi "
                "thông tin này về Etsy trong vòng 5 phút để khách hàng "
                "nhìn thấy trên đơn Etsy."
            ),
            "ai_yc": "Phòng BA, Marketing",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-SYN-05",
            "ten": "Công tắc bật/tắt tự động đẩy tracking",
            "mota": (
                "Marketing có nút bật/tắt 'Tự động đẩy tracking lên Etsy' "
                "theo từng store. Khi tắt, tracking nhập vào nhưng không "
                "được gửi tới Etsy."
            ),
            "ai_yc": "Phòng Marketing",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-SYN-06",
            "ten": "Xuất lịch sử tin nhắn Etsy",
            "mota": (
                "Marketing chọn khoảng thời gian và bấm 'Xuất tin nhắn', "
                "hệ thống tải xuống file Excel chứa tất cả tin nhắn đã "
                "nhận để lưu trữ và rà soát."
            ),
            "ai_yc": "Phòng Marketing (#6)",
            "priority": "P1",
            "phase": "Giai đoạn 2",
        },
    ]


def reqs_data_cleanup():
    return [
        {
            "id": "REQ-MIG-01",
            "ten": "Upload dữ liệu 17.659 đơn cũ từ Excel",
            "mota": (
                "Admin upload file Excel lịch sử, hệ thống đọc và tạo "
                "các đơn hàng tương ứng trong Odoo. Nếu bị gián đoạn "
                "giữa chừng, chạy lại sẽ tiếp tục từ điểm dừng."
            ),
            "ai_yc": "Chủ dự án",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-MIG-02",
            "ten": "Sửa 423 đơn đang có giá 0",
            "mota": (
                "Có 423 đơn hiện bị ghi nhận giá 0. Hệ thống sẽ tính "
                "lại giá từ file nguồn; đơn nào không khôi phục được "
                "sẽ được gộp vào danh sách để BA xử lý thủ công."
            ),
            "ai_yc": "Phòng Sales Audit",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-MIG-03",
            "ten": "Nhận diện đúng tiền tệ USD / EUR / GBP / CAD / VND",
            "mota": (
                "Hệ thống đọc ký hiệu tiền ($, €, £, C$, ₫) trong dữ "
                "liệu nguồn và gán đúng loại tiền cho từng đơn. Đơn "
                "vẫn giữ tiền gốc, không bị quy đổi sai."
            ),
            "ai_yc": "Phòng Sales Audit",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-MIG-04",
            "ten": "Tách phí vận chuyển thành dòng riêng trên đơn",
            "mota": (
                "Mỗi đơn có 1 dòng 'Phí vận chuyển Etsy' riêng với đúng "
                "giá ship, để tổng tiền đơn khớp với dữ liệu gốc trong "
                "sai số 0.01."
            ),
            "ai_yc": "Phòng Sales Audit",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-MIG-05",
            "ten": "Gộp khách hàng trùng (có BA duyệt)",
            "mota": (
                "Hệ thống đề xuất danh sách khách hàng có thể là một "
                "người và xuất ra file Excel. BA xem, đánh dấu đồng ý, "
                "rồi upload lại để hệ thống gộp. KHÔNG tự gộp."
            ),
            "ai_yc": "Phòng BA",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-MIG-06",
            "ten": "Báo cáo đối chiếu & ký nhận",
            "mota": (
                "Sau khi chạy chuẩn hoá, hệ thống xuất báo cáo đối chiếu "
                "giữa Excel cũ và Odoo (tổng đơn, doanh thu, phí ship, "
                "số đơn lỗi). BA Lead ký duyệt trước khi bước vào Giai "
                "đoạn tiếp theo."
            ),
            "ai_yc": "Chủ dự án, BA",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
    ]


def reqs_order_dashboard():
    return [
        {
            "id": "REQ-ORD-01",
            "ten": "Hiển thị 10 cột cốt lõi theo đề xuất",
            "mota": (
                "Dashboard Đơn hàng hiển thị đúng 10 cột: Shop, Order "
                "ID, Tracking, IMG (ảnh sản phẩm), Date, Tình trạng, "
                "Quantity, Shipping Service, Country, Giá tổng. Thứ tự "
                "cột giống file 'Đề xuất hệ thống mẫu'."
            ),
            "ai_yc": "Phòng BA (#1)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-02",
            "ten": "Shop và Order ID đặt ở 2 cột đầu",
            "mota": (
                "Cột đầu tiên là Shop, cột thứ hai là Order ID. Thanh "
                "tìm kiếm hoạt động trên cả hai cột để tìm đơn nhanh."
            ),
            "ai_yc": "Phòng BA (#1)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-03",
            "ten": "Bỏ cột Ngày đi hàng, Giá lẻ, PIC",
            "mota": (
                "Không hiển thị các cột: Ngày đi hàng (tự set khi PD "
                "scan), Giá bán/Giá ship/Discount riêng lẻ (chỉ giữ "
                "Giá tổng), Người phụ trách (xem qua shop và hoạt động "
                "là đủ)."
            ),
            "ai_yc": "Phòng BA (#1)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-04",
            "ten": "Gộp Tracking + Label + Carrier thành 1 cột",
            "mota": (
                "Cột 'Tracking' hiển thị 3 trạng thái: 'Chờ mua label' "
                "(chưa có tem), 'Đang mua label' (đang xử lý), hoặc "
                "hiện số tracking + tên đơn vị vận chuyển khi đã có."
            ),
            "ai_yc": "Phòng BA (#1), Đề xuất hệ thống mẫu",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-05",
            "ten": "Hiển thị ảnh sản phẩm trên mỗi đơn",
            "mota": (
                "Mỗi hàng có 1 ảnh thumbnail sản phẩm chính (128px). "
                "Click vào thumbnail để xem ảnh lớn mà không cần mở "
                "form đơn."
            ),
            "ai_yc": "Phòng Marketing (#2, #10 — nhắc 2 lần)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-06",
            "ten": "Sửa nhanh tại chỗ các cột thao tác",
            "mota": (
                "BA có thể chỉnh sửa nhanh tại hàng các cột: Tracking, "
                "Đơn vị vận chuyển, Trạng thái label, Tình trạng đơn, "
                "Ghi chú — mà không cần mở form chi tiết."
            ),
            "ai_yc": "Phòng BA, Marketing",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-07",
            "ten": "Tô màu hàng theo loại đơn",
            "mota": (
                "Quy tắc màu: đơn có số lượng ≥ 2 → màu cam; đơn trùng "
                "mã (2+ đơn cùng mã) → màu tím; đơn đã bấm Push → màu "
                "đỏ; đơn Amazon → màu đỏ."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-08",
            "ten": "Nút Push đánh dấu đơn ưu tiên",
            "mota": (
                "Marketing bấm nút 'Push' trên đơn → đơn được đánh "
                "dấu ưu tiên và tô màu đỏ. Lịch sử thao tác ghi lại "
                "ai push và khi nào."
            ),
            "ai_yc": "Phòng Marketing (#4)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-09",
            "ten": "Biểu tượng quá hạn duyệt (>2 ngày)",
            "mota": (
                "Đơn quá 2 ngày chưa được duyệt file thiết kế sẽ có "
                "biểu tượng cảnh báo và tô màu vàng trên dashboard."
            ),
            "ai_yc": "Phòng Marketing (#7)",
            "priority": "P2",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-10",
            "ten": "Cột hạn đẩy tracking (ship-by date)",
            "mota": (
                "Thêm cột 'Hạn add tracking' tương ứng với 'ship by "
                "date' từ Etsy để Marketing biết hạn chót mà Etsy yêu "
                "cầu cập nhật tracking. Hàng đỏ nếu quá hạn."
            ),
            "ai_yc": "Phòng Marketing (#3)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-11",
            "ten": "Biểu tượng người quản lý store",
            "mota": (
                "Mỗi đơn hiển thị avatar (hoặc icon) của người quản lý "
                "store để nhìn là biết ngay đơn thuộc ai."
            ),
            "ai_yc": "Phòng Marketing (#8)",
            "priority": "P2",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-12",
            "ten": "Popup thông báo sự kiện đặc biệt",
            "mota": (
                "Khi có đơn được push, hold, hoặc yêu cầu đổi địa chỉ, "
                "hệ thống hiện popup thông báo đến đúng người phụ "
                "trách trong vòng 10 giây."
            ),
            "ai_yc": "Phòng Marketing (#9)",
            "priority": "P2",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-13",
            "ten": "Trường 'Ghi chú MP' trong đơn",
            "mota": (
                "Form chi tiết đơn có thêm trường 'Ghi chú MP' tách "
                "riêng với 'Note từ Sale', để Marketing ghi các yêu "
                "cầu custom của khách."
            ),
            "ai_yc": "Phòng BA (#6)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-14",
            "ten": "Lịch sử cập nhật trạng thái đơn",
            "mota": (
                "Mỗi đơn có tab lịch sử cho thấy ai đổi trạng thái, "
                "khi nào, từ giá trị gì sang giá trị gì. Marketing "
                "xem lại được toàn bộ thao tác."
            ),
            "ai_yc": "Phòng BA (#4), Marketing (#5)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-ORD-15",
            "ten": "Tên sản phẩm hiện rõ, BA có thể phân loại thủ công",
            "mota": (
                "Mỗi đơn hiển thị tên sản phẩm chính. BA có thể tick "
                "chọn loại sản phẩm nếu hệ thống phân loại tự động "
                "chưa đúng."
            ),
            "ai_yc": "Phòng BA (#9)",
            "priority": "P2",
            "phase": "Giai đoạn 1",
        },
    ]


def reqs_tracking_dashboard():
    return [
        {
            "id": "REQ-TRK-01",
            "ten": "Trang Tracking riêng (không phải filter của Order Dashboard)",
            "mota": (
                "Menu 'Tracking' mở một trang riêng biệt, chuyên cho "
                "BA thao tác mua tem và nhập tracking."
            ),
            "ai_yc": "Phòng BA (#2)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-TRK-02",
            "ten": "Hiển thị 13 cột tracking",
            "mota": (
                "Cột: Order ID, Tracking, Đơn vị vận chuyển, Tình "
                "trạng, Loại sản phẩm, Quantity, Tên, Địa chỉ 1, Địa "
                "chỉ 2, Thành phố, Bang, Zip, Quốc gia."
            ),
            "ai_yc": "Phòng BA, Đề xuất hệ thống mẫu",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-TRK-03",
            "ten": "Export danh sách đơn ra Excel",
            "mota": (
                "BA bấm 'Export' để tải file Excel chứa các đơn theo "
                "bộ lọc hiện tại, phục vụ việc mua tem bên ngoài."
            ),
            "ai_yc": "Phòng BA (#2)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-TRK-04",
            "ten": "Chuyển hàng loạt trạng thái label",
            "mota": (
                "BA chọn nhiều đơn cùng lúc và chuyển từ 'Chờ mua "
                "label' sang 'Đang mua label' trong 1 thao tác."
            ),
            "ai_yc": "Phòng BA (#2)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-TRK-05",
            "ten": "Thanh tìm kiếm theo tracking / Order ID / tên khách",
            "mota": (
                "Ô search nhanh trên đầu trang: gõ tracking hoặc "
                "Order ID là ra ngay."
            ),
            "ai_yc": "Phòng BA (#2)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-TRK-06",
            "ten": "Đồng bộ ngay về Dashboard Đơn hàng",
            "mota": (
                "Khi BA cập nhật tracking hay trạng thái label ở đây, "
                "Dashboard Đơn hàng (bên ngoài) phản ánh thay đổi "
                "trong vòng 5 giây."
            ),
            "ai_yc": "Phòng BA (#2)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-TRK-07",
            "ten": "Ngăn mua label trùng khi đơn đang đổi địa chỉ",
            "mota": (
                "Nếu đơn có yêu cầu đổi địa chỉ đang chờ duyệt, nút "
                "'Mua label' bị vô hiệu và hiện cảnh báo để tránh "
                "mua tem sai địa chỉ."
            ),
            "ai_yc": "Phòng BA (#5 — an toàn)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
    ]


def reqs_process_dashboard():
    return [
        {
            "id": "REQ-PRO-01",
            "ten": "Đổi tên thành 'Dashboard Sản xuất' (Process Dashboard)",
            "mota": (
                "Không đặt tên là 'trang của PD' vì BA và PD cùng "
                "thao tác, cả đơn VN và US."
            ),
            "ai_yc": "Phòng BA (#10)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-PRO-02",
            "ten": "Hiển thị 19 cột sản xuất theo đề xuất PD",
            "mota": (
                "Các cột: Ngày duyệt file, Download file, Tình trạng, "
                "Note, Ảnh, Gift message, Personalisation, Loại sản "
                "phẩm, Option, Quantity, Mã đơn, Shop, Tên khách, "
                "Địa chỉ, Shipping service, Ngày đặt, Ngày đi, Scan "
                "hàng, Thống kê tự động."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-PRO-03",
            "ten": "12 trạng thái sản xuất có màu",
            "mota": (
                "Trạng thái tiếng Việt có màu: Chờ sản xuất / Đã sản "
                "xuất / Sản xuất 1 phần / NG-sx lại / Fix đơn / Duyệt "
                "sai / SP thêu (hồng) / SP khắc (nâu) / SP ép nhiệt "
                "(cam) / SP mới (xanh) / Fulfilled (xanh) / Quá hạn "
                "sản xuất (xanh)."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-PRO-04",
            "ten": "Danh sách Loại sản phẩm và Option",
            "mota": (
                "Dropdown Loại sản phẩm: Ceramic dish, Tattoo, Khăn "
                "tay, Đĩa gỗ, Thớt gỗ, Chuông gió, Door hanger, "
                "Recipe dish, Bandana, Baby Bib, Tạp dề, Túi tote, "
                "Mug, Sticker… Dropdown Option: Wave/Heart/Circle "
                "square, Recipe Dish A/B/C với các kích thước, Wooden "
                "Ring Dish, Size S/M/L… Quản trị có thể bổ sung."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-PRO-05",
            "ten": "Hiển thị ảnh thiết kế và ảnh preview",
            "mota": (
                "Mỗi hàng có 2 thumbnail: file thiết kế gốc (đã thu "
                "nhỏ) và ảnh preview. PD và MP nhìn là biết ngay."
            ),
            "ai_yc": "Phòng Marketing (#2)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-PRO-06",
            "ten": "Widget thống kê theo trạng thái / option / loại",
            "mota": (
                "Phía trên dashboard có widget đếm đơn theo 4 chiều: "
                "tình trạng, option, loại sản phẩm, quantity."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P2",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-PRO-07",
            "ten": "Scan hàng chuyển trạng thái 'Fulfilled'",
            "mota": (
                "PD quét mã vạch trên đơn → trạng thái chuyển "
                "'Fulfilled', ngày đi hàng được ghi tự động, lịch sử "
                "log lại ai scan lúc nào."
            ),
            "ai_yc": "Phòng Sản xuất (PD), BA (#1)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-PRO-08",
            "ten": "4 trạng thái sản xuất nội bộ",
            "mota": (
                "Xếp hàng → Đang làm → Kiểm tra chất lượng → Hoàn "
                "thành. Khi Hoàn thành, trạng thái đơn chung thành "
                "'Đã sản xuất' và tồn kho NVL bị trừ tương ứng."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
    ]


def reqs_approval_workflows():
    return [
        # Design file approval
        {
            "id": "REQ-DUY-01",
            "ten": "Upload file in kích thước lớn, xoá và up lại được",
            "mota": (
                "Designer upload file in lớn (ví dụ 150MB) lên từng "
                "đơn. Có thể xoá file up sai và up lại bản mới; các "
                "bản cũ vẫn lưu để truy vết."
            ),
            "ai_yc": "Phòng BA (#8)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-DUY-02",
            "ten": "Quy trình duyệt file 3 trạng thái",
            "mota": (
                "File đi qua: 'Chờ duyệt' → 'Đã duyệt' hoặc 'Cần "
                "chỉnh lại'. Khi chọn 'Cần chỉnh lại' phải nhập lý "
                "do. Hệ thống ghi lại ai duyệt và khi nào."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-DUY-03",
            "ten": "Hàng đợi thiết kế dạng kanban",
            "mota": (
                "Designer xem hàng đợi dưới dạng 3 cột kanban theo "
                "trạng thái, có thể kéo-thả hoặc bấm chuyển trạng "
                "thái (nếu có quyền)."
            ),
            "ai_yc": "Designer, BA",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        # Address change
        {
            "id": "REQ-DUY-04",
            "ten": "Duyệt đổi địa chỉ — an toàn quan trọng",
            "mota": (
                "Marketing không sửa được địa chỉ trực tiếp. Muốn đổi "
                "phải tạo yêu cầu → BA nhận thông báo → BA duyệt hoặc "
                "từ chối. Chỉ sau khi BA duyệt, Marketing mới sửa "
                "được địa chỉ mới."
            ),
            "ai_yc": "Phòng BA (#5 — an toàn)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-DUY-05",
            "ten": "Khoá mua tem khi có yêu cầu đổi địa chỉ",
            "mota": (
                "Khi 1 đơn đang có yêu cầu đổi địa chỉ chưa duyệt, "
                "hệ thống khoá các thao tác mua tem để không mua trùng "
                "với địa chỉ cũ. Có badge cảnh báo trên Tracking."
            ),
            "ai_yc": "Phòng BA (#5 — an toàn)",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        # Ticket
        {
            "id": "REQ-DUY-06",
            "ten": "Tạo ticket replace/refund từ chi tiết đơn",
            "mota": (
                "Trong form chi tiết đơn có nút 'Tạo ticket'. "
                "Marketing nhập lý do (kèm ảnh nếu có) và chọn "
                "replace/refund/discount, gửi BA duyệt."
            ),
            "ai_yc": "Phòng BA (#3)",
            "priority": "P1",
            "phase": "Giai đoạn 2",
        },
        {
            "id": "REQ-DUY-07",
            "ten": "BA duyệt ticket, hệ thống tự xử lý",
            "mota": (
                "Khi BA duyệt: ticket refund → tạo credit note; "
                "ticket replace → tạo đơn mới liên kết đơn gốc; "
                "ticket discount → ghi giảm giá. Ticket đóng sau khi "
                "xử lý."
            ),
            "ai_yc": "Phòng BA (#3)",
            "priority": "P1",
            "phase": "Giai đoạn 2",
        },
        {
            "id": "REQ-DUY-08",
            "ten": "Lịch sử ticket hiển thị trong đơn",
            "mota": (
                "Tab 'Lịch sử' của đơn hiển thị toàn bộ thao tác "
                "ticket (tạo, duyệt, từ chối, đóng) kèm người thao "
                "tác và thời gian."
            ),
            "ai_yc": "Phòng BA (#4)",
            "priority": "P2",
            "phase": "Giai đoạn 2",
        },
    ]


def reqs_tracking_fulfillment():
    return [
        # GKE import
        {
            "id": "REQ-TRF-01",
            "ten": "Nhập tracking từ file Excel GKE Logistics",
            "mota": (
                "BA upload file Excel chuẩn của GKE (19 hoặc 20 cột). "
                "Hệ thống khớp mã đơn với Etsy Order ID và tự điền "
                "tracking + đơn vị vận chuyển. Các hàng không khớp "
                "được log để BA xử lý thủ công."
            ),
            "ai_yc": "Phòng BA (#2), Logistics",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-TRF-02",
            "ten": "Tự nhận diện đơn vị vận chuyển từ tracking",
            "mota": (
                "Hệ thống nhận diện tự động: số thuần 20-22 chữ số → "
                "USPS; bắt đầu 'UU' → UniUni; bắt đầu 'YT' → "
                "YunExpress; khác → 'Khác'."
            ),
            "ai_yc": "Phòng Logistics",
            "priority": "P0",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-TRF-03",
            "ten": "Xử lý đơn '-replace' và lưu URL label + QR",
            "mota": (
                "Đơn có hậu tố '-replace' được đánh dấu là đơn thay "
                "thế và liên kết với đơn gốc. File Excel có URL label "
                "và URL QR code được lưu vào đơn để BA truy cập in tem."
            ),
            "ai_yc": "Phòng BA, Logistics",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        {
            "id": "REQ-TRF-04",
            "ten": "Báo cáo import (khớp / không khớp)",
            "mota": (
                "Sau khi import, wizard hiển thị tóm tắt: N đơn khớp, "
                "M đơn không khớp, số đơn vị vận chuyển nhận diện "
                "đúng. BA click xem chi tiết từng dòng lỗi."
            ),
            "ai_yc": "Phòng BA",
            "priority": "P1",
            "phase": "Giai đoạn 1",
        },
        # Gearment
        {
            "id": "REQ-TRF-05",
            "ten": "Kết nối Gearment và đẩy đơn sang sản xuất",
            "mota": (
                "Quản trị cấu hình kết nối Gearment một lần. Sau khi "
                "file thiết kế đã duyệt, BA bấm 'Đẩy sang Gearment' "
                "để gửi đơn + file thiết kế sang đối tác."
            ),
            "ai_yc": "Chủ dự án, BA",
            "priority": "P0",
            "phase": "Giai đoạn 2",
        },
        {
            "id": "REQ-TRF-06",
            "ten": "Quy trình 4 bước trước khi Gearment sản xuất",
            "mota": (
                "Đơn Gearment đi qua: tạo nháp → lấy báo giá → BA/"
                "operator xem và duyệt → xác nhận. Không xác nhận "
                "trực tiếp không qua bước duyệt báo giá."
            ),
            "ai_yc": "Phòng BA",
            "priority": "P0",
            "phase": "Giai đoạn 2",
        },
        {
            "id": "REQ-TRF-07",
            "ten": "Nhận tracking và trạng thái từ Gearment",
            "mota": (
                "Khi Gearment hoàn thành hoặc ship đơn, hệ thống nhận "
                "tracking và cập nhật vào đơn tương ứng trong Odoo, "
                "tự đẩy tiếp lên Etsy (nếu MP bật auto-push)."
            ),
            "ai_yc": "Phòng BA, Marketing",
            "priority": "P0",
            "phase": "Giai đoạn 2",
        },
        {
            "id": "REQ-TRF-08",
            "ten": "Xử lý lỗi và thử lại khi Gearment không phản hồi",
            "mota": (
                "Nếu Gearment không phản hồi tức thời, hệ thống tự "
                "thử lại tối đa 3 lần. Nếu vẫn không được, log lỗi "
                "và cảnh báo admin để xử lý."
            ),
            "ai_yc": "Chủ dự án",
            "priority": "P1",
            "phase": "Giai đoạn 2",
        },
    ]


def reqs_extensions():
    return [
        # Pricing audit
        {
            "id": "REQ-EXT-01",
            "ten": "Dashboard Kiểm soát giá (Pricing Audit) cho Sales Audit",
            "mota": (
                "Dashboard riêng 25 cột cho phòng Sales Audit: cột "
                "A-F nhập tay, G-T tự lấy từ đơn. Hiển thị cả đơn đa "
                "tiền tệ."
            ),
            "ai_yc": "Phòng Sales Audit (RD)",
            "priority": "P1",
            "phase": "Giai đoạn 2",
        },
        {
            "id": "REQ-EXT-02",
            "ten": "Quy đổi giá về EURO cho các shop USD/VND/CAD",
            "mota": (
                "Đơn thuộc shop ngoại tệ khác EUR được tự động quy "
                "đổi sang EUR theo tỷ giá ngày đặt đơn, hiển thị cột "
                "'Giá tổng (EUR)'."
            ),
            "ai_yc": "Phòng Sales Audit (RD)",
            "priority": "P1",
            "phase": "Giai đoạn 2",
        },
        {
            "id": "REQ-EXT-03",
            "ten": "Tô màu theo chênh lệch giá bán vs giá catalog",
            "mota": (
                "So sánh giá bán với giá catalog: đỏ (thấp hơn), "
                "vàng (bằng), tím (cao hơn). Sales Audit lọc nhanh "
                "đơn bán lệch giá."
            ),
            "ai_yc": "Phòng Sales Audit (RD)",
            "priority": "P1",
            "phase": "Giai đoạn 2",
        },
        # Inventory
        {
            "id": "REQ-EXT-04",
            "ten": "Upload tồn kho NVL từ Excel",
            "mota": (
                "PD upload file Excel tồn kho nguyên vật liệu đầu kỳ, "
                "hệ thống tạo tồn kho ban đầu trong kho 'Nguyên vật "
                "liệu'."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P1",
            "phase": "Giai đoạn 3",
        },
        {
            "id": "REQ-EXT-05",
            "ten": "Tự trừ NVL khi chuyển 'Đã sản xuất'",
            "mota": (
                "Khi đơn chuyển 'Đã sản xuất', hệ thống tự trừ NVL "
                "tương ứng theo định mức sản phẩm. Tồn kho cập nhật "
                "tức thời."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P1",
            "phase": "Giai đoạn 3",
        },
        {
            "id": "REQ-EXT-06",
            "ten": "Dự báo NVL 1 / 3 / 12 tháng",
            "mota": (
                "Dashboard hiển thị NVL còn đủ dùng cho 1, 3, 12 "
                "tháng tới dựa trên tốc độ tiêu thụ + đơn backlog."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P2",
            "phase": "Giai đoạn 3",
        },
        {
            "id": "REQ-EXT-07",
            "ten": "Cảnh báo NVL sắp hết (<2 tháng)",
            "mota": (
                "Khi NVL còn đủ dùng dưới 2 tháng, PD Lead nhận "
                "thông báo và dashboard tô đỏ."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P2",
            "phase": "Giai đoạn 3",
        },
        # Catalog
        {
            "id": "REQ-EXT-08",
            "ten": "Catalog Dashboard theo từng sản phẩm",
            "mota": (
                "Click vào 1 sản phẩm mở form tổng hợp: template "
                "thiết kế, ảnh mockup, danh sách đơn đã bán."
            ),
            "ai_yc": "Phòng BA (#7)",
            "priority": "P2",
            "phase": "Giai đoạn 3",
        },
        {
            "id": "REQ-EXT-09",
            "ten": "Lưu template và mockup trên sản phẩm",
            "mota": (
                "Mỗi sản phẩm có 2 trường file: file template gốc và "
                "ảnh mockup dùng để preview trong catalog."
            ),
            "ai_yc": "Phòng BA (#7)",
            "priority": "P2",
            "phase": "Giai đoạn 3",
        },
        # Scan
        {
            "id": "REQ-EXT-10",
            "ten": "Scan sheet barcode riêng cho PD",
            "mota": (
                "Trang scan đơn giản dành cho PD quét mã vạch liên "
                "tục: ô nhập tự focus, enter xác nhận, hiển thị đơn "
                "vừa scan và trạng thái."
            ),
            "ai_yc": "Phòng BA (#11), PD",
            "priority": "P2",
            "phase": "Giai đoạn 3",
        },
        {
            "id": "REQ-EXT-11",
            "ten": "Scan kết quả đồng bộ về tất cả dashboard",
            "mota": (
                "Mỗi lần scan cập nhật đồng thời Dashboard Đơn hàng "
                "và Dashboard Sản xuất trong vòng 5 giây."
            ),
            "ai_yc": "Phòng BA, PD",
            "priority": "P2",
            "phase": "Giai đoạn 3",
        },
        # Amazon / Website
        {
            "id": "REQ-EXT-12",
            "ten": "Tích hợp kênh Amazon (đã được PD gắn tag đỏ)",
            "mota": (
                "Thêm kết nối Amazon Seller Central để lấy đơn và "
                "đẩy tracking, tương tự cách làm với Etsy. Đơn "
                "Amazon hiện trên Dashboard chung với tag riêng."
            ),
            "ai_yc": "Phòng Sản xuất (PD)",
            "priority": "P2",
            "phase": "Giai đoạn 3",
        },
        {
            "id": "REQ-EXT-13",
            "ten": "Mở kênh Website Odoo",
            "mota": (
                "Dùng module Website sẵn có của Odoo để bán trực "
                "tiếp; đơn website vào chung Dashboard Đơn hàng."
            ),
            "ai_yc": "Chủ dự án",
            "priority": "P2",
            "phase": "Giai đoạn 3",
        },
    ]


# --- Approval -------------------------------------------------------------

def build_approval(wb):
    ws = wb.create_sheet(title="11_Phe_Duyet")
    ws.column_dimensions["A"].width = 6
    ws.column_dimensions["B"].width = 28
    ws.column_dimensions["C"].width = 28
    ws.column_dimensions["D"].width = 18
    ws.column_dimensions["E"].width = 22
    ws.column_dimensions["F"].width = 50

    ws.merge_cells("A1:F1")
    ws["A1"] = "Phê duyệt & chữ ký"
    ws["A1"].font = FONT_H1
    ws.row_dimensions[1].height = 28

    ws.merge_cells("A2:F2")
    ws["A2"] = (
        "Ký vào bảng dưới để xác nhận đồng ý với tất cả yêu cầu trong "
        "tài liệu. Sau khi đủ chữ ký của Chủ dự án + các trưởng phòng "
        "BA / Marketing / Sản xuất, đội phát triển mới bắt đầu Giai đoạn 1."
    )
    ws["A2"].font = FONT_SMALL
    ws["A2"].alignment = Alignment(wrap_text=True, vertical="top")
    ws.row_dimensions[2].height = 50

    for i, h in enumerate(
        ["STT", "Vai trò", "Họ tên", "Ngày ký", "Chữ ký", "Ghi chú / Điều kiện"], start=1
    ):
        ws.cell(row=4, column=i, value=h)
    style_header_row(ws, 4, 6)

    roles = [
        "Chủ dự án",
        "Trưởng phòng BA",
        "Trưởng phòng Marketing",
        "Trưởng phòng Sản xuất (PD)",
        "Trưởng phòng Kiểm soát giá (Sales Audit)",
    ]
    for i, role in enumerate(roles, start=1):
        r = 4 + i
        ws.cell(row=r, column=1, value=i).alignment = ALIGN_CENTER
        ws.cell(row=r, column=2, value=role).font = FONT_BODY_B
        for col in range(1, 7):
            cell = ws.cell(row=r, column=col)
            cell.border = BORDER_ALL
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        ws.row_dimensions[r].height = 55


# --- Main -----------------------------------------------------------------

def main():
    wb = Workbook()
    wb.remove(wb.active)

    build_cover(wb)
    build_overview(wb)
    build_actors(wb)

    req_sheets = [
        (
            "03_Dong_Bo_Don_Etsy",
            "Đồng bộ đơn từ Etsy (qua API) — Giai đoạn 1",
            "Kể từ phiên bản v2, hệ thống chỉ lấy đơn qua Etsy API, "
            "không dùng email. Các yêu cầu dưới đây mô tả cách hệ "
            "thống kết nối, lấy đơn, và đẩy tracking về Etsy.",
            reqs_etsy_sync(),
        ),
        (
            "04_Chuan_Hoa_Du_Lieu_Cu",
            "Chuẩn hoá 17.659 đơn cũ — Giai đoạn 1 (bắt buộc trước)",
            "Trước khi các phòng ban dùng hệ thống mới, 17.659 đơn "
            "hiện có phải được đưa vào Odoo và làm sạch (giá, tiền "
            "tệ, khách hàng). Đây là bước tiên quyết.",
            reqs_data_cleanup(),
        ),
        (
            "05_Dashboard_Don_Hang",
            "Dashboard Đơn hàng (BA + Marketing) — Giai đoạn 1",
            "Màn hình chính cho BA và Marketing, thay thế Google "
            "Sheet hiện tại. Tập trung các yêu cầu đã đề xuất bởi BA "
            "và Marketing.",
            reqs_order_dashboard(),
        ),
        (
            "06_Dashboard_Tracking",
            "Dashboard Tracking (BA) — Giai đoạn 1",
            "Trang riêng cho BA quản lý tem và tracking, với export, "
            "bulk edit, tìm kiếm nhanh. Đồng bộ ngay với Dashboard "
            "Đơn hàng.",
            reqs_tracking_dashboard(),
        ),
        (
            "07_Dashboard_San_Xuat",
            "Dashboard Sản xuất (PD) — Giai đoạn 1",
            "Màn hình chung cho BA và Sản xuất. Hiển thị 19 cột, "
            "trạng thái sản xuất có màu, scan hàng.",
            reqs_process_dashboard(),
        ),
        (
            "08_Quy_Trinh_Duyet",
            "Quy trình duyệt (file thiết kế / địa chỉ / ticket)",
            "Gộp 3 quy trình cần người duyệt: duyệt file thiết kế, "
            "duyệt đổi địa chỉ (an toàn quan trọng), ticket replace/"
            "refund.",
            reqs_approval_workflows(),
        ),
        (
            "09_Tracking_Va_Fulfillment",
            "Nhập tracking & đẩy đơn sản xuất",
            "Gộp 2 luồng liên quan sau duyệt: nhập tracking từ GKE "
            "Logistics (Giai đoạn 1) và đẩy đơn sang Gearment sản "
            "xuất (Giai đoạn 2).",
            reqs_tracking_fulfillment(),
        ),
        (
            "10_Tinh_Nang_Mo_Rong",
            "Tính năng mở rộng (Giai đoạn 2-3)",
            "Các tính năng làm sau MVP: kiểm soát giá, tồn kho NVL, "
            "catalog, scan barcode, Amazon, Website.",
            reqs_extensions(),
        ),
    ]

    for name, title, intro, reqs in req_sheets:
        build_req_sheet(wb, name, title, intro, reqs)

    build_approval(wb)

    wb.save(OUTPUT_FILE)
    print(f"Wrote {OUTPUT_FILE}")
    print(f"Sheets: {len(wb.sheetnames)}")
    total_reqs = 0
    for s in wb.sheetnames:
        if s.startswith(("03_", "04_", "05_", "06_", "07_", "08_", "09_", "10_")):
            ws = wb[s]
            c = sum(
                1
                for row in ws.iter_rows(values_only=True)
                if row and row[0] and str(row[0]).startswith("REQ-")
            )
            total_reqs += c
            print(f"  - {s}: {c} reqs")
        else:
            print(f"  - {s}")
    print(f"Total requirements: {total_reqs}")


if __name__ == "__main__":
    main()
