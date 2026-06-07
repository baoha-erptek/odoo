# Hướng Dẫn Sử Dụng Hệ Thống Đa Kênh — Bản Người Dùng Cuối

**Hệ thống:** `https://odoo.hatafax.com`
**Phiên bản:** Master Plan 006 (Hatafa Multichannel Hub)
**Đối tượng:** Nhân viên kinh doanh, đội sản xuất, đội đóng gói, BA Vận chuyển
**Yêu cầu kỹ thuật:** không có. Chỉ cần biết dùng trình duyệt web (Chrome / Edge / Firefox).

---

## Mục Lục

1. [Đăng nhập lần đầu](#1-đăng-nhập-lần-đầu)
2. [Tổng quan các menu chính](#2-tổng-quan-các-menu-chính)
3. [Xem đơn hàng Etsy](#3-xem-đơn-hàng-etsy)
4. [Hiểu về tuyến sản xuất (Pipeline)](#4-hiểu-về-tuyến-sản-xuất-pipeline)
5. [Upload file thiết kế (Design Files)](#5-upload-file-thiết-kế-design-files)
6. [Nhập file tracking GKE (Excel)](#6-nhập-file-tracking-gke-excel)
7. [Theo dõi vận chuyển (Tracking Dashboard)](#7-theo-dõi-vận-chuyển-tracking-dashboard)
8. [Bảng điều khiển sản xuất (Process Dashboard)](#8-bảng-điều-khiển-sản-xuất-process-dashboard)
9. [Đánh dấu thay đổi địa chỉ giao hàng](#9-đánh-dấu-thay-đổi-địa-chỉ-giao-hàng)
10. [Câu hỏi thường gặp](#10-câu-hỏi-thường-gặp)
11. [Khi gặp lỗi — báo cho ai?](#11-khi-gặp-lỗi--báo-cho-ai)

---

## 1. Đăng nhập lần đầu

1. Mở trình duyệt, vào **`https://odoo.hatafax.com`**.
2. Nhập **tên đăng nhập** (email công ty) và **mật khẩu** quản trị viên cấp cho bạn.
3. Bấm **Đăng nhập**.
4. Lần đầu vào, nên đổi mật khẩu: bấm vào tên bạn ở góc trên phải → **Hồ sơ** → đổi mật khẩu.

**Mẹo:** đánh dấu trang (Ctrl+D) để vào nhanh lần sau.

### Bạn được cấp vai trò nào?

Quản trị viên cấp 1 trong các vai trò sau:

| Vai trò | Bạn làm được gì |
|---|---|
| **Nhân viên kinh doanh** | Xem đơn hàng, xác nhận đơn, xem báo cáo |
| **Đội sản xuất** | Upload file thiết kế, đổi trạng thái đơn sang "đang sản xuất", "đã đóng gói" |
| **BA Vận chuyển** | Nhập file tracking GKE, xem dashboard giao hàng, đánh dấu đã gửi |
| **Quản lý BA Vận chuyển** | Phê duyệt schema (định dạng cột) Excel mới từ GKE |
| **Quản lý kinh doanh** | Mọi quyền trên + cấu hình tuyến sản xuất, đội nhóm, sản phẩm |

Nếu thiếu quyền nào, không thấy menu tương ứng → liên hệ quản trị viên.

---

## 2. Tổng quan các menu chính

Sau khi đăng nhập, bạn sẽ thấy các menu chính ở thanh trên cùng:

- **Etsy** — đơn hàng từ Etsy, danh sách shop, lịch sử email.
- **Bán hàng** — toàn bộ đơn hàng (bao gồm cả không phải Etsy).
- **Vận hành** (Operations) — đây là chỗ bạn dùng nhiều nhất:
  - **Order Dashboard** — danh sách đơn hàng đang xử lý.
  - **Process Dashboard** — đơn hàng theo trạng thái sản xuất.
  - **Tracking Dashboard** — đơn hàng cần gửi đi / đã gửi.
  - **Tracking Import** — nhập file Excel từ GKE.
  - **Fulfillment Pipelines** — danh sách tuyến sản xuất (chỉ quản lý xem).
  - **Pipeline Teams** — đội nhóm phụ trách từng bước.
  - **Pipeline Transitions** — lịch sử mọi lần đơn hàng đổi trạng thái.

Bấm vào menu để mở, dùng nút **back** ở trình duyệt để quay lại.

---

## 3. Xem đơn hàng Etsy

### 3.1 Vào danh sách

**Đường dẫn:** Vận hành → **Order Dashboard**

Bạn sẽ thấy bảng các đơn hàng. Mỗi dòng là một đơn. Các cột chính:

| Cột | Ý nghĩa |
|---|---|
| **Channel** | Kênh bán (Etsy / Amazon / Website) |
| **Order Ref** | Mã đơn hàng từ kênh đó |
| **Customer** | Tên khách |
| **Qty** | Tổng số lượng sản phẩm trong đơn |
| **Pipeline** | Tuyến sản xuất hệ thống đã chọn (xem mục 4) |
| **Pipeline State** | Đơn đang ở bước nào trong tuyến |
| **Duplicate Buyer** | Khách đã đặt thêm đơn khác trong 7 ngày qua |
| **Stuck-Route Badge** | Cảnh báo: file thiết kế bị kẹt >2 giờ |

### 3.2 Lọc và tìm

Phía trên bảng có ô **Search**. Bạn có thể:

- Gõ tên khách → ra đơn của khách đó.
- Bấm mũi tên xuống bên cạnh ô Search → lọc theo:
  - **Sales Channel** = Etsy → chỉ đơn Etsy.
  - **Duplicate Buyer = Có** → đơn của khách hàng quay lại.
  - **Pipeline = Gearment POD** → chỉ đơn gửi qua Gearment.

### 3.3 Mở chi tiết một đơn

Bấm vào dòng → mở form đơn hàng. Bạn sẽ thấy:

- **Đầu form:** mã đơn, khách, ngày, tổng tiền.
- **Tab "Order Lines":** danh sách sản phẩm.
- **Tab "Design Files":** file thiết kế đính kèm.
- **Tab "Other Info":** kênh, mã đơn từ kênh.
- **Phần Chatter (dưới cùng):** lịch sử ghi chú và thay đổi.

### 3.4 Các dấu hiệu màu trên dòng đơn

- **Dòng đậm** = đơn có ≥2 sản phẩm — chú ý đóng gói.
- **Huy hiệu đỏ "Duplicate Buyer"** = khách quen, ưu tiên xử lý nhanh.
- **Huy hiệu cam "Stuck Route"** = file thiết kế bị kẹt khi gửi đi sản xuất → mở đơn → tab Design Files để kiểm tra.

---

## 4. Hiểu về tuyến sản xuất (Pipeline)

Mỗi đơn hàng phải đi qua một **tuyến sản xuất** (pipeline) gồm nhiều **bước** (states). Hệ thống tự động chọn tuyến cho mỗi đơn dựa vào sản phẩm trong đơn.

### 4.1 Ba tuyến chính (đã cấu hình sẵn)

**Tuyến 1 — Sản xuất nội địa (Internal Production VN)**

`Chờ File → Đang Sản Xuất → Đã Đóng Gói → Đã Gửi → Hoàn Thành`

Dùng cho: hàng nội địa Việt Nam, áo / cốc / poster làm tại xưởng.

**Tuyến 2 — Gearment POD (Drop-Ship)**

`Draft → Quoted → Confirmed → Shipped`

Dùng cho: hàng in tại Gearment Mỹ, gửi thẳng cho khách Etsy.

**Tuyến 3 — Multi-Technique Hybrid**

`Setup → Production → Done`

Dùng cho: đơn kết hợp nhiều kỹ thuật (in + thêu, hoặc cần phối hợp 2 đội).

### 4.2 Hệ thống chọn tuyến cho đơn như nào?

Khi đơn được tạo:

1. Hệ thống nhìn từng sản phẩm trong đơn.
2. Mỗi sản phẩm có **Default Pipeline** (cài đặt trong form sản phẩm).
3. Nếu sản phẩm chưa có cài đặt → hệ thống nhìn **danh mục cha** (category).
4. Nếu danh mục cũng chưa có → dùng tuyến mặc định toàn hệ thống (`vn_internal_production`).
5. Nếu đơn có nhiều sản phẩm với tuyến khác nhau → chọn tuyến chiếm đa số.

**Ví dụ:** đơn có 3 áo Gearment + 1 poster nội địa → 3/4 dòng là Gearment → đơn vào tuyến **Gearment POD**.

### 4.3 Đơn đang ở bước nào — cách xem

Mở đơn hàng → cột **Pipeline State** ở Order Dashboard hiển thị bước hiện tại. Form đơn cũng có dòng **Pipeline State** cho biết bước.

### 4.4 Chuyển bước (đổi trạng thái) cho đơn

**Quan trọng:** không bấm trực tiếp vào trường Pipeline State để đổi. Đổi bước phải đi qua **nút hành động** trên form đơn (do đội phù hợp bấm — ví dụ đội sản xuất bấm "Đã đóng gói" khi xong).

Mỗi lần đổi bước, hệ thống tự ghi vào **Pipeline Transitions** (lịch sử) — ai bấm, từ bước nào sang bước nào, thời điểm nào.

### 4.5 Xem lịch sử chuyển bước của một đơn

**Đường dẫn:** Vận hành → **Pipeline Transitions** → lọc theo Sale Order = số đơn hàng.

Hoặc: mở form đơn → cuộn xuống **Chatter** → các thay đổi state đều có ghi chú tự động.

---

## 5. Upload file thiết kế (Design Files) + Quy trình Duyệt

Dành cho **BA** (tạo file), **MP/đội sản xuất** (duyệt), và **đội thiết kế**.

### Quy trình tổng quan

Theo D2_production_flow.md, file thiết kế đi qua **4 trạng thái**:

| Trạng thái | Ý nghĩa | Ai chuyển |
|---|---|---|
| **Chờ duyệt** (pending) | BA mới tạo, chưa gửi proof | (mặc định khi tạo) |
| **Đã gửi proof** (proof_sent) | BA đã gửi mẫu thử cho khách hàng để xem trước | BA hoặc MP |
| **Duyệt** (approved) | MP đã duyệt cuối cùng — có thể đi sản xuất | MP only |
| **Cần chỉnh lại** (rejected) | MP từ chối — BA phải làm lại | MP only |

Khi đã `Duyệt`, không quay lại được. Nếu muốn chỉnh, MP phải `rejected` trước → BA upload mới.

### 5.1 Mở đơn cần upload

1. Vận hành → Order Dashboard → tìm đơn cần xử lý (ví dụ ở bước "Chờ File").
2. Bấm vào dòng đơn → form đơn mở ra.
3. Bấm tab **Design Files**.

### 5.2 Upload file

1. Bấm nút **Upload Design** (góc phải tab).
2. Hộp thoại hiện ra:
   - Bấm **Choose File** → chọn file PNG / JPG / PDF.
   - **Kích thước tối đa: 10 MB.** File lớn hơn sẽ bị từ chối.
3. Bấm **Upload**.
4. Đợi 5–10 giây — hệ thống upload lên Google Drive và tạo ảnh thu nhỏ (thumbnail).
5. Sau khi xong: dòng file mới xuất hiện với
   - **Thumbnail** (ảnh nhỏ xem nhanh)
   - **Link Google Drive** (bấm mở file gốc)
   - **Trạng thái** = "Approved"

### 5.3 Khi upload bị từ chối

- **Lỗi "File exceeds 10 MB cap"** → file quá to, nén lại hoặc giảm độ phân giải.
- **Lỗi "Filename not allowed"** → đặt tên file đơn giản, chỉ chữ và số (ví dụ: `mockup_001.png`, không dùng tiếng Việt có dấu hay ký tự đặc biệt).

### 5.4 Sau khi đơn được "Confirmed"

Khi nhân viên kinh doanh bấm **Confirm** trên đơn:

1. Hệ thống tự động "đẩy" file thiết kế qua tuyến routing đến đúng đội sản xuất.
2. Bạn sẽ thấy mục **Design Routes** trên đơn xuất hiện trạng thái routing (pending / routed / failed).
3. Nếu route bị **failed** quá 2 giờ → huy hiệu cam **Stuck Route** xuất hiện trên Order Dashboard → quản lý kiểm tra ngay.

### 5.5 Gửi Proof cho khách (BA)

Theo D2 §2.1 row 3: với đơn cá nhân hoá phức tạp, BA gửi mẫu thử cho buyer Etsy trước khi MP duyệt cuối.

1. Login BA → Order Dashboard → tìm đơn có file `Chờ duyệt`.
2. Mở đơn → tab **Design Files** → bấm **Gửi Proof** trên file.
3. Nhập lời nhắn (ví dụ: "Vui lòng xác nhận thiết kế. OK thì trả lời tin nhắn này.").
4. Bấm Lưu → state đổi `Đã gửi proof`. Chatter ghi: URL Drive + lời nhắn (đã sanitize chống XSS) + user + thời gian.

**Phím tắt từ Order Dashboard:** chọn 1+ đơn → Action → "Gửi Proof" → fan-out cho mọi file `Chờ duyệt`/`Cần chỉnh lại` của các đơn đó.

### 5.6 MP duyệt thiết kế

Sau khi buyer phản hồi (hoặc đơn không cần proof):

1. Login MP / Production Team → Order Dashboard → mở đơn có file `Đã gửi proof` (hoặc `Chờ duyệt`).
2. Tab Design Files → bấm **Duyệt** (Approve) trên từng file.
3. Hoặc Action → "Duyệt thiết kế" → fan-out duyệt mọi file `Đã gửi proof` của đơn.

Reject: MP bấm Reject + bắt buộc nhập lý do → state `Cần chỉnh lại` → BA upload phiên bản mới.

### 5.7 Quy tắc bảo vệ (FR-017)

- BA **không thể** Approve/Reject — nút ẩn + RPC bị chặn AccessError.
- MP có cả 3 quyền: Gửi Proof, Duyệt, Reject.
- State machine cứng:
  - `Chờ duyệt` → {Đã gửi proof, Duyệt, Cần chỉnh lại}
  - `Đã gửi proof` → {Duyệt, Cần chỉnh lại, Chờ duyệt (rollback)}
  - `Cần chỉnh lại` → {Chờ duyệt, Đã gửi proof}
  - `Duyệt` → terminal (không quay lại được).
- Bất kỳ chuyển state trái quy tắc → ValidationError.
- Mọi state change ghi audit qua `tracking=True` (xuất hiện trên chatter).

---

## 6. Nhập file tracking GKE (Excel)

Dành cho **BA Vận chuyển** và **Quản lý BA Vận chuyển**.

### 6.1 Khi nào cần làm

Hằng ngày, GKE Logistics gửi cho bạn 1 file Excel chứa các đơn đã giao (mã đơn + tracking number + carrier + ngày). Bạn cần đưa thông tin này vào Odoo để hệ thống cập nhật trạng thái giao hàng cho từng đơn.

### 6.2 Mở wizard nhập

**Đường dẫn:** Vận hành → Tracking Import → **Import GKE Excel**

### 6.3 Bước 1 — Tải file lên (Preview)

1. Bấm **Choose File** → chọn file Excel hôm nay nhận từ GKE.
2. Bấm **Preview**.
3. Đợi vài giây — hệ thống đọc file và hiển thị:

   - **Schema Hash** — mã đại diện cho thứ tự cột (đừng quan tâm số này).
   - **New Schema** — nếu có tích ✓ thì cấu trúc cột Excel này là **mới**, hệ thống chưa từng thấy.
   - **Headers** — tab hiển thị danh sách tên cột.
   - **Preview Lines** — bảng các dòng đã đọc với:
     - **Status:** matched (khớp đơn), unmatched (không tìm thấy đơn), conflict (trùng nhiều đơn).
     - **Detected Carrier:** USPS / UniUni / YunExpress / Other (auto-detect dựa vào tracking number).

### 6.4 Bước 2a — Khi schema MỚI (lần đầu thấy cột này)

**Chỉ Quản lý BA Vận chuyển làm được bước này.**

1. Kiểm tra danh sách Headers có giống với file GKE bình thường không.
2. Nếu OK → bấm nút **Approve Schema** (chỉ hiện với quyền Quản lý).
3. Sau khi phê duyệt, hệ thống ghi nhớ cấu trúc cột này — lần sau import file giống vậy sẽ không cần phê duyệt lại.

**Nếu bạn là BA Vận chuyển bình thường**, không thấy nút Approve Schema → báo cho Quản lý BA của bạn duyệt giúp.

### 6.5 Bước 2b — Khi schema đã được phê duyệt

Bấm **Import** → hệ thống chạy.

Sau khi xong (vài giây đến vài phút tùy số dòng):

- **Trạng thái log** sẽ là **OK** (mọi dòng matched + import thành công), **Warning** (có dòng unmatched / conflict), hoặc **Error** (có lỗi nghiêm trọng).
- Mỗi dòng matched: tracking number + ngày giao đã được ghi vào đơn hàng tương ứng.
- Đơn hàng được tự động chuyển sang trạng thái **Đã Gửi** trên Tracking Dashboard.

### 6.6 Xử lý các dòng có vấn đề

Mở **Tracking Import** → chọn lần import vừa làm → tab **Lines**.

Lọc theo trạng thái:

- **Unmatched (không khớp):** mã đơn trong file Excel không tồn tại trong Odoo. Khả năng: GKE đánh máy sai mã, hoặc đơn này chưa được tạo trong Odoo. Liên hệ GKE / kinh doanh kiểm tra.
- **Conflict (trùng):** một mã đơn trùng với 2 đơn Odoo. Cần con người chọn đúng đơn — báo lập trình viên xử lý.
- **Detected Carrier = Other + Needs Review = ✓:** tracking number không khớp định dạng nào quen thuộc. Có thể là carrier mới chưa cấu hình. Báo Quản lý BA để bổ sung quy tắc.

### 6.7 Chạy lại nhận diện carrier (re-detect)

Nếu có người vừa thêm carrier mới vào hệ thống, bạn có thể chạy lại nhận diện cho các dòng cũ:

1. Mở Tracking Import → mở log cần xử lý → tab Lines.
2. Lọc các dòng có **Needs Review = ✓**.
3. Chọn (tích) các dòng đó.
4. Menu **Action** → **Re-detect Carriers**.
5. Hệ thống chạy lại quy tắc nhận diện và cập nhật cột Detected Carrier.

**Lưu ý:** việc này không ghi đè carrier đã có sẵn trên đơn — chỉ cập nhật thông tin trên dòng import để bạn biết.

### 6.8 Import lại file cũ (idempotency)

Nếu lỡ tay import lại đúng file đó: hệ thống thấy trùng → bỏ qua các dòng đã import → không ghi đè dữ liệu lên đơn cũ. An toàn.

### 6.9 File quá lớn

File Excel >10 MB sẽ bị từ chối ngay. Nếu file thực sự lớn (10 ngàn+ dòng), liên hệ lập trình viên tăng giới hạn hoặc chia file.

---

## 7. Theo dõi vận chuyển (Tracking Dashboard)

Dành cho **BA Vận chuyển** và **đội đóng gói**.

### 7.1 Mở dashboard

**Đường dẫn:** Vận hành → **Tracking Dashboard**

Bảng hiển thị các đơn đã đến giai đoạn cần gửi đi / đã gửi.

### 7.2 Cột chính

| Cột | Ý nghĩa |
|---|---|
| Order Ref | Mã đơn hàng |
| Customer | Khách |
| Tracking Number | Mã vận đơn |
| Tracking State | Pending / In Transit / Shipped / Delivered |
| Shipping Carrier | Nhà vận chuyển (USPS, UniUni, ...) |
| Shipping Date | Ngày gửi |
| Warehouse Zone | Kho phân vùng |
| PD PIC | Người phụ trách (Production Designer) |

### 7.3 Tìm đơn theo tracking

Gõ vào ô Search ở phía trên — gõ một phần mã tracking là đủ (không phân biệt hoa thường).

### 7.4 Đánh dấu nhiều đơn "Đã Gửi" cùng lúc

1. Tích chọn nhiều dòng trong bảng.
2. Menu **Action** → **Mark Shipped**.
3. Hệ thống cập nhật:
   - `tracking_state` = Shipped.
   - `shipping_date` = hôm nay (nếu chưa có).

### 7.5 Quy tắc bảo vệ — đơn có thay đổi địa chỉ

Nếu đơn có cờ **Pending Address Change** (khách đã yêu cầu đổi địa chỉ giao), hệ thống **bỏ qua** đơn đó khi bạn bấm Mark Shipped + hiển thị cảnh báo:

> "X đơn đã bị bỏ qua vì có yêu cầu đổi địa chỉ chưa duyệt."

Bạn cần xử lý yêu cầu đổi địa chỉ trước (xem mục 9), rồi quay lại Mark Shipped.

### 7.6 Cập nhật tự động qua thanh thông báo

Khi có đơn mới được nhập tracking, dashboard tự refresh trong vòng 5 giây mà không cần bạn F5.

---

## 8. Bảng điều khiển sản xuất (Process Dashboard)

Dành cho **đội sản xuất** và **quản lý**.

### 8.1 Mở dashboard

**Đường dẫn:** Vận hành → **Process Dashboard**

### 8.2 Cột chính

| Cột | Ý nghĩa |
|---|---|
| Order Ref | Mã đơn |
| Customer | Khách |
| Pipeline | Tuyến sản xuất |
| Pipeline State | Đang ở bước nào |
| Owning Team | Đội phụ trách bước này |
| Stuck Route Badge | Cờ cảnh báo file thiết kế kẹt |
| Qty | Tổng số sản phẩm |

### 8.3 Lọc theo đội của mình

Bấm **Filter** → **Owning Team** → chọn tên đội bạn (ví dụ "Internal Production Team") → chỉ thấy đơn liên quan đến đội mình.

### 8.4 Cờ cảnh báo file kẹt (Stuck Route)

Đơn có huy hiệu cam **Stuck Route**:

- Mở đơn → tab Design Files → xem dòng route nào bị `pending` hoặc `failed`.
- Nếu `failed`: đọc lý do trong cột "Error Message" → upload lại file (mục 5) hoặc báo lập trình viên.

---

## 8.5 Đẩy đơn Gearment POD tự động

Dành cho **đơn đi tuyến `gearment_pod`** (in tại Gearment Mỹ, drop-ship cho buyer).

### Khi nào tự đẩy

Khi đơn ở tuyến `gearment_pod` chuyển bước `quoted → confirmed` (do MP/sales bấm hành động chuyển bước), hệ thống TỰ ĐỘNG:

1. Lấy file thiết kế ở state `Duyệt` hoặc `Đã gửi proof` của đơn.
2. Build payload Gearment (địa chỉ buyer, SKU Gearment, số lượng, file URL, lời nhắn).
3. Gọi Gearment API v3 `push_order` (bất đồng bộ qua queue_job nếu có; đồng bộ trong savepoint nếu không).
4. Nhận response → lưu Gearment Outbound Ref vào đơn (`x_gearment_outbound_ref`) + status='pending'.
5. Pipeline state ở `confirmed` đợi webhook từ Gearment báo `shipped`.

### Khi push lỗi

- Pipeline tự rollback về `quoted` (bằng change_type='rollback', không re-fire push).
- Đơn nhận chatter alert đỏ với lý do lỗi.
- `x_gearment_status='failed'`.
- Cron mỗi giờ tự retry các đơn `confirmed/no-ref` >24h tuổi (date_order < NOW-24h).

### Bật/tắt auto-push

Chế độ kill-switch (admin only): Settings → Technical → Parameters → System Parameters → tìm key `multichannel_hub_fulfillment.gearment_auto_push_enabled`. Đổi value=False để tắt tạm khi sự cố Gearment API.

### Cấu hình SKU Gearment cho sản phẩm

Mỗi sản phẩm tuyến `gearment_pod` PHẢI có Gearment SKU:

1. Sales → Products → mở product → tab "General Information" hoặc tab "Sales".
2. Trường **Gearment SKU** — nhập mã SKU bên Gearment (ví dụ: `T-SHIRT-COTTON-WHITE-M`).
3. Lưu. Đơn sau này có sản phẩm này khi confirmed sẽ tự đẩy đúng SKU sang Gearment.

Nếu không có Gearment SKU → payload có product_id rỗng → Gearment có thể reject. Phải config trước khi vận hành thật.

### Yêu cầu env vars

Server staging/production phải set 3 biến môi trường:
- `GEARMENT_API_KEY`
- `GEARMENT_API_SECRET`
- `GEARMENT_API_BASE_URL` (mặc định: `https://apiv2.gearment.com/integration-handler`)

Nếu chưa set → push fail nhưng không crash đơn (auto-rollback + alert chatter).

---

## 9. Đánh dấu thay đổi địa chỉ giao hàng

Khi khách Etsy nhắn yêu cầu đổi địa chỉ (qua message Etsy hoặc email):

1. Mở đơn hàng → form đơn.
2. Bật cờ **Pending Address Change** (Đang chờ đổi địa chỉ) — hành động này khóa đơn không cho gửi đi cho đến khi được duyệt.
3. Cập nhật địa chỉ mới vào trường **Shipping Address**.
4. Báo cho Quản lý kinh doanh phê duyệt:
   - Quản lý mở đơn → bấm **Approve Address Change**.
   - Hệ thống tắt cờ → đơn có thể gửi.
5. Sau đó BA Vận chuyển có thể Mark Shipped như bình thường.

**Tại sao cần khóa?** Tránh trường hợp đội đóng gói gửi nhầm về địa chỉ cũ trong khi khách đang đợi đổi.

---

## 10. Câu hỏi thường gặp

### Tại sao tôi không thấy menu "Tracking Import"?

Bạn chưa được cấp quyền BA Vận chuyển. Báo Quản trị viên thêm quyền `BA Shipping Operator`.

### Đơn đã import nhưng tracking không hiện trên dashboard

- Kiểm tra log import (Tracking Import → mở log gần nhất) — trạng thái có phải `OK` không?
- Nếu trạng thái `Warning`: có dòng unmatched / conflict, dòng đó không được ghi.
- F5 trang Tracking Dashboard.

### Upload file thiết kế bị quay vòng tròn mãi không xong

Có thể mạng yếu hoặc Google Drive bị nghẽn. Đợi 1 phút, nếu vẫn không xong:

- F5 trang.
- Kiểm tra tab Design Files — file đã được tạo chưa? Nếu có, OK rồi.
- Nếu chưa: báo lập trình viên kiểm tra service GDrive.

### Tôi bấm Confirm đơn nhưng đội sản xuất chưa nhận file

- Mở đơn → tab Design Files → kiểm tra file đã `Approved` chưa.
- Nếu chưa Approved: file chưa được upload đúng cách → upload lại.
- Nếu đã Approved nhưng vẫn không có route: đợi 30 giây, F5. Nếu vẫn không có → báo lập trình viên.

### Khách yêu cầu hoãn đơn — tôi làm gì?

Mở đơn → bấm **Cancel**. Hệ thống tự động:

- Đặt trạng thái đơn = Cancelled.
- Bỏ đơn khỏi mọi dashboard sản xuất / vận chuyển.
- Ghi vào lịch sử chuyển bước.

### Tôi gõ sai mã tracking khi import — sửa thế nào?

Bạn không sửa trực tiếp được trên dòng import (chống chỉnh sửa lịch sử). Cách:

1. Mở đơn hàng tương ứng.
2. Cập nhật tracking number trên form đơn.
3. Hệ thống ghi vào chatter là bạn đã sửa (audit trail).

### Tôi muốn xem khách nào đặt nhiều đơn nhất tuần này

Vận hành → Order Dashboard → Filter → **Date** = trong 7 ngày qua → Group By = Customer → cột bên phải hiển thị số đơn / khách.

### Đơn có 2 sản phẩm — 1 cái nội địa, 1 cái Gearment — đi tuyến nào?

Hệ thống chọn theo **đa số dòng**. Nếu hòa: chọn theo thứ tự ưu tiên cấu hình. Nếu cần tuyến khác → đổi cấu hình `Default Pipeline` cho sản phẩm cụ thể (Quản lý kinh doanh làm).

### Tracking number của carrier mới — hệ thống không nhận ra

Báo Quản lý — họ vào **Settings → Shipping Carriers** thêm dòng mới với:

- Tên carrier.
- Mã (code) — chữ thường, không dấu (ví dụ: `viettel_post`).
- Tracking Prefix Regex — mẫu nhận diện (ví dụ: `^VT[0-9]+$` cho Viettel Post). Nếu không biết viết regex → để trống và carrier sẽ chỉ chọn được thủ công.

Sau khi thêm, vào Tracking Import → chọn các dòng cũ có Needs Review = ✓ → Action → Re-detect Carriers.

---

## 11. Khi gặp lỗi — báo cho ai?

### Trường hợp 1: Đăng nhập không được, hoặc trang trắng

Mạng / hệ thống bị sự cố — chụp màn hình, ghi giờ, gửi cho **đội IT**.

### Trường hợp 2: Bấm nút bị "Lỗi không xác định"

1. Chụp màn hình toàn màn hình (Print Screen).
2. Ghi rõ: bạn đang làm gì, đường dẫn URL trên thanh địa chỉ, mã đơn hàng nếu liên quan.
3. Gửi vào nhóm Telegram **#hatafa-support** với mô tả ngắn.

### Trường hợp 3: Số liệu không đúng (đơn báo "ok" nhưng tracking trống)

Báo cho **lập trình viên** kèm:

- Mã đơn hàng cụ thể.
- Mã log import (nếu liên quan đến tracking).
- Mô tả "tôi mong đợi X, thấy thực tế Y".

### Trường hợp 4: Bị từ chối quyền truy cập

Báo **Quản trị viên** thêm quyền — kèm tên menu / chức năng bạn cần.

### Mức độ ưu tiên

- **BLOCKER** — không bán hàng được, không gửi hàng được. Báo ngay.
- **MAJOR** — chức năng phụ hỏng, có cách làm thay thế. Báo trong giờ hành chính.
- **MINOR / NIT** — vấn đề mỹ thuật, đánh máy. Báo cuối ngày.

---

## Lời cuối

Hệ thống được thiết kế cho **tốc độ vận hành hằng ngày**, không phải để bạn nhớ tất cả các quy tắc. Khi nghi ngờ:

1. Đọc lại mục liên quan trong tài liệu này.
2. Hỏi đồng nghiệp đã dùng quen.
3. Báo cho lập trình viên — họ sẽ vá lại dòng nào dễ nhầm.

Phản hồi tài liệu (chỗ nào khó hiểu, thiếu chỗ nào): ghi vào Telegram **#hatafa-feedback**.

**Chúc bạn dùng hệ thống thuận lợi.**
