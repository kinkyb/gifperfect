import os, sys, subprocess, math, threading, shutil, tempfile, time
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox

# ── Licence ───────────────────────────────────────────────────────────────────
LICENCE_SERVER = "https://api.acaption.com/gifperfect/licence"
FREE_DAILY_LIMIT = 3
WATERMARK_TEXT   = "gifperfect.com"

# ── FFmpeg path ───────────────────────────────────────────────────────────────
def ffmpeg_path():
    """Return path to bundled ffmpeg (PyInstaller) or static/system ffmpeg."""
    if getattr(sys, 'frozen', False):
        # One-directory build: ffmpeg(.exe) is next to the executable, not in _MEIPASS
        base = os.path.dirname(sys.executable)
        for name in ('ffmpeg', 'ffmpeg.exe'):
            ff = os.path.join(base, name)
            if os.path.exists(ff):
                return ff
    # Dev: use static_ffmpeg if available, else fall back to system ffmpeg
    try:
        import static_ffmpeg
        static_ffmpeg.add_paths()
    except ImportError:
        pass
    return 'ffmpeg'

FFMPEG = ffmpeg_path()

# ── Usage tracking (free tier) ────────────────────────────────────────────────
import json, datetime

USAGE_FILE = os.path.join(os.path.expanduser('~'), '.gifperfect_usage.json')

