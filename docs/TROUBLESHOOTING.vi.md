# Xử lý lỗi Check/Tải file

**[🇬🇧 English](TROUBLESHOOTING.md)&nbsp;&nbsp;|&nbsp;&nbsp;🇻🇳 Tiếng Việt**

Nếu dán link vào OmniFlow mà check không được, hoặc việc tải cứ lỗi hoài, hướng dẫn này đi qua các
nguyên nhân phổ biến nhất và hai công cụ có sẵn giúp bạn chẩn đoán thay vì phải đoán mò.

Nếu bạn chưa từng mở OmniFlow lần nào, hoặc đang thấy một cảnh báo bảo mật của macOS thay vì lỗi
trong app, xem [Cảnh báo bảo mật macOS khi mở app lần đầu](FIRST_LAUNCH.vi.md) thay vào đó.

## Bắt đầu từ đây: hai công cụ trong Cài đặt

Trước khi làm gì khác, hãy biết rằng **Cài đặt** (Settings) có sẵn hai công cụ được xây dựng riêng
cho tình huống này:

- **Nhật ký chẩn đoán** (Cài đặt → Nhật ký chẩn đoán → **Mở thư mục Log**) — mở một thư mục chứa
  file `errors.log`, ghi lại nguyên nhân *thật sự*, mang tính kỹ thuật đằng sau một lỗi ngay cả khi
  app chỉ hiện cho bạn một thông báo ngắn gọn, thân thiện. Nếu bạn đang báo lỗi (bug), nội dung file
  này là thứ hữu ích nhất bạn có thể đính kèm.
