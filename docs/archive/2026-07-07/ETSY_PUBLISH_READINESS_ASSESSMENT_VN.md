# Đánh giá mức độ sẵn sàng đồng bộ sản phẩm sang Etsy

**Phiên bản**: v1.0 · **Ngày**: 2026-05-27 · **Phạm vi**: Pilot JaHandmadeArt
trên Etsy sandbox + chuẩn bị triển khai trên shop thật.

---

## 1. Tóm tắt nhanh

**Câu hỏi của Chủ shop**: *"Chúng ta đã sẵn sàng đồng bộ sản phẩm từ
hệ thống Odoo lên Etsy chưa? Khi tạo sản phẩm, chúng ta có dùng đầy đủ
các trường mà Odoo đã hỗ trợ sẵn (Danh mục, Biến thể, Cá nhân hóa,
Thuộc tính, Tags, Giá, Vận chuyển, Mã SKU) thay vì tự nghĩ ra cái mới
không?"*

**Trả lời ngắn**: **Có một phần — chuỗi đồng bộ đã chạy thật trên Etsy
sandbox** (đã tạo được listing ID `4511807545` ngày 26/05/2026), **nhưng
còn 8 nhóm trường Etsy yêu cầu/đề nghị mà hệ thống chưa gửi đầy đủ**.
Đa số phần thiếu là *nối thêm các trường có sẵn của Odoo vào payload
đang gửi đi*, chứ KHÔNG phải xây dựng mô hình mới. Một vài chỗ trước
đây có "tự nghĩ ra" sẽ được rút lại để dùng chuẩn Odoo (xem §5).

**Trả lời ngắn cho phần "dùng đầy đủ Odoo gốc"**: **Phần lớn đã dùng**
(Danh mục, Biến thể, Mô tả). Có hai điểm "tự chế" sẽ được dọn lại:
giá bán dùng trường tùy biến thay vì trường giá chuẩn của Odoo, và
việc tạo SKU đang đi qua một biểu mẫu riêng (Wizard) thay vì sinh thẳng
trên form sản phẩm chuẩn. Cả hai sẽ được điều chỉnh.

---

## 2. Cách tạo sản phẩm mới sẽ thay đổi như thế nào

**Trước đây (đang dùng):**
- BA mở menu Wizard → điền tên + chọn Danh mục → đi qua 4 bước → hệ
  thống ghép SKU theo công thức rồi tạo sản phẩm.
- Có hai biểu mẫu khác nhau (Wizard cổ điển + Wizard SKU 4 bước).

**Sắp tới (đang triển khai):**
- BA mở thẳng menu **Sản phẩm** chuẩn của Odoo → bấm **Tạo mới** →
  điền tên + chọn **Danh mục** → thêm **Biến thể** (Chất liệu, Kích
  thước, Hình dạng) như bình thường.
- **Khi BA chọn Danh mục và Biến thể, ô Mã SKU tự điền giá trị gợi ý**
  (vd: `MUG-CR-F11` cho cốc gốm 11oz). BA xem qua và lưu — không cần
  mở Wizard riêng.
- BA vẫn có thể sửa lại Mã SKU nếu cần (vd: sản phẩm cũ giữ mã lịch sử).
  Hệ thống không bao giờ ghi đè lên mã BA đã sửa tay.
- Wizard sẽ không xuất hiện trong menu nữa, nhưng vẫn được dùng "âm
  thầm" khi nhập sản phẩm hàng loạt từ file Excel.

**Lý do thay đổi**: chuyên ngành gọi là *"dùng tính năng có sẵn thay
vì làm lại"*. Form sản phẩm chuẩn của Odoo đã có sẵn các ô Danh mục,
Biến thể, Mô tả, Giá, Cân nặng, Tags. Đi qua Wizard riêng làm BA phải
học 2 chỗ thay vì 1, và làm cho người mới gia nhập đội bị bối rối.

---

## 3. Etsy yêu cầu gì khi tạo một listing