def load_usage():
    try:
        with open(USAGE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def save_usage(data):
    with open(USAGE_FILE, 'w') as f:
        json.dump(data, f)

def free_uses_today():
    data = load_usage()
    today = str(datetime.date.today())
    return data.get(today, 0)

def increment_free_use():
    data = load_usage()
    today = str(datetime.date.today())
    data[today] = data.get(today, 0) + 1
    save_usage(data)

# ── Licence validation ─────────────────────────────────────────────────────────
LICENCE_FILE = os.path.join(os.path.expanduser('~'), '.gifperfect_licence')

def load_saved_licence():
    """Returns (key, batch) tuple. Handles both legacy plain-key and new JSON format."""
    try:
        raw = open(LICENCE_FILE).read().strip()
        if raw.startswith('{'):
            data = json.loads(raw)
            return data.get('key', ''), data.get('batch', False)
        # legacy plain-text key
        return raw, raw.startswith('GIFB-')
    except Exception:
        return '', False

def save_licence(key, batch=False):
    with open(LICENCE_FILE, 'w') as f:
        json.dump({'key': key.strip(), 'batch': batch}, f)

def validate_licence(key):
    """Returns {'valid': bool, 'batch': bool}. Server check with offline grace."""
    if not key:
        return {'valid': False, 'batch': False}
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({'key': key}).encode()
        req  = urllib.request.Request(LICENCE_SERVER, data=data, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        with urllib.request.urlopen(req, timeout=8) as r:
            body = json.loads(r.read())
            return {'valid': body.get('valid') is True, 'batch': body.get('batch', False)}
    except Exception:
        # Server unreachable — trust locally saved key, infer batch from prefix
        return {'valid': True, 'batch': key.startswith('GIFB-')}

# ── FFmpeg helpers ─────────────────────────────────────────────────────────────

RESOLUTION_MAP = {
    '480p':     'scale=480:-1:flags=lanczos',
    '640p':     'scale=640:-1:flags=lanczos',
    '1080p':    'scale=1080:-1:flags=lanczos',
    'Original': 'scale=iw:ih:flags=lanczos',
}

def get_duration(video_path):
    result = subprocess.run(
        [FFMPEG.replace('ffmpeg', 'ffprobe') if 'ffmpeg' in FFMPEG else 'ffprobe',
         '-v', 'quiet', '-show_entries', 'format=duration',
         '-of', 'csv=p=0', str(video_path)],
        capture_output=True, text=True, timeout=30,
    )
    return float(result.stdout.strip())

def make_vf(resolution, fps, watermark=False):
    scale = RESOLUTION_MAP.get(resolution, RESOLUTION_MAP['640p'])
    vf = f"fps={fps},{scale},split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse=dither=bayer:diff_mode=rectangle"
    if watermark:
        # Full-image tiled watermark — 9 positions across the frame, hard to crop out
        wm = WATERMARK_TEXT
        alpha = "0.35"
        fs = "22"
        draws = ",".join([
            f"drawtext=text='{wm}':fontsize={fs}:fontcolor=white@{alpha}:x=10:y=10",
            f"drawtext=text='{wm}':fontsize={fs}:fontcolor=white@{alpha}:x=(w-tw)/2:y=10",
            f"drawtext=text='{wm}':fontsize={fs}:fontcolor=white@{alpha}:x=w-tw-10:y=10",
            f"drawtext=text='{wm}':fontsize={fs}:fontcolor=white@{alpha}:x=10:y=(h-th)/2",
            f"drawtext=text='{wm}':fontsize={fs}:fontcolor=white@{alpha}:x=(w-tw)/2:y=(h-th)/2",
            f"drawtext=text='{wm}':fontsize={fs}:fontcolor=white@{alpha}:x=w-tw-10:y=(h-th)/2",
            f"drawtext=text='{wm}':fontsize={fs}:fontcolor=white@{alpha}:x=10:y=h-th-10",
            f"drawtext=text='{wm}':fontsize={fs}:fontcolor=white@{alpha}:x=(w-tw)/2:y=h-th-10",
            f"drawtext=text='{wm}':fontsize={fs}:fontcolor=white@{alpha}:x=w-tw-10:y=h-th-10",
        ])
        vf = (
            f"fps={fps},{scale},{draws},"
            f"split[s0][s1];[s0]palettegen=max_colors=256[p];[s1][p]paletteuse=dither=bayer:diff_mode=rectangle"
        )
    return vf

def video_to_gif_chunks(video_path, target_mb, resolution, fps, out_dir,
                         watermark=False, progress_cb=None):
    """
    Cut video into GIF chunks each under target_mb.
    Returns list of output file paths.
    """
    duration  = get_duration(video_path)
    vf        = make_vf(resolution, fps, watermark)

    # Test 5s segment to estimate MB/s
    test_path = os.path.join(out_dir, '_test.gif')
    test_secs = min(5, duration)
    subprocess.run(
        [FFMPEG, '-ss', '0', '-t', str(test_secs), '-i', str(video_path),
         '-vf', vf, test_path, '-y'],
        capture_output=True, timeout=120,
    )
    test_mb   = os.path.getsize(test_path) / (1024 * 1024)
    os.remove(test_path)

    mb_per_sec  = test_mb / test_secs
    chunk_secs  = max(1, math.floor((target_mb * 0.95) / mb_per_sec))
    n_chunks    = math.ceil(duration / chunk_secs)

    output_files = []
    for i in range(n_chunks):
        start   = i * chunk_secs
        out_gif = os.path.join(out_dir, f'chunk_{i+1:03d}.gif')
        subprocess.run(
            [FFMPEG, '-ss', str(start), '-t', str(chunk_secs),
             '-i', str(video_path), '-vf', vf, out_gif, '-y'],
            capture_output=True, timeout=300,
        )
        if os.path.exists(out_gif):
            output_files.append(out_gif)
        if progress_cb:
            progress_cb((i + 1) / n_chunks)

    return output_files

def extract_frame_jpgs(video_path, interval_secs, out_dir, progress_cb=None):
    """Extract JPG frames every interval_secs seconds."""
    subprocess.run(
        [FFMPEG, '-i', str(video_path),
         '-vf', f'fps=1/{interval_secs}', '-q:v', '2',
         os.path.join(out_dir, 'frame_%03d.jpg'), '-y'],
        capture_output=True, timeout=300,
    )
    frames = sorted(Path(out_dir).glob('frame_*.jpg'))
    return frames

# ── GUI ────────────────────────────────────────────────────────────────────────

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

ACCENT   = "#7C5CBF"
BG       = "#1a1a1a"
CARD     = "#242424"
TEXT     = "#f0f0f0"
MUTED    = "#888888"
BTN_FG   = "#ffffff"

class GifPerfectApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("GIF Perfect")
        self.geometry("560x760")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        self.video_path   = None
        self.licence_key, self.batch_tier = load_saved_licence()
        self.licensed     = False
        self.batch_files  = []
        self.output_dir   = None
        self.mode_var     = ctk.StringVar(value="gif")

        self._build_ui()
        self._check_licence_silent()

    # ── UI construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 24}

        # Logo
        ctk.CTkLabel(self, text="GIF Perfect", font=ctk.CTkFont(size=26, weight="bold"),
                     text_color=TEXT).pack(pady=(28, 2))
        ctk.CTkLabel(self, text="Convert video to GIF chunks · or extract JPG frames",
                     font=ctk.CTkFont(size=13), text_color=MUTED).pack(pady=(0, 20))

        # ── Drop zone ──
        self.drop_frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10,
                                        border_width=2, border_color="#444")
        self.drop_frame.pack(fill="x", **pad, pady=(0, 18))
        self.drop_label = ctk.CTkLabel(self.drop_frame,
                                        text="Drop a video here  or  click to browse",
                                        font=ctk.CTkFont(size=13), text_color=MUTED,
                                        height=80)
        self.drop_label.pack(expand=True)
        self.drop_frame.bind("<Button-1>", lambda e: self._pick_file())
        self.drop_label.bind("<Button-1>", lambda e: self._pick_file())

        # ── Batch file list (hidden until batch mode activated) ──
        self.batch_frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=10,
                                         border_width=2, border_color="#444")
        # not packed yet — shown when mode = "batch"
        self.batch_scroll = ctk.CTkScrollableFrame(self.batch_frame, fg_color="transparent",
                                                    height=56)
        self.batch_scroll.pack(fill="x", padx=8, pady=(8, 4))
        self.batch_file_labels = []
        batch_btn_row = ctk.CTkFrame(self.batch_frame, fg_color="transparent")
        batch_btn_row.pack(fill="x", padx=8, pady=(0, 8))
        ctk.CTkButton(batch_btn_row, text="+ Add files", width=110, height=28,
                      font=ctk.CTkFont(size=11), fg_color=ACCENT, hover_color="#6448a8",
                      text_color=BTN_FG, corner_radius=6,
                      command=self._add_batch_files).pack(side="left")
        ctk.CTkButton(batch_btn_row, text="Clear all", width=80, height=28,
                      font=ctk.CTkFont(size=11), fg_color="transparent",
                      border_width=1, border_color="#555", text_color=MUTED,
                      hover_color="#333", corner_radius=6,
                      command=self._clear_batch_files).pack(side="left", padx=(8, 0))
        self.batch_count_label = ctk.CTkLabel(batch_btn_row, text="0 files",
                                               font=ctk.CTkFont(size=11), text_color=MUTED)
        self.batch_count_label.pack(side="right")

        # ── Mode ──
        self._mode_section_label = ctk.CTkLabel(self, text="Mode",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT, anchor="w")
        self._mode_section_label.pack(fill="x", **pad, pady=(0, 6))
        mode_frame = ctk.CTkFrame(self, fg_color="transparent")
        mode_frame.pack(fill="x", **pad, pady=(0, 16))
        self.mode_btns = []
        for label, val in [("GIF Chunks", "gif"), ("Frames Only", "frames")]:
            b = ctk.CTkButton(mode_frame, text=label, width=148, height=36,
                              font=ctk.CTkFont(size=12),
                              fg_color=ACCENT if val == "gif" else CARD,
                              hover_color=ACCENT, text_color=BTN_FG, corner_radius=8,
                              command=lambda v=val: self._set_mode(v))
            b.pack(side="left", padx=(0, 8))
            self.mode_btns.append((b, val))
        # Batch button — always built, only enabled for Studio Batch licence holders
        self.batch_mode_btn = ctk.CTkButton(
            mode_frame, text="Batch", width=100, height=36,
            font=ctk.CTkFont(size=12),
            fg_color="#2a2a2a", hover_color=ACCENT if self.batch_tier else "#2a2a2a",
            text_color="#555" if not self.batch_tier else BTN_FG,
            corner_radius=8,
            command=self._batch_btn_clicked)
        self.batch_mode_btn.pack(side="left")
        self.mode_btns.append((self.batch_mode_btn, "batch"))

        # ── Target size ──
        self.size_label = ctk.CTkLabel(self, text="Target size per GIF",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT, anchor="w")
        self.size_label.pack(fill="x", **pad, pady=(0, 6))

        size_frame = ctk.CTkFrame(self, fg_color="transparent")
        size_frame.pack(fill="x", **pad, pady=(0, 4))
        self.size_var = ctk.StringVar(value="99")
        presets = [("15 MB", "15"), ("25 MB", "25"), ("99 MB", "99")]
        self.size_btns = []
        for label, val in presets:
            b = ctk.CTkButton(size_frame, text=label, width=120, height=40,
                              font=ctk.CTkFont(size=12),
                              fg_color=ACCENT if val == "99" else CARD,
                              hover_color=ACCENT, text_color=BTN_FG, corner_radius=8,
                              command=lambda v=val: self._set_size(v))
            b.pack(side="left", padx=(0, 8))
            self.size_btns.append((b, val))
        ctk.CTkLabel(size_frame,
                     text="* See platform limits\nat gifperfect.com/platforms",
                     font=ctk.CTkFont(size=10), text_color=MUTED,
                     justify="left", wraplength=128).pack(side="left", padx=(4, 0))

        custom_frame = ctk.CTkFrame(self, fg_color="transparent")
        custom_frame.pack(fill="x", **pad, pady=(4, 16))
        ctk.CTkLabel(custom_frame, text="Custom MB:", text_color=MUTED,
                     font=ctk.CTkFont(size=12)).pack(side="left")
        self.custom_entry = ctk.CTkEntry(custom_frame, width=70, placeholder_text="e.g. 50")
        self.custom_entry.pack(side="left", padx=8)
        self.custom_entry.bind("<KeyRelease>", self._on_custom_size)

        # ── Resolution ──
        self.res_label = ctk.CTkLabel(self, text="Resolution",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT, anchor="w")
        self.res_label.pack(fill="x", **pad, pady=(0, 6))
        res_frame = ctk.CTkFrame(self, fg_color="transparent")
        res_frame.pack(fill="x", **pad, pady=(0, 16))
        self.res_var = ctk.StringVar(value="640p")
        for r in ["480p", "640p", "1080p", "Original"]:
            ctk.CTkRadioButton(res_frame, text=r, variable=self.res_var, value=r,
                               font=ctk.CTkFont(size=12),
                               text_color=TEXT).pack(side="left", padx=(0, 16))

        # ── FPS ──
        self.fps_label = ctk.CTkLabel(self, text="FPS",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT, anchor="w")
        self.fps_label.pack(fill="x", **pad, pady=(0, 6))
        fps_frame = ctk.CTkFrame(self, fg_color="transparent")
        fps_frame.pack(fill="x", **pad, pady=(0, 16))
        self.fps_var = ctk.StringVar(value="30")
        for f in ["15", "24", "30"]:
            ctk.CTkRadioButton(fps_frame, text=f"{f} fps", variable=self.fps_var, value=f,
                               font=ctk.CTkFont(size=12),
                               text_color=TEXT).pack(side="left", padx=(0, 16))

        # ── Frame extraction ──
        frames_frame = ctk.CTkFrame(self, fg_color="transparent")
        frames_frame.pack(fill="x", **pad, pady=(0, 20))
        self.frames_var = ctk.BooleanVar(value=False)
        self.frames_checkbox = ctk.CTkCheckBox(frames_frame, text="Extract JPG frames every",
                        variable=self.frames_var,
                        font=ctk.CTkFont(size=12), text_color=TEXT)
        self.frames_checkbox.pack(side="left")
        self.frame_interval = ctk.CTkEntry(frames_frame, width=50, placeholder_text="15")
        self.frame_interval.pack(side="left", padx=8)
        ctk.CTkLabel(frames_frame, text="seconds",
                     font=ctk.CTkFont(size=12), text_color=MUTED).pack(side="left")

        # ── Generate button ──
        self.generate_btn = ctk.CTkButton(self, text="Generate",
                                           font=ctk.CTkFont(size=15, weight="bold"),
                                           height=52, fg_color=ACCENT,
                                           hover_color="#6448a8",
                                           corner_radius=10,
                                           command=self._generate)
        self.generate_btn.pack(fill="x", **pad, pady=(0, 12))

        # ── Progress ──
        self.progress = ctk.CTkProgressBar(self, height=8, corner_radius=4,
                                            progress_color=ACCENT)
        self.progress.pack(fill="x", **pad, pady=(0, 8))
        self.progress.set(0)

        self.status_label = ctk.CTkLabel(self, text="",
                                          font=ctk.CTkFont(size=12), text_color=MUTED)
        self.status_label.pack()

        # ── Licence bar ──
        lic_frame = ctk.CTkFrame(self, fg_color=CARD, corner_radius=8)
        lic_frame.pack(fill="x", **pad, pady=(16, 0))
        self.lic_status = ctk.CTkLabel(lic_frame, text="Free version · 3 uses/day",
                                        font=ctk.CTkFont(size=11), text_color=MUTED)
        self.lic_status.pack(side="left", padx=12, pady=8)
        ctk.CTkButton(lic_frame, text="Enter licence key", width=130,
                      height=28, font=ctk.CTkFont(size=11),
                      fg_color="transparent", border_width=1,
                      border_color=ACCENT, text_color=ACCENT,
                      hover_color="#333",
                      command=self._show_licence_dialog).pack(side="right", padx=12, pady=8)

    # ── Interactions ───────────────────────────────────────────────────────────

    def _batch_btn_clicked(self):
        if not self.batch_tier:
            messagebox.showinfo(
                "Studio Batch required",
                "Batch mode is available on the Studio Batch plan ($199 one-time).\n\n"
                "Visit gifperfect.com to upgrade."
            )
            return
        self._set_mode("batch")

    def _set_mode(self, val):
        self.mode_var.set(val)
        for btn, v in self.mode_btns:
            if v == "batch":
                btn.configure(fg_color=ACCENT if val == "batch" else "#2a2a2a")
            else:
                btn.configure(fg_color=ACCENT if v == val else CARD)

        # Toggle drop zone vs batch file list (both live before _mode_section_label)
        if val == "batch":
            self.drop_frame.pack_forget()
            self.batch_frame.pack(fill="x", padx=24, pady=(0, 18),
                                  before=self._mode_section_label)
        else:
            self.batch_frame.pack_forget()
            self.drop_frame.pack(fill="x", padx=24, pady=(0, 18),
                                 before=self._mode_section_label)

        is_gif = val == "gif"
        is_batch = val == "batch"
        dim = TEXT if (is_gif or is_batch) else "#555555"
        self.size_label.configure(text_color=dim)
        self.res_label.configure(text_color=dim)
        self.fps_label.configure(text_color=dim)
        if val == "frames":
            self.frames_var.set(True)
            self.frames_checkbox.configure(state="disabled")
        else:
            self.frames_checkbox.configure(state="normal")

    def _set_size(self, val):
        self.size_var.set(val)
        self.custom_entry.delete(0, "end")
        for btn, v in self.size_btns:
            btn.configure(fg_color=ACCENT if v == val else CARD)

    def _on_custom_size(self, event=None):
        val = self.custom_entry.get().strip()
        if val.isdigit():
            self.size_var.set(val)
            for btn, v in self.size_btns:
                btn.configure(fg_color=CARD)

    def _pick_file(self):
        path = filedialog.askopenfilename(
            title="Select a video file",
            filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv *.webm *.m4v"), ("All files", "*.*")]
        )
        if path:
            self.video_path = path
            name = os.path.basename(path)
            self.drop_label.configure(text=f"✓  {name}", text_color=TEXT)
            self.drop_frame.configure(border_color=ACCENT)

    def _check_licence_silent(self):
        if self.licence_key:
            def check():
                result = validate_licence(self.licence_key)
                self.licensed   = result['valid']
                self.batch_tier = result['batch']
                self.after(0, self._update_licence_ui)
                if self.batch_tier:
                    self.after(0, self._enable_batch_btn)
            threading.Thread(target=check, daemon=True).start()

    def _enable_batch_btn(self):
        self.batch_mode_btn.configure(
            fg_color=CARD, hover_color=ACCENT,
            text_color=BTN_FG
        )

    def _update_licence_ui(self):
        if self.licensed:
            if self.batch_tier:
                label = "✓  Studio Batch — unlimited use + batch mode"
            else:
                label = "✓  Licensed — unlimited use"
            self.lic_status.configure(text=label, text_color="#5cb85c")
        else:
            uses = free_uses_today()
            remaining = max(0, FREE_DAILY_LIMIT - uses)
            self.lic_status.configure(
                text=f"Free version · {remaining} use{'s' if remaining != 1 else ''} remaining today",
                text_color=MUTED
            )

    def _show_licence_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Enter Licence Key")
        dialog.geometry("400x180")
        dialog.configure(fg_color=BG)
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Licence Key",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT).pack(pady=(20, 8))
        entry = ctk.CTkEntry(dialog, width=320, placeholder_text="GIFP- or GIFB-XXXX-XXXX-XXXX")
        entry.pack(pady=(0, 12))
        if self.licence_key:
            entry.insert(0, self.licence_key)

        def activate():
            key = entry.get().strip()
            if not key:
                return
            ctk.CTkLabel(dialog, text="Validating...", text_color=MUTED,
                         font=ctk.CTkFont(size=11)).pack()
            dialog.update()
            result = validate_licence(key)
            if result['valid']:
                self.licence_key = key
                self.licensed    = True
                self.batch_tier  = result['batch']
                save_licence(key, result['batch'])
                self._update_licence_ui()
                if self.batch_tier:
                    self._enable_batch_btn()
                dialog.destroy()
                msg = ("Licence activated! Unlimited use + Batch Mode enabled."
                       if result['batch'] else
                       "Licence activated! Unlimited use enabled.")
                messagebox.showinfo("GIF Perfect", msg)
            else:
                messagebox.showerror("GIF Perfect", "Invalid licence key. Check your purchase email.")

        ctk.CTkButton(dialog, text="Activate", fg_color=ACCENT,
                      hover_color="#6448a8", command=activate).pack()

    # ── Batch file management ──────────────────────────────────────────────────

    def _add_batch_files(self):
        paths = filedialog.askopenfilenames(
            title="Select video files",
            filetypes=[("Video files", "*.mp4 *.mov *.avi *.mkv *.webm *.m4v"), ("All files", "*.*")]
        )
        for p in paths:
            if p not in self.batch_files:
                self.batch_files.append(p)
        self._refresh_batch_list()

    def _clear_batch_files(self):
        self.batch_files.clear()
        self._refresh_batch_list()

    def _refresh_batch_list(self):
        for lbl in self.batch_file_labels:
            lbl.destroy()
        self.batch_file_labels.clear()
        for path in self.batch_files:
            name = os.path.basename(path)
            lbl = ctk.CTkLabel(self.batch_scroll, text=f"• {name}",
                               font=ctk.CTkFont(size=11), text_color=TEXT,
                               anchor="w")
            lbl.pack(fill="x", pady=1)
            self.batch_file_labels.append(lbl)
        n = len(self.batch_files)
        self.batch_count_label.configure(text=f"{n} file{'s' if n != 1 else ''}")

    # ── Generate ───────────────────────────────────────────────────────────────

    def _generate(self):
        if self.mode_var.get() == "batch":
            self._run_batch()
            return

        if not self.video_path:
            messagebox.showwarning("GIF Perfect", "Please select a video file first.")
            return

        # Free tier check
        if not self.licensed:
            uses = free_uses_today()
            if uses >= FREE_DAILY_LIMIT:
                messagebox.showwarning(
                    "Daily limit reached",
                    f"Free version is limited to {FREE_DAILY_LIMIT} conversions per day.\n\n"
                    "Purchase a licence at gifperfect.com for unlimited use."
                )
                return

        mode     = self.mode_var.get()
        out_dir  = filedialog.askdirectory(title="Choose output folder")
        if not out_dir:
            return

        self.generate_btn.configure(state="disabled", text="Generating…")
        self.progress.set(0)
        self._set_status("Starting…")

        if mode == "frames":
            interval = int(self.frame_interval.get() or 15)

            def run_frames():
                try:
                    if not self.licensed:
                        increment_free_use()
                    self.after(0, lambda: self._set_status("Extracting frames…"))
                    self.after(0, lambda: self.progress.set(0.5))
                    frame_files = extract_frame_jpgs(self.video_path, interval, out_dir)
                    self.after(0, lambda: self.progress.set(1.0))
                    n = len(frame_files)
                    self.after(0, lambda: self._on_done_frames(n, out_dir))
                except Exception as e:
                    self.after(0, lambda: self._on_error(str(e)))

            threading.Thread(target=run_frames, daemon=True).start()
            return

        # GIF Chunks mode
        target_mb   = float(self.size_var.get() or 99)
        resolution  = self.res_var.get()
        fps         = int(self.fps_var.get())
        do_frames   = self.frames_var.get()
        interval    = int(self.frame_interval.get() or 15) if do_frames else None
        watermark   = not self.licensed

        def run():
            try:
                if not self.licensed:
                    increment_free_use()

                gif_files = video_to_gif_chunks(
                    self.video_path, target_mb, resolution, fps, out_dir,
                    watermark=watermark,
                    progress_cb=lambda p: self.after(0, lambda: self.progress.set(p * (0.9 if do_frames else 1.0)))
                )

                if do_frames and interval:
                    self.after(0, lambda: self._set_status("Extracting frames…"))
                    extract_frame_jpgs(self.video_path, interval, out_dir)
                    self.after(0, lambda: self.progress.set(1.0))

                n_gifs = len(gif_files)
                self.after(0, lambda: self._on_done(n_gifs, out_dir))

            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=run, daemon=True).start()

    def _run_batch(self):
        if not self.batch_files:
            messagebox.showwarning("GIF Perfect", "Add at least one video file to the batch list.")
            return

        out_dir = filedialog.askdirectory(title="Choose output folder for batch")
        if not out_dir:
            return

        target_mb  = float(self.size_var.get() or 99)
        resolution = self.res_var.get()
        fps        = int(self.fps_var.get())
        do_frames  = self.frames_var.get()
        interval   = int(self.frame_interval.get() or 15) if do_frames else None
        files      = list(self.batch_files)

        self.generate_btn.configure(state="disabled", text="Processing…")
        self.progress.set(0)
        self._set_status(f"Batch: 0 / {len(files)} files…")

        def run():
            total     = len(files)
            total_gifs = 0
            for idx, video_path in enumerate(files):
                # Free tier: check limit before each file
                if not self.licensed:
                    uses = free_uses_today()
                    if uses >= FREE_DAILY_LIMIT:
                        self.after(0, lambda i=idx: self._set_status(
                            f"Daily limit reached after {i} file(s). Upgrade for unlimited batch."))
                        break

                name     = os.path.splitext(os.path.basename(video_path))[0]
                file_dir = os.path.join(out_dir, name)
                os.makedirs(file_dir, exist_ok=True)

                self.after(0, lambda i=idx, n=name: self._set_status(
                    f"Batch: {i+1}/{total} — {n}…"))

                try:
                    if not self.licensed:
                        increment_free_use()

                    gif_files = video_to_gif_chunks(
                        video_path, target_mb, resolution, fps, file_dir,
                        watermark=not self.licensed,
                        progress_cb=lambda p, i=idx: self.after(0, lambda: self.progress.set(
                            (i + p) / total))
                    )
                    total_gifs += len(gif_files)

                    if do_frames and interval:
                        frames_dir = os.path.join(file_dir, 'frames')
                        os.makedirs(frames_dir, exist_ok=True)
                        extract_frame_jpgs(video_path, interval, frames_dir)

                except Exception as e:
                    self.after(0, lambda err=str(e), n=name: messagebox.showerror(
                        "GIF Perfect — Batch Error", f"Error processing {n}:\n{err}"))

            self.after(0, lambda: self._on_done_batch(total_gifs, out_dir))

        threading.Thread(target=run, daemon=True).start()

    def _on_done_batch(self, total_gifs, out_dir):
        self.progress.set(1.0)
        self._set_status(f"Batch done — {total_gifs} GIF{'s' if total_gifs != 1 else ''} across {len(self.batch_files)} file(s)")
        self.generate_btn.configure(state="normal", text="Generate")
        self._update_licence_ui()
        if sys.platform == "darwin":
            subprocess.run(["open", out_dir])
        elif sys.platform == "win32":
            subprocess.run(["explorer", out_dir])

    def _set_status(self, msg):
        self.status_label.configure(text=msg)

    def _on_done_frames(self, n_frames, out_dir):
        self.progress.set(1.0)
        self._set_status(f"Done — {n_frames} frame{'s' if n_frames != 1 else ''} saved to output folder")
        self.generate_btn.configure(state="normal", text="Generate")
        self._update_licence_ui()
        if sys.platform == "darwin":
            subprocess.run(["open", out_dir])
        elif sys.platform == "win32":
            subprocess.run(["explorer", out_dir])

    def _on_done(self, n_gifs, out_dir):
        self.progress.set(1.0)
        self._set_status(f"Done — {n_gifs} GIF{'s' if n_gifs != 1 else ''} saved to output folder")
        self.generate_btn.configure(state="normal", text="Generate")
        self._update_licence_ui()
        # Open output folder
        if sys.platform == "darwin":
            subprocess.run(["open", out_dir])
        elif sys.platform == "win32":
            subprocess.run(["explorer", out_dir])

    def _on_error(self, msg):
        self.generate_btn.configure(state="normal", text="Generate")
        self._set_status("Error — see details below")
        messagebox.showerror("GIF Perfect — Error", msg)


if __name__ == "__main__":
    app = GifPerfectApp()
    app.mainloop()
