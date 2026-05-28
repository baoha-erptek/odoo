# -*- coding: utf-8 -*-
"""Generate Vietnamese owner-facing project status PDF (plain business view).

Source of truth: .claude/plans/006-overview.md (snapshot 2026-05-17).
All internal slice codes / module / framework jargon intentionally stripped
per the owner-docs convention (plain business language only).
"""
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, KeepTogether,
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_DIR = "/usr/share/fonts/truetype/dejavu"
pdfmetrics.registerFont(TTFont("DV", f"{FONT_DIR}/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DV-B", f"{FONT_DIR}/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B")

INK = colors.HexColor("#1f2933")
MUTED = colors.HexColor("#5b6770")
ACCENT = colors.HexColor("#0b6b5b")        # deep teal
ACCENT_SOFT = colors.HexColor("#e3f1ee")
BAND = colors.HexColor("#0b6b5b")
ROW_ALT = colors.HexColor("#f5f7f7")
LINE = colors.HexColor("#d4dad9")
WARN = colors.HexColor("#b25400")
GOOD = colors.HexColor("#1f8a4c")

styles = getSampleStyleSheet()


def S(name, **kw):
    base = dict(fontName="DV", textColor=INK, leading=14)
    base.update(kw)
    return ParagraphStyle(name, **base)


title_st = S("t", fontName="DV-B", fontSize=20, textColor=colors.white, leading=24)
subtitle_st = S("s", fontSize=10.5, textColor=colors.HexColor("#d6ece7"), leading=15)
h2_st = S("h2", fontName="DV-B", fontSize=13, textColor=ACCENT, leading=17, spaceBefore=6, spaceAfter=4)
body_st = S("b", fontSize=10, leading=15)
body_c = S("bc", fontSize=10, leading=15, alignment=TA_CENTER)
small_st = S("sm", fontSize=8.5, textColor=MUTED, leading=12)
cell_st = S("c", fontSize=9, leading=12)
cell_b = S("cb", fontSize=9, leading=12, fontName="DV-B")
cell_sub = S("csub", fontSize=8.5, leading=11, textColor=MUTED, leftIndent=10)


def pct_bar(pct, label, color):
    """Compact progress bar as a 2-cell nested table."""
    pct = max(0, min(100, pct))
    full, empty = pct, 100 - pct
    inner = Table([[" ", " "]], colWidths=[full * 0.30 * mm, empty * 0.30 * mm], rowHeights=[5])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), color),
        ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#e6e9e9")),
        ("LINEBELOW", (0, 0), (-1, -1), 0, colors.white),
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("ROUNDEDCORNERS", [2, 2, 2, 2]),
    ]))
    wrap = Table([[Paragraph(label, S("pl", fontSize=8.5, fontName="DV-B", textColor=color))], [inner]],
                 colWidths=[34 * mm])
    wrap.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))
    return wrap


def color_for(pct):
    if pct >= 90:
        return GOOD
    if pct >= 50:
        return ACCENT
    return WARN


def header(canvas, doc):
    canvas.saveState()
    w, h = A4
    canvas.setFillColor(BAND)
    canvas.rect(0, h - 46 * mm, w, 46 * mm, stroke=0, fill=1)
    canvas.setFillColor(colors.HexColor("#08574a"))
    canvas.rect(0, h - 46 * mm, w, 3, stroke=0, fill=1)
    # footer
    canvas.setFillColor(MUTED)
    canvas.setFont("DV", 8)
    canvas.drawString(18 * mm, 12 * mm, "Báo cáo tình hình dự án — Bảo mật nội bộ")
    canvas.drawRightString(w - 18 * mm, 12 * mm, f"Trang {doc.page}")
    canvas.setStrokeColor(LINE)
    canvas.line(18 * mm, 15 * mm, w - 18 * mm, 15 * mm)
    canvas.restoreState()


