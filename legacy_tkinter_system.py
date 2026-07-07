import os, json, threading, re, time, sys, subprocess, requests, shutil
from tkinter import filedialog
from PIL import Image
from io import BytesIO
import customtkinter as ctk

# 
from legacy_tkinter_ui import OmniFlowUI, COLOR_ORANGE, COLOR_BLUE, COLOR_BTN_HOVER, COLOR_RED, COLOR_TEXT, COLOR_GREEN, COLOR_PURPLE, COLOR_FB, COLOR_REDNOTE

os.environ['OBJC_DISABLE_INITIALIZE_FORK_SAFETY'] = 'YES'
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
current_proc = None
stop_event = False

app = OmniFlowUI()

def resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except Exception: base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def load_session():
    default_path = os.path.expanduser("~/Downloads")
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                data = json.load(f)
                return {
                    "path": data.get("path", default_path),
                    "notify": data.get("notify", True),
                    "browser": data.get("browser", "chrome")
                }
        except: pass
    return {"path": default_path, "notify": True, "browser": "chrome"}

def save_session(path_val, notify_val=True, browser_val=None):
    existing_data = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                existing_data = json.load(f)
        except: pass
    existing_data["path"] = path_val
    existing_data["notify"] = notify_val
    if browser_val is not None:
        existing_data["browser"] = browser_val
    elif "browser" not in existing_data:
        existing_data["browser"] = "chrome"
    with open(CONFIG_FILE, "w") as f:
        json.dump(existing_data, f)

def show_mac_notification(title, message):
    if app.notify_enabled:
        apple_script = f'display notification "{message}" with title "{title}"'
        subprocess.run(['osascript', '-e', apple_script])

def normalize_rednote_url(url):
    if not url:
        return url
    if "rednote.com/explore/" in url:
        return url.replace("rednote.com/explore/", "xiaohongshu.com/discovery/item/")
    return url


def get_platform_info(url):
    url = normalize_rednote_url(url)
    url_lower = url.lower()
    if "youtube" in url_lower or "youtu.be" in url_lower: return "youtube", "#FF0000"
    elif "instagram" in url_lower: return "instagram", "#E1306C"
    elif "tiktok" in url_lower: return "tiktok", ("#000000", "#ffffff")
    elif "facebook.com" in url_lower or "fb.watch" in url_lower: return "facebook", COLOR_FB
    elif "xiaohongshu" in url_lower or "xhslink" in url_lower or "rednote" in url_lower: return "rednote", COLOR_REDNOTE
    return "link", COLOR_TEXT

def get_ffmpeg_path():
    local_ffmpeg = resource_path("ffmpeg")
    if os.path.exists(local_ffmpeg) and os.access(local_ffmpeg, os.X_OK): return local_ffmpeg
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg: return system_ffmpeg
    return None

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_unique_filename(directory, filename, extension):
    base_name = sanitize_filename(filename)
    full_path = os.path.join(directory, f"{base_name}.{extension}")
    counter = 1
    while os.path.exists(full_path):
        full_path = os.path.join(directory, f"{base_name} ({counter}).{extension}")
        counter += 1
    return full_path

def on_text_change(*args):
    content = app.link_var.get().strip()
    if content:
        app.btn_action.configure(text="CHECK", fg_color=COLOR_ORANGE, hover_color="#d35400")
        if "AGAIN" in app.btn_download.cget("text"):
             app.btn_download.pack_forget()
             app.frame_quality.pack_forget()
             app.btn_open_folder.pack_forget()
             app.label_progress_text.configure(text="")
    else:
        app.btn_action.configure(text="PASTE", fg_color=COLOR_BLUE, hover_color=COLOR_BTN_HOVER)

def handle_input_action():
    state = app.btn_action.cget("text")
    if "PASTE" in state: paste_link_logic()
    elif "CHECK" in state: 
        reset_ui_for_new_check()
        get_video_info()

def cancel_process():
    global current_proc, stop_event
    stop_event = True
    if current_proc:
        try: current_proc.terminate()
        except: pass
    app.label_status_check.configure(text="⛔ Đã hủy!", text_color=COLOR_RED)
    app.btn_cancel.pack_forget()

def reset_ui_for_new_check():
    app.frame_quality.pack_forget()
    app.btn_download.pack_forget()
    app.progress_bar.pack_forget()
    app.label_progress_text.pack_forget()
    app.btn_open_folder.pack_forget()
    app.label_thumb.configure(image=None, text="")
    app.tag_icon_label.configure(image=None, text="")
    app.label_title.configure(text="")

