export type Language = "en" | "vi";

export interface Translations {
  header: {
    nav: { home: string; settings: string; terms: string };
    home: { title: string; descriptionLine1: string; descriptionLine2: string };
    settings: { title: string };
    terms: { title: string };
  };
  footer: { by: string };
  urlInput: {
    label: string;
    placeholder: string;
    paste: string;
    pasting: string;
    checking: string;
    clearUrl: string;
    removeUrl: string;
    checkFailedRetryHint: string; // appended to a failed check's error message
  };
  checkingStatus: { checkingLink: string; cancel: string; keychainHint: string };
  playlist: {
    heading: string;
    empty: string;
    back: string;
    photo: string;
    video: string;
    selectAll: string;
    downloadSelected: string; // "Download {n} selected"
    truncated: string; // "Showing the first {n} videos only."
    itemProgress: string; // "Downloading item {i} of {n}…"
    batchDone: string; // "Saved {saved} of {total} videos"
    batchProgress: string; // "Downloading… ({done}/{n} done)"
    queued: string; // per-item: waiting
    failed: string; // per-item: errored
    showUnavailable: string; // filter toggle label
    unavailable: string; // per-item: hidden/removed video badge
    downloading: string; // per-row status
    downloaded: string; // per-row status (success)
    retry: string; // per-row action after a failure
    downloadAgain: string; // per-row action after success
    cancel: string; // stop the running batch
    totalItems: string; // "Total Items:"
    downloadAll: string; // header bulk button
    orSelect: string; // "Or you can select items to download"
    download: string; // per-row idle action button
    downloadItemsSelected: string; // bulk button for a manual selection
    percentDownloading: string; // per-row: "{p}% Downloading"
    downloadedProgress: string; // global: "{done}/{total} Downloaded"
    savedItems: string; // global: "Saved: {n} Items"
    failedItems: string; // global: "Failed: {n} Items"
  };
  qualityAction: {
    selectQuality: string;
    startDownload: string;
    downloading: string;
    downloadAgain: string;
  };
  downloadProgress: { cancelDownload: string };
  downloadSuccess: { saved: string; openFolder: string; download: string };
  home: {
    introLines: string[];
    howToHeading: string;
    steps: { label: string; body: string }[];
    featuresHeading: string;
    features: { title: string; desc: string }[];
    faqHeading: string;
    faqs: { q: string; a: string }[];
  };
  downloadStatus: {
    cancelled: string;
    failedFallback: string;
  };
  settingsPage: {
    targetPath: {
      heading: string;
      description: string;
      browse: string;
      rememberPath: string;
    };
    language: {
      heading: string;
      description: string;
      english: string;
      vietnamese: string;
    };
    playlistLimit: {
      heading: string;
      description: string;
      option30: string;
      option50: string;
      option100: string;
      option200: string;
      option500: string;
      optionAll: string;
    };
    exportLogs: {
      heading: string;
      description: string;
      button: string;
      noLogsYet: string;
      opened: string;
    };
    resetSettings: {
      heading: string;
      description: string;
      button: string;
      confirm: string;
      done: string;
    };
  };
  terms: {
    heading: string;
    lastUpdatedLabel: string;
    lastUpdatedValue: string;
    intro: string;
    sections: { heading: string; body: string; list?: string[]; trailing?: string }[];
  };
}

