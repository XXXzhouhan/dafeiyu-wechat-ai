import json
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)

import config
CONFIG_LOCAL = os.path.join(PROJECT_DIR, "config_local.py")
ENV_FILE = os.path.join(PROJECT_DIR, ".env")
PERSONA_FILE = os.path.join(PROJECT_DIR, "persona.txt")
STICKERS_DIR = os.path.join(PROJECT_DIR, "stickers")
STOP_FILE = os.path.join(PROJECT_DIR, "bot.stop")
PID_FILE = os.path.join(PROJECT_DIR, "bot.pid")
LOG_FILE = os.path.join(PROJECT_DIR, "bot.log")
ERR_FILE = os.path.join(PROJECT_DIR, "bot_err.log")
STATE_FILE = os.path.join(PROJECT_DIR, "app_state.json")

FONT_NAME = "Microsoft YaHei UI"
BG = "#F3F7FB"
CARD = "#FFFFFF"
SIDEBAR = "#0E2238"
SIDEBAR_ACTIVE = "#1B3B5C"
PRIMARY = "#2D6FDD"
PRIMARY_DARK = "#225BC0"
AQUA = "#2EC4B6"
TEXT = "#142033"
MUTED = "#6B7A90"
BORDER = "#DCE5F0"
SUCCESS = "#1F7D54"
DANGER = "#C2413B"
WARN = "#9A5B00"

NAV_ITEMS = [
    ("basic", "01   基础"),
    ("model", "02   模型"),
    ("persona", "03   人设"),
    ("meme", "04   热梗"),
    ("sticker", "05   表情包"),
    ("run", "06   运行"),
    ("log", "07   日志"),
]

PAGE_META = {
    "basic": ("基础设置", "群、触发方式、回复长度和图片处理"),
    "model": ("模型与视觉", "文本模型、视觉模型和接口 Key"),
    "persona": ("人设", "傲娇鲸鱼娘的语气、边界和示例"),
    "meme": ("热梗语料", "联网搜集、AI 梗占比和语料库维护"),
    "sticker": ("表情包", "自然发送、识别群友表情和素材库"),
    "run": ("运行策略", "暂停、窗口、性能和自动启动"),
    "log": ("运行日志", "实时查看 bot.log，排查启动和发送问题"),
}

CONFIG_KEYS = [
    "GROUPS",
    "BOT_NAMES",
    "EXPECTED_ACCOUNT",
    "TRIGGER_MODE",
    "KEYWORDS",
    "TRIGGER_BY_NAME",
    "FOLLOW_UP_SECONDS",
    "FOLLOW_UP_TURNS",
    "FOLLOW_UP_HINTS",
    "REPLY_WITH_AT",
    "MIN_INTERVAL",
    "CONTEXT_SIZE",
    "MAX_REPLY_CHARS",
    "EMPTY_AT_REPLY",
    "IMAGE_FOLLOW_SECONDS",
    "IMAGE_WAIT_SECONDS",
    "AUTO_CAPTURE_IMAGE_KEY",
    "PAUSE_WHEN_ACTIVE",
    "PAUSE_READ_WHEN_ACTIVE",
    "ACTIVE_IDLE_SECONDS",
    "PAUSE_WHEN_FULLSCREEN",
    "LOW_PRIORITY",
    "HIDE_WECHAT_WINDOW",
    "ONLY_WHEN_UNREAD",
    "KEEP_WINDOW_WIDE",
    "POLL_INTERVAL",
    "ENABLE_VISION",
    "VISION_MODEL",
    "LLM_TIMEOUT",
    "LLM_TEMPERATURE",
    "STICKER_CHANCE",
    "STICKER_MAX_REPLY_CHARS",
    "REACT_TO_STICKERS",
    "STICKER_REACT_CHANCE",
    "STICKER_MIN_INTERVAL",
    "MEME_ENABLE",
    "MEME_REFRESH_HOURS",
    "MEME_PROMPT_LIMIT",
    "MEME_PER_REFRESH",
    "MEME_MAX_ITEMS",
    "MEME_TTL_DAYS",
    "MEME_SOURCE_LIMIT",
    "MEME_AI_SOURCE_LIMIT",
    "MEME_AI_RATIO",
]

BOOL_KEYS = [
    "TRIGGER_BY_NAME",
    "REPLY_WITH_AT",
    "AUTO_CAPTURE_IMAGE_KEY",
    "PAUSE_WHEN_ACTIVE",
    "PAUSE_READ_WHEN_ACTIVE",
    "PAUSE_WHEN_FULLSCREEN",
    "LOW_PRIORITY",
    "HIDE_WECHAT_WINDOW",
    "ONLY_WHEN_UNREAD",
    "KEEP_WINDOW_WIDE",
    "ENABLE_VISION",
    "REACT_TO_STICKERS",
    "MEME_ENABLE",
]

LIST_KEYS = ["BOT_NAMES", "KEYWORDS", "FOLLOW_UP_HINTS"]

INT_KEYS = {
    "FOLLOW_UP_SECONDS": (0, 3600),
    "FOLLOW_UP_TURNS": (0, 20),
    "CONTEXT_SIZE": (5, 200),
    "MAX_REPLY_CHARS": (50, 2000),
    "IMAGE_FOLLOW_SECONDS": (0, 3600),
    "LLM_TIMEOUT": (10, 600),
    "STICKER_MAX_REPLY_CHARS": (0, 2000),
    "MEME_REFRESH_HOURS": (1, 168),
    "MEME_PROMPT_LIMIT": (0, 60),
    "MEME_PER_REFRESH": (0, 30),
    "MEME_MAX_ITEMS": (10, 2000),
    "MEME_TTL_DAYS": (1, 365),
    "MEME_SOURCE_LIMIT": (5, 60),
    "MEME_AI_SOURCE_LIMIT": (5, 60),
}

FLOAT_KEYS = {
    "MIN_INTERVAL": (0, 120),
    "ACTIVE_IDLE_SECONDS": (1, 600),
    "IMAGE_WAIT_SECONDS": (0, 30),
    "POLL_INTERVAL": (0.5, 10),
    "LLM_TEMPERATURE": (0, 2),
    "STICKER_CHANCE": (0, 1),
    "STICKER_REACT_CHANCE": (0, 1),
    "STICKER_MIN_INTERVAL": (0, 60),
    "MEME_AI_RATIO": (0, 1),
}

STRING_KEYS = [
    "EXPECTED_ACCOUNT",
    "EMPTY_AT_REPLY",
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "VISION_BASE_URL",
    "VISION_API_KEY",
    "VISION_MODEL",
]