def paste_link_logic(event=None):
    app.tabview.set("Downloader")
    global stop_event
    text = ""
    try: text = app.clipboard_get().strip()
    except:
        try: text = subprocess.check_output('pbpaste', shell=True).decode('utf-8').strip() 
        except: pass
    if not text: return 

    stop_event = True 
    if current_proc:
        try: current_proc.terminate()
        except: pass
    
    app.entry_link.delete(0, ctk.END)
    app.entry_link.insert(0, text)
    reset_ui_for_new_check()
    get_video_info()

from urllib.parse import urlparse, parse_qs

def normalize_youtube_url(raw_url):
    """
    Làm sạch URL YouTube. 
    Trả về Tuple: (Cleaned_URL, is_playlist, is_mix)
    """
    if "youtube.com" not in raw_url.lower() and "youtu.be" not in raw_url.lower():
        return raw_url, False, False

    parsed = urlparse(raw_url)
    query = parse_qs(parsed.query)

    if 'list' in query:
        list_id = query['list'][0]
        if list_id.startswith('RD'):
            # YouTube Mix/Radio: Giữ nguyên url gốc, đánh dấu là mix
            return raw_url, True, True
        else:
            # Playlist chuẩn: ÉP GHI ĐÈ URL THÀNH DẠNG PLAYLIST THUẦN
            # Xóa sạch tham số 'watch?v='
            clean_url = f"https://www.youtube.com/playlist?list={list_id}"
            return clean_url, True, False
    
    # Nếu không có tham số list, nó là single video
    return raw_url, False, False

