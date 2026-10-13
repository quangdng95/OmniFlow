"""User-facing error text in Vietnamese and English - one catalog shared by the
desktop app (backend/app.py) and the cloud deployment (remote_web).

The frontend's language switch sends its choice as the `X-Language` header on
every API call; a route reads it once with request_language() and passes the
result down, including into worker threads (which have no request context).

Vietnamese stays the default when no language is given: every client that
predates the header (the iOS Shortcut, older callers) only ever received
Vietnamese, and this keeps that unchanged. Pure stdlib apart from a lazy Flask
import, so any module may import it.
"""

VI = "vi"
EN = "en"
DEFAULT_LANGUAGE = VI
LANGUAGE_HEADER = "X-Language"

_CATALOG = {
    "instagram_local_only": {
        VI: "Chỉ tải được Instagram khi chạy ViDrop trực tiếp trên máy của bạn.",
        EN: "Instagram downloads are only available when running ViDrop locally on your own machine.",
    },
    "threads_local_only": {
        VI: "Chỉ tải được Threads khi chạy ViDrop trực tiếp trên máy của bạn.",
        EN: "Threads downloads are only available when running ViDrop locally on your own machine.",
    },
    "instagram_no_session": {
        VI: "❌ Lỗi: Không tìm thấy phiên đăng nhập Instagram nào trên trình duyệt của máy này. Vui lòng đăng nhập Instagram trên Chrome/Safari/Brave (hoặc thêm cookies.txt thủ công trong Settings) rồi thử lại.",
        EN: "❌ Error: No Instagram login session was found in any browser on this machine. Please sign in to Instagram in Chrome/Safari/Brave (or add a cookies.txt manually in Settings), then try again.",
    },
    "threads_auth": {
        VI: "❌ Lỗi: Cần một trình duyệt đã đăng nhập Threads (threads.com) trên máy này để tải bài viết. Vui lòng đăng nhập rồi thử lại.",
        EN: "❌ Error: A browser signed in to Threads (threads.com) is required on this machine to download this post. Please sign in, then try again.",
    },
    "rednote_auth": {
        VI: "❌ Lỗi: RedNote yêu cầu đăng nhập để xem bài này. Hãy đăng nhập RedNote (rednote.com) trong trình duyệt trên máy chủ rồi thử lại.",
        EN: "❌ Error: RedNote requires a signed-in session to view this post. Sign in to RedNote (rednote.com) in the browser on the server, then try again.",
    },
    "extract_failed": {
        VI: "❌ Lỗi: Không thể trích xuất dữ liệu từ liên kết này. Vui lòng kiểm tra lại liên kết hoặc trạng thái công khai của nội dung.",
        EN: "❌ Error: Couldn't extract data from this link. Please check the link, or whether the content is public.",
    },
    # LinkedIn's native document/slide-deck (PDF) post type has no known
    # resolver (see MISTAKES.md), so it gets its own specific message rather
    # than whatever unrelated error yt-dlp raises for the same URL.
    "linkedin_document": {
        VI: "❌ Lỗi: Không đọc được nội dung bài đăng LinkedIn này. Bài có thể đã bị xoá hoặc ở chế độ riêng tư, hoặc là tài liệu/slide (PDF) mà các trang không đọc được. ViDrop hỗ trợ bài LinkedIn công khai dạng video, ảnh và tài liệu.",
        EN: "❌ Error: Couldn't read this LinkedIn post. It may have been removed or be private, or it is a document/slide (PDF) whose pages couldn't be read. ViDrop supports public LinkedIn video, image and document posts.",
    },
    "network_unreachable": {
        VI: "❌ Lỗi: Không thể kết nối mạng để xử lý liên kết này. Vui lòng kiểm tra kết nối Internet (hoặc tường lửa/VPN) rồi thử lại.",
        EN: "❌ Error: Couldn't connect to the network to process this link. Please check your Internet connection (or firewall/VPN) and try again.",
    },
    "instagram_profile_restricted": {
        VI: "❌ Lỗi: Không thể lấy danh sách từ tài khoản Instagram này do giới hạn bảo mật. Vui lòng tải từng bài viết (Post/Reel) hoặc kiểm tra lại Cookies trong Settings.",
        EN: "❌ Error: Couldn't list this Instagram account because of platform restrictions. Please download individual posts (Post/Reel) instead, or check your Cookies in Settings.",
    },
    "ip_blocked": {
        VI: "❌ Lỗi: IP của bạn đang tạm thời bị nền tảng này chặn/giới hạn. Vui lòng thử lại sau ít phút hoặc đổi mạng.",
        EN: "❌ Error: Your IP is temporarily blocked or rate-limited by this platform. Please try again in a few minutes or switch networks.",
    },
    "private_account": {
        VI: "❌ Lỗi: Không thể tải video từ tài khoản Private (Kín). ViDrop hiện tại chỉ hỗ trợ tải nội dung Public (Công khai).",
        EN: "❌ Error: Can't download videos from a Private account. ViDrop only supports Public content.",
    },
    "process_failed": {
        VI: "❌ Lỗi: Không thể xử lý liên kết này. Vui lòng kiểm tra lại link hoặc thử lại sau.",
        EN: "❌ Error: Couldn't process this link. Please check the link or try again later.",
    },
    # YouTube failures, told apart so the user knows what to do (the retry
    # button is the single instruction - never "paste the link again").
    "youtube_signin_required": {
        VI: "❌ YouTube đang yêu cầu đăng nhập trước khi cho tải video này. Nếu dùng app Mac, hãy chọn profile Chrome của bạn trong Cài đặt → Đăng nhập YouTube, rồi bấm Thử lại.",
        EN: "❌ YouTube wants you signed in before it allows this download. If you use the Mac app, choose your Chrome profile in Settings → YouTube sign-in, then press Retry.",
    },
    "youtube_restricted": {
        VI: "❌ Không tải được video YouTube này. Video có thể ở chế độ riêng tư, dành cho hội viên, giới hạn độ tuổi hoặc bị chặn ở khu vực của bạn.",
        EN: "❌ Couldn't download this YouTube video. It may be private, members-only, age-limited, or blocked in your region.",
    },
    "youtube_cookies_keychain": {
        VI: "❌ Không đọc được phiên đăng nhập YouTube từ Chrome. Khi macOS hỏi quyền Keychain, hãy chọn \"Luôn cho phép\", rồi bấm Thử lại.",
        EN: "❌ Couldn't read your YouTube sign-in from Chrome. When macOS asks for Keychain access, choose \"Always Allow\", then press Retry.",
    },
    # A platform yt-dlp has no extractor for (e.g. a Threads /share/ link).
    # Two variants: with the platform name when classify recognised it.
    "unsupported_platform": {
        VI: "❌ ViDrop chưa tải được link {platform} dạng này. Hãy thử link video từ nền tảng khác được hỗ trợ.",
        EN: "❌ ViDrop can't download {platform} links like this one yet. Try a video link from another supported site.",
    },
    "unsupported_site": {
        VI: "❌ ViDrop chưa hỗ trợ trang này. Hãy thử link từ YouTube, TikTok, Instagram, Facebook, X, LinkedIn hoặc RedNote.",
        EN: "❌ ViDrop doesn't support this site yet. Try a link from YouTube, TikTok, Instagram, Facebook, X, LinkedIn or RedNote.",
    },
    "page_changed": {
        VI: "❌ Trang này đã đổi cách phát video nên ViDrop chưa đọc được. Hãy thử lại sau hoặc dùng link khác.",
        EN: "❌ This site changed how it plays video, so ViDrop couldn't read it. Try again later or use another link.",
    },
    "load_failed": {
        VI: "❌ Lỗi: Đã xảy ra lỗi khi tải nội dung. Vui lòng thử lại sau.",
        EN: "❌ Error: Something went wrong while loading the content. Please try again later.",
    },
    "ffmpeg_wrong_chip": {
        VI: "❌ Lỗi: Bản ViDrop này không tương thích với chip của máy Mac bạn đang dùng (kiến trúc {machine}). Vui lòng tải đúng bản dành cho máy bạn ({dmg}) tại trang GitHub Releases của ViDrop.",
        EN: "❌ Error: This build of ViDrop isn't compatible with your Mac's chip ({machine} architecture). Please download the right build for your Mac ({dmg}) from ViDrop's GitHub Releases page.",
    },
    "ffmpeg_missing": {
        VI: "❌ Lỗi: Không tìm thấy FFmpeg khả dụng. Vui lòng cài FFmpeg (brew install ffmpeg) hoặc tải lại ViDrop.",
        EN: "❌ Error: No usable FFmpeg was found. Please install FFmpeg (brew install ffmpeg) or re-download ViDrop.",
    },
    "ffmpeg_missing_server_linux": {
        VI: "❌ Lỗi: Không tìm thấy FFmpeg khả dụng trên máy chủ này. Vui lòng cài đặt qua trình quản lý gói của hệ điều hành (vd: apt install ffmpeg) rồi khởi động lại dịch vụ.",
        EN: "❌ Error: No usable FFmpeg was found on this server. Please install it with your OS package manager (e.g. apt install ffmpeg) and restart the service.",
    },
    "ffmpeg_missing_server_other": {
        VI: "❌ Lỗi: Không tìm thấy FFmpeg khả dụng cho kiến trúc CPU của máy chủ này ({machine}). Vui lòng liên hệ quản trị viên để kiểm tra lại triển khai.",
        EN: "❌ Error: No usable FFmpeg was found for this server's CPU architecture ({machine}). Please contact the administrator to check the deployment.",
    },
}


def normalize_language(raw):
    # Accepts "en", "en-US", "vi", "vi-VN", any case; anything else (None, "",
    # "fr") falls back to the default so a bad header can never raise.
    value = str(raw or "").strip().lower()
    if value.startswith(EN):
        return EN
    if value.startswith(VI):
        return VI
    return DEFAULT_LANGUAGE


def request_language():
    # Outside a Flask request (worker threads, plain scripts, tests) this is
    # the default - callers that spawn a thread must capture the language in
    # the route first and pass it in.
    try:
        from flask import has_request_context, request
    except ImportError:
        return DEFAULT_LANGUAGE
    if not has_request_context():
        return DEFAULT_LANGUAGE
    return normalize_language(request.headers.get(LANGUAGE_HEADER))


def text(key, lang=None, **fields):
    template = _CATALOG[key][normalize_language(lang)]
    return template.format(**fields) if fields else template
