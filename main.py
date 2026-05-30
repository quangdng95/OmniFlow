import os, json, threading, re, time, sys, subprocess, requests, shutil
from tkinter import filedialog
from PIL import Image
from io import BytesIO
import customtkinter as ctk

# 
from ui import OmniFlowUI, COLOR_ORANGE, COLOR_BLUE, COLOR_BTN_HOVER, COLOR_RED, COLOR_TEXT, COLOR_GREEN, COLOR_PURPLE, COLOR_FB, COLOR_REDNOTE

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
                return {"path": data.get("path", default_path), "notify": data.get("notify", True)}
        except: pass
    return {"path": default_path, "notify": True}

def save_session(path_val, notify_val=True):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"path": path_val, "notify": notify_val}, f)

def show_mac_notification(title, message):
    if app.notify_enabled:
        apple_script = f'display notification "{message}" with title "{title}"'
        subprocess.run(['osascript', '-e', apple_script])

def get_platform_info(url):
    url_lower = url.lower()
    if "youtube" in url_lower or "youtu.be" in url_lower: return "YouTube", "#FF0000"
    elif "instagram" in url_lower: return "Instagram", "#E1306C"
    elif "tiktok" in url_lower: return "TikTok", ("#000000", "#ffffff")
    elif "facebook.com" in url_lower or "fb.watch" in url_lower: return "Facebook", COLOR_FB
    elif "xiaohongshu" in url_lower or "xhslink" in url_lower: return "RedNote", COLOR_REDNOTE
    return "Link", COLOR_TEXT

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
    app.label_platform.configure(text="")
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

def get_video_info():
    global stop_event, start_time, current_proc
    link = app.entry_link.get().strip()
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
            info_cmd = [ytdlp_path, '--simulate', '--dump-json', '--no-warnings', '--playlist-items', '1', link]
            
            current_proc = subprocess.Popen(info_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            stdout, stderr = current_proc.communicate()
            
            if stop_event: return

            if current_proc.returncode != 0:
                app.after(0, lambda: [
                    app.label_status_check.configure(text="❌ Invalid Link / Private Video", text_color=COLOR_RED), 
                    app.btn_cancel.pack_forget()
                ])
                return

            data = json.loads(stdout)
            title = data.get('title', 'Video')
            thumb_url = data.get('thumbnail')
            uploader = data.get('uploader', '') 
            
            app.current_title = title 
            
            res_set = set()
            for f in data.get('formats', []):
                h = f.get('height')
                if h and isinstance(h, int) and h >= 360: res_set.add(h)
            
            sorted_res = sorted(list(res_set), reverse=True)
            dynamic_qualities = [f"{h}p" for h in sorted_res]
            if not dynamic_qualities: dynamic_qualities = ["Best"]
            else: dynamic_qualities.append("Best")
            dynamic_qualities.append("Audio Only")
            
            try:
                res = requests.get(thumb_url, timeout=5)
                img = Image.open(BytesIO(res.content))
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(280, 158))
            except: ctk_img = None

            def complete():
                if stop_event: return
                if ctk_img:
                    app.label_thumb.configure(image=ctk_img)
                    app.label_thumb.pack(pady=(20, 10))
                
                p_text, p_color = get_platform_info(link)
                app.label_platform.configure(text=p_text, text_color=p_color)
                app.label_platform.pack(pady=0)
                
                full_title = f"{title}"
                if uploader: full_title += f"\n👤 {uploader}"
                app.label_title.configure(text=full_title)
                app.label_title.pack(pady=5)
                
                app.label_status_check.configure(text="")
                app.btn_cancel.pack_forget()
                
                app.seg_quality.configure(values=dynamic_qualities)
                app.seg_quality.set(dynamic_qualities[0]) 
                
                app.frame_quality.pack(pady=(15, 10))
                app.btn_download.configure(text="START DOWNLOAD")
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
            
            raw_title = getattr(app, 'current_title', 'Video')
            ext = "mp3" if "Audio" in q else "mp4"
            
            final_output_path = get_unique_filename(save_dir, raw_title, ext)
            final_filename = os.path.basename(final_output_path)

            cmd = [
                ytdlp_path, '--ffmpeg-location', ffmpeg_bin, 
                '-o', final_output_path, '--newline', '--no-warnings'
            ]
            
            if "Audio" in q: cmd += ['-x', '--audio-format', 'mp3']
            else: 
                cmd += ['-f', f"bestvideo[height<={h}]+bestaudio/best[height<={h}]/best"]
                cmd += ['-S', 'vcodec:h264,res:' + h]
                cmd += ['--recode-video', 'mp4'] 
                cmd += ['--postprocessor-args', 'ffmpeg:-c:v libx264 -pix_fmt yuv420p -c:a aac -movflags +faststart']

            cmd.append(link)
            current_proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
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
                        app.after(0, lambda v=p/100: app.progress_bar.set(v))
                        app.after(0, lambda t=f"♻️ Downloading '{final_filename}'... ({p}%)": app.label_progress_text.configure(text=t, text_color="gray"))
                    if "Fixing" in output or "Remux" in output or "Convert" in output:
                         app.after(0, lambda: app.label_progress_text.configure(text="🎬 Finalizing for Mac...", text_color="gray"))

            return_code = current_proc.wait()
            
            if stop_event:
                app.after(0, lambda: [
                    app.btn_download.configure(state="normal", text="START DOWNLOAD", fg_color=COLOR_GREEN),
                    app.btn_cancel.pack_forget()
                ])
                return

            if return_code == 0:
                app.after(0, lambda: [
                    app.progress_bar.set(1.0), 
                    app.label_progress_text.configure(text=f"✅ Saved: {final_filename}", text_color=COLOR_GREEN),
                    app.btn_download.configure(state="normal", text="↺ DOWNLOAD AGAIN", fg_color=COLOR_GREEN), 
                    app.btn_open_folder.configure(fg_color=COLOR_PURPLE),
                    app.btn_open_folder.pack(pady=15),
                    app.btn_cancel.pack_forget(),
                    show_mac_notification("OmniFlow Downloader", f"Đã tải xong: {final_filename}")
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
        save_session(new_path, app.notify_enabled)

def toggle_notify():
    app.notify_enabled = app.notify_var.get()
    save_session(app.current_path, app.notify_enabled)

# --- NẠP DỮ LIỆU & GẮN SỰ KIỆN ---
session = load_session()
app.current_path = session.get("path")
app.notify_enabled = session.get("notify", True)
app.path_var.set(app.current_path)
app.notify_var.set(app.notify_enabled)

app.link_var.trace_add("write", on_text_change)
app.bind_all("<Command-v>", paste_link_logic)

app.btn_action.configure(command=handle_input_action)
app.btn_cancel.configure(command=cancel_process)
app.btn_download.configure(command=download_logic)
app.btn_browse.configure(command=browse_target_path)
app.switch_notify.configure(command=toggle_notify)
app.btn_open_folder.configure(command=lambda: subprocess.run(['open', app.current_path]))

if __name__ == "__main__":
    app.mainloop()