def get_video_info():
    global stop_event, start_time, current_proc
    link = app.entry_link.get().strip()
    link = normalize_rednote_url(link)
    if not link: return
    
    stop_event = False
    start_time = time.time()
    
    app.label_status_check.configure(text="Checking link... (0s)", text_color=("#f39c12", "#f1c40f"))
    app.btn_cancel.pack(pady=5)
    
    def update_timer():
        if not stop_event and "Checking" in app.label_status_check.cget("text"):
            elapsed = int(time.time() - start_time)
            app.label_status_check.configure(text=f"Checking link... ({elapsed}s)")
            app.after(1000, update_timer)
    update_timer()
    
    def fetch():
        global current_proc
        try:
            ytdlp_path = resource_path("yt-dlp")
            
            # Setup info_cmd and playlist_flags dynamically to handle regular playlists vs YouTube Mixes
            info_cmd = [ytdlp_path, '--simulate', '--dump-json', '--no-warnings']
            playlist_flags = []
            
            # 1. CHUẨN HÓA VÀ GHI ĐÈ BIẾN URL NGAY TỪ ĐẦU
            url = link
            url, is_yt_playlist, is_yt_mix = normalize_youtube_url(url)
            link = url
            
            # 2. CẤU HÌNH CỜ (FLAGS) CHO YT-DLP THEO KẾT QUẢ
            if is_yt_playlist:
                info_cmd.extend(['--yes-playlist', '--flat-playlist'])
                playlist_flags = ['--yes-playlist', '--flat-playlist']
                if is_yt_mix:
                    # Nếu là Mix (RD) thì chèn cờ giới hạn
                    info_cmd.extend(['--playlist-end', '50'])
                    playlist_flags.extend(['--playlist-end', '50'])
            else:
                info_cmd.append('--no-playlist')
                playlist_flags = ['--no-playlist']
                
            # 3. Kế tiếp mới truyền `link` (đã được làm sạch) vào lệnh gọi yt-dlp
            info_cmd.append(link)
            current_proc = subprocess.Popen(info_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = current_proc.communicate()
            
            if stop_event: return

            success = (current_proc.returncode == 0)
            err_msg = stderr.lower()
            
            # 2. Nếu thất bại, kiểm tra xem có phải do yêu cầu đăng nhập/cookies không
            is_login_err = ("login" in err_msg or "confirm your identity" in err_msg or 
                            "cookie" in err_msg or "empty media response" in err_msg or 
                            "requires logged-in session" in err_msg or "sign in" in err_msg)
            
            if not success and is_login_err:
                # A. Thử tự động lấy cookies từ các trình duyệt phổ biến
                session = load_session()
                pref_browser = session.get("browser", "chrome")
                
                browsers_to_try = []
                if pref_browser:
                    browsers_to_try.append(pref_browser)
                
                all_browsers = [
                    "chrome", "chrome:Default", "chrome:Profile 1", "chrome:Profile 2",
                    "chrome:Profile 3", "chrome:Profile 4", "chrome:Profile 5",
                    "safari", "edge", "brave", "firefox"
                ]
                for b in all_browsers:
                    if b not in browsers_to_try:
                        browsers_to_try.append(b)
                
                for browser in browsers_to_try:
                    if stop_event: return
                    app.after(0, lambda b=browser: app.label_status_check.configure(
                        text=f"Trying cookies from {b.capitalize()}...", 
                        text_color=("#f39c12", "#f1c40f")
                    ))
                    
                    info_cmd = [
                        ytdlp_path, '--simulate', '--dump-json', '--no-warnings'
                    ] + playlist_flags + ['--cookies-from-browser', browser, link]
                    current_proc = subprocess.Popen(info_cmd, stdout=subprocess.PIPE, stderr=stderr, text=True)
                    stdout, stderr = current_proc.communicate()
                    
                    if current_proc.returncode == 0:
                        success = True
                        app.working_browser = browser
                        app.use_manual_cookies = False
                        save_session(app.current_path, app.notify_enabled, browser, session.get("cookies_path", ""))
                        break
                    else:
                        err_msg = stderr.lower()
                
                # B. Kế hoạch B: Nếu tự động thất bại, thử dùng cookies.txt thủ công
                if not success:
                    cookies_path = session.get("cookies_path", "")
                    if cookies_path and os.path.isfile(cookies_path):
                        app.after(0, lambda: app.label_status_check.configure(
                            text="Trying manual cookies.txt...", 
                            text_color=("#f39c12", "#f1c40f")
                        ))
                        info_cmd = [
                            ytdlp_path, '--simulate', '--dump-json', '--no-warnings'
                        ] + playlist_flags + ['--cookiefile', cookies_path, link]
                        current_proc = subprocess.Popen(info_cmd, stdout=subprocess.PIPE, stderr=stderr, text=True)
                        stdout, stderr = current_proc.communicate()
                        
                        if current_proc.returncode == 0:
                            success = True
                            app.working_browser = None
                            app.use_manual_cookies = True
                        else:
                            err_msg = stderr.lower()

            if stop_event: return

            if not success:
                is_login_err = ("login" in err_msg or "confirm your identity" in err_msg or 
                                "cookie" in err_msg or "empty media response" in err_msg or 
                                "requires logged-in session" in err_msg or "sign in" in err_msg)
                
                is_major_platform = any(p in link.lower() for p in ("instagram", "tiktok", "facebook", "fb.watch", "fb.com"))
                if is_major_platform and is_login_err:
                    app.after(0, lambda: [
                        app.label_status_check.configure(
                            text="❌ Lỗi: Không thể tải video từ tài khoản Private (Kín).\nOmniFlow hiện tại chỉ hỗ trợ tải nội dung Public (Công khai).", 
                            text_color=COLOR_RED
                        ), 
                        app.btn_cancel.pack_forget()
                    ])
                else:
                    app.after(0, lambda: [
                        app.label_status_check.configure(text="❌ Invalid Link / Private Video", text_color=COLOR_RED), 
                        app.btn_cancel.pack_forget()
                    ])
                return

            # 1. Parse JSON data from stdout (supports both multi-line JSON or single playlist JSON)
            entries = []
            primary_data = None
            
            try:
                lines = [ln.strip() for ln in stdout.strip().splitlines() if ln.strip()]
                if len(lines) > 1:
                    for idx, line in enumerate(lines):
                        try:
                            entry_data = json.loads(line)
                            entry_data['original_index'] = idx + 1
                            entries.append(entry_data)
                        except Exception:
                            pass
                    if entries:
                        primary_data = entries[0]
                elif len(lines) == 1:
                    primary_data = json.loads(lines[0])
                    if primary_data.get("_type") == "playlist" or "entries" in primary_data:
                        raw_entries = primary_data.get("entries") or []
                        for idx, entry_data in enumerate(raw_entries):
                            entry_data['original_index'] = idx + 1
                            entries.append(entry_data)
            except Exception as e:
                print(f"[debug] JSON parsing failed: {e}", flush=True)
                
            if not primary_data:
                app.after(0, lambda: [
                    app.label_status_check.configure(text="❌ System Error (Invalid JSON)", text_color=COLOR_RED), 
                    app.btn_cancel.pack_forget()
                ])
                return

            success_data = primary_data
            is_playlist = False
            if success_data and (success_data.get("_type") == "playlist" or "entries" in success_data):
                is_playlist = True
                if not entries and "entries" in success_data:
                    raw_entries = success_data.get("entries") or []
                    for idx, entry_data in enumerate(raw_entries):
                        entry_data['original_index'] = idx + 1
                        entries.append(entry_data)
            elif len(lines) > 1 and entries:
                is_playlist = True

            # Filter out [Private video] or [Deleted video]
            if is_playlist and entries:
                filtered_entries = []
                for entry in entries:
                    entry_title = entry.get("title") or ""
                    if "[private video]" in entry_title.lower() or "[deleted video]" in entry_title.lower():
                        continue
                    filtered_entries.append(entry)
                entries = filtered_entries

            title = success_data.get('title', 'Video')
            thumb_url = success_data.get('thumbnail')
            uploader = success_data.get('uploader', '') 
            app.current_title = title 
            
            res_set = set()
            formats_source = success_data
            if is_playlist and entries:
                for entry in entries:
                    if entry.get("formats"):
                        formats_source = entry
                        break
            
            for f in formats_source.get('formats', []):
                h = f.get('height')
                if h and isinstance(h, int) and h >= 360: res_set.add(h)
            
            sorted_res = sorted(list(res_set), reverse=True)
            dynamic_qualities = [f"{h}p" for h in sorted_res]
            if not dynamic_qualities: dynamic_qualities = ["Best"]
            else: dynamic_qualities.append("Best")
            dynamic_qualities.append("Audio Only")
            
            try:
                headers = {}
                if thumb_url and any(k in thumb_url.lower() for k in ("xiaohongshu", "xhslink", "rednote", "sns-img")):
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                        "Referer": "https://www.xiaohongshu.com/",
                    }
                res = requests.get(thumb_url, headers=headers, timeout=5)
                img = Image.open(BytesIO(res.content))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(280, 158))
            except: ctk_img = None

            def complete():
                if stop_event: return
                if ctk_img:
                    app.label_thumb.configure(image=ctk_img)
                    app.label_thumb.pack(pady=(20, 10))
                
                p_text, p_color = get_platform_info(link)
                tag_img = app.tags.get(p_text)
                if tag_img:
                    app.tag_icon_label.configure(image=tag_img, text="")
                else:
                    app.tag_icon_label.configure(image=None, text=p_text.capitalize(), text_color=p_color)
                app.tag_icon_label.pack(anchor="nw", pady=(0, 4))
                
                full_title = f"{title}"
                if uploader: full_title += f"\n👤 {uploader}"
                app.label_title.configure(text=full_title)
                app.label_title.pack(pady=5)
                
                app.label_status_check.configure(text="")
                app.btn_cancel.pack_forget()
                
                # Reset playlist frame and ensure it is hidden
                for child in app.playlist_items_container.winfo_children():
                    child.destroy()
                app.section_playlist.pack_forget()
                app.item_vars = []
                app.current_playlist_items = []

                def update_download_button_text():
                    if not getattr(app, "item_vars", []):
                        app.btn_download.configure(state="normal", text="START DOWNLOAD", fg_color=COLOR_PRIMARY)
                        return
                    checked_count = sum(var.get() for var in app.item_vars)
                    if checked_count == len(app.item_vars):
                        app.btn_download.configure(
                            state="normal", 
                            text="DOWNLOAD ALL",
                            fg_color=COLOR_PRIMARY
                        )
                    elif checked_count > 0:
                        app.btn_download.configure(
                            state="normal", 
                            text=f"DOWNLOAD ({checked_count} {'items' if checked_count > 1 else 'item'})",
                            fg_color=COLOR_PRIMARY
                        )
                    else:
                        app.btn_download.configure(
                            state="disabled",
                            text="NO ITEMS SELECTED",
                            fg_color=COLOR_DISABLED
                        )

                def on_item_toggle():
                    all_checked = all(var.get() for var in app.item_vars)
                    if all_checked:
                        app.chk_select_all.select()
                    else:
                        app.chk_select_all.deselect()
                    update_download_button_text()

                def on_select_all():
                    val = app.select_all_var.get()
                    for var in app.item_vars:
                        var.set(val)
                    update_download_button_text()

                if is_playlist and entries:
                    # Hide the single-video quality selector box for playlists
                    try: app.q_frame.pack_forget()
                    except: pass
                    
                    app.section_playlist.pack(fill="x", pady=SPACE_BETWEEN_BOXES)
                    app.chk_select_all.select()
                    app.chk_select_all.configure(command=on_select_all)
                    
                    for idx, entry in enumerate(entries):
                        entry_id = entry.get("id")
                        entry_url = entry.get("url") or entry.get("webpage_url")
                        if not entry_url and entry_id:
                            entry_url = f"https://www.youtube.com/watch?v={entry_id}"
                        if not entry_url:
                            entry_url = link
                        
                        entry_title = entry.get("title") or f"Item {idx + 1}"
                        
                        is_video = True
                        if entry.get("formats") is not None or (entry_url and "youtube.com" in entry_url.lower()):
                            is_video = True
                        else:
                            is_video = bool(entry.get("formats"))
                        kind = "video" if is_video else "image"
                        
                        duration_val = entry.get("duration")
                        duration_str = ""
                        if duration_val is not None:
                            try:
                                duration_seconds = int(float(duration_val))
                                m, s = divmod(duration_seconds, 60)
                                duration_str = f" ({m:02d}:{s:02d})"
                            except Exception:
                                pass
                        
                        orig_idx = entry.get('original_index', idx + 1)
                        
                        app.current_playlist_items.append({
                            "url": entry_url,
                            "title": entry_title,
                            "kind": kind,
                            "index": orig_idx
                        })
                        
                        var = ctk.BooleanVar(value=True)
                        app.item_vars.append(var)
                        
                        row = ctk.CTkFrame(app.playlist_items_container, fg_color="transparent")
                        row.pack(fill="x", pady=4)
                        
                        chk = ctk.CTkCheckBox(
                            row, text="", variable=var, width=24, height=24,
                            fg_color=COLOR_PRIMARY, command=on_item_toggle
                        )
                        chk.pack(side="left", padx=(8, 12))
                        
                        info_frame = ctk.CTkFrame(row, fg_color="transparent")
                        info_frame.pack(side="left", fill="both", expand=True)
                        
                        # Prepend index sequence number
                        display_title = f"{idx + 1}. {entry_title}{duration_str}"
                        lbl_title = ctk.CTkLabel(
                            info_frame, text=display_title, font=("Inter", 13),
                            text_color=COLOR_TEXT_MAIN, anchor="w", justify="left"
                        )
                        lbl_title.pack(anchor="w")
                        
                        tag_text = "Photo" if kind == "image" else "Video"
                        tag_color = "#3B82F6" if kind == "image" else "#10B981"
                        lbl_tag = ctk.CTkLabel(
                            info_frame, text=tag_text, font=("Inter", 10, "bold"),
                            text_color=tag_color, fg_color="transparent"
                        )
                        lbl_tag.pack(anchor="w", pady=(2, 0))
                    
                    update_download_button_text()
                else:
                    # Show the single-video quality selector box back
                    try: app.q_frame.pack(fill="x", padx=16, pady=(16, 8))
                    except: pass
                    
                    # Setup Single Video Item
                    app.current_playlist_items = [{
                        "url": link,
                        "title": title,
                        "kind": "video",
                        "index": None
                    }]
                    update_download_button_text()

                app.frame_quality.pack(pady=(15, 10))
                app.btn_download.pack(pady=(0, 20))
                
            app.after(0, complete)
        except Exception as e:
            if not stop_event:
                app.after(0, lambda: [
                    app.label_status_check.configure(text="❌ System Error", text_color=COLOR_RED), 
                    app.btn_cancel.pack_forget()
                ])

    threading.Thread(target=fetch, daemon=True).start()