def build():
    out = "/tmp/bao_cao_tinh_hinh_du_an.pdf"
    doc = SimpleDocTemplate(
        out, pagesize=A4,
        leftMargin=18 * mm, rightMargin=18 * mm,
        topMargin=52 * mm, bottomMargin=20 * mm,
        title="Báo cáo tình hình dự án", author="Đội dự án",
    )
    story = []

    # ---- title block (overlaps header band) ----
    tb = Table([
        [Paragraph("BÁO CÁO TÌNH HÌNH DỰ ÁN", title_st)],
        [Paragraph("Tự động hóa quy trình: Etsy → Hệ thống → Đối tác sản xuất → Theo dõi vận chuyển", subtitle_st)],
        [Paragraph("Ngày chốt số liệu: 17/05/2026", subtitle_st)],
    ], colWidths=[174 * mm])
    tb.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (0, 0), 0), ("BOTTOMPADDING", (0, 0), (0, 0), 3),
        ("TOPPADDING", (0, 1), (-1, -1), 1),
    ]))
    story.append(tb)
    story.append(Spacer(1, 14))

    # ---- 1. Goal ----
    story.append(Paragraph("1. Mục tiêu cuối cùng", h2_st))
    story.append(Paragraph(
        "Xây dựng quy trình <b>tự động hoàn toàn</b>: hệ thống tự lấy đơn hàng từ Etsy, "
        "xử lý nội bộ, chuyển sang đối tác sản xuất, rồi tự động theo dõi vận chuyển — "
        "thay thế hoàn toàn cách làm thủ công qua email trước đây.", body_st))
    story.append(Spacer(1, 6))

    kpi = Table([[
        Paragraph("≈ 85%", S("k", fontName="DV-B", fontSize=22, textColor=ACCENT, alignment=TA_CENTER)),
        Paragraph("Khối lượng phát triển hướng tới mục tiêu đã hoàn thành. "
                  "Vòng lặp chính <b>nhận đơn → sản xuất → theo dõi</b> đã chạy thông suốt đầu–cuối. "
                  "Phần còn lại chủ yếu là <b>thao tác chuyển đổi vận hành</b>, không phải phát triển tính năng mới.",
                  body_st),
    ]], colWidths=[34 * mm, 140 * mm])
    kpi.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT),
        ("BOX", (0, 0), (-1, -1), 0.5, ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 12), ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LINEAFTER", (0, 0), (0, 0), 0.5, ACCENT),
    ]))
    story.append(kpi)
    story.append(Spacer(1, 16))

    # ---- 2. Scorecard ----
    story.append(Paragraph("2. Tiến độ theo hạng mục", h2_st))
    rows = [
        ("Kết nối với các đối tác bên ngoài (Etsy, đối tác sản xuất, Google Drive)", 80,
         "Chờ khóa thử nghiệm của đối tác sản xuất; quyền nhắn tin sau bán của Etsy chưa được duyệt", False),
        ("Dọn dữ liệu & môi trường thử nghiệm", 63,
         "Các việc quan trọng đã xong; phần còn lại là tinh chỉnh không gấp", False),
        ("Bảng điều khiển, phê duyệt & chuyển shop sang hệ thống mới", 80,
         "Dịch giao diện tiếng Việt; chuyển shop thí điểm (chờ chủ dự án thao tác)", False),
        ("Xử lý đơn dropship & sản xuất theo yêu cầu", 100, "Hoàn tất", True),
        ("Hình ảnh sản phẩm", 100, "Hoàn tất", True),
        ("Đơn hàng nhiều thiết kế", 70, "Còn: tự động lưu trữ thiết kế", True),
        ("Nhắn tin chăm sóc sau bán", 0, "Đang chờ Etsy cấp quyền truy cập (chặn từ bên ngoài)", True),
        ("Thu thập khách hàng tiềm năng", 70, "Còn: định tuyến email & kết nối tự động", True),
        ("Đồng bộ sản phẩm & tồn kho", 75, "Còn: ghi tồn kho ngược về Etsy", True),
        ("Nhập theo dõi vận chuyển & đồng bộ Google Drive", 75,
         "Mục tiêu: chuyển toàn bộ 19 shop sang hệ thống tự động", False),
        ("Tích hợp đối tác sản xuất, đổi/trả & kiểm tra giá", 80,
         "Còn: xử lý đổi/trả; rà soát giá", False),
        ("Mở rộng tương lai (tồn kho/danh mục/quét mã/Amazon/website)", 0,
         "Thuộc giai đoạn sau", False),
    ]
    data = [[Paragraph("Hạng mục", cell_b), Paragraph("Tiến độ", cell_b), Paragraph("Còn lại / Ghi chú", cell_b)]]
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "DV-B"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
        ("BOX", (0, 0), (-1, -1), 0.6, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    for i, (name, pct, note, sub) in enumerate(rows, start=1):
        nm_st = cell_sub if sub else cell_b
        prefix = "— " if sub else ""
        data.append([
            Paragraph(prefix + name, nm_st),
            pct_bar(pct, f"{pct}%", color_for(pct)),
            Paragraph(note, cell_st),
        ])
        if i % 2 == 0:
            style_cmds.append(("BACKGROUND", (0, i), (-1, i), ROW_ALT))
    tbl = Table(data, colWidths=[74 * mm, 38 * mm, 62 * mm], repeatRows=1)
    tbl.setStyle(TableStyle(style_cmds))
    story.append(tbl)
    story.append(Spacer(1, 6))
    story.append(Paragraph("Các dòng thụt đầu dòng (—) là hạng mục con của “Bảng điều khiển & chuyển shop”.",
                            small_st))
    story.append(Spacer(1, 16))

    # ---- 3. Priorities ----
    story.append(Paragraph("3. Ưu tiên để về đích", h2_st))

    def block(heading, items, hcolor):
        head = Paragraph(heading, S("ph", fontName="DV-B", fontSize=10.5, textColor=colors.white))
        rws = [[head]]
        for it in items:
            rws.append([Paragraph("•  " + it, body_st)])
        t = Table(rws, colWidths=[174 * mm])
        cmds = [
            ("BACKGROUND", (0, 0), (0, 0), hcolor),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.5, LINE),
            ("LINEBELOW", (0, 1), (-1, -1), 0.3, LINE),
        ]
        for r in range(1, len(rws)):
            if r % 2 == 1:
                cmds.append(("BACKGROUND", (0, r), (0, r), colors.HexColor("#fafbfb")))
        t.setStyle(TableStyle(cmds))
        return KeepTogether([t, Spacer(1, 8)])

    story.append(block("Ưu tiên cao nhất — cần để vận hành thật", [
        "Chuyển shop thí điểm sang hệ thống tự động — cần chủ dự án thao tác; đây là mắt xích mở khóa lớn nhất.",
        "Chuyển tiếp 2–4 shop nữa sau khi shop thí điểm chạy ổn.",
        "Tắt phương thức cũ qua email; đưa toàn bộ 19 shop sang kết nối tự động.",
        "Lấy khóa thử nghiệm từ đối tác sản xuất — cần chủ dự án cung cấp.",
    ], ACCENT))
    story.append(block("Tiếp theo — hoàn thiện quy trình", [
        "Ghi tồn kho ngược về Etsy.",
        "Dịch giao diện sang tiếng Việt.",
        "Tự động lưu trữ thiết kế đã dùng.",
    ], colors.HexColor("#3a7d6e")))
    story.append(block("Tạm hoãn đến khi chạy thật ổn định", [
        "Phân loại & dọn dữ liệu (phụ thuộc nghiệp vụ).",
        "Giám sát sức khỏe hệ thống, tối ưu hiệu năng.",
    ], MUTED))
    story.append(block("Ngoài lộ trình tới đích", [
        "Nhắn tin chăm sóc sau bán — đang chờ Etsy duyệt quyền.",
        "Hoàn thiện thu thập khách hàng tiềm năng.",
        "Đổi/trả, rà soát giá; toàn bộ giai đoạn mở rộng tương lai.",
    ], MUTED))
    story.append(Spacer(1, 8))

    # ---- 4. Takeaways ----
    story.append(Paragraph("4. Tóm tắt cho chủ dự án", h2_st))
    take = Table([[Paragraph(
        "•  Phần lập trình gần như hoàn tất (~85%); quy trình chính đã chạy đầu–cuối.<br/>"
        "•  Việc còn lại chủ yếu là <b>chủ dự án bấm “chuyển đổi”</b> cho từng shop và "
        "<b>cung cấp khóa thử nghiệm</b> của đối tác sản xuất.<br/>"
        "•  Một hạng mục đang bị chặn từ bên ngoài: <b>quyền nhắn tin sau bán của Etsy</b> "
        "(không ảnh hưởng quy trình bán hàng chính).",
        body_st)]], colWidths=[174 * mm])
    take.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT),
        ("BOX", (0, 0), (-1, -1), 0.6, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(take)

    doc.build(story, onFirstPage=header, onLaterPages=header)
    print("WROTE", out)


if __name__ == "__main__":
    build()