- **Đặt lại dữ liệu ứng dụng** (Cài đặt → Đặt lại dữ liệu ứng dụng → **Xóa Cache & Đặt lại Cài
  đặt**) — xóa các cài đặt đã lưu của OmniFlow (thư mục tải, thông tin đăng nhập đã lưu) và bắt đầu
  lại từ đầu. Thao tác này **không** xóa bất kỳ file nào bạn đã tải. Dùng cách này khi một lỗi có
  vẻ vô lý so với thực tế bạn biết (ví dụ: "mình chắc chắn đang đăng nhập Instagram, nhưng app báo
  không tìm thấy session") — một cài đặt cũ còn sót lại từ phiên bản trước là nguyên nhân thường
  gặp.

## Các thông báo thường gặp và ý nghĩa

Dưới đây là nguyên văn các thông báo lỗi mà OmniFlow hiển thị (app luôn báo lỗi bằng tiếng Việt,
bất kể ngôn ngữ giao diện bạn chọn trong Cài đặt), kèm giải thích và cách xử lý.

### Sai bản cài đặt cho chip máy Mac

> ❌ Lỗi: Bản OmniFlow này không tương thích với chip của máy Mac bạn đang dùng (kiến trúc ...).
> Vui lòng tải đúng bản dành cho máy bạn (OmniFlow-AppleSilicon.dmg hoặc OmniFlow-Intel.dmg) tại
> trang GitHub Releases của OmniFlow.

OmniFlow có hai bản build riêng biệt — một bản native cho Apple Silicon (M1/M2/M3/M4) và một bản
native cho Intel — vì công cụ `ffmpeg` đi kèm chỉ chạy được trên đúng loại chip mà nó được build
cho. Thông báo này nghĩa là bạn đã cài nhầm bản không đúng với máy Mac của mình.

**Cách sửa:** tải lại từ [mục Tải xuống trong README](../README.vi.md#tải-xuống) hoặc từ
[Releases](https://github.com/quangdng95/OmniFlow/releases/latest), chọn
**OmniFlow-AppleSilicon.dmg** cho Mac M1/M2/M3/M4 hoặc **OmniFlow-Intel.dmg** cho Mac Intel.
Không chắc máy mình dùng chip gì? Menu Apple (góc trên bên trái) → **About This Mac** — sẽ ghi rõ
tên chip.

### "Không thể tải video từ tài khoản Private (Kín)"

> ❌ Lỗi: Không thể tải video từ tài khoản Private (Kín). OmniFlow hiện tại chỉ hỗ trợ tải nội
> dung Public (Công khai).

Thông báo này bao gồm hai tình huống khác nhau mà OmniFlow không phải lúc nào cũng phân biệt được:

1. Tài khoản/bài đăng thực sự đang ở chế độ Private, và bạn không follow từ một phiên đăng nhập
   trên máy này — đây là điều bình thường; OmniFlow chỉ truy cập được những gì tài khoản đã đăng
   nhập của bạn thấy được.
2. Phiên đăng nhập Instagram/Threads đã lưu của bạn bị hết hạn hoặc không còn hợp lệ — phản hồi từ
   nền tảng trông giống nhau trong cả hai trường hợp, nên OmniFlow không phải lúc nào cũng phân
   biệt được "thực sự riêng tư" với "session đã chết".

**Thử cách này:** mở link đó trên trình duyệt trước — nếu bạn xem được mà không bị hỏi đăng nhập,
nghĩa là nó công khai, và bạn nhiều khả năng đang gặp tình huống 2. Thử **Đặt lại dữ liệu ứng
dụng**, rồi thử lại link đó. Nếu bạn vẫn đang đăng nhập Instagram/Threads trên trình duyệt,
OmniFlow sẽ tự lấy session mới ở lần thử tiếp theo.

### "Không tìm thấy phiên đăng nhập Instagram/Threads"

> ❌ Lỗi: Không tìm thấy phiên đăng nhập Instagram nào trên trình duyệt của máy này. Vui lòng
> đăng nhập Instagram trên Chrome/Safari/Brave (hoặc thêm cookies.txt thủ công trong Settings) rồi
> thử lại.
>
> *(Với Threads: ❌ Lỗi: Cần một trình duyệt đã đăng nhập Threads (threads.com) trên máy này để
> tải bài viết. Vui lòng đăng nhập rồi thử lại.)*

OmniFlow tự động tìm một phiên đăng nhập Instagram hoặc Threads trong các trình duyệt cục bộ trên
máy bạn (Chrome, Brave, Edge, Vivaldi, Opera, Safari) — bạn không bao giờ cần export cookie thủ
công. Thông báo này nghĩa là nó không tìm thấy phiên nào. Kiểm tra lại:

- Bạn có thực sự đang đăng nhập Instagram hoặc Threads trên một trong các trình duyệt đó, trên
  **chính máy này** không.
- Bạn đã bấm **Allow** hoặc **Always Allow** ở hộp thoại xin quyền Keychain chưa — xem
  [Cảnh báo bảo mật macOS khi mở app lần đầu](FIRST_LAUNCH.vi.md#2-omniflow-wants-to-use-your-confidential-information-stored-in-chrome-safe-storage-in-your-keychain)
  nếu bạn chưa chắc đó là gì.

Cookie của Safari được macOS bảo vệ theo cách mà OmniFlow hiện tại hoàn toàn không đọc được (đây
là giới hạn ở cấp hệ thống, không phải điều OmniFlow có thể vượt qua) — nếu Safari là trình duyệt
duy nhất bạn đăng nhập Instagram/Threads, hãy dùng Chrome, Brave, hoặc Edge thay thế cho hai nền
tảng này.

### "Không thể kết nối mạng"

> ❌ Lỗi: Không thể kết nối mạng để xử lý liên kết này. Vui lòng kiểm tra kết nối Internet (hoặc
> tường lửa/VPN) rồi thử lại.

OmniFlow không kết nối được internet để xử lý link. Kiểm tra lại kết nối Wi-Fi/Ethernet, và nếu
bạn đang dùng VPN hay tường lửa (firewall) chặt, thử tắt tạm thời — một số mạng công ty hoặc
trường học chặn các nền tảng mà OmniFlow cần kết nối tới.

### "IP của bạn đang tạm thời bị chặn/giới hạn"

> ❌ Lỗi: IP của bạn đang tạm thời bị nền tảng này chặn/giới hạn. Vui lòng thử lại sau ít phút
> hoặc đổi mạng.

Một số nền tảng (đặc biệt là TikTok) giới hạn tốc độ hoặc tạm chặn một địa chỉ IP gửi quá nhiều
request trong thời gian ngắn. Đợi vài phút rồi thử lại, hoặc đổi mạng (ví dụ: phát Wi-Fi từ điện
thoại) nếu vẫn còn lỗi.

### Bài đăng LinkedIn dạng tài liệu/slide (PDF)

> ❌ Lỗi: Bài đăng LinkedIn dạng tài liệu/slide (PDF) hiện chưa được OmniFlow hỗ trợ tải. OmniFlow
> hiện chỉ hỗ trợ bài đăng LinkedIn dạng video hoặc ảnh.

LinkedIn có ba dạng bài đăng khác nhau: video, ảnh, và bài dạng tài liệu/slide (PDF) native.
OmniFlow hỗ trợ hai dạng đầu; dạng thứ ba hiện chưa có cách nào để trích xuất. Thông báo này nghĩa
là link bạn dán vào chính xác thuộc dạng thứ ba, chưa được hỗ trợ này — đây không phải lỗi (bug),
chỉ là một gap vẫn còn tồn đọng (xem [Roadmap](../README.vi.md#roadmap) trong README chính). Nếu
bạn có một ví dụ công khai của dạng bài đăng này, mở một GitHub Issue kèm link đó sẽ giúp ích cho
việc phát triển tính năng này.

### Thông báo chung chung "Không thể xử lý liên kết này"

> ❌ Lỗi: Không thể xử lý liên kết này. Vui lòng kiểm tra lại link hoặc thử lại sau.

Đây là thông báo dự phòng của OmniFlow cho một lỗi mà nó không có lời giải thích cụ thể, thân
thiện nào. Đây chính xác là lúc `errors.log` phát huy tác dụng — mở **Cài đặt → Nhật ký chẩn đoán
→ Mở thư mục Log**, mở file `errors.log`, và tìm mục gần nhất (có timestamp). Nếu bạn đang báo lỗi
này, hãy đính kèm toàn bộ nội dung mục đó.

## Vẫn chưa hoạt động?

1. Thử **Đặt lại dữ liệu ứng dụng** một lần (trong Cài đặt), rồi thử lại link.
2. Thoát và mở lại OmniFlow.
3. Kiểm tra `errors.log` (Cài đặt → Nhật ký chẩn đoán) để xem lỗi cụ thể.
4. Nếu vẫn không giải quyết được, mở một
   [GitHub Issue](https://github.com/quangdng95/OmniFlow/issues) kèm link đó (nếu không phải nội
   dung riêng tư/nhạy cảm), chip máy Mac và phiên bản macOS của bạn, và mục `errors.log` liên
   quan — xem [Hỗ trợ & Báo lỗi](../README.vi.md#hỗ-trợ--báo-lỗi) trong README chính.