def python_exe():
    exe = sys.executable
    if os.name == "nt" and exe.lower().endswith("pythonw.exe"):
        candidate = exe[: -len("pythonw.exe")] + "python.exe"
        if os.path.exists(candidate):
            return candidate
    venv_py = os.path.join(PROJECT_DIR, ".venv", "Scripts", "python.exe")
    if not os.path.basename(exe).lower().startswith("python") and os.path.exists(venv_py):
        return venv_py
    return exe


PYTHON = python_exe()
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def cfg(name, default=None):
    return getattr(config, name, default)


def split_words(text):
    text = (text or "").replace("，", ",").replace("；", ",").replace(";", ",")
    text = text.replace("|", ",").replace("\n", ",")
    out = []
    for item in text.split(","):
        item = item.strip()
        if item and item not in out:
            out.append(item)
    return out


def split_lines(text):
    return [line.strip() for line in (text or "").replace("\r", "").split("\n") if line.strip()]


def read_text(path, default=""):
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return default


def write_atomic(path, text):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}
    return {"auto_start": bool(data.get("auto_start", True))}


def save_state(data):
    try:
        write_atomic(STATE_FILE, json.dumps(data, ensure_ascii=False, indent=1))
    except Exception:
        pass


def settings_from_config():
    data = {}
    for key in CONFIG_KEYS:
        data[key] = cfg(key, [] if key in LIST_KEYS or key == "GROUPS" else "")
    data["GROUPS"] = list(data.get("GROUPS") or [])
    for key in LIST_KEYS:
        data[key] = list(data.get(key) or [])
    data["LLM_BASE_URL"] = cfg("LLM_BASE_URL", "")
    data["LLM_API_KEY"] = cfg("LLM_API_KEY", "")
    data["LLM_MODEL"] = cfg("LLM_MODEL", "")
    vision_base = os.getenv("VISION_BASE_URL", "")
    vision_key = os.getenv("VISION_API_KEY", "")
    data["VISION_BASE_URL"] = (
        ""
        if vision_base
        and vision_base.rstrip("/") == str(data.get("LLM_BASE_URL", "")).rstrip("/")
        else vision_base
    )
    data["VISION_API_KEY"] = (
        "" if vision_key and vision_key == data.get("LLM_API_KEY", "") else vision_key
    )
    data["VISION_MODEL"] = cfg("VISION_MODEL", "")
    data["PERSONA"] = read_text(PERSONA_FILE, "")
    return data


def render_config_local(data):
    lines = ["# 由桌面助手 app.py 生成；在 APP 里保存会覆盖这个文件", ""]
    for key in CONFIG_KEYS:
        lines.append("{} = {!r}".format(key, data[key]))
    lines.append("")
    return "\n".join(lines)


def update_env_text(existing, data):
    values = {
        "LLM_BASE_URL": data.get("LLM_BASE_URL", ""),
        "LLM_API_KEY": data.get("LLM_API_KEY", ""),
        "LLM_MODEL": data.get("LLM_MODEL", ""),
        "VISION_BASE_URL": data.get("VISION_BASE_URL") or data.get("LLM_BASE_URL", ""),
        "VISION_API_KEY": data.get("VISION_API_KEY", ""),
        "VISION_MODEL": data.get("VISION_MODEL", ""),
    }
    values = {key: str(value).replace("\n", " ").strip() for key, value in values.items()}
    out = []
    seen = set()
    for line in (existing or "").replace("\r", "").split("\n"):
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in values:
                out.append("{}={}".format(key, values[key]))
                seen.add(key)
                continue
        out.append(line)
    for key, value in values.items():
        if key not in seen:
            out.append("{}={}".format(key, value))
    text = "\n".join(out).strip()
    return text + "\n"


def write_settings(data):
    write_atomic(CONFIG_LOCAL, render_config_local(data))
    write_atomic(ENV_FILE, update_env_text(read_text(ENV_FILE, ""), data))
    write_atomic(PERSONA_FILE, data.get("PERSONA", ""))


def tail_text(path, lines=80):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except FileNotFoundError:
        return ""


def pid_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        try:
            import ctypes

            handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
        except Exception:
            pass
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def running_pid():
    try:
        pid = int(read_text(PID_FILE, "").strip())
    except ValueError:
        return 0
    return pid if pid and pid_alive(pid) else 0


def find_bot_process():
    try:
        import psutil
    except Exception:
        return 0
    root = os.path.normcase(PROJECT_DIR)
    for proc in psutil.process_iter(["pid", "cmdline", "cwd"]):
        try:
            cmd = " ".join(proc.info.get("cmdline") or []).lower()
            cwd = os.path.normcase(proc.info.get("cwd") or "")
            if "bot.py" in cmd and cwd == root and proc.pid != os.getpid():
                return proc.pid
        except Exception:
            continue
    return 0


def sticker_stats():
    exts = (".png", ".jpg", ".jpeg", ".gif", ".webp")
    count = 0
    tags = set()
    try:
        for name in os.listdir(STICKERS_DIR):
            path = os.path.join(STICKERS_DIR, name)
            if not os.path.isfile(path) or os.path.splitext(name)[1].lower() not in exts:
                continue
            count += 1
            tags.add(name.split("_", 1)[0] if "_" in name else os.path.splitext(name)[0])
    except FileNotFoundError:
        pass
    return count, len(tags)


class ScrollFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg=BG)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.scroll = ttk.Scrollbar(
            self, orient="vertical", command=self.canvas.yview, style="Vertical.TScrollbar"
        )
        self.inner = tk.Frame(self.canvas, bg=BG)
        self.window = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scroll.pack(side="right", fill="y")
        self.canvas.bind("<Enter>", self._bind_wheel)
        self.canvas.bind("<Leave>", self._unbind_wheel)

    def _on_inner(self, _event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, event):
        self.canvas.itemconfigure(self.window, width=event.width)

    def _bind_wheel(self, _event):
        self.canvas.bind_all("<MouseWheel>", self._wheel)

    def _unbind_wheel(self, _event):
        self.canvas.unbind_all("<MouseWheel>")

    def _wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class AssistantApp:
    def __init__(self, root):
        self.root = root
        self.proc = None
        self.err_handle = None
        self.quiet_start = False
        self.v = {}
        self.b = {}
        self.t = {}
        self.last_log = ""
        self.status_changed_at = time.time()
        self.state = load_state()
        self.status_var = tk.StringVar(value="未接管")
        self.sticker_count_var = tk.StringVar(value="")
        self.auto_start_var = tk.BooleanVar(value=self.state.get("auto_start", True))

        self.root.title("大肥鱼 · 傲娇鲸鱼娘")
        self.root.minsize(900, 700)
        self.root.update_idletasks()
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1040, max(900, screen_w - 80))
        height = min(820, max(700, screen_h - 80))
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2 - 20)
        self.root.geometry("{}x{}+{}+{}".format(width, height, x, y))
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._setup_style()
        self._build_ui()
        self._load_settings()
        self._update_status()
        self._poll_log()
        if self.auto_start_var.get():
            self.root.after(1200, lambda: self.start_bot(quiet=True))

    def _setup_style(self):
        self.root.configure(bg=BG)
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", font=(FONT_NAME, 10), background=BG, foreground=TEXT)
        style.configure("TFrame", background=BG)
        style.configure("Card.TFrame", background=CARD)
        style.configure("TLabel", background=BG, foreground=TEXT)
        style.configure("Card.TLabel", background=CARD, foreground=TEXT)
        style.configure("Field.TLabel", background=CARD, foreground=TEXT, font=(FONT_NAME, 9))
        style.configure("CardTitle.TLabel", background=CARD, foreground=PRIMARY, font=(FONT_NAME, 11, "bold"))
        style.configure("Hint.TLabel", background=CARD, foreground=MUTED, font=(FONT_NAME, 9))
        style.configure("PageTitle.TLabel", background=BG, foreground=TEXT, font=(FONT_NAME, 19, "bold"))
        style.configure("PageSub.TLabel", background=BG, foreground=MUTED, font=(FONT_NAME, 9))
        style.configure(
            "TEntry",
            fieldbackground="#FFFFFF",
            foreground=TEXT,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            padding=6,
        )
        style.map(
            "TEntry",
            bordercolor=[("focus", PRIMARY)],
            lightcolor=[("focus", PRIMARY)],
            darkcolor=[("focus", PRIMARY)],
        )
        style.configure(
            "TCombobox",
            fieldbackground="#FFFFFF",
            background="#FFFFFF",
            foreground=TEXT,
            arrowcolor=MUTED,
            bordercolor=BORDER,
            padding=5,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", "#FFFFFF")],
            bordercolor=[("focus", PRIMARY)],
        )
        style.configure("Card.TCheckbutton", background=CARD, foreground=TEXT, font=(FONT_NAME, 9))
        style.map("Card.TCheckbutton", background=[("active", CARD)])
        style.configure(
            "Accent.TButton",
            background=PRIMARY,
            foreground="#FFFFFF",
            borderwidth=0,
            padding=(16, 9),
            font=(FONT_NAME, 10, "bold"),
        )
        style.map(
            "Accent.TButton",
            background=[("active", PRIMARY_DARK), ("disabled", "#A9BDD9")],
            foreground=[("disabled", "#F7FAFF")],
        )
        style.configure(
            "Ghost.TButton",
            background=CARD,
            foreground=PRIMARY,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            borderwidth=1,
            padding=(12, 8),
            font=(FONT_NAME, 9),
        )
        style.map(
            "Ghost.TButton",
            background=[("active", "#EEF4FC"), ("disabled", "#F3F6FA")],
            foreground=[("disabled", "#A6B4C5")],
            bordercolor=[("active", PRIMARY)],
        )
        style.configure(
            "Danger.TButton",
            background=CARD,
            foreground=DANGER,
            bordercolor="#F2C9C7",
            lightcolor="#F2C9C7",
            darkcolor="#F2C9C7",
            borderwidth=1,
            padding=(12, 8),
            font=(FONT_NAME, 9),
        )
        style.map(
            "Danger.TButton",
            background=[("active", "#FDECEC"), ("disabled", "#F3F6FA")],
            foreground=[("disabled", "#C9A5A3")],
        )
        style.configure(
            "Nav.TButton",
            background=SIDEBAR,
            foreground="#B9CCE2",
            borderwidth=0,
            anchor="w",
            padding=(18, 11),
            font=(FONT_NAME, 9),
        )
        style.map(
            "Nav.TButton",
            background=[("active", SIDEBAR_ACTIVE)],
            foreground=[("active", "#FFFFFF")],
        )
        style.configure(
            "NavActive.TButton",
            background=SIDEBAR_ACTIVE,
            foreground="#FFFFFF",
            borderwidth=0,
            anchor="w",
            padding=(18, 11),
            font=(FONT_NAME, 9, "bold"),
        )
        style.map(
            "NavActive.TButton",
            background=[("active", SIDEBAR_ACTIVE)],
            foreground=[("active", "#FFFFFF")],
        )
        style.configure(
            "Vertical.TScrollbar",
            background="#C7D6E6",
            troughcolor=BG,
            bordercolor=BG,
            arrowcolor=MUTED,
        )
        style.map("Vertical.TScrollbar", background=[("active", "#AFC4DD")])
        self.root.option_add("*TCombobox*Listbox.background", CARD)
        self.root.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", PRIMARY)
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#FFFFFF")

    def _build_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        main = tk.Frame(self.root, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(1, weight=1)
        self._build_header(main)
        self.page_container = tk.Frame(main, bg=BG)
        self.page_container.grid(row=1, column=0, sticky="nsew")
        self.page_container.columnconfigure(0, weight=1)
        self.page_container.rowconfigure(0, weight=1)
        self.pages = {}
        self._build_basic_page()
        self._build_model_page()
        self._build_persona_page()
        self._build_meme_page()
        self._build_sticker_page()
        self._build_run_page()
        self._build_log_page()
        self._build_sidebar()
        self.show_page("basic")

    def _build_header(self, parent):
        header = tk.Frame(parent, bg=BG)
        header.grid(row=0, column=0, sticky="ew", padx=30, pady=(22, 14))
        left = tk.Frame(header, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        self.page_title_var = tk.StringVar(value="基础设置")
        self.page_subtitle_var = tk.StringVar(value="")
        ttk.Label(left, textvariable=self.page_title_var, style="PageTitle.TLabel").pack(anchor="w")
        ttk.Label(left, textvariable=self.page_subtitle_var, style="PageSub.TLabel").pack(anchor="w", pady=(2, 0))

        right = tk.Frame(header, bg=BG)
        right.pack(side="right")
        self.status_label = tk.Label(
            right,
            textvariable=self.status_var,
            bg="#E9F0FA",
            fg="#4A6484",
            font=(FONT_NAME, 9, "bold"),
            padx=12,
            pady=6,
        )
        self.status_label.pack(side="left", padx=(0, 14))
        self.start_btn = ttk.Button(right, text="启动接管", style="Accent.TButton", command=self.start_bot)
        self.start_btn.pack(side="left", padx=4)
        self.stop_btn = ttk.Button(right, text="退出接管", style="Danger.TButton", command=self.stop_bot)
        self.stop_btn.pack(side="left", padx=4)
        self.restart_btn = ttk.Button(right, text="重启", style="Ghost.TButton", command=self.restart_bot)
        self.restart_btn.pack(side="left", padx=4)
        ttk.Button(right, text="保存", style="Ghost.TButton", command=self.save_settings_ui).pack(side="left", padx=4)

    def _build_sidebar(self):
        side = tk.Frame(self.root, bg=SIDEBAR, width=214)
        side.grid(row=0, column=0, sticky="nsew")
        side.grid_propagate(False)
        tk.Frame(side, bg=AQUA, height=3).pack(fill="x")

        brand = tk.Frame(side, bg=SIDEBAR)
        brand.pack(fill="x", padx=20, pady=(22, 8))
        tk.Label(
            brand,
            text="大肥鱼",
            font=(FONT_NAME, 21, "bold"),
            fg="#FFFFFF",
            bg=SIDEBAR,
        ).pack(anchor="w")
        tk.Label(
            brand,
            text="傲娇鲸鱼娘 · AI 助手",
            font=(FONT_NAME, 9),
            fg="#8FB3D9",
            bg=SIDEBAR,
        ).pack(anchor="w", pady=(2, 0))
        wave = tk.Canvas(brand, width=172, height=26, bg=SIDEBAR, highlightthickness=0)
        wave.pack(anchor="w", pady=(10, 0))
        wave.create_line(
            0, 18, 22, 8, 44, 18, 66, 8, 88, 18, 110, 8, 132, 18, 154, 8, 172, 18,
            fill=AQUA,
            width=2,
            smooth=True,
        )

        tk.Label(
            side,
            text="功能",
            font=(FONT_NAME, 8, "bold"),
            fg="#6E8BA8",
            bg=SIDEBAR,
        ).pack(anchor="w", padx=22, pady=(18, 6))
        self.nav_buttons = {}
        for key, label in NAV_ITEMS:
            btn = ttk.Button(
                side,
                text=label,
                style="Nav.TButton",
                command=lambda k=key: self.show_page(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self.nav_buttons[key] = btn

        footer = tk.Frame(side, bg=SIDEBAR)
        footer.pack(side="bottom", fill="x", padx=20, pady=18)
        tk.Label(
            footer,
            text="配置保存后\n点「重启」生效",
            font=(FONT_NAME, 8),
            fg="#6E8BA8",
            bg=SIDEBAR,
            justify="left",
        ).pack(anchor="w")
        tk.Button(
            footer,
            text="打开项目目录",
            font=(FONT_NAME, 8),
            fg="#8FB3D9",
            bg=SIDEBAR,
            activebackground=SIDEBAR_ACTIVE,
            activeforeground="#FFFFFF",
            bd=0,
            relief="flat",
            cursor="hand2",
            command=lambda: os.startfile(PROJECT_DIR),
        ).pack(anchor="w", pady=(8, 0))

    def show_page(self, key):
        page = self.pages[key]
        page.tkraise()
        self.root.unbind_all("<MouseWheel>")
        for name, button in self.nav_buttons.items():
            button.configure(style="NavActive.TButton" if name == key else "Nav.TButton")
        title, subtitle = PAGE_META[key]
        self.page_title_var.set(title)
        self.page_subtitle_var.set(subtitle)

    def _new_scroll_page(self, key):
        page = ScrollFrame(self.page_container)
        page.grid(row=0, column=0, sticky="nsew")
        self.pages[key] = page
        return page.inner

    def _new_page(self, key):
        page = tk.Frame(self.page_container, bg=BG)
        page.grid(row=0, column=0, sticky="nsew")
        self.pages[key] = page
        return page

    def _card(self, parent, title, subtitle=None, wide=False):
        outer = tk.Frame(parent, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        outer.pack(fill="x", padx=18, pady=(0, 14))
        inner = tk.Frame(outer, bg=CARD)
        inner.pack(fill="x", padx=18, pady=14)
        ttk.Label(inner, text=title, style="CardTitle.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w"
        )
        row = 1
        if subtitle:
            ttk.Label(
                inner,
                text=subtitle,
                style="Hint.TLabel",
                wraplength=720,
                justify="left",
            ).grid(row=1, column=0, columnspan=4, sticky="w", pady=(2, 8))
            row = 2
        inner.columnconfigure(1, weight=1)
        if wide:
            inner.columnconfigure(3, weight=1)
        return inner, row

    def _actions(self, parent):
        row = tk.Frame(parent, bg=BG)
        row.pack(fill="x", padx=18, pady=(0, 16))
        return row

    def _spacer(self, parent):
        tk.Frame(parent, bg=BG, height=8).pack(fill="x")

    def _entry(self, parent, row, key, label, width=30, show=None, col=0, span=1):
        ttk.Label(parent, text=label, style="Field.TLabel").grid(
            row=row, column=col, sticky="w", padx=(0, 10), pady=6
        )
        var = tk.StringVar()
        ttk.Entry(parent, textvariable=var, width=width, show=show).grid(
            row=row, column=col + 1, columnspan=span, sticky="we", padx=(0, 16), pady=6
        )
        self.v[key] = var

    def _check(self, parent, row, key, label, columnspan=4, col=0):
        var = tk.BooleanVar()
        ttk.Checkbutton(
            parent, text=label, variable=var, style="Card.TCheckbutton"
        ).grid(row=row, column=col, columnspan=columnspan, sticky="w", padx=(0, 10), pady=4)
        self.b[key] = var

    def _combo(self, parent, row, key, label, values, col=0):
        ttk.Label(parent, text=label, style="Field.TLabel").grid(
            row=row, column=col, sticky="w", padx=(0, 10), pady=6
        )
        var = tk.StringVar()
        ttk.Combobox(
            parent, textvariable=var, values=values, state="readonly", width=28
        ).grid(row=row, column=col + 1, sticky="we", padx=(0, 16), pady=6)
        self.v[key] = var

    def _text(self, parent, row, key, label, height=6, span=3):
        ttk.Label(parent, text=label, style="Field.TLabel").grid(
            row=row, column=0, sticky="nw", padx=(0, 10), pady=6
        )
        box = tk.Frame(parent, bg=CARD)
        box.grid(row=row, column=1, columnspan=span, sticky="nsew", padx=(0, 16), pady=6)
        text = tk.Text(
            box,
            height=height,
            wrap="word",
            undo=True,
            bg="#FBFDFF",
            fg=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=PRIMARY,
            font=(FONT_NAME, 10),
            padx=8,
            pady=6,
        )
        scroll = ttk.Scrollbar(box, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.t[key] = text
        return text

    def _build_basic_page(self):
        page = self._new_scroll_page("basic")
        card, row = self._card(
            page,
            "群与身份",
            "群名要和微信里一字不差；群昵称和登录昵称用来确认是机器人小号。",
            wide=True,
        )
        self._text(card, row, "GROUPS", "群名（每行一个）", 4, span=3)
        row += 1
        self._entry(card, row, "BOT_NAMES", "群昵称（逗号分隔）", span=3)
        row += 1
        self._entry(card, row, "EXPECTED_ACCOUNT", "登录昵称校验", span=3)
        row += 1

        card, row = self._card(
            page,
            "触发与追问",
            "叫名字、关键词、@，或者刚聊完接着问，都能触发。",
            wide=True,
        )
        self._combo(card, row, "TRIGGER_MODE", "触发方式", ["smart", "at_or_keyword", "at"])
        self._entry(card, row, "KEYWORDS", "关键词（逗号分隔）", col=2)
        row += 1
        self._check(card, row, "TRIGGER_BY_NAME", "叫名字（不带 @）也触发")
        row += 1
        self._entry(card, row, "FOLLOW_UP_SECONDS", "追问窗口（秒）")
        self._entry(card, row, "FOLLOW_UP_TURNS", "最多追问轮数", col=2)
        row += 1
        self._entry(card, row, "FOLLOW_UP_HINTS", "追问信号（逗号分隔）", span=3)
        row += 1
        ttk.Label(
            card,
            text="smart：名字/关键词/追问都接；at_or_keyword：名字和关键词；at：只认 @。",
            style="Hint.TLabel",
            wraplength=720,
        ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(2, 2))

        card, row = self._card(
            page,
            "回复与图片",
            "默认简洁；需要步骤时最多 5 条、300 字。",
            wide=True,
        )
        self._entry(card, row, "MAX_REPLY_CHARS", "回复字数上限")
        self._entry(card, row, "CONTEXT_SIZE", "上下文条数", col=2)
        row += 1
        self._entry(card, row, "MIN_INTERVAL", "同群回复间隔（秒）")
        self._entry(card, row, "EMPTY_AT_REPLY", "只叫它不说话时", col=2)
        row += 1
        self._check(card, row, "REPLY_WITH_AT", "明确 @ 时回复带 @")
        row += 1
        self._entry(card, row, "IMAGE_FOLLOW_SECONDS", "先叫再发图（秒）")
        self._entry(card, row, "IMAGE_WAIT_SECONDS", "等图时间（秒）", col=2)
        row += 1
        self._check(card, row, "AUTO_CAPTURE_IMAGE_KEY", "图片密钥缺失时自动抓")
        self._spacer(page)

    def _build_model_page(self):
        page = self._new_scroll_page("model")
        card, row = self._card(
            page,
            "文本模型",
            "OpenAI 兼容接口；换服务商时改地址、模型名和 Key。",
            wide=True,
        )
        self._entry(card, row, "LLM_BASE_URL", "接口地址", span=3)
        row += 1
        self._entry(card, row, "LLM_API_KEY", "API Key", show="*", span=3)
        row += 1
        self._entry(card, row, "LLM_MODEL", "文本模型")
        self._entry(card, row, "LLM_TIMEOUT", "超时（秒）", col=2)
        row += 1
        self._entry(card, row, "LLM_TEMPERATURE", "温度 0-2")

        card, row = self._card(
            page,
            "视觉模型",
            "图片和群友表情包识别；留空则和文本模型共用地址与 Key。",
            wide=True,
        )
        self._check(card, row, "ENABLE_VISION", "启用图片 / 表情包识别")
        row += 1
        self._entry(card, row, "VISION_BASE_URL", "视觉接口（留空同上）", span=3)
        row += 1
        self._entry(card, row, "VISION_API_KEY", "视觉 Key（留空同上）", show="*", span=3)
        row += 1
        self._entry(card, row, "VISION_MODEL", "视觉模型")

        card, row = self._card(page, "连接测试", "保存当前配置后，用小请求检查接口是否正常。")
        ttk.Button(
            card,
            text="测试文本模型",
            style="Ghost.TButton",
            command=lambda: self.run_cli("--test-llm", "测试文本模型", True),
        ).grid(row=row, column=0, sticky="w", pady=(0, 4))
        ttk.Button(
            card,
            text="测试视觉模型",
            style="Ghost.TButton",
            command=lambda: self.run_cli("--test-vision", "测试视觉模型", True),
        ).grid(row=row, column=1, sticky="w", pady=(0, 4))
        self._spacer(page)

    def _build_persona_page(self):
        page = self._new_page("persona")
        card = tk.Frame(page, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", padx=18, pady=(14, 4))
        ttk.Label(head, text="人设文本", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(
            head,
            text="重新载入文件",
            style="Ghost.TButton",
            command=self.reload_persona,
        ).pack(side="right")
        ttk.Label(
            card,
            text="以 # 开头的行会被忽略；不要写花括号。保存后点「重启接管」生效。",
            style="Hint.TLabel",
        ).pack(anchor="w", padx=18)
        box = tk.Frame(card, bg=CARD)
        box.pack(fill="both", expand=True, padx=18, pady=(8, 18))
        text = tk.Text(
            box,
            wrap="word",
            undo=True,
            bg="#FBFDFF",
            fg=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=PRIMARY,
            font=(FONT_NAME, 10),
            padx=10,
            pady=8,
        )
        scroll = ttk.Scrollbar(box, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.t["PERSONA"] = text

    def _build_meme_page(self):
        page = self._new_scroll_page("meme")
        card, row = self._card(
            page,
            "更新与注入",
            "面向 20 岁左右、优先 AI 相关；更新会花一次小模型请求。",
            wide=True,
        )
        self._check(card, row, "MEME_ENABLE", "启用联网热梗语料")
        row += 1
        self._entry(card, row, "MEME_REFRESH_HOURS", "更新间隔（小时）")
        self._entry(card, row, "MEME_PROMPT_LIMIT", "进入提示词条数", col=2)
        row += 1
        self._entry(card, row, "MEME_PER_REFRESH", "每轮最多新增")
        self._entry(card, row, "MEME_AI_RATIO", "AI 梗占比 0-1", col=2)
        row += 1

        card, row = self._card(
            page,
            "语料库",
            "旧梗会自动淘汰；只保留最近一段时间还在出现的说法。",
            wide=True,
        )
        self._entry(card, row, "MEME_MAX_ITEMS", "库内最多保留")
        self._entry(card, row, "MEME_TTL_DAYS", "多少天没出现淘汰", col=2)
        row += 1
        self._entry(card, row, "MEME_SOURCE_LIMIT", "普通热榜每源条数")
        self._entry(card, row, "MEME_AI_SOURCE_LIMIT", "AI 源每源条数", col=2)
        row += 1

        actions = self._actions(page)
        ttk.Button(
            actions,
            text="立即更新热梗",
            style="Accent.TButton",
            command=self.update_memes,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="查看当前语料",
            style="Ghost.TButton",
            command=lambda: self.run_cli("--show-memes", "当前热梗语料", False),
        ).pack(side="left", padx=(8, 0))
        ttk.Label(
            actions,
            text="更新后需要重启接管才会进入提示词。",
            style="PageSub.TLabel",
        ).pack(side="left", padx=(14, 0))
        self._spacer(page)

    def _build_sticker_page(self):
        page = self._new_scroll_page("sticker")
        card, row = self._card(
            page,
            "自然发送",
            "普通闲聊回完有概率补一张；正经报错、配置类长回答不补。",
            wide=True,
        )
        self._entry(card, row, "STICKER_CHANCE", "闲聊后补表情概率 0-1")
        self._entry(card, row, "STICKER_MAX_REPLY_CHARS", "超过多少字不补", col=2)
        row += 1

        card, row = self._card(
            page,
            "识别群友表情包",
            "正在跟它聊或刚问过它时，会截图识别；窗口会短暂恢复约 1 秒。",
            wide=True,
        )
        self._check(card, row, "REACT_TO_STICKERS", "识别群友发的表情包")
        row += 1
        self._entry(card, row, "STICKER_REACT_CHANCE", "没在聊时接梗概率 0-1")
        self._entry(card, row, "STICKER_MIN_INTERVAL", "两次接梗最小间隔（秒）", col=2)
        row += 1

        card, row = self._card(
            page,
            "素材库",
            "文件名用「标签_xxx.png」，标签决定发哪一类表情。",
            wide=True,
        )
        ttk.Label(
            card,
            textvariable=self.sticker_count_var,
            style="Hint.TLabel",
        ).grid(row=row, column=0, columnspan=4, sticky="w", pady=(0, 8))
        row += 1
        ttk.Button(
            card,
            text="打开表情包文件夹",
            style="Ghost.TButton",
            command=self.open_stickers,
        ).grid(row=row, column=0, sticky="w")
        ttk.Button(
            card,
            text="刷新数量",
            style="Ghost.TButton",
            command=self.update_sticker_count,
        ).grid(row=row, column=1, sticky="w", padx=(8, 0))
        self._spacer(page)

    def _build_run_page(self):
        page = self._new_scroll_page("run")
        card, row = self._card(
            page,
            "启动行为",
            "打开 APP 时自动接管；关闭窗口会退出接管并恢复微信窗口。",
        )
        ttk.Checkbutton(
            card,
            text="打开 APP 时自动启动接管",
            variable=self.auto_start_var,
            style="Card.TCheckbutton",
        ).grid(row=row, column=0, columnspan=4, sticky="w", pady=4)
        row += 1

        card, row = self._card(
            page,
            "暂停策略",
            "两个开关任意一个打开都会暂停；都关掉才会边用电脑边回。",
            wide=True,
        )
        self._check(card, row, "PAUSE_WHEN_ACTIVE", "用电脑时暂停", 2, col=0)
        self._check(card, row, "PAUSE_READ_WHEN_ACTIVE", "用电脑时连消息也不读", 2, col=2)
        row += 1
        self._entry(card, row, "ACTIVE_IDLE_SECONDS", "空闲多少秒后恢复")
        self._entry(card, row, "POLL_INTERVAL", "检查间隔（秒）", col=2)
        row += 1
        self._check(card, row, "PAUSE_WHEN_FULLSCREEN", "全屏游戏 / 视频时暂停")
        row += 1

        card, row = self._card(
            page,
            "窗口与性能",
            "窗口移到屏幕外发送，回复不弹窗；全屏时可自动暂停。",
            wide=True,
        )
        self._check(card, row, "HIDE_WECHAT_WINDOW", "窗口移到屏幕外发送", 2, col=0)
        self._check(card, row, "LOW_PRIORITY", "降低进程优先级", 2, col=2)
        row += 1
        self._check(card, row, "ONLY_WHEN_UNREAD", "只处理有未读的群", 2, col=0)
        self._check(card, row, "KEEP_WINDOW_WIDE", "启动时临时拉宽窗口", 2, col=2)
        self._spacer(page)

    def _build_log_page(self):
        page = self._new_page("log")
        card = tk.Frame(page, bg=CARD, highlightbackground=BORDER, highlightthickness=1)
        card.pack(fill="both", expand=True, padx=18, pady=(0, 16))
        head = tk.Frame(card, bg=CARD)
        head.pack(fill="x", padx=18, pady=(14, 6))
        ttk.Label(head, text="实时日志", style="CardTitle.TLabel").pack(side="left")
        ttk.Button(
            head,
            text="打开日志文件",
            style="Ghost.TButton",
            command=self.open_log,
        ).pack(side="right")
        box = tk.Frame(card, bg="#0F172A")
        box.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        self.log_text = tk.Text(
            box,
            wrap="word",
            state="disabled",
            bg="#0F172A",
            fg="#DCE7F5",
            insertbackground="#DCE7F5",
            relief="flat",
            font=("Consolas", 9),
            padx=10,
            pady=8,
        )
        scroll = ttk.Scrollbar(box, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def reload_persona(self):
        self.t["PERSONA"].delete("1.0", "end")
        self.t["PERSONA"].insert("1.0", read_text(PERSONA_FILE, ""))

    def open_log(self):
        if os.path.exists(LOG_FILE):
            os.startfile(LOG_FILE)
        else:
            messagebox.showinfo("还没有日志", "启动接管后才会生成日志。")

    def _set_var(self, key, value):
        if key in self.b:
            self.b[key].set(bool(value))
        elif key in self.v:
            if isinstance(value, (list, tuple)):
                self.v[key].set(", ".join(str(x) for x in value))
            else:
                self.v[key].set("" if value is None else str(value))

    def _load_settings(self):
        data = settings_from_config()
        for key in self.b:
            self.b[key].set(bool(data.get(key, False)))
        for key in self.v:
            self._set_var(key, data.get(key, ""))
        self.t["GROUPS"].delete("1.0", "end")
        self.t["GROUPS"].insert("1.0", "\n".join(data.get("GROUPS") or []))
        self.t["PERSONA"].delete("1.0", "end")
        self.t["PERSONA"].insert("1.0", data.get("PERSONA") or "")
        self.auto_start_var.set(self.state.get("auto_start", True))
        self.update_sticker_count()

    def _number(self, key, name, cast, low, high):
        raw = self.v[key].get().strip()
        try:
            value = cast(raw)
        except Exception as exc:
            raise ValueError("{} 要是数字".format(name)) from exc
        if value < low or value > high:
            raise ValueError("{} 要在 {} 到 {} 之间".format(name, low, high))
        return value

    def collect_settings(self, require_key=False):
        data = {}
        groups = split_lines(self.t["GROUPS"].get("1.0", "end"))
        if not groups:
            raise ValueError("至少填一个群名")
        data["GROUPS"] = groups
        for key in LIST_KEYS:
            data[key] = split_words(self.v[key].get())
            if key == "BOT_NAMES" and not data[key]:
                raise ValueError("群昵称不能为空")
        data["EXPECTED_ACCOUNT"] = self.v["EXPECTED_ACCOUNT"].get().strip()
        mode = self.v["TRIGGER_MODE"].get().strip()
        if mode not in ("smart", "at_or_keyword", "at"):
            raise ValueError("触发方式只能是 smart / at_or_keyword / at")
        data["TRIGGER_MODE"] = mode
        for key in BOOL_KEYS:
            data[key] = bool(self.b[key].get())
        for key, (low, high) in FLOAT_KEYS.items():
            data[key] = self._number(key, key, float, low, high)
        for key, (low, high) in INT_KEYS.items():
            data[key] = self._number(key, key, int, low, high)
        for key in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL", "VISION_MODEL"):
            data[key] = self.v[key].get().strip()
        if not data["LLM_BASE_URL"]:
            raise ValueError("接口地址不能为空")
        if not data["LLM_MODEL"]:
            raise ValueError("文本模型不能为空")
        if require_key and not data["LLM_API_KEY"]:
            raise ValueError("API Key 不能为空")
        if data["ENABLE_VISION"] and not data["VISION_MODEL"]:
            raise ValueError("启用图片识别时视觉模型不能为空")
        data["VISION_BASE_URL"] = self.v["VISION_BASE_URL"].get().strip()
        data["VISION_API_KEY"] = self.v["VISION_API_KEY"].get().strip()
        vision_base = (data["VISION_BASE_URL"] or data["LLM_BASE_URL"]).rstrip("/")
        if (
            data["ENABLE_VISION"]
            and vision_base != data["LLM_BASE_URL"].rstrip("/")
            and not data["VISION_API_KEY"]
        ):
            raise ValueError("视觉接口和文本接口不同时，视觉 Key 不能为空")
        data["EMPTY_AT_REPLY"] = self.v["EMPTY_AT_REPLY"].get().strip()
        data["PERSONA"] = self.t["PERSONA"].get("1.0", "end-1c").rstrip() + "\n"
        return data

    def save_settings(self, require_key=False, show_message=True, success_message=True):
        try:
            data = self.collect_settings(require_key=require_key)
            write_settings(data)
        except Exception as exc:
            self._set_status("配置有误")
            if show_message:
                messagebox.showerror("配置有误", str(exc))
            return None
        save_state({"auto_start": bool(self.auto_start_var.get())})
        self.update_sticker_count()
        if success_message:
            messagebox.showinfo("已保存", "配置已保存；重启接管后生效。")
        return data

    def save_settings_ui(self):
        self.save_settings(require_key=False, show_message=True)

    def update_sticker_count(self):
        count, tags = sticker_stats()
        self.sticker_count_var.set("当前 {} 张表情，{} 个标签。".format(count, tags))

    def open_stickers(self):
        if os.path.isdir(STICKERS_DIR):
            os.startfile(STICKERS_DIR)
        else:
            messagebox.showwarning("没有文件夹", "找不到 stickers 文件夹")

    def _set_status(self, text, color="#b45309"):
        self.status_var.set(text)
        self.status_changed_at = time.time()
        palette = {
            "#15803d": ("#E7F7EF", SUCCESS),
            "#b91c1c": ("#FDECEC", DANGER),
            "#b45309": ("#FFF4E5", WARN),
            "#6b7280": ("#E9F0FA", "#4A6484"),
        }
        bg, fg = palette.get(color, ("#E9F0FA", "#4A6484"))
        try:
            self.status_label.configure(bg=bg, fg=fg)
        except Exception:
            pass

    def _update_status(self):
        running = self.proc is not None and self.proc.poll() is None
        if self.proc is None:
            if time.time() - self.status_changed_at >= 6:
                self._set_status("未接管", "#6b7280")
        elif running:
            self._set_status("接管中 · 助手运行中", "#15803d")
        else:
            self._set_status("已退出（代码 {}）".format(self.proc.returncode), "#b91c1c")
        try:
            self.start_btn.configure(state="disabled" if running else "normal")
            self.stop_btn.configure(state="normal" if running else "disabled")
        except Exception:
            pass
        self.root.after(1000, self._update_status)

    def _poll_log(self):
        text = tail_text(LOG_FILE, 200) or "还没有日志。"
        if text != self.last_log:
            self.last_log = text
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.insert("end", text)
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        self.root.after(1000, self._poll_log)

    def start_bot(self, quiet=False):
        if self.proc is not None and self.proc.poll() is None:
            if not quiet:
                messagebox.showinfo("已在运行", "助手已经在接管了。")
            return
        self.quiet_start = quiet
        data = self.save_settings(
            require_key=True, show_message=not quiet, success_message=False
        )
        if data is None:
            return
        try:
            os.remove(STOP_FILE)
        except FileNotFoundError:
            pass
        pid = running_pid() or find_bot_process()
        if pid:
            message = (
                "已经有一个机器人在运行（PID {}）。\n\n"
                "如果你之前用 run.bat 启动，去那个窗口按 Ctrl+C；"
                "或者先在任务管理器结束对应的 python.exe，再点启动接管。"
            ).format(pid)
            self._set_status("已有机器人在运行", "#b91c1c")
            messagebox.showwarning("已有机器人", message)
            return
        try:
            os.remove(PID_FILE)
        except FileNotFoundError:
            pass
        if self.err_handle is not None:
            try:
                self.err_handle.close()
            except Exception:
                pass
            self.err_handle = None
        try:
            self.err_handle = open(ERR_FILE, "ab", buffering=0)
            self.proc = subprocess.Popen(
                [PYTHON, os.path.join(PROJECT_DIR, "bot.py")],
                cwd=PROJECT_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=self.err_handle,
                creationflags=NO_WINDOW,
            )
        except Exception as exc:
            self.proc = None
            if self.err_handle is not None:
                try:
                    self.err_handle.close()
                except Exception:
                    pass
                self.err_handle = None
            self._set_status("启动失败", "#b91c1c")
            if not quiet:
                messagebox.showerror("启动失败", str(exc))
            return
        self._set_status("启动中 · 正在接管", "#b45309")
        self.root.after(2500, self._check_started)

    def _check_started(self):
        if self.proc is None or self.proc.poll() is None:
            return
        code = self.proc.returncode
        self._set_status("已退出（代码 {}）".format(code), "#b91c1c")
        if self.quiet_start:
            return
        detail = (tail_text(LOG_FILE, 60) + "\n" + tail_text(ERR_FILE, 30)).strip()
        messagebox.showerror("助手已退出", "退出码 {}\n\n{}".format(code, detail[-2500:] or "没有日志，检查微信是否登录。"))

    def stop_bot(self, wait=6.0, quiet=False):
        if self.proc is None:
            try:
                os.remove(STOP_FILE)
            except FileNotFoundError:
                pass
            self._set_status("未接管", "#6b7280")
            return
        if self.proc.poll() is not None:
            if self.err_handle is not None:
                try:
                    self.err_handle.close()
                except Exception:
                    pass
                self.err_handle = None
            self.proc = None
            self._set_status("已退出", "#6b7280")
            return
        try:
            with open(STOP_FILE, "w", encoding="utf-8") as f:
                f.write(str(time.time()))
        except Exception:
            pass
        self._set_status("正在退出接管...", "#b45309")
        self.root.update_idletasks()
        deadline = time.time() + max(1.0, wait)
        while time.time() < deadline and self.proc.poll() is None:
            time.sleep(0.2)
        forced = self.proc.poll() is None
        if forced:
            try:
                self.proc.terminate()
                self.proc.wait(timeout=3)
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self._restore_window()
        try:
            os.remove(STOP_FILE)
        except FileNotFoundError:
            pass
        if self.err_handle is not None:
            try:
                self.err_handle.close()
            except Exception:
                pass
            self.err_handle = None
        self.proc = None
        try:
            os.remove(PID_FILE)
        except FileNotFoundError:
            pass
        self._set_status("未接管", "#6b7280")
        if not quiet:
            messagebox.showinfo("已退出", "助手已停止，微信窗口已恢复。")

    def _restore_window(self):
        try:
            import ctypes
            import win32gui
            from wechatauto.uia_driver import WeChatUIA

            uia = WeChatUIA()
            if uia.ensure_window() and uia._win is not None:
                hwnd = uia._win.NativeWindowHandle
                x, y, right, bottom = win32gui.GetWindowRect(hwnd)
                user32 = ctypes.windll.user32
                vx, vy = user32.GetSystemMetrics(76), user32.GetSystemMetrics(77)
                vw, vh = user32.GetSystemMetrics(78), user32.GetSystemMetrics(79)
                on_screen = not (right <= vx or x >= vx + vw or bottom <= vy or y >= vy + vh)
                if not on_screen:
                    win32gui.ShowWindow(hwnd, 9)
                    win32gui.MoveWindow(hwnd, 100, 80, 1100, 800, True)
                    win32gui.ShowWindow(hwnd, 5)
                    win32gui.SetForegroundWindow(hwnd)
            return
        except Exception:
            pass
        try:
            subprocess.run(
                [PYTHON, os.path.join(PROJECT_DIR, "bot.py"), "--fix-window"],
                cwd=PROJECT_DIR,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                creationflags=NO_WINDOW,
            )
        except Exception:
            pass

    def restart_bot(self):
        if self.proc is not None and self.proc.poll() is None:
            self.stop_bot(wait=6, quiet=True)
        self.start_bot()

    def run_cli(self, arg, title, require_key):
        data = self.save_settings(
            require_key=require_key, show_message=True, success_message=False
        )
        if data is None:
            return

        def work():
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            try:
                proc = subprocess.run(
                    [PYTHON, os.path.join(PROJECT_DIR, "bot.py"), arg],
                    cwd=PROJECT_DIR,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300,
                    env=env,
                    creationflags=NO_WINDOW,
                )
                output = (proc.stdout or "") + (proc.stderr or "")
                code = proc.returncode
            except Exception as exc:
                output = str(exc)
                code = -1
            try:
                self.root.after(0, lambda: self._show_output(title, output, code))
            except Exception:
                pass

        self._set_status("执行中：{}".format(title), "#b45309")
        threading.Thread(target=work, daemon=True).start()

    def _show_output(self, title, output, code):
        self._set_status("接管中 · 助手运行中" if self.proc and self.proc.poll() is None else "未接管", "#15803d" if self.proc and self.proc.poll() is None else "#6b7280")
        win = tk.Toplevel(self.root)
        win.title(title)
        win.geometry("820x560")
        win.transient(self.root)
        text = tk.Text(win, wrap="word", undo=False)
        scroll = ttk.Scrollbar(win, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        scroll.pack(side="right", fill="y", padx=(0, 8), pady=8)
        text.insert("1.0", output.strip() or "没有输出（退出码 {}）".format(code))
        text.configure(state="disabled")
        ttk.Button(win, text="关闭", command=win.destroy).pack(pady=(0, 8))

    def update_memes(self):
        self.run_cli("--update-memes", "更新热梗", True)

    def on_close(self):
        save_state({"auto_start": bool(self.auto_start_var.get())})
        if self.proc is not None and self.proc.poll() is None:
            self.stop_bot(wait=6, quiet=True)
        self.root.destroy()


def main():
    try:
        root = tk.Tk()
        AssistantApp(root)
        root.mainloop()
    except Exception:
        import traceback

        detail = traceback.format_exc()
        try:
            with open(os.path.join(PROJECT_DIR, "app.log"), "a", encoding="utf-8") as f:
                f.write(detail + "\n")
        except Exception:
            pass
        try:
            messagebox.showerror("助手启动失败", detail[-2000:])
        except Exception:
            pass


if __name__ == "__main__":
    main()

