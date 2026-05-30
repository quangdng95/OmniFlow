import customtkinter as ctk
from PIL import Image
import os, requests, platform
from io import BytesIO
import threading

ctk.set_appearance_mode("Light")

COLOR_BG_DARK = "#12372A"       
COLOR_TEXT_GREEN = "#ADBC9F"    
COLOR_BG_LIGHT = "#F9FAFB"      
COLOR_TEXT_MAIN = "#1F2937"     
COLOR_PRIMARY = "#0E8388"       
COLOR_BORDER = "#E5E7EB"        
COLOR_GREEN = "#059669"
COLOR_RED = "#FF4B4B"
COLOR_RED_LIGHT = "#FEE2E2"     
COLOR_DISABLED = "#E5E7EB"
COLOR_TEXT_DISABLED = "#9CA3AF"

class OmniFlowUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("OmniFlow")
        self.geometry("680x760")
        self.configure(fg_color=COLOR_BG_LIGHT)
        
        self.link_var = ctk.StringVar()
        self.icons = {}
        self.tags = {}
        self.logo_img = None
        self._last_width = 0 
        
        self.load_assets()
        self.init_ui()
        
        self.bind("<Configure>", self.update_wraplength)

    def load_assets(self):
        self.base_path = os.path.dirname(__file__)
        icon_dir = os.path.join(self.base_path, "Assets", "Icons")
        
        icon_names = ["paste", "folder", "cancel", "download", "clear", "DownloadAgain", "OpenFolder", "Cancel", "CancelDownload", "Downloading"]
        for ico in icon_names:
            p = os.path.join(icon_dir, f"{ico}.svg") 
            if os.path.exists(p):
                try:
                    import cairosvg
                    # Scale=4.0 để ép icon nét gấp 4 lần cho màn Retina
                    png_data = cairosvg.svg2png(url=p, scale=4.0)
                    img = Image.open(BytesIO(png_data)).convert("RGBA")
                    self.icons[ico] = ctk.CTkImage(light_image=img, dark_image=img, size=(20, 20))
                except Exception: pass
            elif ico == "clear" and "Cancel" in self.icons:
                self.icons["clear"] = self.icons["Cancel"] 
                
        tag_dirs = [
            os.path.join(self.base_path, "Assets", "Tag PNG"),
            os.path.join(self.base_path, "Assets", "Tags"),
            os.path.join(self.base_path, "assets", "tags")
        ]
        tag_dir = next((d for d in tag_dirs if os.path.exists(d)), None)
        
        if tag_dir:
            for file in os.listdir(tag_dir):
                if file.endswith(".svg"): 
                    name = file.split(".")[0].lower()
                    p = os.path.join(tag_dir, file)
                    try:
                        import cairosvg
                        # Scale=4.0 để tag SVG lên hình nét căng đét
                        png_data = cairosvg.svg2png(url=p, scale=4.0)
                        img = Image.open(BytesIO(png_data)).convert("RGBA")
                        w, h = img.size
                        self.tags[name] = ctk.CTkImage(light_image=img, dark_image=img, size=(int(w*(22/h)), 22))
                    except Exception: pass

        logo_path_1 = os.path.join(self.base_path, "Assets", "Logo", "logo.svg")
        logo_path_2 = os.path.join(self.base_path, "assets", "logo", "logo.svg")
        
        logo_file = None
        if os.path.exists(logo_path_1): logo_file = logo_path_1
        elif os.path.exists(logo_path_2): logo_file = logo_path_2
        
        if logo_file:
            try:
                import cairosvg
                png_data = cairosvg.svg2png(url=logo_file, scale=4.0)
                img = Image.open(BytesIO(png_data)).convert("RGBA")
                w, h = img.size
                target_h = 56
                target_w = int(w * (target_h / h))
                self.logo_img = ctk.CTkImage(light_image=img, dark_image=img, size=(target_w, target_h))
            except Exception: pass

    def init_ui(self):
        self.scroll_container = ctk.CTkScrollableFrame(
            self, fg_color=COLOR_BG_LIGHT, corner_radius=0,
            scrollbar_fg_color=COLOR_BG_LIGHT, scrollbar_button_color="#D1D5DB", scrollbar_button_hover_color="#9CA3AF"     
        )
        self.scroll_container.pack(fill="both", expand=True)

        PAD_X = (24, 8) 
        BOX_KWARGS = {"fg_color": "white", "corner_radius": 16, "border_width": 1, "border_color": COLOR_BORDER}
        SPACE_BETWEEN_BOXES = (0, 16) 

        # ==========================================
        # HEADER
        # ==========================================
        self.header_frame = ctk.CTkFrame(self.scroll_container, fg_color=COLOR_BG_DARK, corner_radius=0)
        self.header_frame.pack(fill="x")
        
        self.nav_container = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.nav_container.pack(pady=(32, 12), padx=32, anchor="w")
        for name in ["Home", "Settings", "Terms of Use"]:
            ctk.CTkButton(self.nav_container, text=name, font=("Inter", 14), text_color="white", fg_color="transparent", hover=False, width=1).pack(side="left", padx=(0, 24))

        ctk.CTkFrame(self.header_frame, fg_color="#1E3F35", height=1).pack(fill="x", padx=32, pady=0)
        
        self.brand_container = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.brand_container.pack(fill="x", padx=32, pady=(24, 16))
        
        if self.logo_img:
            self.logo_label = ctk.CTkLabel(self.brand_container, text="", image=self.logo_img)
            self.logo_label.pack(side="left")

        ctk.CTkLabel(self.header_frame, text="OmniFlow – All-in-One Video Downloader", font=("Inter", 26, "bold"), text_color="white", anchor="w", justify="left").pack(fill="x", padx=32, pady=(0, 8))
        ctk.CTkLabel(self.header_frame, text="Download videos and stories instantly with OmniFlow.\nIt's fast, free, and fully compatible with all your devices!", font=("Inter", 14), text_color=COLOR_TEXT_GREEN, justify="left", anchor="w").pack(fill="x", padx=32, pady=(0, 32))

        # ==========================================
        # SECTION 1: URL BOX
        # ==========================================
        self.section1_url = ctk.CTkFrame(self.scroll_container, **BOX_KWARGS)
        self.section1_url.pack(pady=(24, 16), padx=PAD_X, fill="x")

        ctk.CTkLabel(self.section1_url, text="* Insert a video URL", font=("Inter", 14, "bold"), text_color=COLOR_TEXT_MAIN).pack(anchor="w", padx=16, pady=(16, 5))
        e_frame = ctk.CTkFrame(self.section1_url, fg_color="transparent")
        e_frame.pack(fill="x", padx=16, pady=(0, 16))
        self.entry_link = ctk.CTkEntry(e_frame, textvariable=self.link_var, placeholder_text="Copy and Paste your url", height=52, corner_radius=8)
        self.entry_link.pack(side="left", fill="x", expand=True, padx=(0, 12))
        
        self.btn_action = ctk.CTkButton(e_frame, text=" Paste", image=self.icons.get("paste"), compound="left", width=140, height=52, corner_radius=8, fg_color=COLOR_PRIMARY, font=("Inter", 15, "bold"))
        self.btn_action.pack(side="right")

        self.content_stack = ctk.CTkFrame(self.scroll_container, fg_color="transparent")
        self.content_stack.pack(fill="x", pady=0, padx=PAD_X)

        self.screen_instruction = ctk.CTkLabel(self.content_stack, text="OmniFlow allows you to easily download videos from YouTube, TikTok, Instagram, Facebook, or Rednote.\n\nThe service is completely free and requires no sign-up or additional software.\n\nBy using OmniFlow, you accept our Terms of Use.\n\nHow to download a video:\n• Copy the link: Go to YouTube, TikTok, Instagram, Facebook, or Rednote.\n• Paste & Choose Format: Paste the URL into the OmniFlow input box above.\n• Download: Click the “Convert” button once the processing is complete.", font=("Inter", 14), text_color=COLOR_TEXT_MAIN, justify="left", anchor="w")
        self.screen_instruction.pack(fill="x", pady=(0, 24))

        # ==========================================
        # MÀN HÌNH CHECKING
        # ==========================================
        self.screen_checking = ctk.CTkFrame(self.content_stack, **BOX_KWARGS)
        self.label_check_status = ctk.CTkLabel(self.screen_checking, text="Checking Link... (0s)", font=("Inter", 16, "bold"), text_color=COLOR_PRIMARY)
        self.label_check_status.pack(pady=(16, 10), padx=16, anchor="w") 
        
        self.btn_cancel = ctk.CTkButton(self.screen_checking, text=" Cancel", image=self.icons.get("Cancel"), compound="left", height=48, corner_radius=8, fg_color=COLOR_RED_LIGHT, text_color=COLOR_RED, hover_color="#FECACA", font=("Inter", 15, "bold"))
        self.btn_cancel.pack(fill="x", padx=16, pady=(0, 16))

        self.screen_result_container = ctk.CTkFrame(self.content_stack, fg_color="transparent")

        # ==========================================
        # SECTION 2: BOX OF DATA
        # ==========================================
        self.section2_data = ctk.CTkFrame(self.screen_result_container, **BOX_KWARGS)
        self.section2_data.pack(fill="x", pady=SPACE_BETWEEN_BOXES)

        self.left_col = ctk.CTkFrame(self.section2_data, fg_color="transparent")
        self.left_col.pack(side="left", padx=(16, 0), pady=16, anchor="n")
        self.label_thumb = ctk.CTkLabel(self.left_col, text="", width=140, fg_color="#E5E7EB", corner_radius=8)
        self.label_thumb.pack()

        self.right_col = ctk.CTkFrame(self.section2_data, fg_color="transparent")
        self.right_col.pack(side="left", fill="both", expand=True, padx=16, pady=16, anchor="n")
        
        self.tag_icon_label = ctk.CTkLabel(self.right_col, text="")
        self.tag_icon_label.pack(anchor="nw", pady=(0, 4))
        
        self.label_title = ctk.CTkLabel(self.right_col, text="Title: ", font=("Inter", 15, "bold"), text_color=COLOR_TEXT_MAIN, justify="left", anchor="nw")
        self.label_title.pack(anchor="nw", fill="x", pady=(0, 4))
        
        self.author_frame = ctk.CTkFrame(self.right_col, fg_color="transparent")
        self.author_frame.pack(anchor="nw", fill="x", pady=(0, 2))
        self.label_author_title = ctk.CTkLabel(self.author_frame, text="Author: ", font=("Inter", 14), text_color="#6B7280")
        self.label_author_title.pack(side="left")
        self.label_author_val = ctk.CTkLabel(self.author_frame, text="", font=("Inter Medium", 14), text_color="#6B7280") 
        self.label_author_val.pack(side="left")

        self.time_frame = ctk.CTkFrame(self.right_col, fg_color="transparent")
        self.time_frame.pack(anchor="nw", fill="x", pady=(0, 0))
        self.label_time_title = ctk.CTkLabel(self.time_frame, text="Time: ", font=("Inter", 14), text_color="#6B7280")
        self.label_time_title.pack(side="left")
        self.label_time_val = ctk.CTkLabel(self.time_frame, text="", font=("Inter Medium", 14), text_color="#6B7280")
        self.label_time_val.pack(side="left")

        # ==========================================
        # SECTION 3: BOX OF QUALITY
        # ==========================================
        self.section3_quality = ctk.CTkFrame(self.screen_result_container, **BOX_KWARGS)
        self.section3_quality.pack(fill="x", pady=SPACE_BETWEEN_BOXES)

        q_frame = ctk.CTkFrame(self.section3_quality, fg_color="transparent")
        q_frame.pack(fill="x", padx=16, pady=(16, 8))
        ctk.CTkLabel(q_frame, text="Video Quality:", font=("Inter", 14, "bold"), text_color=COLOR_TEXT_MAIN).pack(side="left", padx=(0, 12))
        
        self.seg_quality = ctk.CTkSegmentedButton(
            q_frame, height=40, corner_radius=8,
            fg_color="#F3F4F6", selected_color="#FFFFFF", selected_hover_color="#FFFFFF",
            unselected_color="#F3F4F6", unselected_hover_color="#E5E7EB", text_color="#1F2937" 
        )
        self.seg_quality.pack(side="left", fill="x", expand=True)

        self.btn_download = ctk.CTkButton(self.section3_quality, text=" Start Download", image=self.icons.get("download"), compound="left", height=48, corner_radius=8, fg_color=COLOR_PRIMARY, font=("Inter", 15, "bold"))
        self.btn_download.pack(fill="x", padx=16, pady=(8, 16))

        # ==========================================
        # SECTION 4: BOX OF DOWNLOADING
        # ==========================================
        self.section4_download = ctk.CTkFrame(self.screen_result_container, **BOX_KWARGS)
        
        self.progress_view = ctk.CTkFrame(self.section4_download, fg_color="transparent")
        
        self.label_progress_text = ctk.CTkLabel(self.progress_view, text="Downloading... 0%", font=("Inter", 13, "bold"), text_color=COLOR_TEXT_MAIN)
        self.label_progress_text.pack(anchor="w", padx=16, pady=(16, 0))
        
        self.progressbar = ctk.CTkProgressBar(self.progress_view, height=10, fg_color=COLOR_BORDER, progress_color="#3B82F6")
        self.progressbar.pack(fill="x", padx=16, pady=(12, 16))
        self.progressbar.set(0)
        
        self.btn_cancel_dl = ctk.CTkButton(self.progress_view, text=" Cancel Download", image=self.icons.get("CancelDownload"), compound="left", height=48, corner_radius=8, fg_color=COLOR_RED, font=("Inter", 15, "bold"))
        self.btn_cancel_dl.pack(fill="x", padx=16, pady=(0, 16))

        self.success_view = ctk.CTkFrame(self.section4_download, fg_color="transparent")
        self.label_saved_info = ctk.CTkLabel(self.success_view, text="Saved: Video Title", font=("Inter", 14, "bold"), text_color=COLOR_PRIMARY, anchor="w", justify="left")
        self.label_saved_info.pack(pady=(16, 12), padx=16, fill="x")
        
        self.btn_open_folder = ctk.CTkButton(self.success_view, text=" Open Folder", image=self.icons.get("OpenFolder"), compound="left", height=48, corner_radius=8, fg_color=COLOR_PRIMARY, font=("Inter", 15, "bold"))
        self.btn_open_folder.pack(fill="x", padx=16, pady=(0, 16))

        self.screen_checking.pack_forget()
        self.screen_result_container.pack_forget()
        self.section4_download.pack_forget()

    def set_dl_ready(self):
        self.btn_download.configure(state="normal", text=" Start Download", fg_color=COLOR_PRIMARY, text_color="white", border_width=0, image=self.icons.get("download"))
        self.section4_download.pack_forget()
        self.progress_view.pack_forget()
        self.success_view.pack_forget()

    def set_dl_progress(self):
        self.btn_download.configure(state="disabled", text=" Downloading...", fg_color=COLOR_DISABLED, text_color=COLOR_TEXT_DISABLED, border_width=0, image=self.icons.get("Downloading"))
        self.section4_download.pack(fill="x", pady=(0, 16))
        self.success_view.pack_forget()
        self.progress_view.pack(fill="x")
        self.label_progress_text.configure(text="Downloading... 0%")
        self.progressbar.set(0)

    def set_dl_success(self, title):
        self.btn_download.configure(state="normal", text=" Download Again", fg_color="transparent", text_color=COLOR_PRIMARY, border_color=COLOR_PRIMARY, border_width=1, image=self.icons.get("DownloadAgain"))
        self.section4_download.pack(fill="x", pady=(0, 16))
        self.progress_view.pack_forget()
        self.label_saved_info.configure(text=f"✓ Saved: {title}")
        self.success_view.pack(fill="x")

    def update_thumbnail(self, url):
        def _download():
            try:
                res = requests.get(url, timeout=10)
                img = Image.open(BytesIO(res.content))
                w, h = img.size
                target_w = 140
                target_h = int(target_w / (w / h)) 
                ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(target_w, target_h))
                self.after(0, lambda: self.label_thumb.configure(image=ctk_img, height=target_h))
            except: pass
        threading.Thread(target=_download, daemon=True).start()

    def update_wraplength(self, event=None):
        if event and event.widget != self:
            return 
        w_main = self.winfo_width() - 80
        if w_main == self._last_width:
            return
        self._last_width = w_main
        
        if w_main > 100:
            self.screen_instruction.configure(wraplength=w_main)
            self.label_title.configure(wraplength=w_main - 200) 
            self.label_saved_info.configure(wraplength=w_main - 32)