const en: Translations = {
  header: {
    nav: { home: "Home", settings: "Settings", terms: "Terms of Use" },
    home: {
      title: "OmniFlow – All-in-One Video Downloader",
      descriptionLine1: "Download videos and media instantly with OmniFlow.",
      descriptionLine2: "It's fast, free, and fully compatible with all your devices!",
    },
    settings: { title: "Settings" },
    terms: { title: "Terms of Use" },
  },
  footer: { by: "By" },
  urlInput: {
    label: "Insert URL (All in One)",
    placeholder: "Copy and Paste your url",
    paste: "Paste",
    pasting: "Pasting…",
    checking: "Checking",
    clearUrl: "Clear URL",
    removeUrl: "Remove URL",
    checkFailedRetryHint: "Please clear the URL and paste the link again to try once more.",
  },
  checkingStatus: {
    checkingLink: "Checking Link…",
    cancel: "Cancel",
    keychainHint:
      "🔐 macOS may ask for Keychain permission to read your Instagram/Threads login from your browser — this is expected, click \"Always Allow\" so it only happens once.",
  },
  playlist: {
    heading: "Select items to download",
    empty: "This story has no downloadable video content.",
    back: "Back to list",
    photo: "Photo",
    video: "Video",
    selectAll: "Select all",
    downloadSelected: "Download {n} selected",
    truncated: "Large playlist/channel — showing the first {n} videos only.",
    itemProgress: "Downloading item {i} of {n}…",
    batchDone: "Saved {saved} of {total} videos",
    batchProgress: "Downloading… ({done}/{n} done)",
    queued: "Queued",
    failed: "Failed",
    showUnavailable: "Show unavailable videos",
    unavailable: "Unavailable",
    downloading: "Downloading…",
    downloaded: "Downloaded",
    retry: "Retry",
    downloadAgain: "Download again",
    cancel: "Cancel",
    totalItems: "Total Items:",
    downloadAll: "Download All",
    orSelect: "Or you can select items to download",
    download: "Download",
    downloadItemsSelected: "Download Items Selected",
    percentDownloading: "{p}% Downloading",
    downloadedProgress: "{done}/{total} Downloaded",
    savedItems: "Saved: {n} Items",
    failedItems: "Failed: {n} Items",
  },
  qualityAction: {
    selectQuality: "Select Quality:",
    startDownload: "Start Download",
    downloading: "Downloading",
    downloadAgain: "Download Again",
  },
  downloadProgress: { cancelDownload: "Cancel Download" },
  downloadSuccess: { saved: "Saved:", openFolder: "Open Folder", download: "Download" },
  home: {
    introLines: [
      "OmniFlow allows you to easily download videos from YouTube (including entire playlists and channels), TikTok, Instagram, Facebook, RedNote, Threads, X (Twitter), or LinkedIn.",
      "The service is completely free and requires no sign-up or additional software.",
      "It's optimized to work seamlessly across all modern devices, from your computer to your phone.",
      "Built entirely on our self-developed technology without third-party reliance, OmniFlow ensures lightning-fast processing and safe, verified downloads.",
      "By using OmniFlow, you accept our Terms of Use.",
    ],
    howToHeading: "How to download a video:",
    steps: [
      {
        label: "Copy the link:",
        body: "Go to YouTube (playlist, channel, or video), TikTok, Instagram, Facebook, RedNote, Threads, X (Twitter), or LinkedIn and find the content you want. Copy the URL from the app or your browser.",
      },
      {
        label: "Paste & Choose Format:",
        body: 'Paste the URL into the OmniFlow input box above. Choose whether you want MP4 (Video) or MP3 (Audio), and select your preferred quality.',
      },
      {
        label: "Download:",
        body: 'Click the "Convert" button. Once the fast processing is complete, hit "Download" to save the file straight to your device.',
      },
    ],
    featuresHeading: "Why use OmniFlow Video Downloader:",
    features: [
      { title: "100% Free", desc: "No subscriptions, no hidden limits, completely free forever." },
      { title: "No Registration", desc: "Start downloading immediately without sign-up or accounts." },
      { title: "Lightning Fast", desc: "Optimized processing engine for high-speed downloads." },
      { title: "Playlists & Channels", desc: "Download full playlists and channels from YouTube in one click." },
      { title: "High Quality", desc: "Download videos in full HD, 1080p, and high-fidelity audio." },
      { title: "Multi-Platform", desc: "Works seamlessly on macOS, Windows, iOS, and Android." },
    ],
    faqHeading: "Frequently Asked Questions",
    faqs: [
      {
        q: "Where are downloaded files saved?",
        a: "By default, files are saved to your Downloads folder. You can customize the destination path inside the App Settings page.",
      },
      {
        q: "How do I download playlist or channel videos?",
        a: "Just paste the link of a YouTube playlist or channel. OmniFlow will automatically scan it and display a list where you can select and download all items.",
      },
      {
        q: "Does OmniFlow support audio conversion?",
        a: "Yes! You can choose to extract audio (MP3) or keep video (MP4) in various resolutions before clicking download.",
      },
      {
        q: "Is it safe to use OmniFlow?",
        a: "Yes. OmniFlow is fully local, processes everything directly, contains no malware or third-party ads, and requires no registration.",
      },
    ],
  },
  downloadStatus: {
    cancelled: "Download cancelled",
    failedFallback: "Download failed",
  },
  settingsPage: {
    targetPath: {
      heading: "Target Path",
      description: "Here you can configure where the downloaded videos are to be saved.",
      browse: "Browse…",
      rememberPath: "Always save at the last used path.",
    },
    language: {
      heading: "Language",
      description: "Please select a language from the list below. You have to restart OmniFlow in order to apply your selection.",
      english: "English",
      vietnamese: "Vietnamese",
    },
    playlistLimit: {
      heading: "Playlist / Channel Loading Limit",
      description: "Configure the maximum number of videos to load when parsing a playlist or channel (applies to YouTube, Instagram Reels, etc.). Lower values load faster.",
      option30: "30 items (Fastest)",
      option50: "50 items",
      option100: "100 items (Recommended)",
      option200: "200 items",
      option500: "500 items",
      optionAll: "All items (Slowest, could hit rate limits)",
    },
    exportLogs: {
      heading: "Diagnostic Logs",
      description: "If check/download keeps failing with a generic error, open the log folder below and send us the errors.log file — it records the real cause even when the app only shows a friendly message.",
      button: "Open Log Folder",
      noLogsYet: "No errors have been logged on this machine yet.",
      opened: "Log folder opened.",
    },
    resetSettings: {
      heading: "Reset App Data",
      description: "If check/download keeps failing for no clear reason, clearing OmniFlow's saved settings (download path, saved cookies, etc.) and starting fresh can help — this does not delete any of your downloaded files.",
      button: "Clear Cache & Reset Settings",
      confirm: "This will reset your save folder, language, and saved settings back to default. Continue?",
      done: "Settings have been reset.",
    },
  },
  terms: {
    heading: "Terms of Use for OmniFlow",
    lastUpdatedLabel: "Last Updated:",
    lastUpdatedValue: "27-02-2026",
    intro:
      "By accessing or using OmniFlow, you agree to be bound by these Terms of Use. If you do not agree with any part of these terms, please stop using our service immediately.",
    sections: [
      {
        heading: "1. Our Service",
        body: "OmniFlow is a free, general-purpose utility tool designed to help users download video and audio content from third-party platforms, including YouTube (with full support for playlists and channels), TikTok, Instagram, Facebook, RedNote, Threads, X (Twitter), and LinkedIn.",
      },
      {
        heading: "2. Personal & Non-Commercial Use",
        body: "We grant you a limited, non-exclusive right to use OmniFlow strictly for your personal, non-commercial purposes. You agree not to use our service to license, sell, distribute, or commercially exploit any downloaded content.",
      },
      {
        heading: "3. Copyright & User Responsibility",
        body: "OmniFlow acts only as a technical conduit. We do not host, store, or own any of the media content downloaded through our service.",
        list: [
          "Your Responsibility: You are solely responsible for the media you download. You must ensure you have the legal right, explicit permission, or fair-use justification from the rightful copyright owner to download and use the content.",
          "No Infringement: OmniFlow does not encourage, condone, or support the unauthorized downloading or distribution of copyrighted material.",
        ],
      },
      {
        heading: "4. Acceptable Conduct",
        body: "To keep OmniFlow running smoothly for everyone, you agree NOT to:",
        list: [
          "Use any automated scripts, bots, crawlers, or data mining tools on our website.",
          "Take any action that imposes an unreasonable load on our server infrastructure.",
          "Interfere with the security features of the website.",
          "Use the service for any illegal or unlawful purpose.",
        ],
        trailing:
          "We reserve the right to block IP addresses or terminate access for anyone violating these rules, without prior notice.",
      },
      {
        heading: "5. Disclaimer of Warranties",
        body: 'OmniFlow is provided on an "AS-IS" and "AS-AVAILABLE" basis. While we strive for the best experience, we do not guarantee that the service will be entirely error-free, perfectly secure, or uninterrupted, especially since third-party platforms constantly update their systems.',
      },
      {
        heading: "6. Limitation of Liability",
        body: "To the maximum extent permitted by law, OmniFlow and its team shall not be held liable for any direct, indirect, incidental, or consequential damages resulting from your use of the website, including but not limited to data loss, device issues, or legal claims from third parties regarding the content you download.",
      },
      {
        heading: "7. Changes to These Terms",
        body: "We reserve the right to modify these Terms at any time. Your continued use of OmniFlow after any changes indicates your acceptance of the updated terms.",
      },
    ],
  },
};

