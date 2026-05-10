"""Sinh hai tài liệu cho Anh/Chị Owner và đội nghiệp vụ rà soát:

- ``Theo_Doi_Du_An_VN.xlsx``  — file theo dõi 2 sheet (Tóm tắt + Hạng mục công việc).
- ``SRS_He_Thong_Quan_Ly_Don_Hang_VN.docx`` — bản mô tả chi tiết hệ thống.

Cả hai file viết hoàn toàn bằng tiếng Việt nghiệp vụ, không dùng mã yêu cầu nội bộ
(REQ-*, P0-*, ADR-*), không dùng tên module/Odoo. Mỗi tài liệu là bản độc lập, không
nhắc tới phiên bản trước.
"""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import CellIsRule

from docx import Document
from docx.enum.section import WD_ORIENTATION
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt, RGBColor

# ---------------------------------------------------------------------------
# Hằng số chung
# ---------------------------------------------------------------------------

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
XLSX_PATH = os.path.join(OUT_DIR, "Theo_Doi_Du_An_VN.xlsx")
DOCX_PATH = os.path.join(OUT_DIR, "SRS_He_Thong_Quan_Ly_Don_Hang_VN.docx")
JIRA_KEYS_PATH = os.path.join(OUT_DIR, "jira_keys.json")
STATUS_OVERRIDES_PATH = os.path.join(OUT_DIR, "status_overrides.json")

PROJECT_TITLE = "Hệ thống quản lý đơn hàng đa kênh"
RELEASE_DATE = "Tháng 5/2026"
PROJECT_OWNER = "Chủ dự án Etsy Shop"

PRIORITY_VALUES = ["Cao", "Trung bình", "Thấp"]
PHASE_VALUES = ["Giai đoạn 1", "Giai đoạn 2", "Giai đoạn 3"]
STATUS_VALUES = ["Chưa bắt đầu", "Đang làm", "Hoàn thành", "Chặn"]

# ---------------------------------------------------------------------------
# Danh mục hạng mục công việc (catalog)
# Mỗi hàng = một việc Owner / phòng ban có thể theo dõi.
# Không có mã nội bộ. STT chạy tuần tự khi sinh file.
# ---------------------------------------------------------------------------

# Nhóm hạng mục được sắp theo thứ tự xuất hiện trong file SRS.
GROUPS = [
    "1. Đồng bộ đơn hàng từ Etsy",
    "2. Làm sạch dữ liệu đơn hàng cũ",
    "3. Bảng điều khiển Đơn hàng",
    "4. Bảng điều khiển Vận chuyển",
    "5. Bảng điều khiển Sản xuất",
    "6. Quy trình duyệt (file thiết kế / địa chỉ / ticket)",
    "7. Nhập tracking & giao đối tác",
    "8. Quản lý file thiết kế",
    "9. Pipeline sản xuất có thể cấu hình",
    "10. Hộp thư khách hàng",
    "11. Mở rộng giai đoạn 2-3",
    "12. Tồn kho nguyên liệu",
]

