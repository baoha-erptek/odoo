#!/usr/bin/env python3
"""Restructure the concatenated UAT markdown into one coherent guide.

The UAT PDF concatenates 8 standalone docs (4 flows x FLOW_ + HUONG_DAN_). Raw,
they collide: 8 separate `# ` titles, 4 embedded "## Mục lục" tables of contents
(redundant with make-pdf's own --toc), and no part structure.

This runs at BUILD time on the concatenated file only, so the source files stay
intact (still usable standalone + on Confluence). It:
  1. prepends one cover / front-matter block,
  2. inserts a `# Phần N — <name>` divider before each flow (the FLOW_ title line),
  3. demotes every original `# ` title to `## ` so the Part dividers are the only H1s,
  4. strips each embedded "## Mục lục" block (make-pdf --toc is the single master TOC).

Usage: python3 uat_restructure.py <concatenated.md>   (edits the file in place)
"""
import sys

# Each flow starts at its FLOW_ file, whose title begins with "# Quy trình".
# Order matches build-pdfs.sh's build_set for huong_dan_uat_vn.
PART_NAMES = [
    "Tạo sản phẩm mới",
    "Tiếp nhận đơn hàng Etsy",
    "Giao hàng (MTO nội bộ + Dropship Gearment)",
    "Hậu mãi (In lại, Tin nhắn, Hoàn trả & Hoàn tiền)",
]

FRONT_MATTER = """# Hướng dẫn sử dụng & Kiểm thử (UAT) — Hệ thống Etsy đa kênh

**Đối tượng:** Chủ shop, BA Lead / BA User, Đội vận hành · **Ngôn ngữ:** Tiếng Việt
**Hệ thống:** Odoo 19 (Hatafa UI) + Etsy + Gearment

Tài liệu này gộp 4 luồng nghiệp vụ chính. Mỗi **Phần** gồm hai lớp:
tài liệu nghiệp vụ (tổng quan quy trình) rồi hướng dẫn thao tác từng bước, kèm ảnh
chụp màn hình thật. Dùng mục lục ở đầu để nhảy tới đúng phần cần đọc.

| Phần | Luồng | Dành cho |
|---|---|---|
| Phần 1 | Tạo sản phẩm mới + đăng bán Etsy | BA tạo & đăng sản phẩm |
| Phần 2 | Tiếp nhận đơn hàng Etsy | BA xử lý đơn về |
| Phần 3 | Giao hàng — In nội bộ (MTO) & Dropship Gearment | BA/Đội vận hành |
| Phần 4 | Hậu mãi — In lại, Tin nhắn, Hoàn trả/Hoàn tiền | BA Marketing/Lead |

"""


def restructure(text):
    lines = text.split("\n")
    out = []
    part = 0
    skip_toc = False
    for line in lines:
        # Strip an embedded "## Mục lục" block: drop from the heading until the
        # next H2/H1 (the TOC is a flat list, so the next `#`/`##` ends it).
        if line.strip() == "## Mục lục":
            skip_toc = True
            continue
        if skip_toc:
            if line.startswith("## ") or line.startswith("# "):
                skip_toc = False  # fall through to normal handling
            else:
                continue
        # A flow starts at its FLOW_ title ("# Quy trình ...") -> Part divider.
        if line.startswith("# Quy trình"):
            name = PART_NAMES[part] if part < len(PART_NAMES) else line[2:].strip()
            part += 1
            out.append(f"# Phần {part} — {name}")
            out.append("")
            out.append("## " + line[2:])  # demote the FLOW_ title to H2
            continue
        # Any other original H1 title (the HUONG_DAN_ titles) -> H2.
        if line.startswith("# ") and not line.startswith("# Phần"):
            out.append("## " + line[2:])
            continue
        out.append(line)
    return FRONT_MATTER + "\n".join(out)


def _selfcheck():
    sample = (
        "# Quy trình tạo sản phẩm mới\n\n## Mục lục\n1. [a](#a)\n2. [b](#b)\n\n"
        "## Tổng quan\nx\n\n# Hướng dẫn sử dụng — Tạo sản phẩm\n## 1. Bước\n"
    )
    r = restructure(sample)
    assert "# Phần 1 — Tạo sản phẩm mới" in r, "part divider missing"
    assert "## Quy trình tạo sản phẩm mới" in r, "FLOW title not demoted"
    assert "## Hướng dẫn sử dụng — Tạo sản phẩm" in r, "HUONG title not demoted"
    assert "## Mục lục" not in r, "embedded TOC not stripped"
    assert "1. [a](#a)" not in r, "TOC body not stripped"
    assert "## Tổng quan\nx" in r, "content after TOC wrongly dropped"
    print("selfcheck OK")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--selfcheck":
        _selfcheck()
        sys.exit(0)
    path = sys.argv[1]
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(restructure(src))
    print(f"restructured {path}")
