<div align="center">
  <img src="docs/logo.png" alt="ViDrop" width="120" />

  # ViDrop

  **Ứng dụng tải video, âm thanh & ảnh đa nền tảng cho macOS.**

  Dán link. Nhận file. Không watermark, không quảng cáo, không bị chặn bởi anti-bot.

  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
  [![Platform: macOS](https://img.shields.io/badge/platform-macOS-lightgrey.svg)](#cài-đặt)
  [![Latest Release](https://img.shields.io/github/v/release/quangdng95/ViDrop)](../../releases/latest)

  **[🇬🇧 English](README.md)&nbsp;&nbsp;|&nbsp;&nbsp;🇻🇳 Tiếng Việt**
</div>

---

## Tải xuống

Không chắc máy Mac của bạn dùng chip gì? Menu Apple (góc trên bên trái) → **Giới thiệu về máy
Mac này** (About This Mac).

<p align="center">
  <a href="https://github.com/quangdng95/ViDrop/releases/latest/download/ViDrop-AppleSilicon.dmg"><img src="https://img.shields.io/badge/Tải_về-Apple_Silicon-black?style=for-the-badge&logo=apple" alt="Tải cho Apple Silicon (M1/M2/M3/M4)" /></a>
  <a href="https://github.com/quangdng95/ViDrop/releases/latest/download/ViDrop-Intel.dmg"><img src="https://img.shields.io/badge/Tải_về-Intel_Mac-black?style=for-the-badge&logo=apple" alt="Tải cho Mac Intel" /></a>
</p>

Hai link trên luôn trỏ tới bản phát hành mới nhất. Xem [Cài đặt](#cài-đặt) bên dưới để biết việc
cần làm sau khi tải — bao gồm các cảnh báo bảo mật macOS xuất hiện một lần khi mở app lần đầu.

---

## Ứng dụng làm được gì

ViDrop trích xuất và tải video, âm thanh, ảnh chất lượng cao, không watermark từ những nền tảng
mà các nhà sáng tạo, designer, và nhà nghiên cứu thực sự lấy tư liệu tham khảo:

<p align="center">
  <img src="Assets/Tags/Youtube.svg" height="28" alt="YouTube" />
  <img src="Assets/Tags/Tiktok.svg" height="28" alt="TikTok" />
  <img src="Assets/Tags/Instagram.svg" height="28" alt="Instagram" />
  <img src="Assets/Tags/Facebook.svg" height="28" alt="Facebook" />
  <img src="Assets/Tags/Rednote.svg" height="28" alt="RedNote" />
  <img src="Assets/Tags/Linked.svg" height="28" alt="LinkedIn" />
  <img src="Assets/Tags/Threads.svg" height="28" alt="Threads" />
  <img src="Assets/Tags/x.com.svg" height="28" alt="X (Twitter)" />
</p>

**YouTube · TikTok · Instagram · Facebook · RedNote (Xiaohongshu) · LinkedIn · Threads · X (Twitter)**

| Nền tảng | Dùng được | Ghi chú |
|---|---|---|
| YouTube | Video đến 4K, chỉ âm thanh (MP3), Mix, playlist, kênh | Có thể cần đăng nhập Chrome: Cài đặt → Đăng nhập YouTube |
| TikTok | Video, chỉ âm thanh (MP3), slideshow Photo Mode | Photo Mode dùng dịch vụ bên thứ ba tikwm.com |
| Instagram | Reel, bài ảnh, carousel | Cần đăng nhập trên trình duyệt. Danh sách profile / Reels thường bị Instagram từ chối |
| Facebook | Video, Reel, link `share/r/` | |
| X (Twitter) | Bài video | |
| Threads | Bài video, bài ảnh | Cần đăng nhập trên trình duyệt |
| LinkedIn | Bài video, bài ảnh, slide (PDF) — mỗi trang là một ảnh | Link `lnkd.in` dùng được. Không cần đăng nhập |
| RedNote (Xiaohongshu) | Bài video, bài ảnh | Cần đăng nhập trên trình duyệt. Link chia sẻ hết hạn nên hãy copy link mới |

Mọi dòng đều được kiểm tra bằng link thật. Bảng đầy đủ, ghi rõ phần đã và chưa kiểm tra, nằm ở
[docs/PLATFORM_SUPPORT.md](docs/PLATFORM_SUPPORT.md) (bằng tiếng Anh).

## Tính năng

- **Tải đơn hoặc hàng loạt** — một video, hay cả playlist/kênh YouTube, carousel Instagram, hoặc
  Story Instagram, chỉ trong một lần dán link.
- **Tự động nhận diện link** — ViDrop tự xác định link là một item đơn hay nguồn nhiều item;
  bạn không cần khai báo gì cả.
- **Điều khiển từng item** — trong playlist hay carousel, tải hết một lượt, chọn riêng từng cái,
  hoặc thử lại một item bị lỗi.
- **Phát được mọi nơi trên Mac** — xuất file H.264/AAC MP4 phát được ngay trong QuickLook và
  QuickTime. Đến 1080p, app tải song song nhiều fragment và merge kiểu stream-copy (không
  transcode toàn bộ). Bản 1440p và 4K được chuyển sang H.264 sau khi tải (dùng bộ mã hoá phần cứng của Mac khi nhanh hơn); chọn **Giữ codec gốc** để bỏ qua bước chuyển đổi và lưu thành file `.mkv` (có thể không mở được bằng QuickTime hoặc trên iPhone).
- **Theo dõi tiến trình trực tiếp** — tiến trình tải từng item và tổng thể, có thể hủy bất cứ lúc
  nào.
- **Chạy trên máy bạn** — link và cookie của bạn ở lại trên máy (riêng TikTok có một ngoại lệ, xem
  [Quyền riêng tư](#quyền-riêng-tư)).

## Cài đặt

1. Tải file `.dmg` đúng với chip máy Mac của bạn — xem [Tải xuống](#tải-xuống) ở trên, hoặc lấy
   từ [Releases](../../releases/latest):
   - **ViDrop-AppleSilicon.dmg** — cho Mac M1/M2/M3/M4
   - **ViDrop-Intel.dmg** — cho Mac dùng chip Intel
2. Mở file `.dmg` và kéo **ViDrop** vào thư mục `Applications`.
3. Lần đầu mở app, macOS sẽ hiện một hoặc hai cảnh báo bảo mật (cảnh báo "nhà phát triển không
   xác định", và — chỉ khi bạn định tải từ Instagram, Threads hoặc RedNote, hoặc bật đăng nhập
   YouTube — yêu cầu quyền truy cập Keychain). Cả hai đều bình thường, chỉ xuất hiện một lần, và
   được giải thích từng bước trong [Cảnh báo bảo mật macOS khi mở app lần đầu](docs/FIRST_LAUNCH.vi.md).

**Đang dùng app cũ (OmniFlow)?** ViDrop là một app riêng. Lần đầu mở, nó sao chép cài đặt từ thư
mục của app cũ và giữ nguyên thư mục đó, nên bạn có thể giữ app cũ đến khi yên tâm. macOS coi ViDrop
là app mới nên sẽ hỏi lại quyền Keychain. Lịch sử của bạn bắt đầu từ trống.

Muốn tự build app? Xem [Build từ mã nguồn](#build-từ-mã-nguồn) bên dưới.

## Cách dùng

1. Dán link vào ViDrop (từ clipboard, hoặc gõ/dán thủ công).
2. ViDrop tự nhận diện nền tảng và xác định đây là một item đơn hay một danh sách.
3. Chọn chất lượng (Best, 1080p, 720p, 480p, Chỉ âm thanh, …) — hoặc, nếu là danh sách, chọn
   những item bạn muốn.
4. Bấm **Download** và theo dõi tiến trình theo thời gian thực.
5. File hoàn tất sẽ nằm trong thư mục tải đã cấu hình (mặc định là `~/Downloads`).

Một số nền tảng (Instagram, Threads, RedNote) cần một phiên đăng nhập trên trình duyệt để lấy được nội
dung riêng tư/bị giới hạn — ViDrop tự đọc thông tin này từ cookie trình duyệt trên máy bạn;
không cần export thủ công. Nếu YouTube yêu cầu đăng nhập, hãy chọn profile Chrome của bạn trong
**Cài đặt → Đăng nhập YouTube** (mặc định đang tắt).

**Ví dụ:**

```
Dán:    https://www.youtube.com/watch?v=dQw4w9WgXcQ
Chọn:   Best
Nhận:   Never Gonna Give You Up.mp4  (trong ~/Downloads)
```

Chưa biết thử link nào trước? [**Link ví dụ**](docs/EXAMPLE_LINKS.vi.md) có sẵn một link mẫu
dán-là-chạy cho mỗi nền tảng được hỗ trợ.

## Build từ mã nguồn

**Yêu cầu:** Node.js, Python 3.9+, npm.

```bash
# clone và vào thư mục repo
git clone https://github.com/quangdng95/ViDrop.git
cd ViDrop

# cài đặt một lần
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm install && cd ..
```

**Chạy ở chế độ dev** (hot-reload, backend Flask trên `:5001` + frontend Vite trên `:5173`):

```bash
./scripts/dev.sh
```

**Build app macOS độc lập** (tạo ra `release/v<phiên bản>/ViDrop-AppleSilicon.dmg`, hoặc `ViDrop-Intel.dmg` trên Mac Intel, cùng app đã ký trong `release/v<phiên bản>/_build/`):

```bash
./scripts/build.sh
```

## Tech stack

- **Backend:** Python, Flask, [`yt-dlp`](https://github.com/yt-dlp/yt-dlp) (gọi trực tiếp
  in-process), `ffmpeg` được đóng gói sẵn để remux.
- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, [shadcn/ui](https://ui.shadcn.com).
- **Desktop shell:** [`pywebview`](https://pywebview.flowrl.com), đóng gói bằng PyInstaller.

## Quyền riêng tư

ViDrop chạy hoàn toàn trên máy Mac của bạn. Ứng dụng **không**:

- Lưu trữ hay chuyển tiếp file tải qua bất kỳ server bên ngoài nào
- Theo dõi hay ghi log lịch sử tải của bạn
- Thu thập hay truyền đi bất kỳ dữ liệu cá nhân nào

Có một ngoại lệ: khi không đọc trực tiếp được link TikTok, ViDrop gửi link đó tới dịch vụ bên thứ
ba tikwm.com để phân giải. Mục này nói về app Mac. Bản web được lưu trữ sẽ xử lý các link bạn dán
trên server của nó.

Cookie trình duyệt (dùng để lấy nội dung Instagram, Threads và RedNote) được đọc cục bộ trên máy
bạn và không bao giờ rời khỏi máy.

## Roadmap

Những gap còn tồn đọng, được ghi nhận trung thực thay vì giấu đi.

**Hoàn thiện app macOS**

- [x] `ffmpeg` native `arm64` cho bản Apple Silicon, không còn cần Rosetta 2 lúc chạy (cả bản
  Apple Silicon lẫn Intel giờ đều dùng binary native cho đúng chip của mình)
- [ ] Code signing + notarization, để macOS không còn cảnh báo "nhà phát triển không xác định"
  khi mở lần đầu — cần một tài khoản Apple Developer trả phí; xem [First Launch](docs/FIRST_LAUNCH.vi.md)
  để biết cách xử lý tạm thời (miễn phí, chỉ làm một lần) trong lúc chờ
- [x] Hỗ trợ bài đăng LinkedIn dạng tài liệu/slide (PDF) — liệt kê và tải từng trang thành ảnh
  (kèm link rút gọn `lnkd.in`, giờ được mở rộng trước khi phân loại link)
- [ ] Build cho Windows / Linux

**Mở rộng nền tảng**

- [ ] Chrome extension — bấm một nút ngay trên trình duyệt để gửi video đang xem thẳng vào
  ViDrop, không cần copy-paste link
- [ ] Một cách tiện lợi để gửi link vào ViDrop từ điện thoại trong khi app đang chạy trên máy
  Mac (ví dụ: một iOS Shortcut, hoặc một trang web tối ưu cho di động)
- [ ] App Android native
- [ ] App iOS native

> **Về 2 mục app di động native ở trên:** đây vẫn là ý tưởng sớm, mang tính khám phá, chưa cam
> kết thực hiện. `yt-dlp` là một công cụ Python, nên app di động native sẽ cần một server làm phần xử
> lý, như bản web. Hiện ViDrop có hai chế độ: app Mac xử lý mọi link ngay trên máy của người dùng,
> còn bản web (`remote_web`) xử lý link trên server, có access token (xem
> [Disclaimer](.github/DISCLAIMER.md)). Cả
> App Store lẫn Play Store đều có lịch sử rõ ràng về việc từ chối hoặc gỡ bỏ các app "tải video"
> vì lo ngại bản quyền/ToS, nên một app di động native có thể sẽ phải phân phối ngoài store chính
> thức (sideloading, kiểu phân phối như TestFlight) thay vì mặc định có sẵn trên store thông
> thường.

## Xử lý sự cố

Gặp cảnh báo bảo mật khi mở lần đầu, hay việc check/tải cứ lỗi hoài? Hai hướng dẫn dưới đây giải
thích chi tiết, từng bước:

- **[Cảnh báo bảo mật macOS khi mở app lần đầu](docs/FIRST_LAUNCH.vi.md)** — cảnh báo "nhà phát
  triển không xác định" và yêu cầu quyền Keychain bạn có thể gặp lần đầu mở app hoặc tải từ
  Instagram/Threads.
- **[Xử lý lỗi Check/Tải file](docs/TROUBLESHOOTING.vi.md)** — cần làm gì khi một link không check
  được hoặc tải cứ lỗi, bao gồm cách dùng công cụ **Diagnostic Logs** và **Reset App Data** có sẵn
  trong Settings.

Nếu vẫn không giải quyết được, xem [Hỗ trợ & Báo lỗi](#hỗ-trợ--báo-lỗi) bên dưới.

## Đóng góp

Rất hoan nghênh mọi đóng góp:

1. Fork repository
2. Tạo một branch mới (`git checkout -b feat/my-feature`)
3. Commit thay đổi của bạn
4. Push lên branch và mở một Pull Request

## Hỗ trợ & Báo lỗi

Vẫn bị kẹt sau khi đã xem hướng dẫn [Xử lý sự cố](#xử-lý-sự-cố) ở trên? Mở một issue trên
[GitHub Issues](https://github.com/quangdng95/ViDrop/issues) — kèm theo:

- Link bạn đang cố tải (nếu không phải nội dung riêng tư/nhạy cảm)
- Chip máy Mac của bạn (Apple Silicon hay Intel) và phiên bản macOS
- Nội dung file `errors.log`, nếu có — Settings → **Diagnostic Logs** → **Open Log Folder**

Có ý tưởng tính năng mới? Cũng mở issue để đề xuất nhé.

## Disclaimer

ViDrop được xây dựng cho **mục đích cá nhân, phi thương mại** — nghiên cứu, học tập, và lưu trữ
tư liệu tham khảo của riêng bạn. Bạn tự chịu trách nhiệm về vấn đề bản quyền của bất kỳ nội dung
nào bạn tải xuống, và về việc tuân thủ Điều khoản Dịch vụ của từng nền tảng. Nhóm phát triển cung
cấp công cụ này "NGUYÊN TRẠNG" (AS IS), không chịu trách nhiệm pháp lý cho cách nó được sử dụng —
xem [DISCLAIMER.md](.github/DISCLAIMER.md) để đọc toàn bộ tuyên bố miễn trừ trách nhiệm và
[CODE_OF_CONDUCT.md](.github/CODE_OF_CONDUCT.md) để biết chính sách sử dụng được chấp nhận.

## Giấy phép

Phát hành theo giấy phép [GNU General Public License v3.0](LICENSE).