const vi: Translations = {
  header: {
    nav: { home: "Trang chủ", settings: "Cài đặt", terms: "Điều khoản sử dụng" },
    home: {
      title: "OmniFlow – Tải video từ mọi nền tảng",
      descriptionLine1: "Tải video và media ngay lập tức với OmniFlow.",
      descriptionLine2: "Nhanh, miễn phí và tương thích với mọi thiết bị của bạn!",
    },
    settings: { title: "Cài đặt" },
    terms: { title: "Điều khoản sử dụng" },
  },
  footer: { by: "Bởi" },
  urlInput: {
    label: "Nhập đường dẫn (Tất cả trong một)",
    placeholder: "Sao chép và dán đường dẫn của bạn",
    paste: "Dán",
    pasting: "Đang dán…",
    checking: "Đang kiểm tra",
    clearUrl: "Xoá đường dẫn",
    removeUrl: "Gỡ đường dẫn",
    checkFailedRetryHint: "Vui lòng xoá đường dẫn và dán lại link để thử lại.",
  },
  checkingStatus: {
    checkingLink: "Đang kiểm tra đường dẫn…",
    cancel: "Huỷ",
    keychainHint:
      "🔐 macOS có thể hỏi quyền Keychain để đọc phiên đăng nhập Instagram/Threads từ trình duyệt của bạn — đây là điều bình thường, hãy chọn \"Always Allow\" để chỉ cần cấp quyền một lần.",
  },
  playlist: {
    heading: "Chọn các mục để tải",
    empty: "Story này không có video nào để tải.",
    back: "Quay lại danh sách",
    photo: "Ảnh",
    video: "Video",
    selectAll: "Chọn tất cả",
    downloadSelected: "Tải {n} mục đã chọn",
    truncated: "Playlist/kênh lớn — chỉ hiển thị {n} video đầu tiên.",
    itemProgress: "Đang tải mục {i}/{n}…",
    batchDone: "Đã tải {saved}/{total} video",
    batchProgress: "Đang tải… (xong {done}/{n})",
    queued: "Đang chờ",
    failed: "Lỗi",
    showUnavailable: "Hiện video không khả dụng",
    unavailable: "Không khả dụng",
    downloading: "Đang tải…",
    downloaded: "Đã tải",
    retry: "Thử lại",
    downloadAgain: "Tải lại",
    cancel: "Huỷ",
    totalItems: "Tổng số mục:",
    downloadAll: "Tải tất cả",
    orSelect: "Hoặc bạn có thể chọn từng mục để tải",
    download: "Tải",
    downloadItemsSelected: "Tải các mục đã chọn",
    percentDownloading: "{p}% Đang tải",
    downloadedProgress: "Đã tải {done}/{total}",
    savedItems: "Đã lưu: {n} mục",
    failedItems: "Lỗi: {n} mục",
  },
  qualityAction: {
    selectQuality: "Chọn chất lượng:",
    startDownload: "Bắt đầu tải xuống",
    downloading: "Đang tải xuống",
    downloadAgain: "Tải lại",
  },
  downloadProgress: { cancelDownload: "Huỷ tải xuống" },
  downloadSuccess: { saved: "Đã lưu:", openFolder: "Mở thư mục", download: "Tải xuống" },
  home: {
    introLines: [
      "OmniFlow giúp bạn dễ dàng tải video từ YouTube (bao gồm cả danh sách phát và kênh), TikTok, Instagram, Facebook, RedNote, Threads, X (Twitter) hoặc LinkedIn.",
      "Dịch vụ hoàn toàn miễn phí và không yêu cầu đăng ký hay cài thêm phần mềm nào khác.",
      "Được tối ưu để hoạt động mượt mà trên mọi thiết bị hiện đại, từ máy tính đến điện thoại.",
      "Được xây dựng hoàn toàn trên công nghệ tự phát triển, không phụ thuộc bên thứ ba, OmniFlow đảm bảo xử lý cực nhanh và tải xuống an toàn, đã được xác minh.",
      "Bằng việc sử dụng OmniFlow, bạn đồng ý với Điều khoản sử dụng của chúng tôi.",
    ],
    howToHeading: "Cách tải một video:",
    steps: [
      {
        label: "Sao chép đường dẫn:",
        body: "Vào YouTube (danh sách phát, kênh hoặc video), TikTok, Instagram, Facebook, RedNote, Threads, X (Twitter) hoặc LinkedIn và tìm nội dung bạn muốn. Sao chép đường dẫn từ ứng dụng hoặc trình duyệt.",
      },
      {
        label: "Dán & Chọn định dạng:",
        body: "Dán đường dẫn vào ô nhập của OmniFlow ở trên. Chọn MP4 (Video) hoặc MP3 (Âm thanh), và chọn chất lượng bạn muốn.",
      },
      {
        label: "Tải xuống:",
        body: 'Nhấn nút "Bắt đầu tải xuống". Sau khi xử lý xong, tệp sẽ được lưu thẳng vào thiết bị của bạn.',
      },
    ],
    featuresHeading: "Tại sao nên dùng OmniFlow Downloader:",
    features: [
      { title: "100% Miễn phí", desc: "Không yêu cầu phí dịch vụ, không giới hạn tải xuống, miễn phí trọn đời." },
      { title: "Không cần đăng ký", desc: "Tải ngay lập tức mà không cần tạo tài khoản hay đăng nhập." },
      { title: "Tốc độ cực nhanh", desc: "Công cụ tối ưu hóa xử lý giúp tải video về thiết bị nhanh chóng." },
      { title: "Tải Playlist & Kênh", desc: "Hỗ trợ tải toàn bộ danh sách phát và kênh YouTube chỉ với một click." },
      { title: "Chất lượng cao", desc: "Tải video Full HD, 1080p và trích xuất nhạc chất lượng cao." },
      { title: "Đa nền tảng", desc: "Tương thích mượt mà trên macOS, Windows, iOS và Android." },
    ],
    faqHeading: "Câu hỏi thường gặp (FAQ)",
    faqs: [
      {
        q: "Video sau khi tải xuống được lưu ở đâu?",
        a: "Theo mặc định, tệp sẽ được lưu vào thư mục Downloads của thiết bị. Bạn có thể thay đổi thư mục lưu trong mục Cài đặt của ứng dụng.",
      },
      {
        q: "Làm thế nào để tải toàn bộ danh sách phát hoặc kênh?",
        a: "Bạn chỉ cần dán liên kết danh sách phát hoặc kênh YouTube vào ô nhập liệu. OmniFlow sẽ quét và hiển thị danh sách để bạn chọn tải về hàng loạt.",
      },
      {
        q: "OmniFlow có hỗ trợ chuyển đổi sang MP3 không?",
        a: "Có! Bạn có thể chọn tải về định dạng Âm thanh (MP3) hoặc Video (MP4) với các mức chất lượng khác nhau.",
      },
      {
        q: "Sử dụng OmniFlow có an toàn không?",
        a: "Có. OmniFlow chạy hoàn toàn cục bộ, không chứa quảng cáo bên thứ ba độc hại và không yêu cầu cung cấp thông tin cá nhân.",
      },
    ],
  },
  downloadStatus: {
    cancelled: "Đã huỷ tải xuống",
    failedFallback: "Tải xuống thất bại",
  },
  settingsPage: {
    targetPath: {
      heading: "Thư mục lưu",
      description: "Tại đây bạn có thể cấu hình nơi lưu các video đã tải xuống.",
      browse: "Chọn thư mục…",
      rememberPath: "Luôn lưu vào thư mục đã dùng gần nhất.",
    },
    language: {
      heading: "Ngôn ngữ",
      description: "Vui lòng chọn ngôn ngữ từ danh sách bên dưới. Bạn cần khởi động lại OmniFlow để áp dụng lựa chọn.",
      english: "Tiếng Anh",
      vietnamese: "Tiếng Việt",
    },
    playlistLimit: {
      heading: "Giới hạn tải Playlist / Kênh",
      description: "Cấu hình số lượng video tối đa được tải khi quét playlist hoặc kênh (áp dụng cho YouTube, Instagram Reels, v.v.). Giới hạn nhỏ giúp tải nhanh hơn.",
      option30: "30 video (Nhanh nhất)",
      option50: "50 video",
      option100: "100 video (Khuyên dùng)",
      option200: "200 video",
      option500: "500 video",
      optionAll: "Tất cả video (Chậm nhất, có thể bị giới hạn chặn)",
    },
    exportLogs: {
      heading: "Nhật ký chẩn đoán",
      description: "Nếu việc check/tải liên tục báo lỗi chung chung, hãy mở thư mục log bên dưới và gửi file errors.log cho chúng tôi — file này ghi lại nguyên nhân thật sự ngay cả khi app chỉ hiển thị một thông báo thân thiện.",
      button: "Mở thư mục Log",
      noLogsYet: "Chưa có lỗi nào được ghi lại trên máy này.",
      opened: "Đã mở thư mục log.",
    },
    resetSettings: {
      heading: "Đặt lại dữ liệu ứng dụng",
      description: "Nếu việc check/tải liên tục báo lỗi không rõ nguyên nhân, xóa cấu hình đã lưu của OmniFlow (thư mục lưu, cookies đã lưu, v.v.) và bắt đầu lại từ đầu có thể giúp ích — thao tác này không xóa bất kỳ file đã tải nào của bạn.",
      button: "Xóa Cache & Đặt lại Cài đặt",
      confirm: "Thao tác này sẽ đặt lại thư mục lưu, ngôn ngữ và các cài đặt đã lưu về mặc định. Tiếp tục?",
      done: "Đã đặt lại cài đặt.",
    },
  },
  terms: {
    heading: "Điều khoản sử dụng OmniFlow",
    lastUpdatedLabel: "Cập nhật lần cuối:",
    lastUpdatedValue: "27-02-2026",
    intro:
      "Khi truy cập hoặc sử dụng OmniFlow, bạn đồng ý tuân theo các Điều khoản sử dụng này. Nếu bạn không đồng ý với bất kỳ phần nào trong các điều khoản này, vui lòng ngừng sử dụng dịch vụ của chúng tôi ngay lập tức.",
    sections: [
      {
        heading: "1. Dịch vụ của chúng tôi",
        body: "OmniFlow là một công cụ tiện ích miễn phí, đa năng, được thiết kế để giúp người dùng tải video và âm thanh từ các nền tảng bên thứ ba, bao gồm YouTube (hỗ trợ đầy đủ danh sách phát và kênh), TikTok, Instagram, Facebook, RedNote, Threads, X (Twitter) và LinkedIn.",
      },
      {
        heading: "2. Sử dụng cá nhân & phi thương mại",
        body: "Chúng tôi cấp cho bạn quyền hạn chế, không độc quyền để sử dụng OmniFlow chỉ cho mục đích cá nhân, phi thương mại. Bạn đồng ý không sử dụng dịch vụ của chúng tôi để cấp phép, bán, phân phối hoặc khai thác thương mại bất kỳ nội dung nào đã tải xuống.",
      },
      {
        heading: "3. Bản quyền & Trách nhiệm của người dùng",
        body: "OmniFlow chỉ đóng vai trò là công cụ kỹ thuật trung gian. Chúng tôi không lưu trữ, sở hữu bất kỳ nội dung media nào được tải xuống thông qua dịch vụ của chúng tôi.",
        list: [
          "Trách nhiệm của bạn: Bạn hoàn toàn chịu trách nhiệm về nội dung mình tải xuống. Bạn phải đảm bảo có quyền hợp pháp, được cho phép rõ ràng, hoặc có căn cứ sử dụng hợp lý từ chủ sở hữu bản quyền hợp pháp để tải xuống và sử dụng nội dung đó.",
          "Không vi phạm: OmniFlow không khuyến khích, dung túng hay hỗ trợ việc tải xuống hoặc phân phối trái phép nội dung có bản quyền.",
        ],
      },
      {
        heading: "4. Hành vi được chấp nhận",
        body: "Để OmniFlow vận hành trơn tru cho mọi người, bạn đồng ý KHÔNG:",
        list: [
          "Sử dụng bất kỳ script tự động, bot, crawler hoặc công cụ khai thác dữ liệu nào trên website của chúng tôi.",
          "Thực hiện bất kỳ hành động nào gây tải trọng bất hợp lý lên hạ tầng máy chủ của chúng tôi.",
          "Can thiệp vào các tính năng bảo mật của website.",
          "Sử dụng dịch vụ cho bất kỳ mục đích bất hợp pháp hoặc trái luật nào.",
        ],
        trailing:
          "Chúng tôi có quyền chặn địa chỉ IP hoặc chấm dứt quyền truy cập đối với bất kỳ ai vi phạm các quy tắc này mà không cần báo trước.",
      },
      {
        heading: "5. Từ chối bảo đảm",
        body: 'OmniFlow được cung cấp trên cơ sở "NGUYÊN TRẠNG" và "TUỲ THEO SẴN CÓ". Mặc dù chúng tôi luôn cố gắng mang lại trải nghiệm tốt nhất, chúng tôi không đảm bảo dịch vụ sẽ hoàn toàn không có lỗi, an toàn tuyệt đối hoặc không bị gián đoạn, đặc biệt khi các nền tảng bên thứ ba liên tục thay đổi hệ thống của họ.',
      },
      {
        heading: "6. Giới hạn trách nhiệm pháp lý",
        body: "Trong phạm vi tối đa được pháp luật cho phép, OmniFlow và đội ngũ của chúng tôi sẽ không chịu trách nhiệm cho bất kỳ thiệt hại trực tiếp, gián tiếp, ngẫu nhiên hay hệ quả nào phát sinh từ việc bạn sử dụng website, bao gồm nhưng không giới hạn ở mất dữ liệu, hư hỏng thiết bị, hoặc khiếu nại pháp lý từ bên thứ ba liên quan đến nội dung bạn tải xuống.",
      },
      {
        heading: "7. Thay đổi điều khoản",
        body: "Chúng tôi có quyền chỉnh sửa các Điều khoản này bất kỳ lúc nào. Việc bạn tiếp tục sử dụng OmniFlow sau khi có thay đổi đồng nghĩa với việc bạn chấp nhận các điều khoản đã cập nhật.",
      },
    ],
  },
};

export const translations: Record<Language, Translations> = { en, vi };