Theo trang [How to Create a Listing](https://help.etsy.com/hc/en-us/articles/115015628707)
của Etsy + tài liệu API v3, một listing Etsy cần (sắp xếp theo mức độ
bắt buộc):

### Bắt buộc

| # | Mục | Giới hạn / Ghi chú |
|---|---|---|
| 1 | **Tiêu đề (Title)** | ≤ 140 ký tự; chỉ được dùng tối đa 1 lần các ký tự `%`, `:`, `&`, `+` |
| 2 | **Mô tả (Description)** | Văn bản tự do |
| 3 | **Danh mục Etsy (Taxonomy)** | Chọn từ cây danh mục của Etsy (vd: Home & Living > Kitchen > Drinkware > Mugs) |
| 4 | **Giá (Price)** | USD, lớn hơn 0; Etsy còn thu phí listing $0.20/listing |
| 5 | **Số lượng (Quantity)** | Số nguyên dương; cho Made-To-Order có thể đặt = 1 |
| 6 | **Ai làm (Who made)** | `Tôi tự làm` / `Người khác làm` / `Tập thể` |
| 7 | **Làm khi nào (When made)** | Made-to-Order / 2020-2023 / 1970s / Trước 1700 / … (20 lựa chọn) |
| 8 | **Trạng thái sẵn sàng (Readiness state)** | Mới *bắt buộc từ 2025* cho listing vật lý; chọn từ shop (vd: "Made to order 3-5 ngày") |

### Bắt buộc khi đăng "Active" (không phải Draft)

| # | Mục | Giới hạn |
|---|---|---|
| 9 | **Ảnh sản phẩm** | Ít nhất 1; tối đa **10**; |
| 10 | **Profile vận chuyển (Shipping profile)** | Cấu hình trước trên shop Etsy; chọn 1 |

### Tùy chọn (nên có để tăng SEO + trải nghiệm khách)

| # | Mục | Giới hạn |
|---|---|---|
| 11 | **Mã SKU** | Chuỗi tự do; nên thống nhất công thức nội bộ |
| 12 | **Tags (từ khóa tìm kiếm)** | Tối đa **13 tags**; mỗi tag ≤ 20 ký tự; chỉ chữ/số/khoảng trắng/`'`/`-` |
| 13 | **Vật liệu (Materials)** | Liệt kê (Ceramic, Cotton, …); tối đa 13 |
| 14 | **Styles** | Tối đa 2 nhãn phong cách |
| 15 | **Cá nhân hóa (Personalization)** | 4 trường: cho phép hay không / bắt buộc hay không / số ký tự tối đa / hướng dẫn cho khách |
| 16 | **Biến thể** | Chất liệu / Kích thước / Màu — với giá riêng và tồn kho riêng cho từng biến thể |
| 17 | **Cân nặng & Kích thước** | Cân nặng (oz/g) + Dài/Rộng/Cao (cho gói hàng) |
| 18 | **Chính sách đổi trả (Return policy)** | Chọn từ shop |
| 19 | **Tự gia hạn (Auto renew)** | Etsy tự động gia hạn listing sau 4 tháng |

### Ghi chú quan trọng (cập nhật 2025)

- Trước đây Etsy bắt buộc Shipping profile ngay cả với Draft → **từ 2025
  chỉ bắt buộc khi đăng Active**.
- **Readiness state** *bây giờ là bắt buộc* cho listing vật lý — đã được
  cấu hình sẵn cho JaHandmadeArt (Made to order 3-5 ngày).

---

## 4. Hệ thống đang cover được gì

(Tất cả các mục dưới đây đã được kiểm chứng bằng chạy thật trên sandbox
JaHandmadeArt — listing `4511807545` được tạo ngày 26/05/2026.)

| Mục Etsy | Trạng thái | Nguồn dữ liệu |
|---|---|---|
| Tiêu đề | ✅ Đầy đủ | Tên sản phẩm |
| Mô tả | ✅ Đầy đủ | Ô mô tả bán hàng trên form |
| Danh mục Etsy | ⚠️ Một phần | Dùng giá trị mặc định toàn shop; chưa cho phép đặt riêng cho từng sản phẩm |
| Giá | ✅ Đầy đủ | Dùng trường giá bán chuẩn của Odoo (USD). Hệ thống tự đổi sang đơn vị tiền của shop Etsy (ví dụ VND) khi publish — dựa trên trường *Listing Currency* trên shop + bảng tỷ giá *Cài đặt → Currencies → Rates*. Yêu cầu: 2 thứ phải được set 1 lần (xem mục "Điều kiện hoạt động" trong `HUONG_DAN_TAO_SAN_PHAM_VN.md` §3.2). |
| Số lượng | ✅ Đầy đủ | Tồn kho sản phẩm (mặc định = 1 cho MTO) |
| Ai làm / Làm khi nào / Có phải supply không | ⚠️ Một phần | Dùng giá trị mặc định toàn shop; chưa cho phép đặt riêng cho từng sản phẩm |
| Trạng thái sẵn sàng | ✅ Đầy đủ | Mặc định shop (Made to order 3-5 ngày cho JaHandmadeArt) |
| Profile vận chuyển | ✅ Đầy đủ | Mặc định shop |
| Chính sách đổi trả | ✅ Đầy đủ | Mặc định shop |
| Mã SKU | ✅ Đầy đủ | Trường mã nội bộ chuẩn (`Internal Reference`) — sắp được tự động sinh khi BA chọn Danh mục + Biến thể |
| Ảnh sản phẩm | ⚠️ Một phần | Chỉ gửi 1 ảnh chính; Etsy cho phép tới 10 |
| Tags | ✅ Đầy đủ | Wave-2 P-LIST-* đã ship; nhập trong tab Marketing trên form |
| Vật liệu (Materials) | ✅ Đầy đủ | Wave-2 ship; lấy từ tab Materials per-variant |
| Cá nhân hóa | ✅ Đầy đủ | Wave-2 ship; bật check + chỉ dẫn trên form (per-product override) |
| Biến thể (giá/tồn theo từng biến thể) | ✅ Đầy đủ | Wave-2 P-BUG-ESTY-188 iter3 ship; per-variant SKU/qty/price + nhãn Material/Color/Size đúng cho Etsy v3 |
| Cân nặng | ✅ Đầy đủ | Wave-2 ship; lấy trường chuẩn Odoo |
| Kích thước (D/R/C) | ✅ Đầy đủ | Wave-2 ship; per-variant nếu biến thể kích thước |
| Auto renew | ⚠️ Không quan trọng | Có thể cấu hình sau khi listing đã đăng |
| Tiền tệ shop (preview giá VND/EUR/CAD) | ✅ Đầy đủ | Wave-3 P-ENH-ESTY-195 (2026-06-06); Marketing xem giá quy đổi trực tiếp trên Listing form trước khi publish |
| Brand voice mặc định theo shop (Title/Description/Image) | ✅ Đầy đủ | Wave-3 P-ENH-ESTY-190 (2026-06-07); 3-tier fallback listing → product → shop default |

**Kết luận §4 (cập nhật 2026-06-07)**: Mọi mục **bắt buộc** + gần như mọi
mục **tùy chọn nên có** đều đã được hệ thống hỗ trợ sau Wave-2 + Wave-3.
Riêng *Auto renew* không gửi vì có thể chỉnh trực tiếp trên Etsy. Toàn bộ
danh sách lỗi từ owner review 2026-06-03 đã được closure (Jira ESTY-187 →
ESTY-199 đã rời "IN PROCESS" trừ ESTY-188 đang đợi owner re-publish xác
nhận iter3 fix).

---

## 5. Còn thiếu gì — Ưu tiên rõ ràng

### Ưu tiên 1 — Phải có trước khi mở rộng

1. **Tự sinh Mã SKU trên form chuẩn**
   - Khi BA chọn Danh mục + Biến thể, ô Mã SKU tự đề xuất giá trị
     theo công thức nội bộ (vd: `MUG-CR-F11`).
   - Cho phép BA sửa tay nếu cần.
   - Wizard SKU cũ sẽ ẩn khỏi menu nhưng vẫn dùng cho nhập Excel.

2. **Chuyển trường Giá về chuẩn Odoo** *(Đã xong 2026-06-06)*
   - Trước đây có 1 trường giá tùy chỉnh (chỉ dùng cho Etsy) chạy
     song song với ô giá bán chuẩn của Odoo. Đã rút lại còn 1 trường
     duy nhất là **Giá bán (Sales Price USD)** chuẩn của Odoo.
   - BA và Kế toán nhìn cùng một con số ở mọi nơi.
   - Bổ sung 2026-06-06: hệ thống tự **đổi giá USD sang đơn vị tiền
     của shop Etsy** khi publish (ví dụ shop *JaHandmadeArt* dùng VND →
     USD `12.99` × tỷ giá `25.400` ≈ `329.946 ₫`). BA chỉ điền giá USD,
     không cần tự nhân tỷ giá.

3. **Thêm Tags**
   - Bổ sung ô Tags trên form sản phẩm (dùng `product.tag` chuẩn của
     Odoo, không tạo bảng mới).
   - Validator nội bộ enforce giới hạn Etsy (13 tags × 20 ký tự).
   - Publisher gửi mảng tags theo payload.

4. **Đa ảnh (multi-image)**
   - Form sản phẩm Odoo đã có sẵn thư viện ảnh phụ — sẽ được
     bật và gửi lên Etsy (tối đa 10 ảnh, theo thứ tự BA sắp xếp).

### Ưu tiên 2 — Nâng chất lượng listing

5. **Cá nhân hóa (Personalization)**
   - 4 trường mới trên form sản phẩm (tên đặt theo kiểu chung, không
     gắn riêng Etsy, để Amazon hoặc kênh khác sau này tái sử dụng):
     - Cho phép cá nhân hóa hay không
     - Bắt buộc khách điền hay tùy chọn
     - Số ký tự tối đa
     - Hướng dẫn cho khách

6. **Override Danh mục / Ai làm / Làm khi nào theo từng sản phẩm**
   - Hôm nay tất cả sản phẩm dùng chung 1 giá trị mặc định của shop.
   - Sẽ thêm trường trên form sản phẩm để override khi cần (vd: nửa
     catalog là Mug, nửa kia là Apron — không cùng Etsy taxonomy).
   - Quy tắc: nếu BA đã đặt giá trị riêng → dùng giá trị riêng; nếu
     trống → dùng mặc định shop.

7. **Vật liệu (Materials) cho listing**
   - Suy ra từ thuộc tính Chất liệu của biến thể (vd: `Ceramic`,
     `Chrome`). Không cần BA điền 2 lần — dùng dữ liệu đã có.

### Ưu tiên 3 — Hoàn thiện

8. **Nhãn biến thể (Material / Color / Size) gửi kèm offerings**
   - Hôm nay publisher có gửi biến thể với giá/tồn, nhưng nhãn biến
     thể trống. Bổ sung để Etsy hiển thị đúng các tùy chọn cho khách.

9. **Cân nặng & Kích thước**
   - Lấy từ trường cân nặng chuẩn của Odoo; kích thước suy ra từ biến
     thể Size (vd: R30X18 → dài 30, rộng 18).

10. **Tài liệu hướng dẫn cho BA (HUONG_DAN v1.2)**
    - Viết lại §3-§5 của hướng dẫn hiện tại quanh trục "form sản phẩm
      chuẩn", thay vì Wizard.
    - Bổ sung §10 cho 9 mục trên.
    - Cập nhật checklist UAT.

---

## 6. Lộ trình bổ sung (cao tầng)

Mỗi mục dưới đây là một đợt cải tiến độc lập, có thể chạy song song
nếu đội phát triển có sức:

| Đợt | Nội dung | Phụ thuộc |
|---|---|---|
| 1 | Tự sinh Mã SKU trên form chuẩn + ẩn Wizard | Không |
| 2 | Dọn trường Giá về chuẩn Odoo | Không |
| 3 | Bật Tags trên form + publisher | Không |
| 4 | Bật đa ảnh trên form + publisher | Không |
| 5 | Thêm 4 trường Cá nhân hóa | Không |
| 6 | Override Danh mục / Ai làm / Khi nào theo sản phẩm | Không |
| 7 | Vật liệu trong payload | Không |
| 8 | Nhãn biến thể trong payload | Sau đợt 7 (dùng chung helper) |
| 9 | Cân nặng + Kích thước | Không |
| 10 | Tài liệu hướng dẫn v1.2 + UAT mới | Sau đợt 1-9 |

**Thứ tự đề xuất chạy**:
1. Đợt 1 (đổi luồng tạo sản phẩm — nền tảng cho mọi thứ)
2. Đợt 2 (dọn nợ kỹ thuật)
3. Đợt 3 và Đợt 4 chạy song song (giá trị thấy được lớn nhất)
4. Đợt 5 và Đợt 6 chạy song song
5. Đợt 7 → 8
6. Đợt 9
7. Đợt 10 (sau khi tất cả ổn)

---

## 7. Câu hỏi thường gặp

**Q1. Vì sao bỏ Wizard SKU?**
A. Vì form sản phẩm chuẩn của Odoo đã có sẵn các ô Danh mục + Biến thể
mà Wizard đang yêu cầu BA nhập. Đi qua Wizard riêng là làm BA học 2
chỗ, người mới sẽ bối rối. Để hệ thống tự sinh SKU khi BA điền Danh
mục + Biến thể → một chỗ duy nhất, ít sai sót hơn.

**Q2. SKU cũ (legacy) còn dùng được không?**
A. Còn. Hệ thống chỉ tự đề xuất Mã SKU khi ô đó đang trống. Nếu BA
đã nhập tay (hoặc nhập từ Excel) thì giữ nguyên. Có cờ "đã được BA
duyệt là legacy" để validator không cảnh báo nữa.

**Q3. Vì sao dùng `product.tag` chuẩn của Odoo thay vì tự tạo bảng?**
A. Vì Odoo đã có sẵn cơ chế Tags từ phiên bản 17. Tự tạo bảng riêng
sẽ phải tự viết view, ACL, dropdown autocomplete, tìm kiếm — tất cả
đã có. Dùng chuẩn → ít code hơn, dễ bảo trì hơn, dễ tận dụng cho các
kênh khác (Amazon, website).

**Q4. Vì sao bỏ trường `x_listing_price` tự chế?**
A. Vì Odoo đã có trường giá bán chuẩn (`list_price`). Có 2 trường
song song → BA và Kế toán dễ nhìn 2 con số khác nhau cho cùng một
sản phẩm, dễ gây tranh cãi. Dọn lại 1 trường duy nhất.

**Q5. Khi nào sẵn sàng publish hàng loạt lên shop thật?**
A. Hiện tại có thể publish thủ công từng sản phẩm (đã chứng minh
trên sandbox). Để publish hàng loạt cần thêm:
- Đợt 1 (auto SKU) — để BA không bị tắc ở khâu tạo sản phẩm
- Đợt 3, 4, 5 (tags + ảnh + cá nhân hóa) — để listing đủ chất lượng
- Đồng bộ Excel hàng ngày (đã có hơn nửa, còn chờ phần cron)

Ước lượng: 4-6 tuần nếu đội phát triển tập trung.

**Q6. Có rủi ro gì khi đổi luồng tạo sản phẩm?**
A. Rủi ro thấp. Cả Wizard cũ và form chuẩn dùng chung 1 database;
sản phẩm đã tạo trước đây không bị ảnh hưởng. Validator SKU vẫn
chạy y nguyên — sản phẩm SKU sai sẽ bị từ chối ở cả hai luồng.

**Q7. BA cần học lại không?**
A. Không nhiều. Form sản phẩm chuẩn của Odoo đã quen thuộc với bất
kỳ ai dùng Odoo. Cái mới chỉ là: thay vì mở Wizard, mở thẳng menu
**Sản phẩm**. Sẽ có tài liệu hướng dẫn v1.2 viết lại các bước với
ảnh chụp màn hình mới.

**Q8. Các kênh khác (Amazon, website) sau này có phải làm lại không?**
A. Không. Tất cả các trường mới (tags, cá nhân hóa, danh mục, ai
làm, khi nào, vật liệu, cân nặng, kích thước) được đặt tên trung
tính — không gắn "etsy" trong tên — để Amazon và website tái sử dụng
ngay khi tới lượt.

---

## 8. Liên hệ khi có vấn đề

- **Câu hỏi nghiệp vụ (BA / Ops)**: Chủ shop trực tiếp.
- **Vấn đề kỹ thuật khi tạo sản phẩm**: log lại tại Telegram DM của
  Chủ shop với mã sản phẩm + ảnh chụp màn hình.
- **Lỗi publish lên Etsy**: nếu thấy nút "Resume Publish" trên form
  sản phẩm → bấm thử trước; nếu vẫn lỗi → báo cùng nội dung như trên.