# Mỗi tuple: (nhom, ten_ngan, mo_ta, phong_ban, muc_uu_tien, giai_doan, ghi_chu)
CATALOG_RAW = [

    # 1. Đồng bộ đơn hàng từ Etsy --------------------------------------------
    (GROUPS[0], "Kết nối tài khoản Etsy an toàn",
     "Owner đăng nhập Etsy một lần trong phần Cài đặt; hệ thống tự gia hạn kết nối và "
     "cảnh báo trước 7 ngày khi cần đăng nhập lại.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[0], "Tự động kéo đơn mới mỗi 5 phút",
     "Hệ thống quét Etsy mỗi 5 phút để lấy đơn mới và đơn vừa thay đổi; không tạo đơn trùng.",
     "BA, Marketing", "Cao", "Giai đoạn 1", ""),
    (GROUPS[0], "Không ghi đè ghi chú nội bộ khi đồng bộ lại",
     "Khi Etsy báo cập nhật cho đơn đã có, hệ thống chỉ làm mới trạng thái thanh toán và "
     "vận chuyển; ghi chú của Marketing, người phụ trách, trạng thái duyệt thiết kế giữ nguyên.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[0], "Tự đẩy tracking về Etsy",
     "Khi BA nhập số tracking và carrier, hệ thống gửi thông tin về Etsy trong vòng 5 phút.",
     "BA, Marketing", "Cao", "Giai đoạn 1", ""),
    (GROUPS[0], "Bật/tắt tự đẩy tracking theo từng cửa hàng",
     "Marketing có công tắc 'Tự đẩy tracking' theo từng cửa hàng Etsy.",
     "Marketing", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[0], "Đường đồng bộ chính + đường dự phòng",
     "Đường chính: kéo đơn qua dịch vụ chính thức của Etsy. Đường dự phòng: đọc email Etsy. "
     "Cả hai cùng tạo ra một bản ghi đơn hàng thống nhất; người dùng không thấy khác biệt.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[0], "Tự chuyển sang đường dự phòng khi đường chính lỗi",
     "Mỗi 5 phút hệ thống kiểm tra đường đang dùng. Sau 3 lần lỗi liên tiếp, tự chuyển "
     "sang đường còn lại và gửi cảnh báo cho admin; mọi thay đổi được lưu lại.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[0], "Tự quay về đường chính khi đã ổn định",
     "Khi đang chạy đường dự phòng, hệ thống thử lại đường chính mỗi giờ. Sau 6 lần "
     "thành công liên tiếp, tự quay về đường chính. Admin có thể khoá việc tự quay về.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[0], "Đối chiếu dữ liệu giữa đường chính và đường dự phòng",
     "Sau mỗi đợt đồng bộ, hệ thống so sánh đơn lấy từ kết nối Etsy chính thức với đơn "
     "lấy từ email dự phòng để bảo đảm 100% trùng khớp về số đơn, sản phẩm, giá, người "
     "nhận và phí vận chuyển. Sai lệch được liệt kê trên một trang riêng cho BA xử lý.",
     "Chủ dự án", "Cao", "Giai đoạn 1",
     "Đã đối chiếu thành công 12/12 đơn mẫu trên môi trường demo."),
    (GROUPS[0], "Xuất Excel tin nhắn khách theo khoảng thời gian",
     "Marketing chọn khoảng thời gian, bấm 'Xuất tin nhắn' để tải Excel tất cả tin nhắn khách.",
     "Marketing", "Trung bình", "Giai đoạn 2", ""),

    # 2. Làm sạch dữ liệu đơn hàng cũ ----------------------------------------
    (GROUPS[1], "Nhập 17.659 đơn hàng cũ từ file Excel",
     "Admin tải file Excel lịch sử lên; hệ thống đọc và tạo đơn. Có thể tiếp tục từ điểm "
     "dừng nếu bị gián đoạn.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[1], "Sửa 423 đơn ghi giá 0 USD",
     "Hệ thống tự tính lại giá từ nguồn; đơn không khôi phục được sẽ liệt kê cho BA xử lý tay.",
     "Kiểm soát giá", "Cao", "Giai đoạn 1", ""),
    (GROUPS[1], "Nhận đúng tiền tệ USD/EUR/GBP/CAD/VND",
     "Đọc ký hiệu tiền tệ ($, €, £, C$, ₫) và gán đúng cho từng đơn. Đơn vẫn giữ tiền gốc.",
     "Kiểm soát giá", "Cao", "Giai đoạn 1", ""),
    (GROUPS[1], "Tách phí ship thành dòng riêng",
     "Mỗi đơn có dòng 'Phí vận chuyển Etsy' riêng để tổng đơn khớp nguồn trong sai số 0,01 USD.",
     "Kiểm soát giá", "Cao", "Giai đoạn 1", ""),
    (GROUPS[1], "Gộp khách hàng trùng có BA duyệt",
     "Hệ thống đề xuất danh sách khách hàng nghi trùng, xuất Excel, BA tích chọn rồi tải lên "
     "để gộp. Hệ thống KHÔNG tự gộp.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[1], "Báo cáo đối chiếu sau khi làm sạch dữ liệu",
     "Sau khi chạy xong, hệ thống xuất báo cáo: tổng đơn, doanh thu, phí ship, đơn lỗi. "
     "BA Lead ký xác nhận trước khi sang giai đoạn tiếp theo.",
     "Chủ dự án, BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[1], "Đặt đơn cũ ở trạng thái 'đã hoàn tất'",
     "Toàn bộ 17.659 đơn cũ được mặc định trạng thái 'đã hoàn tất' và để ngoài pipeline "
     "sản xuất hiện tại; admin có thể chuyển vào pipeline 'Lưu trữ' nếu muốn.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),

    # 3. Bảng điều khiển Đơn hàng -------------------------------------------
    (GROUPS[2], "Hiển thị 10 cột chính",
     "Cửa hàng, Mã đơn, Tracking, Ảnh, Ngày, Tình trạng, Số lượng, Dịch vụ vận chuyển, "
     "Quốc gia, Tổng tiền.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[2], "Cửa hàng và Mã đơn ở 2 cột đầu, có ô tìm kiếm",
     "Search hoạt động trên cả Cửa hàng và Mã đơn.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[2], "Bỏ các cột không cần thiết",
     "Cột 'Ngày đi' tự đặt khi PD scan; giá lẻ gộp vào Tổng tiền; người phụ trách suy ra "
     "từ cửa hàng — không cần cột riêng.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[2], "Gộp Tracking + tình trạng nhãn + carrier vào 1 cột",
     "Hiển thị: 'Chờ in nhãn' / 'Đang mua nhãn' / '<carrier>: <số tracking>'.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[2], "Ảnh sản phẩm trên mỗi đơn",
     "Ảnh thu nhỏ 128px; bấm vào để xem ảnh lớn.",
     "Marketing", "Cao", "Giai đoạn 1", ""),
    (GROUPS[2], "Chỉnh trực tiếp các cột thao tác",
     "BA chỉnh ngay trên dòng: Tracking, Carrier, Tình trạng nhãn, Trạng thái đơn, Ghi chú.",
     "BA, Marketing", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[2], "Tô màu hàng theo loại đơn",
     "Số lượng ≥ 2 tô cam; trùng mã tô tím; đơn ưu tiên (Push) tô đỏ; đơn Amazon tô đỏ.",
     "Sản xuất", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[2], "Nút Push đánh dấu đơn ưu tiên",
     "Marketing bấm Push, đơn được đánh dấu và tô đỏ; lịch sử ghi lại ai bấm và lúc nào. "
     "Đơn Amazon đặt cùng ngày tự động được Push.",
     "Marketing", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[2], "Cảnh báo đơn quá 2 ngày chưa duyệt file",
     "Đơn quá 2 ngày chưa duyệt file thiết kế tô vàng và hiện cảnh báo.",
     "Marketing", "Thấp", "Giai đoạn 1", ""),
    (GROUPS[2], "Cột hạn ship",
     "Hiển thị hạn ship mà Etsy yêu cầu; quá hạn tô đỏ.",
     "Marketing", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[2], "Avatar người quản lý cửa hàng",
     "Mỗi đơn có avatar/icon của người quản lý cửa hàng tương ứng.",
     "Marketing", "Thấp", "Giai đoạn 1", ""),
    (GROUPS[2], "Popup thông báo các sự kiện đặc biệt",
     "Push, tạm dừng, đổi địa chỉ — popup hiện đến đúng người trong 10 giây.",
     "Marketing", "Thấp", "Giai đoạn 1", ""),
    (GROUPS[2], "Trường 'Ghi chú Marketing' trên đơn",
     "Tách riêng với 'Ghi chú đơn' để Marketing ghi yêu cầu custom của khách.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[2], "Lịch sử thay đổi trạng thái đơn",
     "Tab Lịch sử: ai đổi, lúc nào, từ giá trị nào sang giá trị nào.",
     "BA, Marketing", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[2], "BA tự phân loại lại sản phẩm",
     "BA có thể chỉnh phân loại sản phẩm tự động khi cần.",
     "BA", "Thấp", "Giai đoạn 1", ""),
    (GROUPS[2], "Nhãn trạng thái file thiết kế trên mỗi dòng đơn",
     "Mỗi dòng đơn hiện nhãn: chờ duyệt / đã duyệt / cần chỉnh sửa. Bấm vào để mở file.",
     "BA, Marketing", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[2], "Bảng điều khiển dạng dòng sản phẩm (theo từng sản phẩm trong đơn)",
     "Bảng điều khiển Đơn hàng có chế độ xem theo từng dòng sản phẩm thay vì cả đơn — "
     "BA thấy ngay 34 cột thông tin Marketing đang dùng trên Excel (mã đơn, ảnh, chú "
     "thích cá nhân hoá, kích thước, số lượng, ngày hứa giao, người phụ trách...). Tất "
     "cả thao tác sửa, lọc, sắp xếp đều hoạt động ở mức dòng sản phẩm.",
     "BA", "Cao", "Giai đoạn 1", ""),

    # 4. Bảng điều khiển Vận chuyển -----------------------------------------
    (GROUPS[3], "Trang Tracking riêng (không phải bộ lọc Đơn hàng)",
     "Menu 'Tracking' mở ra trang riêng, có 13 cột phục vụ BA xử lý vận chuyển.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[3], "13 cột phục vụ vận chuyển",
     "Mã đơn, Tracking, Carrier, Tình trạng, Loại sản phẩm, Số lượng, Tên người nhận, "
     "Địa chỉ 1-2, Thành phố, Bang, Mã ZIP, Quốc gia.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[3], "Xuất Excel theo bộ lọc đang xem",
     "Tải ra Excel đúng các đơn đang lọc trên màn hình.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[3], "Đổi trạng thái nhãn hàng loạt",
     "Chọn nhiều đơn cùng lúc và đổi từ 'Chờ in nhãn' sang 'Đang mua nhãn' chỉ với 1 thao tác.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[3], "Ô tìm kiếm nhanh",
     "Tìm theo tracking, mã đơn hoặc tên khách ngay trên đầu trang.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[3], "Đồng bộ thay đổi sang Bảng điều khiển Đơn hàng",
     "Mọi cập nhật phản ánh sang bảng Đơn hàng trong vòng 5 giây.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[3], "Khoá thao tác mua nhãn khi đang chờ duyệt đổi địa chỉ",
     "Vô hiệu nút 'Mua nhãn' và hiện cảnh báo khi đơn đang chờ duyệt đổi địa chỉ — tránh "
     "in nhãn sai địa chỉ.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[3], "Hiển thị tình trạng tracking thực tế (in-transit, delivered, returned)",
     "Lấy tình trạng từ carrier (USPS, UniUni, YunExpress) và cập nhật lên màn hình theo thời gian thực.",
     "Marketing", "Trung bình", "Giai đoạn 2", ""),
    (GROUPS[3], "Trạng thái nhãn vận chuyển có ảnh minh hoạ",
     "Khi BA chọn trạng thái cho nhãn vận chuyển (Đã in, Đã dán, Đã giao bưu cục, ...), "
     "danh sách tuỳ chọn hiển thị kèm ảnh thực tế của nhãn ở mỗi trạng thái — giúp BA "
     "nhận diện nhanh và giảm sai sót. Admin có thể thêm/sửa trạng thái và ảnh trong phần "
     "Cài đặt mà không cần lập trình viên.",
     "BA, Sản xuất", "Trung bình", "Giai đoạn 1", ""),

    # 5. Bảng điều khiển Sản xuất -------------------------------------------
    (GROUPS[4], "Đặt tên 'Bảng điều khiển Sản xuất'",
     "BA và Sản xuất cùng dùng; bao gồm cả đơn Việt Nam và đơn Mỹ.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[4], "Bộ cột phục vụ sản xuất",
     "Ngày duyệt file, Tải file, Tình trạng, Ghi chú, Ảnh, Lời nhắn quà tặng, Cá nhân hoá, "
     "Loại sản phẩm, Lựa chọn, Số lượng, Mã đơn, Cửa hàng, Tên khách, Địa chỉ, Dịch vụ vận "
     "chuyển, Ngày đặt, Ngày đi, Scan, Thống kê tự động.",
     "Sản xuất", "Cao", "Giai đoạn 1", ""),
    (GROUPS[4], "Toàn bộ phòng ban xem trên CÙNG MỘT MÀN HÌNH",
     "Tất cả phòng ban xem chung một bảng (không phải tách 3 sheet như cách làm cũ). "
     "Phòng ban nào quan tâm thì lọc theo cột tình trạng / pipeline.",
     "Chủ dự án", "Cao", "Giai đoạn 1", "Tiếp thu phản hồi của Owner"),
    (GROUPS[4], "Cột pipeline-state (giai đoạn sản xuất hiện tại)",
     "Mỗi đơn hiển thị giai đoạn sản xuất hiện tại với màu của giai đoạn đó. Tên và ý nghĩa "
     "giai đoạn do admin tự cấu hình tại runtime, không cần lập trình.",
     "Sản xuất", "Cao", "Giai đoạn 1", ""),
    (GROUPS[4], "Gán nhóm phụ trách cho từng giai đoạn",
     "Mỗi giai đoạn sản xuất có thể gán mặc định cho một nhóm phụ trách. Có thể đổi cho "
     "từng đơn cụ thể khi cần.",
     "Sản xuất", "Cao", "Giai đoạn 1", ""),
    (GROUPS[4], "Hiển thị ảnh thiết kế và bản preview",
     "Mỗi dòng đơn có 2 ảnh thu nhỏ: file thiết kế gốc và bản preview gửi khách.",
     "Marketing", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[4], "Widget thống kê đơn",
     "Đếm theo giai đoạn sản xuất, lựa chọn, loại sản phẩm, số lượng.",
     "Sản xuất", "Thấp", "Giai đoạn 1", ""),
    (GROUPS[4], "Scan barcode để chốt đơn hoàn thành",
     "PD scan barcode, đơn tự nhảy về giai đoạn cuối được đánh dấu 'hoàn tất'; ngày ship "
     "tự đặt; lịch sử ghi lại ai scan và lúc nào.",
     "Sản xuất, BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[4], "Lịch sử các thay đổi giai đoạn sản xuất",
     "Mọi thay đổi cấu trúc pipeline, đổi tên giai đoạn, đổi nhóm phụ trách, hoặc đơn nhảy "
     "giai đoạn đều được ghi vào sổ lịch sử để truy vết.",
     "Sản xuất", "Cao", "Giai đoạn 1", ""),

    # 6. Quy trình duyệt -----------------------------------------------------
    (GROUPS[5], "Cho phép upload lại file thiết kế kích thước lớn",
     "Designer có thể upload file lớn (ví dụ 150MB) lên Google Drive; có thể xoá và up lại; "
     "bản cũ vẫn được lưu để truy vết.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[5], "Quy trình duyệt file thiết kế",
     "File thiết kế đi qua 3 trạng thái: Chờ duyệt → Đã duyệt / Cần chỉnh sửa (phải nhập "
     "lý do). Lưu lại ai duyệt và thời điểm duyệt.",
     "Sản xuất", "Cao", "Giai đoạn 1", ""),
    (GROUPS[5], "Hàng đợi thiết kế dạng kanban 3 cột",
     "Designer và BA kéo-thả hoặc click để chuyển file giữa các trạng thái duyệt.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[5], "Quy trình duyệt đổi địa chỉ giao hàng",
     "Marketing không sửa địa chỉ trực tiếp. Phải tạo yêu cầu đổi → BA duyệt hoặc từ chối "
     "→ rồi mới được sửa.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[5], "Khoá mua nhãn khi đang chờ duyệt đổi địa chỉ",
     "Vô hiệu nút Mua nhãn và hiện cảnh báo trên Bảng Vận chuyển.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[5], "Tạo ticket đổi/hoàn tiền từ trang chi tiết đơn",
     "Form đơn có nút 'Tạo ticket'; Marketing nhập lý do và ảnh; chọn loại: đổi hàng, hoàn "
     "tiền, hoặc giảm giá; gửi BA duyệt.",
     "BA", "Trung bình", "Giai đoạn 2", ""),
    (GROUPS[5], "BA duyệt ticket → hệ thống tự xử lý",
     "Hoàn tiền sinh credit note; đổi hàng tạo đơn mới link đơn cũ; giảm giá ghi nhận giảm trên đơn.",
     "BA", "Trung bình", "Giai đoạn 2", ""),
    (GROUPS[5], "Lịch sử ticket trên trang đơn",
     "Tab 'Lịch sử' hiển thị toàn bộ thao tác của ticket trên đơn đó.",
     "BA", "Thấp", "Giai đoạn 2", ""),

    # 7. Nhập tracking & giao đối tác ---------------------------------------
    (GROUPS[6], "Nhập tracking từ file Excel logistics (GKE)",
     "Tải Excel chuẩn GKE lên; hệ thống khớp Mã đơn rồi tự điền tracking và carrier. Hàng "
     "không khớp được liệt kê cho BA xử lý tay.",
     "BA, Logistics", "Cao", "Giai đoạn 1", "Tiếp thu phản hồi: thay vì copy tay từ file logistics sang Google Excel"),
    (GROUPS[6], "Tự nhận diện carrier từ số tracking",
     "20-22 chữ số → USPS; bắt đầu 'UU' → UniUni; bắt đầu 'YT' → YunExpress; còn lại → 'Khác'.",
     "Logistics", "Cao", "Giai đoạn 1", ""),
    (GROUPS[6], "Xử lý đơn '-replace' và lưu URL nhãn / mã QR",
     "Đơn có hậu tố '-replace' tự động link đơn gốc. URL nhãn và mã QR lưu trên đơn.",
     "BA, Logistics", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[6], "Báo cáo nhập tracking (đã khớp / chưa khớp)",
     "Sau khi nhập, hiện wizard tóm tắt và cho phép xem chi tiết các dòng lỗi.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[6], "Kết nối Gearment và đẩy đơn",
     "Cấu hình Gearment 1 lần; BA bấm 'Push to Gearment' để đẩy đơn kèm file thiết kế.",
     "Chủ dự án, BA", "Cao", "Giai đoạn 2", ""),
    (GROUPS[6], "Quy trình Gearment 4 bước",
     "Nháp → báo giá → BA duyệt → xác nhận đặt sản xuất.",
     "BA", "Cao", "Giai đoạn 2", ""),
    (GROUPS[6], "Nhận tracking và tình trạng từ Gearment",
     "Hệ thống nhận thông báo từ Gearment hoặc tự kéo theo lịch để cập nhật đơn, rồi đẩy "
     "tracking lên Etsy nếu Marketing đã bật tự đẩy.",
     "BA, Marketing", "Cao", "Giai đoạn 2", ""),
    (GROUPS[6], "Xử lý lỗi và thử lại tự động",
     "Mỗi đơn thử tối đa 3 lần; nếu vẫn lỗi sẽ ghi nhật ký và cảnh báo admin.",
     "Chủ dự án", "Trung bình", "Giai đoạn 2", ""),
    (GROUPS[6], "Chính sách huỷ đơn nháp ở Gearment khi rework",
     "Khi Marketing yêu cầu làm lại đơn (giai đoạn 'Sửa'), đơn nháp/báo giá cũ phía Gearment "
     "phải được huỷ hoặc tự hết hạn.",
     "BA", "Cao", "Giai đoạn 2", ""),

    # 8. Quản lý file thiết kế ----------------------------------------------
    (GROUPS[7], "Một lần upload — gửi đến nhiều nơi",
     "BA upload file 1 lần; hệ thống lưu file và checksum. Có thể gửi sang nhiều nơi nhận "
     "(Marketing duyệt, PD in, đối tác sản xuất) mà không cần upload lại.",
     "Marketing, BA, Sản xuất", "Cao", "Giai đoạn 1",
     "Tiếp thu phản hồi: file 8MB không gửi được Discord, hay bị thất lạc, mất thời gian "
     "tải lên-tải xuống nhiều lần"),
    (GROUPS[7], "Theo dõi tình trạng nhận file của từng nơi",
     "Mỗi lần gửi file đi đâu đều ghi nhận: chờ gửi / đã gửi / đã xác nhận / lỗi và thời "
     "điểm tương ứng.",
     "BA", "Cao", "Giai đoạn 1", ""),
    (GROUPS[7], "Wizard tải hàng loạt file đã duyệt theo khổ A4",
     "PD chọn nhiều file đã duyệt cùng lúc, hệ thống dàn thành PDF khổ A4 và lưu cache 24h "
     "để PD in.",
     "Sản xuất", "Trung bình", "Giai đoạn 1",
     "Tiếp thu phản hồi: PD mất nhiều thời gian search mã đơn, download file, sắp lên Photoshop"),
    (GROUPS[7], "Lưu trữ chính trên Google Drive, có hàng đợi an toàn khi lỗi",
     "Khi Google Drive gặp sự cố, hệ thống không chuyển ngầm sang Discord — thay vào đó "
     "đưa file vào hàng đợi và cảnh báo. Discord vẫn được giữ làm kênh thủ công khẩn cấp.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[7], "Upload lại sau khi 'Cần chỉnh sửa' tạo bản version mới",
     "File bị từ chối ở trạng thái 'cần chỉnh sửa'. Bản upload mới được lưu là phiên bản "
     "tiếp theo (link tới bản cũ) để có thể đo tỷ lệ duyệt lần đầu.",
     "BA, Sản xuất", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[7], "Cảnh báo khi 'gửi file' bị treo > 2 giờ",
     "Nếu thao tác gửi file (cấp quyền Google Drive, đẩy sang đối tác) chưa xong sau 2 giờ, "
     "đơn nổi cảnh báo trên Bảng Sản xuất.",
     "Sản xuất, BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[7], "Tự động gửi file thiết kế khi BA xác nhận đơn",
     "Khi BA xác nhận đơn có file đã duyệt, hệ thống tự tạo các phiếu gửi file đến đúng nơi "
     "nhận và chạy nền để cấp quyền/gửi đi.",
     "BA", "Trung bình", "Giai đoạn 1", ""),

    # 9. Pipeline sản xuất có thể cấu hình ---------------------------------
    (GROUPS[8], "Pipeline có thể tự định nghĩa (không cần lập trình)",
     "Admin tự đặt tên pipeline, thêm/sửa/xoá giai đoạn, đặt màu, đánh dấu giai đoạn bắt "
     "đầu/giai đoạn kết thúc.",
     "Chủ dự án, Sản xuất", "Cao", "Giai đoạn 1", ""),
    (GROUPS[8], "Mỗi sản phẩm/danh mục dùng pipeline phù hợp",
     "Sản phẩm chọn pipeline mặc định; nếu chưa, lấy theo danh mục; nếu vẫn chưa, dùng "
     "pipeline mặc định toàn hệ thống.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[8], "Đơn có nhiều sản phẩm khác pipeline — BA chọn pipeline",
     "Khi đơn chứa nhiều sản phẩm thuộc nhiều pipeline, mặc định lấy pipeline của sản phẩm "
     "đầu tiên; UI cảnh báo để BA xác nhận lại.",
     "BA", "Trung bình", "Giai đoạn 1", ""),
    (GROUPS[8], "Tự sao lưu phiên bản pipeline khi sửa lúc đang có đơn chạy",
     "Khi pipeline đang được dùng bị sửa, hệ thống tạo phiên bản mới tự động; đơn cũ tiếp "
     "tục dùng phiên bản cũ; đơn mới dùng phiên bản mới.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[8], "Chính sách di chuyển giữa các giai đoạn",
     "Mỗi pipeline chọn một trong các kiểu: theo sơ đồ chặt; theo sơ đồ nhưng admin được "
     "phá rào; tự do chuyển bất kỳ. Mặc định là sơ đồ với quyền admin phá rào.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[8], "Bộ pipeline mẫu sẵn",
     "Hệ thống ship sẵn 3 pipeline mẫu: 'Sản xuất nội bộ Việt Nam' (17 giai đoạn từ thực "
     "tế PD đang dùng), 'Gearment POD' (4 giai đoạn), 'Đa kỹ thuật pha trộn'.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[8], "Sổ lịch sử pipeline duy nhất",
     "Mọi thay đổi (sửa pipeline, đổi tên giai đoạn, đổi nhóm phụ trách, đơn chuyển giai "
     "đoạn) ghi vào cùng một sổ lịch sử để dễ truy vết.",
     "Chủ dự án", "Cao", "Giai đoạn 1", ""),
    (GROUPS[8], "Trigger tự nhảy giai đoạn (giai đoạn 2)",
     "Hệ thống cho cấu hình trigger tự nhảy giai đoạn (khi thanh toán, khi duyệt thiết kế, "
     "khi nhập tracking) — bật ở giai đoạn 2.",
     "Marketing, BA, Sản xuất", "Thấp", "Giai đoạn 2", ""),

    # 10. Hộp thư khách hàng ------------------------------------------------
    (GROUPS[9], "Tổng hợp tin nhắn khách 19 cửa hàng vào một chỗ",
     "Hệ thống tự kéo lời nhắn của khách (buyer message) khi khách đặt hàng và hiển thị: "
     "(a) trên trang đơn; (b) trên trang 'Hộp thư khách hàng' để Marketing/BA tìm xuyên cửa hàng.",
     "Marketing", "Trung bình", "Giai đoạn 2",
     "Tiếp thu phản hồi: chưa có dashboard tổng hợp tin nhắn khách trong ngày"),

    # 11. Mở rộng giai đoạn 2-3 --------------------------------------------
    (GROUPS[10], "Bảng kiểm soát giá (Pricing Audit) 25 cột",
     "RD nhập tay 6 cột (A-F), 19 cột còn lại tự lấy từ đơn. Hỗ trợ đa tiền tệ.",
     "Kiểm soát giá", "Trung bình", "Giai đoạn 2", ""),
    (GROUPS[10], "Quy đổi giá đơn về EUR theo ngày đặt",
     "Tự quy đổi USD/VND/CAD về EUR theo tỷ giá ngày đặt. Hiện 'Tổng tiền (EUR)'.",
     "Kiểm soát giá", "Trung bình", "Giai đoạn 2", ""),
    (GROUPS[10], "Tô màu chênh lệch giá so với catalog",
     "Đỏ = thấp hơn catalog; vàng = bằng; tím = cao hơn.",
     "Kiểm soát giá", "Trung bình", "Giai đoạn 2", ""),
    (GROUPS[10], "Cảnh báo đơn lệch giá tự động hằng ngày",
     "Mỗi sáng hệ thống lọc đơn vượt ngưỡng, gửi ping cho RD và tô màu trên dashboard.",
     "Kiểm soát giá", "Trung bình", "Giai đoạn 2", ""),
    (GROUPS[10], "Catalog Dashboard riêng cho từng sản phẩm",
     "Trên trang sản phẩm có template thiết kế, mockup, lịch sử bán.",
     "BA", "Thấp", "Giai đoạn 3", ""),
    (GROUPS[10], "Lưu template + mockup ngay trên sản phẩm",
     "Hai trường file trên sản phẩm: template gốc và mockup.",
     "BA", "Thấp", "Giai đoạn 3", ""),
    (GROUPS[10], "Trang scan barcode đơn giản cho PD",
     "Trang scan tối giản: ô input tự focus, enter là xác nhận.",
     "BA, Sản xuất", "Thấp", "Giai đoạn 3", ""),
    (GROUPS[10], "Scan đồng bộ tất cả dashboard",
     "Khi PD scan, mọi dashboard liên quan cập nhật trong vòng 5 giây.",
     "BA, Sản xuất", "Thấp", "Giai đoạn 3", ""),
    (GROUPS[10], "Tích hợp Amazon — đơn vào dashboard chung",
     "Kết nối Amazon Seller Central; đơn Amazon hiển thị chung Bảng Đơn hàng.",
     "Sản xuất", "Thấp", "Giai đoạn 3", ""),
    (GROUPS[10], "Mở Website Odoo và đưa đơn về dashboard chung",
     "Bật module Website của Odoo; đơn website hiển thị chung Bảng Đơn hàng.",
     "Chủ dự án", "Thấp", "Giai đoạn 3", ""),
    (GROUPS[10], "Hỗ trợ AI tổng hợp / trực quan hoá dữ liệu",
     "Giai đoạn 1 chốt cấu trúc dữ liệu để các công cụ BI/AI đọc. Giai đoạn 3 mới triển khai "
     "phân tích, dự báo và trực quan hoá.",
     "Marketing, BA, Sản xuất", "Thấp", "Giai đoạn 3",
     "Tiếp thu phản hồi: cần AI hỗ trợ trích xuất, tổng kết, trực quan hoá dữ liệu"),

    # 12. Tồn kho nguyên liệu ----------------------------------------------
    (GROUPS[11], "Upload tồn kho nguyên liệu từ Excel",
     "PD upload Excel; hệ thống tạo tồn kho đầu kỳ.",
     "Sản xuất", "Trung bình", "Giai đoạn 3",
     "Tiếp thu phản hồi: nguyên liệu cập nhật hằng tháng"),
    (GROUPS[11], "Tự trừ nguyên liệu khi đơn đến giai đoạn cuối",
     "Khi đơn nhảy đến giai đoạn được đánh dấu 'Trừ kho', hệ thống tự trừ nguyên liệu "
     "theo định mức.",
     "Sản xuất", "Trung bình", "Giai đoạn 3", ""),
    (GROUPS[11], "Dự báo tồn kho 1 / 3 / 12 tháng",
     "Bảng dự báo: tồn kho hiện tại đủ dùng bao lâu.",
     "Sản xuất", "Thấp", "Giai đoạn 3", ""),
    (GROUPS[11], "Cảnh báo nguyên liệu còn dưới 2 tháng",
     "PD Lead nhận thông báo và dashboard tô đỏ những NVL sắp hết.",
     "Sản xuất", "Thấp", "Giai đoạn 3", ""),
]


def _load_jira_keys():
    """Sidecar map từ ten_ngan -> mã JIRA (vd ESTY-123). Trả về {} nếu chưa có."""
    if not os.path.exists(JIRA_KEYS_PATH):
        return {}
    with open(JIRA_KEYS_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _load_status_overrides():
    """Sidecar map từ ten_ngan -> trạng thái (Đang làm / Hoàn thành / Chặn). Trả về {} nếu chưa có."""
    if not os.path.exists(STATUS_OVERRIDES_PATH):
        return {}
    with open(STATUS_OVERRIDES_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def build_catalog():
    """Trả về danh sách hạng mục với STT và status mặc định."""
    jira_keys = _load_jira_keys()
    status_overrides = _load_status_overrides()
    out = []
    for stt, row in enumerate(CATALOG_RAW, start=1):
        nhom, ten_ngan, mo_ta, phong_ban, muc_uu_tien, giai_doan, ghi_chu = row
        out.append(
            {
                "stt": stt,
                "nhom": nhom,
                "ten_ngan": ten_ngan,
                "mo_ta": mo_ta,
                "phong_ban": phong_ban,
                "muc_uu_tien": muc_uu_tien,
                "giai_doan": giai_doan,
                "trang_thai": status_overrides.get(ten_ngan, "Chưa bắt đầu"),
                "ghi_chu": ghi_chu,
                "jira_key": jira_keys.get(ten_ngan, ""),
            }
        )
    return out


# ---------------------------------------------------------------------------
# Sinh file Excel
# ---------------------------------------------------------------------------

def _border():
    side = Side(style="thin", color="A0A0A0")
    return Border(left=side, right=side, top=side, bottom=side)


def _header_fill():
    return PatternFill("solid", fgColor="305496")


def _header_font():
    return Font(name="Calibri", size=11, bold=True, color="FFFFFF")


def _section_fill():
    return PatternFill("solid", fgColor="D9E1F2")


def _wrap():
    return Alignment(horizontal="left", vertical="top", wrap_text=True)


def _center():
    return Alignment(horizontal="center", vertical="center", wrap_text=True)


def build_xlsx(catalog):
    wb = Workbook()

    # ---------- Sheet 1 : Tom_Tat_Du_An -----------------------------------
    s1 = wb.active
    s1.title = "Tom_Tat_Du_An"

    s1.column_dimensions["A"].width = 4
    s1.column_dimensions["B"].width = 30
    s1.column_dimensions["C"].width = 60
    s1.column_dimensions["D"].width = 25
    s1.column_dimensions["E"].width = 25

    row = 1
    s1.cell(row=row, column=2, value=PROJECT_TITLE).font = Font(size=18, bold=True, color="305496")
    s1.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
    row += 1
    s1.cell(row=row, column=2, value=f"Ngày phát hành: {RELEASE_DATE}").font = Font(italic=True)
    s1.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
    row += 1
    s1.cell(row=row, column=2, value=f"Chủ dự án: {PROJECT_OWNER}").font = Font(italic=True)
    s1.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
    row += 2

    s1.cell(row=row, column=2, value="1. Giới thiệu hệ thống").font = Font(size=14, bold=True, color="305496")
    row += 1
    intro_lines = [
        "Hệ thống quản lý đơn hàng đa kênh giúp shop tập trung tất cả đơn Etsy về một nơi, "
        "thay cho cách làm thủ công trên Google Sheet hiện nay.",
        "Đơn hàng được kéo tự động từ Etsy mỗi 5 phút, hiển thị trên 3 bảng điều khiển: "
        "Đơn hàng, Vận chuyển, Sản xuất.",
        "BA và Marketing duyệt thiết kế, đổi địa chỉ và xử lý ticket trực tiếp trong hệ thống. "
        "Sản xuất theo dõi tiến độ qua pipeline có thể tự cấu hình.",
        "Sau giai đoạn 1, hệ thống mở rộng sang Gearment, Pricing Audit, sau đó là Amazon, "
        "Website và quản lý nguyên liệu.",
    ]
    for line in intro_lines:
        c = s1.cell(row=row, column=2, value=line)
        c.alignment = _wrap()
        s1.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
        s1.row_dimensions[row].height = 36
        row += 1
    row += 1

    # 2. Vai trò người dùng
    s1.cell(row=row, column=2, value="2. Vai trò người dùng").font = Font(size=14, bold=True, color="305496")
    row += 1
    headers_role = ["Vai trò", "Công việc chính", "Màn hình họ dùng nhiều nhất"]
    for i, h in enumerate(headers_role):
        c = s1.cell(row=row, column=2 + i, value=h)
        c.fill = _header_fill()
        c.font = _header_font()
        c.alignment = _center()
        c.border = _border()
    row += 1
    roles = [
        ("Chủ dự án",
         "Quyết định chiến lược, ký duyệt từng giai đoạn, theo dõi tiến độ và kết quả tổng.",
         "Bản tóm tắt KPI; tất cả bảng điều khiển (chỉ đọc)."),
        ("BA",
         "Làm file thiết kế, gửi nội bộ cho Marketing duyệt; điều phối đơn (US/VN); cung cấp "
         "tracking; duyệt đổi địa chỉ; duyệt ticket đổi/hoàn.",
         "Bảng Đơn hàng, Bảng Vận chuyển, trang Đổi địa chỉ, Ticket, Hộp thư khách hàng."),
        ("Marketing",
         "Quản lý 19 cửa hàng Etsy, push đơn ưu tiên, duyệt file thiết kế do BA làm, gửi file "
         "preview cho khách, xử lý tin nhắn khách.",
         "Bảng Đơn hàng, trang chi tiết đơn, Hộp thư khách hàng."),
        ("Sản xuất (PD)",
         "Sản xuất thực tế; chuyển trạng thái pipeline; scan đơn khi xong; quản lý tồn kho NVL.",
         "Bảng Sản xuất, trang Scan, Tồn kho, Wizard in hàng loạt."),
        ("Kiểm soát giá",
         "Kiểm tra giá bán và giá ship hằng ngày, phát hiện đơn lệch giá, báo cáo đa tiền tệ.",
         "Bảng Pricing Audit (giai đoạn 2)."),
        ("Kho",
         "Xuất nguyên liệu khi PD yêu cầu; sau khi triển khai, NVL trừ tự động khi đơn đến "
         "giai đoạn cuối.",
         "Tồn kho; Dự báo 30/90/365 ngày (giai đoạn 3)."),
    ]
    for r in roles:
        for i, v in enumerate(r):
            c = s1.cell(row=row, column=2 + i, value=v)
            c.alignment = _wrap()
            c.border = _border()
        s1.row_dimensions[row].height = 50
        row += 1
    row += 1

    # 3. Lộ trình
    s1.cell(row=row, column=2, value="3. Lộ trình triển khai").font = Font(size=14, bold=True, color="305496")
    row += 1
    headers_phase = ["Giai đoạn", "Mục tiêu", "Thời gian dự kiến", "Trạng thái tổng"]
    for i, h in enumerate(headers_phase):
        c = s1.cell(row=row, column=2 + i, value=h)
        c.fill = _header_fill()
        c.font = _header_font()
        c.alignment = _center()
        c.border = _border()
    row += 1
    phases = [
        ("Giai đoạn 1 — Nền tảng",
         "Đồng bộ Etsy (chính + dự phòng), làm sạch đơn cũ, ba bảng điều khiển, pipeline "
         "cấu hình được, quản lý file thiết kế, duyệt đổi địa chỉ, nhập tracking từ logistics.",
         "≈ 3-4 tháng",
         "Đang làm"),
        ("Giai đoạn 2 — Mở rộng",
         "Đẩy đơn cho Gearment qua kết nối tự động, ticket đổi/hoàn, Bảng Pricing Audit, "
         "Hộp thư khách hàng.",
         "≈ 3-4 tháng",
         "Chưa bắt đầu"),
        ("Giai đoạn 3 — Tương lai",
         "Quản lý tồn kho NVL + dự báo, Catalog Dashboard, scan barcode toàn diện, mở Amazon "
         "và Website, AI tổng hợp dữ liệu.",
         "≈ 4-6 tháng",
         "Chưa bắt đầu"),
    ]
    for ph in phases:
        for i, v in enumerate(ph):
            c = s1.cell(row=row, column=2 + i, value=v)
            c.alignment = _wrap()
            c.border = _border()
        s1.row_dimensions[row].height = 60
        row += 1
    row += 1

    # 4. Tổng hợp tiến độ — COUNTIF công thức trỏ vào sheet 2
    s1.cell(row=row, column=2, value="4. Tổng hợp tiến độ").font = Font(size=14, bold=True, color="305496")
    row += 1
    headers_status = ["Trạng thái", "Số lượng hạng mục"]
    for i, h in enumerate(headers_status):
        c = s1.cell(row=row, column=2 + i, value=h)
        c.fill = _header_fill()
        c.font = _header_font()
        c.alignment = _center()
        c.border = _border()
    row += 1
    n = len(catalog)
    last_row_s2 = n + 1  # sheet 2 has 1 header row
    for status in STATUS_VALUES + ["Tổng cộng"]:
        if status == "Tổng cộng":
            c1 = s1.cell(row=row, column=2, value=status)
            c1.font = Font(bold=True)
            c1.alignment = _wrap()
            c1.border = _border()
            c2 = s1.cell(row=row, column=3, value=f"=COUNTA(Hang_Muc_Cong_Viec!C2:C{last_row_s2})")
            c2.font = Font(bold=True)
        else:
            c1 = s1.cell(row=row, column=2, value=status)
            c1.alignment = _wrap()
            c1.border = _border()
            c2 = s1.cell(
                row=row,
                column=3,
                value=f'=COUNTIF(Hang_Muc_Cong_Viec!H2:H{last_row_s2},"{status}")',
            )
        c2.alignment = _center()
        c2.border = _border()
        row += 1

    # ---------- Sheet 2 : Hang_Muc_Cong_Viec ------------------------------
    s2 = wb.create_sheet("Hang_Muc_Cong_Viec")
    headers = [
        "STT", "Nhóm hạng mục", "Tên hạng mục", "Mô tả ngắn", "Phòng ban đề xuất",
        "Mức ưu tiên", "Giai đoạn", "Trạng thái", "Ghi chú", "JIRA",
    ]
    widths = [6, 32, 38, 60, 22, 14, 14, 16, 35, 14]
    for i, (h, w) in enumerate(zip(headers, widths), start=1):
        c = s2.cell(row=1, column=i, value=h)
        c.fill = _header_fill()
        c.font = _header_font()
        c.alignment = _center()
        c.border = _border()
        s2.column_dimensions[get_column_letter(i)].width = w

    s2.row_dimensions[1].height = 28

    for idx, item in enumerate(catalog, start=2):
        values = [
            item["stt"],
            item["nhom"],
            item["ten_ngan"],
            item["mo_ta"],
            item["phong_ban"],
            item["muc_uu_tien"],
            item["giai_doan"],
            item["trang_thai"],
            item["ghi_chu"],
            item["jira_key"],
        ]
        for col, val in enumerate(values, start=1):
            c = s2.cell(row=idx, column=col, value=val)
            c.alignment = _wrap() if col not in (1, 6, 7, 8, 10) else _center()
            c.border = _border()
        s2.row_dimensions[idx].height = 48

    s2.freeze_panes = "A2"
    s2.auto_filter.ref = s2.dimensions

    # Data validation
    last_row = 1 + len(catalog)
    dv_priority = DataValidation(type="list", formula1='"' + ",".join(PRIORITY_VALUES) + '"', allow_blank=False)
    dv_phase = DataValidation(type="list", formula1='"' + ",".join(PHASE_VALUES) + '"', allow_blank=False)
    dv_status = DataValidation(type="list", formula1='"' + ",".join(STATUS_VALUES) + '"', allow_blank=False)
    s2.add_data_validation(dv_priority)
    s2.add_data_validation(dv_phase)
    s2.add_data_validation(dv_status)
    dv_priority.add(f"F2:F{last_row}")
    dv_phase.add(f"G2:G{last_row}")
    dv_status.add(f"H2:H{last_row}")

    # Conditional fills
    fill_priority_high = PatternFill("solid", fgColor="F8CBAD")
    fill_priority_med = PatternFill("solid", fgColor="FFE699")
    fill_priority_low = PatternFill("solid", fgColor="C6E0B4")
    fill_status_done = PatternFill("solid", fgColor="C6E0B4")
    fill_status_block = PatternFill("solid", fgColor="F4B084")

    s2.conditional_formatting.add(
        f"F2:F{last_row}",
        CellIsRule(operator="equal", formula=['"Cao"'], fill=fill_priority_high),
    )
    s2.conditional_formatting.add(
        f"F2:F{last_row}",
        CellIsRule(operator="equal", formula=['"Trung bình"'], fill=fill_priority_med),
    )
    s2.conditional_formatting.add(
        f"F2:F{last_row}",
        CellIsRule(operator="equal", formula=['"Thấp"'], fill=fill_priority_low),
    )
    s2.conditional_formatting.add(
        f"H2:H{last_row}",
        CellIsRule(operator="equal", formula=['"Hoàn thành"'], fill=fill_status_done),
    )
    s2.conditional_formatting.add(
        f"H2:H{last_row}",
        CellIsRule(operator="equal", formula=['"Chặn"'], fill=fill_status_block),
    )

    wb.save(XLSX_PATH)
    return XLSX_PATH


# ---------------------------------------------------------------------------
# Sinh file Word
# ---------------------------------------------------------------------------

def _set_a4(doc):
    section = doc.sections[0]
    section.orientation = WD_ORIENTATION.PORTRAIT
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.left_margin = Cm(2.0)
    section.right_margin = Cm(2.0)
    section.top_margin = Cm(2.0)
    section.bottom_margin = Cm(2.0)


def _add_heading(doc, text, level):
    h = doc.add_heading(text, level=level)
    for run in h.runs:
        run.font.name = "Calibri"
    return h


def _add_paragraph(doc, text, italic=False, bold=False):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.name = "Calibri"
    run.font.size = Pt(11)
    if italic:
        run.italic = True
    if bold:
        run.bold = True
    return p


def _add_mono(doc, text):
    """ASCII art / sơ đồ — Courier New 9pt, mỗi dòng 1 paragraph."""
    for line in text.splitlines():
        p = doc.add_paragraph()
        run = p.add_run(line if line else " ")
        run.font.name = "Courier New"
        run.font.size = Pt(9)
        # Set East Asian font
        rPr = run._element.get_or_add_rPr()
        rFonts = rPr.find(qn("w:rFonts"))
        if rFonts is None:
            rFonts = OxmlElement("w:rFonts")
            rPr.append(rFonts)
        rFonts.set(qn("w:ascii"), "Courier New")
        rFonts.set(qn("w:hAnsi"), "Courier New")
        rFonts.set(qn("w:cs"), "Courier New")
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)


def _add_table(doc, headers, rows, widths_cm=None):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = h
        for p in hdr[i].paragraphs:
            for run in p.runs:
                run.bold = True
        hdr[i].vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    for r_idx, r in enumerate(rows, start=1):
        cells = table.rows[r_idx].cells
        for c_idx, v in enumerate(r):
            cells[c_idx].text = str(v) if v is not None else ""
            cells[c_idx].vertical_alignment = WD_ALIGN_VERTICAL.TOP
    if widths_cm:
        for col, w in enumerate(widths_cm):
            for row in table.rows:
                row.cells[col].width = Cm(w)
    return table


def build_docx(catalog):
    doc = Document()
    _set_a4(doc)

    # Cover
    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title.add_run("BẢN MÔ TẢ HỆ THỐNG")
    run.font.size = Pt(20)
    run.bold = True
    run.font.color.rgb = RGBColor(0x30, 0x54, 0x96)

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = sub.add_run(PROJECT_TITLE)
    run.font.size = Pt(16)
    run.bold = True

    info = doc.add_paragraph()
    info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = info.add_run(f"\nNgày phát hành: {RELEASE_DATE}\nChủ dự án: {PROJECT_OWNER}\n")
    run.italic = True
    run.font.size = Pt(12)

    doc.add_page_break()

    # --- Mục lục giả lập (không tự sinh page-number; mục lục sẽ được Word
    # tự cập nhật khi mở file) -------------------------------------------------
    _add_heading(doc, "Mục lục", level=1)
    toc_items = [
        "1. Giới thiệu chung",
        "2. Vai trò người dùng",
        "3. Lộ trình triển khai",
        "4. Đồng bộ đơn hàng từ Etsy",
        "5. Làm sạch dữ liệu đơn hàng cũ",
        "6. Bảng điều khiển Đơn hàng",
        "7. Bảng điều khiển Vận chuyển",
        "8. Bảng điều khiển Sản xuất",
        "9. Quy trình duyệt",
        "10. Nhập tracking và giao đối tác",
        "11. Quản lý file thiết kế",
        "12. Pipeline sản xuất có thể cấu hình",
        "13. Hộp thư khách hàng",
        "14. Tính năng mở rộng giai đoạn 2 và 3",
        "15. Phụ lục A — Phản hồi của Anh/Chị Owner đã được đưa vào hệ thống",
        "16. Phụ lục B — Danh sách hạng mục công việc",
        "17. Ký xác nhận",
    ]
    for it in toc_items:
        _add_paragraph(doc, it)
    doc.add_page_break()

    # --- 1. Giới thiệu chung -------------------------------------------------
    _add_heading(doc, "1. Giới thiệu chung", level=1)
    _add_heading(doc, "1.1 Mục tiêu của hệ thống", level=2)
    _add_paragraph(
        doc,
        "Hệ thống quản lý đơn hàng đa kênh được xây dựng để tập trung tất cả đơn Etsy về "
        "một nơi duy nhất, thay cho cách làm thủ công trên Google Sheet hiện tại. Mục tiêu "
        "là cắt giảm thao tác tay, giảm thất lạc đơn và file thiết kế, đồng thời cung cấp "
        "góc nhìn xuyên suốt từ lúc đơn vào hệ thống đến khi giao xong cho khách.",
    )
    _add_paragraph(
        doc,
        "Khi triển khai xong giai đoạn 1, mọi phòng ban sẽ thao tác trên cùng một bảng điều "
        "khiển (không còn 3 sheet riêng); đơn hàng tự đẩy tracking về Etsy; file thiết kế "
        "chỉ cần upload một lần và hệ thống tự gửi đến đúng nơi nhận.",
    )

    _add_heading(doc, "1.2 Phạm vi", level=2)
    _add_paragraph(
        doc,
        "Giai đoạn 1: 19 cửa hàng Etsy hiện tại của shop. Giai đoạn 2: thêm đối tác sản "
        "xuất Gearment, thêm Bảng Pricing Audit và Hộp thư khách hàng. Giai đoạn 3: mở "
        "thêm Amazon, Website, quản lý tồn kho nguyên liệu, hỗ trợ AI tổng hợp dữ liệu.",
    )

    _add_heading(doc, "1.3 Các nguyên tắc thiết kế", level=2)
    for line in [
        "• Một màn hình duy nhất cho mỗi vai trò, phòng ban tự lọc theo cột tình trạng — "
        "không tách 3 sheet như cách cũ.",
        "• Tự động hoá thay cho thao tác tay: nhập tracking từ file logistics, đẩy tracking "
        "về Etsy, gửi file thiết kế đến đúng nơi nhận.",
        "• Mọi thay đổi đều được lưu lịch sử để truy vết khi cần.",
        "• Pipeline sản xuất có thể tự cấu hình: tên giai đoạn và quy tắc chuyển giai đoạn "
        "do đội nghiệp vụ tự đặt, không cần lập trình.",
    ]:
        _add_paragraph(doc, line)

    # --- 2. Vai trò người dùng ----------------------------------------------
    _add_heading(doc, "2. Vai trò người dùng", level=1)
    _add_table(
        doc,
        ["Vai trò", "Công việc chính", "Màn hình họ dùng nhiều nhất"],
        [
            ("Chủ dự án",
             "Quyết định chiến lược; ký duyệt từng giai đoạn; theo dõi tiến độ và kết quả tổng.",
             "Bản tóm tắt KPI; tất cả bảng điều khiển (chỉ đọc)."),
            ("BA",
             "Làm file thiết kế và gửi nội bộ cho Marketing duyệt; điều phối đơn (US/VN); "
             "cung cấp tracking; duyệt đổi địa chỉ; duyệt ticket đổi/hoàn.",
             "Bảng Đơn hàng, Bảng Vận chuyển, trang Đổi địa chỉ, Ticket, Hộp thư khách hàng."),
            ("Marketing",
             "Quản lý 19 cửa hàng Etsy, push đơn ưu tiên, duyệt file thiết kế do BA làm, "
             "gửi file preview cho khách, xử lý tin nhắn khách, gửi yêu cầu đổi địa chỉ.",
             "Bảng Đơn hàng, trang chi tiết đơn, popup, Hộp thư khách hàng."),
            ("Sản xuất (PD)",
             "Sản xuất thực tế; duy trì trạng thái pipeline; scan đơn khi xong; quản lý "
             "tồn kho nguyên liệu.",
             "Bảng Sản xuất, trang Scan, Tồn kho, Wizard in hàng loạt."),
            ("Kiểm soát giá",
             "Kiểm tra giá bán và phí ship hằng ngày; phát hiện đơn lệch giá; báo cáo đa "
             "tiền tệ; báo Discord để Marketing xử lý trong ngày.",
             "Bảng Pricing Audit (giai đoạn 2)."),
            ("Kho",
             "Xuất nguyên liệu khi PD yêu cầu; sau khi triển khai, NVL trừ tự động khi đơn "
             "đến giai đoạn cuối.",
             "Tồn kho; Dự báo 30/90/365 ngày (giai đoạn 3)."),
        ],
        widths_cm=[3.5, 7.5, 5.5],
    )

    # --- 3. Lộ trình ---------------------------------------------------------
    _add_heading(doc, "3. Lộ trình triển khai", level=1)
    _add_paragraph(
        doc,
        "Hệ thống chia làm ba giai đoạn. Mỗi giai đoạn có nội dung riêng và điều kiện "
        "nghiệm thu trước khi sang giai đoạn tiếp theo.",
    )
    _add_table(
        doc,
        ["Giai đoạn", "Nội dung chính", "Thời gian", "Điều kiện nghiệm thu"],
        [
            ("Giai đoạn 1 — Nền tảng",
             "Đồng bộ Etsy (chính + dự phòng), làm sạch 17.659 đơn cũ, ba bảng điều khiển, "
             "pipeline cấu hình được, quản lý file thiết kế, duyệt đổi địa chỉ, nhập tracking "
             "từ logistics.",
             "≈ 3-4 tháng",
             "BA Lead ký nghiệm thu; hệ thống thay Google Sheet trong vòng 1 tháng; ≥ 80 % "
             "đơn chạy đến giai đoạn cuối qua pipeline."),
            ("Giai đoạn 2 — Mở rộng",
             "Đẩy đơn cho Gearment qua kết nối tự động, ticket đổi/hoàn, Bảng Pricing Audit, "
             "Hộp thư khách hàng.",
             "≈ 3-4 tháng",
             "Đơn Gearment chạy live không lỗi 2 tuần liên tiếp; Kiểm soát giá nghiệm thu "
             "Pricing Audit."),
            ("Giai đoạn 3 — Tương lai",
             "Quản lý tồn kho nguyên liệu + dự báo 1/3/12 tháng, Catalog Dashboard, scan "
             "barcode toàn diện, mở Amazon và Website, AI tổng hợp dữ liệu.",
             "≈ 4-6 tháng",
             "Quyết định nội dung chi tiết khi kết thúc giai đoạn 2."),
        ],
        widths_cm=[3.5, 6.0, 2.0, 5.0],
    )
    _add_heading(doc, "3.1 Tình trạng triển khai hiện tại", level=2)
    _add_paragraph(
        doc,
        "Môi trường demo đã chạy ổn định trên máy chủ riêng và hoàn tất một lượt vòng "
        "đời đơn hàng đầu tiên: kéo đơn từ Etsy về, gửi file thiết kế lên Google Drive, "
        "đẩy đơn cho Gearment, nhận webhook trạng thái, nhập tracking, đánh dấu đã giao "
        "và đồng bộ về Etsy. 12/12 đơn mẫu của đợt thử nghiệm đầu tiên đạt kết quả "
        "đúng. Đây là cơ sở để bước tiếp sang giai đoạn cấu hình cho dữ liệu thực.",
    )

    # --- 4. Đồng bộ đơn -----------------------------------------------------
    _add_heading(doc, "4. Đồng bộ đơn hàng từ Etsy", level=1)
    _add_heading(doc, "4.1 Mục tiêu", level=2)
    _add_paragraph(
        doc,
        "Đơn Etsy phải tự vào hệ thống, không cần ai gõ tay; đảm bảo không trùng và không "
        "ghi đè ghi chú nội bộ khi đồng bộ lại.",
    )
    _add_heading(doc, "4.2 Cách đơn hàng vào hệ thống", level=2)
    _add_paragraph(
        doc,
        "Hệ thống dùng đường chính (kết nối qua dịch vụ chính thức của Etsy) và đường dự "
        "phòng (đọc email Etsy). Cả hai đường tạo ra cùng một bản ghi đơn hàng, vì vậy "
        "người dùng không thấy khác biệt.",
    )
    _add_mono(
        doc,
        """
+--------------------+      +-----------------------------+
|  Cửa hàng Etsy     | ──►  |  Đường đồng bộ chính        | ─┐
+--------------------+      +-----------------------------+  │
                                                              ▼
+--------------------+      +-----------------------------+   +-----------------------+
|  Email Etsy        | ──►  |  Đường dự phòng (tự động)   | ─►|  Đơn hàng trong hệ    |
+--------------------+      +-----------------------------+   |  thống quản lý        |
                                                              +-----------------------+
                                                                        │
                                                                        ▼
                                                  +-----------------------------------+
                                                  | 3 bảng điều khiển: Đơn / Vận chuyển|
                                                  | / Sản xuất                         |
                                                  +-----------------------------------+
""".strip("\n"),
    )
    _add_heading(doc, "4.3 Khi đường chính gặp sự cố", level=2)
    _add_paragraph(
        doc,
        "Sau 3 lần lỗi liên tiếp, hệ thống tự chuyển sang đường dự phòng và gửi cảnh báo "
        "cho admin; mọi thay đổi được lưu lại. Khi đường chính ổn định trở lại (6 lần "
        "thành công liên tiếp), hệ thống tự quay về đường chính. Admin có thể khoá việc "
        "tự quay về.",
    )
    _add_heading(doc, "4.4 Đối chiếu giữa hai đường", level=2)
    _add_paragraph(
        doc,
        "Sau mỗi đợt đồng bộ, hệ thống tự so sánh đơn lấy từ kết nối Etsy chính thức với "
        "đơn lấy từ email dự phòng. Mọi sai lệch về số đơn, sản phẩm, giá, người nhận và "
        "phí vận chuyển được liệt kê trên một trang riêng để BA xử lý trước khi đóng đợt. "
        "Đợt thử nghiệm đầu tiên trên môi trường demo đạt 12/12 đơn khớp tuyệt đối.",
    )

    # --- 5. Làm sạch dữ liệu cũ --------------------------------------------
    _add_heading(doc, "5. Làm sạch dữ liệu đơn hàng cũ", level=1)
    _add_paragraph(
        doc,
        "Có khoảng 17.659 đơn lịch sử cần đưa vào hệ thống mới. Trong số đó có 423 đơn "
        "ghi giá 0 USD do vấn đề lịch sử. Hệ thống thực hiện các bước sau:",
    )
    for line in [
        "• Nhập 17.659 đơn từ file Excel; có thể tiếp tục từ điểm dừng nếu bị gián đoạn.",
        "• Tính lại giá cho 423 đơn 0 USD; đơn không khôi phục được sẽ liệt kê cho BA xử lý tay.",
        "• Nhận diện đúng tiền tệ (USD/EUR/GBP/CAD/VND) theo ký hiệu.",
        "• Tách phí ship thành dòng riêng để tổng đơn khớp nguồn trong sai số 0,01 USD.",
        "• Gộp khách hàng nghi trùng có BA duyệt — hệ thống không tự gộp.",
        "• Xuất báo cáo đối chiếu: tổng đơn, doanh thu, phí ship, đơn lỗi. BA Lead ký xác "
        "nhận trước khi sang giai đoạn tiếp theo.",
    ]:
        _add_paragraph(doc, line)

    # --- 6. Bảng Đơn hàng ---------------------------------------------------
    _add_heading(doc, "6. Bảng điều khiển Đơn hàng (BA + Marketing)", level=1)
    _add_heading(doc, "6.1 Mục đích", level=2)
    _add_paragraph(
        doc,
        "Là màn hình BA và Marketing dùng nhiều nhất; hiển thị 10 cột chính và cho phép "
        "chỉnh trực tiếp các cột thao tác.",
    )
    _add_heading(doc, "6.2 Hình dung giao diện 10 cột", level=2)
    _add_mono(
        doc,
        """
+-------+-----------+----------------------+-----+--------+--------+----+----------+--------+----------+
| Shop  | Mã đơn    | Tracking             | Ảnh | Ngày   | Tình   | SL | Dịch vụ  | Quốc   | Tổng     |
|       |           |                      |     |        | trạng  |    | vận chuyển| gia   | tiền     |
+-------+-----------+----------------------+-----+--------+--------+----+----------+--------+----------+
| etsy1 | 1234567   | USPS 9400 1112 ...   | [□] | 30/04  | Đang sx| 2  | Standard | US     | 38,90 $  |
| etsy2 | 1234899   | Chờ in nhãn          | [□] | 30/04  | Push   | 1  | Express  | DE     | 24,50 €  |
| etsy3 | 1235001   | UU8842211...         | [□] | 29/04  | Đã ship| 3  | UniUni   | US     | 56,00 $  |
+-------+-----------+----------------------+-----+--------+--------+----+----------+--------+----------+
""".strip("\n"),
    )
    _add_heading(doc, "6.3 Các thao tác chính", level=2)
    for line in [
        "• Lọc, tìm kiếm theo Cửa hàng, Mã đơn, Tracking, tên khách.",
        "• Chỉnh trực tiếp ngay trên dòng: Tracking, Carrier, Tình trạng nhãn, Trạng thái đơn, Ghi chú.",
        "• Tô màu hàng theo loại đơn: ≥2 sản phẩm = cam; trùng mã = tím; Push = đỏ; Amazon = đỏ.",
        "• Nút 'Push' đánh dấu đơn ưu tiên; lịch sử lưu ai bấm và lúc nào.",
        "• Cảnh báo đơn quá 2 ngày chưa duyệt file thiết kế.",
        "• Mỗi dòng đơn có nhãn trạng thái file thiết kế: chờ duyệt / đã duyệt / cần chỉnh sửa.",
        "• Tab Lịch sử trên đơn: ai đổi, lúc nào, từ giá trị nào sang giá trị nào.",
        "• Chế độ xem theo dòng sản phẩm: hiển thị 34 cột thông tin Marketing đang dùng "
        "trên Excel (mã đơn, ảnh, chú thích cá nhân hoá, kích thước, số lượng, ngày hứa "
        "giao, người phụ trách, ...) — sửa, lọc, sắp xếp đều ở mức từng sản phẩm.",
    ]:
        _add_paragraph(doc, line)

    # --- 7. Bảng Vận chuyển -------------------------------------------------
    _add_heading(doc, "7. Bảng điều khiển Vận chuyển (BA)", level=1)
    _add_paragraph(
        doc,
        "Trang riêng cho BA xử lý vận chuyển. Hiển thị 13 cột: Mã đơn, Tracking, Carrier, "
        "Tình trạng, Loại sản phẩm, Số lượng, Tên người nhận, Địa chỉ 1, Địa chỉ 2, Thành "
        "phố, Bang, Mã ZIP, Quốc gia.",
    )
    for line in [
        "• Xuất Excel theo bộ lọc đang xem.",
        "• Đổi trạng thái nhãn hàng loạt (Chờ in nhãn → Đang mua nhãn) chỉ với 1 thao tác.",
        "• Ô tìm kiếm nhanh theo tracking, mã đơn, tên khách.",
        "• Mọi thay đổi đồng bộ sang Bảng Đơn hàng trong vòng 5 giây.",
        "• Khoá thao tác mua nhãn khi đơn đang chờ duyệt đổi địa chỉ — tránh in nhãn sai.",
        "• Hiển thị tình trạng tracking thực tế (in-transit, delivered, returned) — bật ở giai đoạn 2.",
        "• Trạng thái nhãn vận chuyển có ảnh minh hoạ: khi BA chọn trạng thái, danh sách "
        "tuỳ chọn hiển thị kèm ảnh thực tế của nhãn — giúp nhận diện nhanh và giảm sai sót. "
        "Admin có thể thêm/sửa trạng thái và ảnh trong phần Cài đặt.",
    ]:
        _add_paragraph(doc, line)

    # --- 8. Bảng Sản xuất ---------------------------------------------------
    _add_heading(doc, "8. Bảng điều khiển Sản xuất (PD + BA)", level=1)
    _add_paragraph(
        doc,
        "Tất cả phòng ban xem trên CÙNG MỘT MÀN HÌNH (không phải tách 3 sheet như cách cũ). "
        "Phòng ban nào quan tâm thì lọc theo cột tình trạng / pipeline.",
        bold=False,
    )
    _add_heading(doc, "8.1 Pipeline 17 giai đoạn — bộ mặc định ship sẵn", level=2)
    _add_paragraph(
        doc,
        "Bộ pipeline mặc định 'Sản xuất nội bộ Việt Nam' ship sẵn 17 giai đoạn khớp với "
        "cách đội PD đang vận hành. Admin có thể đổi tên, thêm/xoá giai đoạn, đặt màu, "
        "không cần lập trình.",
    )
    _add_mono(
        doc,
        """
CHỜ FILE ─► CHỜ DUYỆT ─► ĐÃ DUYỆT ─► IN ─► ÉP NHIỆT ─► CẮT ─► MAY ─►
    KIỂM HÀNG ─► ĐÓNG GÓI ─► [Sửa] ─► CHỜ NHÃN ─► DÁN NHÃN ─►
    GỬI LOGISTICS ─► VN-Packed 1 ─► VN-Packed 2 ─► VN-Dispatched ─► VN-Fulfilled
""".strip("\n"),
    )
    _add_heading(doc, "8.2 Các tính năng chính", level=2)
    for line in [
        "• Mỗi đơn hiển thị giai đoạn hiện tại và màu của giai đoạn đó.",
        "• Mỗi giai đoạn có thể gán nhóm phụ trách mặc định; admin có thể đổi cho từng đơn.",
        "• Mỗi dòng có 2 ảnh thu nhỏ: file thiết kế gốc và bản preview gửi khách.",
        "• Widget thống kê: đếm theo giai đoạn / lựa chọn / loại sản phẩm / số lượng.",
        "• PD scan barcode → đơn nhảy về giai đoạn 'hoàn tất'; ngày ship tự đặt.",
        "• Mọi thay đổi cấu trúc pipeline / tên giai đoạn / nhóm phụ trách / đơn nhảy giai "
        "đoạn đều ghi vào sổ lịch sử để truy vết.",
    ]:
        _add_paragraph(doc, line)

    # --- 9. Quy trình duyệt -------------------------------------------------
    _add_heading(doc, "9. Quy trình duyệt", level=1)
    _add_heading(doc, "9.1 Duyệt file thiết kế", level=2)
    _add_paragraph(
        doc,
        "File thiết kế đi qua 3 trạng thái: Chờ duyệt → Đã duyệt / Cần chỉnh sửa (phải nhập "
        "lý do). Lưu lại ai duyệt và lúc nào. Designer và BA dùng kanban 3 cột để kéo-thả "
        "hoặc click chuyển trạng thái.",
    )
    _add_paragraph(
        doc,
        "Khi file bị từ chối ('cần chỉnh sửa') và designer upload lại, bản mới được lưu là "
        "phiên bản tiếp theo và link tới bản cũ — để có thể đo tỷ lệ duyệt lần đầu.",
    )
    _add_heading(doc, "9.2 Duyệt đổi địa chỉ giao hàng", level=2)
    _add_paragraph(
        doc,
        "Marketing không sửa địa chỉ trực tiếp. Phải tạo yêu cầu đổi → BA duyệt hoặc từ "
        "chối → mới được sửa. Trong lúc chờ duyệt, hệ thống vô hiệu nút Mua nhãn.",
    )
    _add_heading(doc, "9.3 Ticket đổi / hoàn / giảm giá", level=2)
    _add_paragraph(
        doc,
        "Trên trang đơn có nút 'Tạo ticket'; Marketing nhập lý do và ảnh; chọn loại: đổi "
        "hàng / hoàn tiền / giảm giá; gửi BA duyệt. Khi BA duyệt: Hoàn tiền sinh credit "
        "note; Đổi hàng tạo đơn mới link đơn cũ; Giảm giá ghi nhận giảm trên đơn. Tab "
        "'Lịch sử' hiển thị toàn bộ thao tác ticket. (Bật ở giai đoạn 2.)",
    )

    # --- 10. Tracking & giao đối tác ---------------------------------------
    _add_heading(doc, "10. Nhập tracking và giao đối tác", level=1)
    _add_heading(doc, "10.1 Nhập tracking từ file logistics", level=2)
    _add_paragraph(
        doc,
        "Tải file Excel chuẩn của hãng logistics (GKE) lên hệ thống. Hệ thống khớp Mã đơn "
        "rồi tự điền tracking và carrier; những hàng không khớp được liệt kê cho BA xử lý "
        "tay. Sau khi nhập, wizard hiện tóm tắt 'đã khớp / chưa khớp' để BA xem chi tiết.",
    )
    _add_paragraph(
        doc,
        "Tự nhận diện carrier: 20-22 chữ số → USPS; bắt đầu 'UU' → UniUni; bắt đầu 'YT' → "
        "YunExpress; còn lại → 'Khác'.",
    )
    _add_heading(doc, "10.2 Đẩy đơn cho Gearment (giai đoạn 2)", level=2)
    _add_paragraph(
        doc,
        "Cấu hình Gearment 1 lần. BA bấm 'Push to Gearment' để đẩy đơn kèm file thiết kế. "
        "Quy trình 4 bước: Nháp → Báo giá → BA duyệt → Xác nhận đặt sản xuất. Hệ thống "
        "nhận thông báo từ Gearment để cập nhật đơn, rồi đẩy tracking lên Etsy nếu "
        "Marketing đã bật tự đẩy. Mỗi đơn thử lại tối đa 3 lần khi gặp lỗi.",
    )

    # --- 11. File thiết kế --------------------------------------------------
    _add_heading(doc, "11. Quản lý file thiết kế", level=1)
    _add_paragraph(
        doc,
        "Mục tiêu: BA upload file 1 lần, hệ thống tự gửi đến đúng nơi nhận — tránh tình "
        "trạng tải lên rồi lại tải xuống nhiều lần ở mỗi công đoạn, và tránh thất lạc file "
        "trong Discord.",
    )
    for line in [
        "• Lưu trữ chính trên Google Drive; có hàng đợi an toàn khi Drive lỗi (không tự "
        "chuyển ngầm sang Discord).",
        "• Discord vẫn được giữ làm kênh thủ công khẩn cấp — khi cần.",
        "• Mỗi lần gửi file đi đâu đều ghi nhận: chờ gửi / đã gửi / đã xác nhận / lỗi và "
        "thời điểm tương ứng.",
        "• Nếu thao tác gửi file chưa xong sau 2 giờ, đơn hiện cảnh báo trên Bảng Sản xuất.",
        "• Wizard tải hàng loạt file đã duyệt theo khổ A4 — PD có thể in ngay.",
        "• Khi BA xác nhận đơn có file đã duyệt, hệ thống tự tạo các phiếu gửi file đến "
        "đúng nơi nhận và chạy nền để cấp quyền/gửi đi.",
    ]:
        _add_paragraph(doc, line)

    # --- 12. Pipeline -------------------------------------------------------
    _add_heading(doc, "12. Pipeline sản xuất có thể cấu hình", level=1)
    _add_paragraph(
        doc,
        "Admin tự định nghĩa pipeline (tên pipeline, các giai đoạn, màu, nhóm phụ trách "
        "mặc định, quy tắc chuyển giai đoạn) qua trang quản trị — không cần lập trình.",
    )
    for line in [
        "• Mỗi sản phẩm/danh mục dùng pipeline phù hợp; nếu chưa cấu hình thì lấy mặc định.",
        "• Đơn có nhiều sản phẩm khác pipeline: hệ thống đề xuất pipeline của sản phẩm "
        "đầu tiên và cảnh báo BA xác nhận lại.",
        "• Khi pipeline đang được dùng bị sửa, hệ thống tự tạo phiên bản mới; đơn cũ tiếp "
        "tục dùng phiên bản cũ; đơn mới dùng phiên bản mới.",
        "• Chính sách di chuyển giữa các giai đoạn: theo sơ đồ chặt / theo sơ đồ nhưng "
        "admin được phá rào (mặc định) / tự do chuyển bất kỳ.",
        "• Bộ pipeline mẫu sẵn: 'Sản xuất nội bộ Việt Nam' (17 giai đoạn), 'Gearment POD' "
        "(4 giai đoạn), 'Đa kỹ thuật pha trộn'.",
        "• Sổ lịch sử pipeline duy nhất, ghi lại mọi thay đổi để truy vết.",
    ]:
        _add_paragraph(doc, line)

    # --- 13. Hộp thư khách hàng --------------------------------------------
    _add_heading(doc, "13. Hộp thư khách hàng", level=1)
    _add_paragraph(
        doc,
        "Hệ thống tự kéo lời nhắn của khách (buyer message) khi khách đặt hàng từ 19 cửa "
        "hàng và gom lại một chỗ. Có 2 cách xem: (a) tab tin nhắn ngay trên trang đơn; "
        "(b) trang 'Hộp thư khách hàng' để Marketing/BA tìm xuyên cửa hàng. (Bật ở giai "
        "đoạn 2.)",
    )

    # --- 14. Mở rộng --------------------------------------------------------
    _add_heading(doc, "14. Tính năng mở rộng giai đoạn 2 và 3", level=1)
    _add_heading(doc, "14.1 Bảng Pricing Audit (giai đoạn 2)", level=2)
    _add_paragraph(
        doc,
        "Bảng 25 cột: 6 cột RD nhập tay, 19 cột tự lấy từ đơn. Hỗ trợ đa tiền tệ. Quy đổi "
        "giá đơn về EUR theo tỷ giá ngày đặt. Tô màu chênh lệch giá so với catalog (đỏ "
        "thấp, vàng bằng, tím cao). Cảnh báo đơn lệch giá tự động hằng ngày.",
    )
    _add_heading(doc, "14.2 Catalog Dashboard (giai đoạn 3)", level=2)
    _add_paragraph(
        doc,
        "Mỗi sản phẩm có template thiết kế, mockup, lịch sử bán. Hai trường file trên sản "
        "phẩm: template gốc và mockup.",
    )
    _add_heading(doc, "14.3 Scan barcode toàn diện (giai đoạn 3)", level=2)
    _add_paragraph(
        doc,
        "Trang scan tối giản: ô input tự focus, enter là xác nhận. Khi PD scan, mọi "
        "dashboard liên quan cập nhật trong vòng 5 giây.",
    )
    _add_heading(doc, "14.4 Mở Amazon và Website (giai đoạn 3)", level=2)
    _add_paragraph(
        doc,
        "Kết nối Amazon Seller Central và Website Odoo; đơn từ hai kênh này hiển thị "
        "chung Bảng Đơn hàng.",
    )
    _add_heading(doc, "14.5 AI tổng hợp dữ liệu (giai đoạn 3)", level=2)
    _add_paragraph(
        doc,
        "Giai đoạn 1 chốt cấu trúc dữ liệu để công cụ BI/AI có thể đọc. Giai đoạn 3 mới "
        "triển khai phân tích, dự báo và trực quan hoá — đáp ứng mong muốn 'cần AI hỗ trợ "
        "trích xuất, tổng kết, trực quan hoá dữ liệu' đã nêu trong feedback.",
    )
    _add_heading(doc, "14.6 Tồn kho nguyên liệu (giai đoạn 3)", level=2)
    _add_paragraph(
        doc,
        "PD upload tồn kho NVL từ Excel để khởi tạo. Khi đơn đến giai đoạn 'Trừ kho', hệ "
        "thống tự trừ NVL theo định mức. Bảng dự báo cho biết tồn kho hiện tại đủ dùng "
        "1 / 3 / 12 tháng. Cảnh báo NVL còn dưới 2 tháng.",
    )

    # --- 15. Phụ lục A ------------------------------------------------------
    _add_heading(doc, "15. Phụ lục A — Phản hồi của Anh/Chị Owner đã được đưa vào hệ thống", level=1)
    _add_paragraph(
        doc,
        "Mỗi dòng dưới đây là một phản hồi của Owner trong buổi rà soát quy trình sản "
        "xuất. Cột bên phải mô tả hệ thống xử lý ra sao.",
    )
    feedback_rows = [
        ("Marketing cũng cập nhật đơn khi khách yêu cầu thêm; xử lý tin nhắn khách; lưu "
         "file preview gửi khách; duyệt file thiết kế do BA làm; list mẫu mới lên cửa hàng.",
         "Vai trò Marketing trong tài liệu này đã ghi đầy đủ các đầu việc trên (xem mục 2)."),
        ("BA cũng làm file thiết kế, gửi nội bộ cho Marketing duyệt; cung cấp tracking "
         "cho khách; chuyển bộ phận sản xuất khi đơn được duyệt.",
         "Vai trò BA trong tài liệu này đã ghi đầy đủ (xem mục 2 và mục 9)."),
        ("Tất cả phòng ban đều xem trên 1 sheet, không phải 3 sheet như mô tả cũ.",
         "Đã sửa: ba bảng điều khiển hợp nhất ở mục 8 — phòng ban nào quan tâm thì lọc "
         "theo cột tình trạng / pipeline."),
        ("Đơn tự chạy lên Google Excel qua hệ thống cũ — tỷ lệ lỗi gõ tay dưới 1 %.",
         "Hệ thống mới đồng bộ hoàn toàn tự động (đường chính + đường dự phòng), tỷ lệ "
         "lỗi sẽ thấp hơn nữa và mọi thay đổi được lưu lịch sử."),
        ("Nguyên liệu cập nhật hằng tháng.",
         "Module Tồn kho nguyên liệu (giai đoạn 3) thiết kế cho upload theo định kỳ — "
         "PD chủ động upload Excel hằng tháng (xem mục 14.6)."),
        ("Có thông báo nhưng vẫn tuỳ thuộc vào người phụ trách và thường chậm.",
         "Hệ thống có popup thông báo sự kiện đặc biệt và badge cảnh báo (đơn quá 2 ngày "
         "chưa duyệt file, đơn quá hạn ship); không phụ thuộc người gõ tay."),
        ("File 8 MB không gửi qua Discord được.",
         "Đã chuyển sang Google Drive làm nơi lưu chính (kích thước file lớn không còn "
         "vướng); Discord vẫn giữ làm kênh thủ công khẩn cấp (mục 11)."),
        ("File thiết kế của mỗi đơn thỉnh thoảng vẫn lạc; tìm file khó.",
         "File được lưu dưới dạng record có gắn vào đơn (1 upload nhiều route); tìm theo "
         "đơn thay vì tìm theo Discord (mục 11)."),
        ("PD mất nhiều thời gian search mã đơn, download file, sắp lên Photoshop để in.",
         "Có wizard tải hàng loạt file đã duyệt theo khổ A4 và cache 24h — PD chọn nhiều "
         "đơn cùng lúc để in (mục 11)."),
        ("Vận hành phải tự chuyển tình trạng đơn bằng tay; mất thời gian, có thể nhầm hoặc sót.",
         "Pipeline sản xuất có thể tự cấu hình; ở giai đoạn 2 có thêm trigger tự nhảy giai "
         "đoạn (khi thanh toán, khi duyệt thiết kế, khi nhập tracking) — xem mục 12."),
        ("Chuyển nội dung đơn cho đối tác phải làm tay; tốn thời gian.",
         "Giai đoạn 2 có nút 'Push to Gearment' đẩy đơn kèm file thiết kế qua kết nối tự "
         "động (mục 10.2)."),
        ("Tracking từ nhà cung cấp phải copy lên Google Excel; tốn thời gian, sai sót.",
         "Có 'Nhập tracking từ file logistics': upload Excel chuẩn → hệ thống khớp mã đơn "
         "→ tự điền tracking + carrier (mục 10.1)."),
        ("Tình trạng tracking không thể hiện trên Google Excel.",
         "Bảng Vận chuyển hiển thị tình trạng tracking thực tế (in-transit, delivered, "
         "returned) — bật ở giai đoạn 2 (mục 7)."),
        ("Không có 1 dashboard tổng hợp xem hết tin nhắn khách trong ngày.",
         "Hộp thư khách hàng tổng hợp tin nhắn 19 cửa hàng vào 1 chỗ (mục 13)."),
        ("File thiết kế gửi lên Discord nhưng vẫn phải download ngược về rồi up lại ở mỗi "
         "công đoạn.",
         "1 lần upload — gửi đến nhiều nơi nhận với theo dõi tình trạng từng nơi (mục 11)."),
        ("Không có nhân lực tổng kết data; mong muốn AI hỗ trợ trích xuất, tổng kết, "
         "trực quan hoá.",
         "Giai đoạn 1 chốt cấu trúc dữ liệu để công cụ BI/AI đọc; giai đoạn 3 triển khai "
         "phân tích và trực quan hoá (mục 14.5)."),
    ]
    _add_table(
        doc,
        ["Phản hồi của Owner", "Hệ thống xử lý ra sao"],
        feedback_rows,
        widths_cm=[8.0, 8.5],
    )

    # --- 16. Phụ lục B ------------------------------------------------------
    _add_heading(doc, "16. Phụ lục B — Danh sách hạng mục công việc", level=1)
    _add_paragraph(
        doc,
        "Bảng dưới đồng bộ với sheet 'Hang_Muc_Cong_Viec' trong file Excel theo dõi dự án. "
        "Trạng thái mặc định là 'Chưa bắt đầu'; Anh/Chị Owner cập nhật trạng thái trên "
        "file Excel khi triển khai.",
    )
    rows_b = [
        (item["stt"], item["ten_ngan"], item["giai_doan"], item["trang_thai"])
        for item in catalog
    ]
    _add_table(
        doc,
        ["STT", "Tên hạng mục", "Giai đoạn", "Trạng thái"],
        rows_b,
        widths_cm=[1.5, 9.5, 2.5, 3.0],
    )

    # --- 17. Ký xác nhận ----------------------------------------------------
    doc.add_page_break()
    _add_heading(doc, "17. Ký xác nhận", level=1)
    _add_paragraph(
        doc,
        "Anh/Chị Owner và các trưởng bộ phận xác nhận nội dung tài liệu này phản ánh đúng "
        "yêu cầu để đội triển khai bắt tay vào làm.",
    )
    _add_table(
        doc,
        ["STT", "Vai trò", "Họ và tên", "Ngày ký", "Chữ ký"],
        [
            (1, "Chủ dự án", "", "", ""),
            (2, "Trưởng phòng BA", "", "", ""),
            (3, "Trưởng phòng Marketing", "", "", ""),
            (4, "Trưởng phòng Sản xuất", "", "", ""),
            (5, "Trưởng phòng Kiểm soát giá", "", "", ""),
        ],
        widths_cm=[1.0, 4.5, 4.0, 2.5, 4.0],
    )

    doc.save(DOCX_PATH)
    return DOCX_PATH


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    catalog = build_catalog()
    xlsx = build_xlsx(deepcopy(catalog))
    docx = build_docx(deepcopy(catalog))
    print("Xlsx :", xlsx)
    print("Docx :", docx)
    print("Tổng số hạng mục:", len(catalog))


if __name__ == "__main__":
    sys.exit(main())