def download_logic():
    global current_proc, stop_event
    link = app.entry_link.get()
    link = normalize_rednote_url(link)
    link, is_playlist, is_mix = normalize_youtube_url(link)
    save_dir = app.current_path
    
    if not os.access(save_dir, os.W_OK):
        app.label_progress_text.configure(text="❌ Permission Denied (Folder)", text_color=COLOR_RED)
        app.label_progress_text.pack(pady=5)
        return

    ffmpeg_bin = get_ffmpeg_path()
    if not ffmpeg_bin:
        app.label_progress_text.configure(text="❌ FFmpeg missing! Run 'brew install ffmpeg'", text_color=COLOR_RED)
        app.label_progress_text.pack(pady=5)
        return

    app.progress_bar.pack(pady=(20, 5))
    app.progress_bar.set(0)
    app.label_progress_text.pack(pady=5)
    
    app.btn_download.configure(state="disabled", text="DOWNLOADING...", fg_color="gray")
    app.btn_cancel.configure(text="CANCEL DOWNLOAD", command=lambda: [cancel_process(), app.label_progress_text.configure(text="⛔ Cancelled")])
    app.btn_cancel.pack(pady=5)

    def run():
        global current_proc
        try:
            ytdlp_path = resource_path("yt-dlp")
            q = app.seg_quality.get()
            h = q.replace("p", "").replace("Best", "2160")
            
            ext = "mp3" if "Audio" in q else "mp4"
            
            session = load_session()
            use_manual = getattr(app, "use_manual_cookies", False)
            browser = getattr(app, "working_browser", session.get("browser", "chrome"))
            cookies_path = session.get("cookies_path", "")

            # Get checked items
            checked_items = []
            if getattr(app, "item_vars", []):
                for idx, var in enumerate(app.item_vars):
                    if var.get():
                        checked_items.append(app.current_playlist_items[idx])
            else:
                checked_items = getattr(app, "current_playlist_items", [])

            if not checked_items:
                app.after(0, lambda: app.label_progress_text.configure(text="❌ No items selected!", text_color=COLOR_RED))
                app.after(0, lambda: app.btn_download.configure(state="normal", text="START DOWNLOAD", fg_color=COLOR_PRIMARY))
                return

            total_items = len(checked_items)
            last_filename = ""
            return_code = 0
            
            for current_idx, item in enumerate(checked_items, start=1):
                if stop_event:
                    break
                    
                item_title = item.get("title") or f"Item {current_idx}"
                item_output_path = get_unique_filename(save_dir, item_title, ext)
                item_filename = os.path.basename(item_output_path)
                last_filename = item_filename

                item_url = item.get("url") or link
                cmd = [
                    ytdlp_path, '--ffmpeg-location', ffmpeg_bin, 
                    '-o', item_output_path, '--newline', '--no-warnings'
                ]
                
                # Add specific item index from playlist if available
                if item_url == link and item.get("index") is not None:
                    cmd += ['--playlist-items', str(item["index"])]
                else:
                    # If downloading a specific direct video URL or outside playlist, force no-playlist
                    cmd += ['--no-playlist']
                
                if use_manual and cookies_path and os.path.isfile(cookies_path):
                    cmd += ['--cookiefile', cookies_path]
                elif browser:
                    cmd += ['--cookies-from-browser', browser]
                
                if "Audio" in q: 
                    cmd += ['-x', '--audio-format', 'mp3']
                else: 
                    cmd += ['-f', f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"]
                    cmd += ['-S', 'vcodec:h264,res:' + h]
                    cmd += ['--recode-video', 'mp4'] 
                    cmd += ['--postprocessor-args', 'ffmpeg:-c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart']

                current_proc = subprocess.Popen(cmd + [item_url], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                
                while True:
                    if stop_event: 
                        current_proc.terminate()
                        break
                    output = current_proc.stdout.readline()
                    if output == '' and current_proc.poll() is not None: break
                    if output:
                        match = re.search(r'(\d+(\.\d+)?)%', output)
                        if match: 
                            p = float(match.group(1))
                            overall_p = ((current_idx - 1) + (p / 100)) / total_items
                            app.after(0, lambda v=overall_p: app.progress_bar.set(v))
                            app.after(0, lambda t=f"♻️ Downloading ({current_idx}/{total_items}) - {p}%: '{item_filename}'": app.label_progress_text.configure(text=t, text_color="gray"))
                        if "Fixing" in output or "Remux" in output or "Convert" in output:
                             app.after(0, lambda: app.label_progress_text.configure(text=f"🎬 Finalizing ({current_idx}/{total_items}) for Mac...", text_color="gray"))

                if stop_event:
                    break
                    
                return_code = current_proc.wait()
                if return_code != 0:
                    break

            if stop_event:
                app.after(0, lambda: [
                    app.btn_download.configure(state="normal", text="START DOWNLOAD", fg_color=COLOR_PRIMARY),
                    app.btn_cancel.pack_forget()
                ])
                return

            if return_code == 0:
                final_filename = last_filename
                if total_items > 1:
                    success_msg = f"✅ Saved {total_items} items successfully"
                    notify_msg = f"Đã tải xong {total_items} video/audio!"
                else:
                    success_msg = f"✅ Saved: {final_filename}"
                    notify_msg = f"Đã tải xong: {final_filename}"

                app.after(0, lambda: [
                    app.progress_bar.set(1.0), 
                    app.label_progress_text.configure(text=success_msg, text_color=COLOR_GREEN),
                    app.btn_download.configure(state="normal", text="↺ DOWNLOAD AGAIN", fg_color=COLOR_PRIMARY), 
                    app.btn_open_folder.configure(fg_color=COLOR_PURPLE),
                    app.btn_open_folder.pack(pady=15),
                    app.btn_cancel.pack_forget(),
                    show_mac_notification("OmniFlow Downloader", notify_msg)
                ])
            else:
                stderr_output = ""
                try:
                    stderr_output = current_proc.stderr.read().lower()
                except:
                    pass
                
                is_login_err = ("login" in stderr_output or "confirm your identity" in stderr_output or 
                                "cookie" in stderr_output or "empty media response" in stderr_output or 
                                "requires logged-in session" in stderr_output or "sign in" in stderr_output)
                
                is_major_platform = any(p in link.lower() for p in ("instagram", "tiktok", "facebook", "fb.watch", "fb.com"))
                if is_major_platform and is_login_err:
                    app.after(0, lambda: [
                        app.label_progress_text.configure(
                            text="❌ Lỗi: Không thể tải video từ tài khoản Private (Kín).\nOmniFlow hiện tại chỉ hỗ trợ tải nội dung Public (Công khai).",
                            text_color=COLOR_RED
                        ),
                        app.btn_download.configure(state="normal", text="RETRY", fg_color=COLOR_RED),
                        app.btn_cancel.pack_forget(),
                        show_mac_notification("OmniFlow Error", "Tài khoản Private không hỗ trợ!")
                    ])
                else:
                    app.after(0, lambda: [
                        app.label_progress_text.configure(text="❌ Error! Check Terminal.", text_color=COLOR_RED),
                        app.btn_download.configure(state="normal", text="RETRY", fg_color=COLOR_RED),
                        app.btn_cancel.pack_forget(),
                        show_mac_notification("OmniFlow Error", "Tải thất bại, hãy thử lại nghen!")
                    ])
        except Exception as e:
            app.after(0, lambda: app.btn_download.configure(state="normal", text="START DOWNLOAD"))

    threading.Thread(target=run, daemon=True).start()

def browse_target_path():
    new_path = filedialog.askdirectory()
    if new_path:
        app.current_path = new_path
        app.path_var.set(new_path)
        save_session(new_path, app.notify_enabled, app.browser_var.get(), app.cookies_var.get())

def browse_cookies_path():
    file_path = filedialog.askopenfilename(filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")])
    if file_path:
        app.cookies_var.set(file_path)
        save_session(app.current_path, app.notify_enabled, app.browser_var.get(), file_path)

def on_browser_change(*args):
    save_session(app.current_path, app.notify_enabled, app.browser_var.get(), app.cookies_var.get())

def toggle_notify():
    app.notify_enabled = app.notify_var.get()
    save_session(app.current_path, app.notify_enabled, app.browser_var.get(), app.cookies_var.get())

# --- NẠP DỮ LIỆU & GẮN SỰ KIỆN ---
session = load_session()
app.current_path = session.get("path")
app.notify_enabled = session.get("notify", True)
app.working_browser = session.get("browser", "chrome")

app.path_var.set(app.current_path)
app.notify_var.set(app.notify_enabled)
app.cookies_var.set(session.get("cookies_path", ""))
app.browser_var.set(app.working_browser)

app.link_var.trace_add("write", on_text_change)
app.browser_var.trace_add("write", on_browser_change)
app.bind_all("<Command-v>", paste_link_logic)

app.btn_action.configure(command=handle_input_action)
app.btn_cancel.configure(command=cancel_process)
app.btn_download.configure(command=download_logic)
app.btn_browse.configure(command=browse_target_path)
app.btn_browse_cookies.configure(command=browse_cookies_path)
app.switch_notify.configure(command=toggle_notify)
app.btn_open_folder.configure(command=lambda: subprocess.run(['open', app.current_path]))

if __name__ == "__main__":
    app.mainloop()