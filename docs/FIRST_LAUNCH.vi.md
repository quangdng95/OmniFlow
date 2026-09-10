# Cảnh báo bảo mật macOS khi mở app lần đầu

**[🇬🇧 English](FIRST_LAUNCH.md)&nbsp;&nbsp;|&nbsp;&nbsp;🇻🇳 Tiếng Việt**

OmniFlow chưa được Apple notarize (việc này cần một tài khoản Apple Developer trả phí $99/năm),
nên macOS sẽ hiện một vài cảnh báo bảo mật chỉ xuất hiện một lần trong lần đầu bạn dùng app. Cả
hai cảnh báo đều không có nghĩa là có gì đó sai — hướng dẫn này sẽ chỉ chính xác bạn sẽ thấy gì và
cần bấm gì.

## 1. "OmniFlow can't be opened because it is from an unidentified developer"

Cảnh báo này xuất hiện ngay lần đầu tiên bạn cố mở app sau khi cài đặt.

**Cần làm gì:**

1. **Đừng** double-click vào icon app trong `Applications` — làm vậy sẽ bị chặn lại lần nữa.
2. Thay vào đó, **right-click** (hoặc Control-click) vào **OmniFlow** trong `Applications` và chọn
   **Open** từ menu hiện ra.
3. Một hộp thoại hỏi "Are you sure you want to open it?" — bấm **Open**.

Vậy là xong. macOS sẽ nhớ lựa chọn này, nên bạn sẽ không bao giờ thấy lại cảnh báo này cho đúng
phiên bản app đó nữa.

**Cách khác**, nếu right-click → Open không hiện nút Open:

1. Thử double-click app một lần (vẫn sẽ bị chặn).
2. Mở **System Settings → Privacy & Security**.
3. Cuộn xuống — bạn sẽ thấy dòng chữ kiểu *"OmniFlow was blocked to protect your Mac"* kèm nút
   **Open Anyway**. Bấm vào đó, rồi xác nhận ở hộp thoại tiếp theo.

> **Vì sao lại có cảnh báo này?** Gatekeeper của macOS chỉ tin tưởng những app đã được Apple
> notarize hoặc ký bằng Developer ID trả phí. OmniFlow được ký kiểu "ad-hoc" (chữ ký miễn phí, chỉ
> có giá trị cục bộ) để có thể phân phối tự do mà không cần tài khoản developer — nhưng điều đó
> cũng có nghĩa Gatekeeper không nhận ra đây là app "đã biết" trong lần mở đầu tiên. Đây là bước
> tiêu chuẩn với mọi app macOS nhỏ, phân phối độc lập, không phải dấu hiệu bất thường.

## 2. "OmniFlow wants to use your confidential information stored in 'Chrome Safe Storage' in your keychain"

Cảnh báo này **không bắt buộc** để dùng OmniFlow — nó chỉ xuất hiện khi bạn check hoặc tải một
link từ **Instagram** hoặc **Threads**, và chỉ khi bạn đang đăng nhập một trong hai nền tảng đó
trên trình duyệt của máy này (Chrome, Brave, Edge, Vivaldi, Opera, hoặc Safari).

**Nó đang xin quyền gì:** để tải nội dung Instagram/Threads riêng tư hoặc yêu cầu đăng nhập (một
Reel từ tài khoản bạn follow, một Story, một bài đăng riêng tư), OmniFlow cần dùng lại phiên đăng
nhập trên trình duyệt *của chính bạn* — giống hệt cách trình duyệt của bạn đã tin tưởng bạn từ
trước. Để làm vậy, nó cần đọc một giá trị được mã hóa mà macOS lưu cho trình duyệt của bạn ("Chrome
Safe Storage" là tên Chrome/Brave/Edge dùng chung cho việc này, dù nội dung hộp thoại chính xác có
thể hơi khác theo từng trình duyệt).

**Nên bấm gì:** khuyến nghị bấm **Always Allow** — như vậy các lượt tải Instagram/Threads sau này
sẽ hoạt động mà không hỏi lại. Nếu bạn bấm **Allow** (dùng một lần) hoặc **Deny**:

- **Allow (một lần):** hoạt động cho lượt tải đó, nhưng lần sau có thể sẽ hỏi lại.
- **Deny:** OmniFlow sẽ không đọc được phiên đăng nhập của trình duyệt đó — các lượt tải
  Instagram/Threads cần đăng nhập sẽ báo lỗi "không tìm thấy session", nhưng mọi nền tảng khác
  (YouTube, TikTok, Facebook, RedNote, LinkedIn, X) hoàn toàn không bị ảnh hưởng.

**Mọi thứ đều ở lại trên máy bạn.** Quyền này chỉ cho phép OmniFlow đọc session token cục bộ,
ngay trên máy của bạn, để gửi request tới Instagram/Threads thay bạn — không có gì được gửi đi
nơi khác. Xem [Quyền riêng tư](../README.vi.md#quyền-riêng-tư) trong README chính.

> **Vì sao cảnh báo này có thể hiện lại sau khi cập nhật app?** Mỗi phiên bản OmniFlow mới bạn
> tải về được ký độc lập (xem giải thích về Gatekeeper ở trên), và Keychain của macOS gắn quyền
> này với *đúng* phiên bản app đã xin quyền đó. Điều đó có nghĩa cập nhật lên bản OmniFlow mới hơn
> có thể khiến cảnh báo này hiện lại, dù bạn đã từng bấm "Always Allow" cho phiên bản trước — đây
> là hành vi bình thường của macOS, không phải lỗi, và bấm **Always Allow** lần nữa sẽ xử lý y hệt
> như trước.

## Vẫn còn kẹt?

Nếu OmniFlow mở được nhưng bản thân việc check/tải không hoạt động, đó là một vấn đề khác — xem
[Xử lý lỗi Check/Tải file](TROUBLESHOOTING.vi.md) thay vào đó.
