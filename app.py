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
        self.root.geometry("1040x820")
        self.root.minsize(900, 700)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._setup_style()
        self._build_ui()
        self._load_settings()
        self._update_status()
        self._poll_log()
        if self.auto_start_var.get():
            self.root.after(1200, lambda: self.start_bot(quiet=True))

    def _setup_style(self):
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except Exception:
            pass
        try:
            self.root.option_add("*Font", ("Microsoft YaHei UI", 10))
        except Exception:
            pass

    def _build_ui(self):
        header = ttk.Frame(self.root)
        header.pack(fill="x", padx=12, pady=(10, 6))
        ttk.Label(header, text="大肥鱼 · 傲娇鲸鱼娘", font=("Microsoft YaHei UI", 16, "bold")).pack(side="left")
        ttk.Label(header, text="  状态：").pack(side="left", padx=(12, 0))
        self.status_label = tk.Label(header, textvariable=self.status_var, fg="#b45309", font=("Microsoft YaHei UI", 10, "bold"))
        self.status_label.pack(side="left")

        self.start_btn = ttk.Button(header, text="启动接管", command=self.start_bot)
        self.start_btn.pack(side="right", padx=4)
        self.stop_btn = ttk.Button(header, text="退出接管", command=self.stop_bot)
        self.stop_btn.pack(side="right", padx=4)
        self.restart_btn = ttk.Button(header, text="重启接管", command=self.restart_bot)
        self.restart_btn.pack(side="right", padx=4)
        ttk.Button(header, text="保存配置", command=self.save_settings_ui).pack(side="right", padx=4)
        ttk.Button(header, text="打开目录", command=lambda: os.startfile(PROJECT_DIR)).pack(side="right", padx=4)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self._build_basic_tab()
        self._build_model_tab()
        self._build_persona_tab()
        self._build_meme_tab()
        self._build_sticker_tab()
        self._build_run_tab()
        self._build_log()

    def _entry(self, parent, row, key, label, width=36, show=None, col=0):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=8, pady=4)
        var = tk.StringVar()
        ttk.Entry(parent, textvariable=var, width=width, show=show).grid(
            row=row, column=col + 1, sticky="we", padx=8, pady=4
        )
        self.v[key] = var

    def _check(self, parent, row, key, label, columnspan=2, col=0):
        var = tk.BooleanVar()
        ttk.Checkbutton(parent, text=label, variable=var).grid(
            row=row, column=col, columnspan=columnspan, sticky="w", padx=8, pady=3
        )
        self.b[key] = var

    def _combo(self, parent, row, key, label, values, col=0):
        ttk.Label(parent, text=label).grid(row=row, column=col, sticky="w", padx=8, pady=4)
        var = tk.StringVar()
        ttk.Combobox(parent, textvariable=var, values=values, state="readonly", width=33).grid(
            row=row, column=col + 1, sticky="we", padx=8, pady=4
        )
        self.v[key] = var

    def _text(self, parent, row, key, label, height=6):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="nw", padx=8, pady=4)
        box = ttk.Frame(parent)
        box.grid(row=row, column=1, sticky="nsew", padx=8, pady=4)
        text = tk.Text(box, height=height, wrap="word", undo=True)
        scroll = ttk.Scrollbar(box, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.t[key] = text
        return text

    def _build_basic_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="基础")
        tab.columnconfigure(0, weight=1)
        tab.columnconfigure(1, weight=1)

        left = ttk.LabelFrame(tab, text="群和触发")
        left.grid(row=0, column=0, sticky="nsew", padx=(8, 4), pady=8)
        left.columnconfigure(1, weight=1)
        self._text(left, 0, "GROUPS", "群名（每行一个）", 4)
        self._entry(left, 1, "BOT_NAMES", "群昵称（逗号分隔）")
        self._entry(left, 2, "EXPECTED_ACCOUNT", "登录昵称校验")
        self._combo(left, 3, "TRIGGER_MODE", "触发方式", ["smart", "at_or_keyword", "at"])
        self._entry(left, 4, "KEYWORDS", "关键词（逗号分隔）")
        self._check(left, 5, "TRIGGER_BY_NAME", "叫名字（不带 @）也触发")
        self._entry(left, 6, "FOLLOW_UP_SECONDS", "追问窗口（秒）")
        self._entry(left, 7, "FOLLOW_UP_TURNS", "最多追问轮数")
        self._entry(left, 8, "FOLLOW_UP_HINTS", "追问信号（逗号分隔）")

        right = ttk.LabelFrame(tab, text="回复和图片")
        right.grid(row=0, column=1, sticky="nsew", padx=(4, 8), pady=8)
        right.columnconfigure(1, weight=1)
        self._entry(right, 0, "MAX_REPLY_CHARS", "单条回复字数上限")
        self._entry(right, 1, "CONTEXT_SIZE", "上下文条数")
        self._entry(right, 2, "MIN_INTERVAL", "同群回复间隔（秒）")
        self._entry(right, 3, "EMPTY_AT_REPLY", "只叫它不说话时")
        self._check(right, 4, "REPLY_WITH_AT", "明确 @ 时回复带 @")
        self._entry(right, 5, "IMAGE_FOLLOW_SECONDS", "先叫再发图（秒）")
        self._entry(right, 6, "IMAGE_WAIT_SECONDS", "等图时间（秒）")
        self._check(right, 7, "AUTO_CAPTURE_IMAGE_KEY", "图片密钥缺失时自动抓")
        ttk.Label(
            right,
            text="smart：叫名字/关键词/追问都能触发；at_or_keyword：只认名字和关键词；at：只认 @。",
            wraplength=430,
            foreground="#666666",
        ).grid(row=8, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))

    def _build_model_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="模型")
        tab.columnconfigure(1, weight=1)
        self._entry(tab, 0, "LLM_BASE_URL", "接口地址")
        self._entry(tab, 1, "LLM_API_KEY", "API Key", show="*")
        self._entry(tab, 2, "LLM_MODEL", "文本模型")
        self._entry(tab, 3, "LLM_TIMEOUT", "超时（秒）")
        self._entry(tab, 4, "LLM_TEMPERATURE", "温度 0-2")
        self._check(tab, 5, "ENABLE_VISION", "启用图片/表情包识别")
        self._entry(tab, 6, "VISION_BASE_URL", "视觉接口（留空同上方）")
        self._entry(tab, 7, "VISION_API_KEY", "视觉 Key（留空同上方）", show="*")
        self._entry(tab, 8, "VISION_MODEL", "视觉模型")
        buttons = ttk.Frame(tab)
        buttons.grid(row=9, column=0, columnspan=2, sticky="w", padx=8, pady=10)
        ttk.Button(buttons, text="测试文本模型", command=lambda: self.run_cli("--test-llm", "测试文本模型", True)).pack(side="left", padx=4)
        ttk.Button(buttons, text="测试视觉模型", command=lambda: self.run_cli("--test-vision", "测试视觉模型", True)).pack(side="left", padx=4)
        ttk.Label(
            tab,
            text="换智谱/通义/Kimi 时改接口地址、模型名和 Key。视觉模型默认 deepseek-flash。",
            wraplength=760,
            foreground="#666666",
        ).grid(row=10, column=0, columnspan=2, sticky="w", padx=8, pady=4)

    def _build_persona_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="人设")
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=1)
        ttk.Label(
            tab,
            text="以 # 开头的行会被忽略；不要写花括号。改完保存，重启接管后生效。",
            foreground="#666666",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        box = ttk.Frame(tab)
        box.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        text = tk.Text(box, wrap="word", undo=True)
        scroll = ttk.Scrollbar(box, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.t["PERSONA"] = text

    def _build_meme_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="热梗")
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)
        self._check(tab, 0, "MEME_ENABLE", "启用联网热梗语料", 4)
        self._entry(tab, 1, "MEME_REFRESH_HOURS", "更新间隔（小时）", width=18, col=0)
        self._entry(tab, 1, "MEME_PROMPT_LIMIT", "进入提示词条数", width=18, col=2)
        self._entry(tab, 2, "MEME_PER_REFRESH", "每轮最多新增", width=18, col=0)
        self._entry(tab, 2, "MEME_AI_RATIO", "AI 梗占比 0-1", width=18, col=2)
        self._entry(tab, 3, "MEME_MAX_ITEMS", "库内最多保留", width=18, col=0)
        self._entry(tab, 3, "MEME_TTL_DAYS", "多少天没出现淘汰", width=18, col=2)
        self._entry(tab, 4, "MEME_SOURCE_LIMIT", "普通热榜每源条数", width=18, col=0)
        self._entry(tab, 4, "MEME_AI_SOURCE_LIMIT", "AI 源每源条数", width=18, col=2)
        buttons = ttk.Frame(tab)
        buttons.grid(row=5, column=0, columnspan=4, sticky="w", padx=8, pady=10)
        ttk.Button(buttons, text="立即更新热梗", command=self.update_memes).pack(side="left", padx=4)
        ttk.Button(buttons, text="查看当前语料", command=lambda: self.run_cli("--show-memes", "当前热梗语料", False)).pack(side="left", padx=4)
        ttk.Label(
            tab,
            text="热梗面向 20 岁左右、优先 AI 相关；更新后需要重启接管才会进入提示词。",
            wraplength=780,
            foreground="#666666",
        ).grid(row=6, column=0, columnspan=4, sticky="w", padx=8, pady=4)

    def _build_sticker_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="表情包")
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)
        self._entry(tab, 0, "STICKER_CHANCE", "闲聊后补表情概率 0-1")
        self._entry(tab, 1, "STICKER_MAX_REPLY_CHARS", "超过多少字不补")
        self._check(tab, 2, "REACT_TO_STICKERS", "识别群友发的表情包", 4)
        self._entry(tab, 3, "STICKER_REACT_CHANCE", "没在聊时接梗概率 0-1")
        self._entry(tab, 4, "STICKER_MIN_INTERVAL", "两次接梗最小间隔（秒）")
        ttk.Label(tab, textvariable=self.sticker_count_var, foreground="#666666").grid(
            row=5, column=0, columnspan=4, sticky="w", padx=8, pady=6
        )
        buttons = ttk.Frame(tab)
        buttons.grid(row=6, column=0, columnspan=4, sticky="w", padx=8, pady=6)
        ttk.Button(buttons, text="打开表情包文件夹", command=self.open_stickers).pack(side="left", padx=4)
        ttk.Button(buttons, text="刷新数量", command=self.update_sticker_count).pack(side="left", padx=4)
        ttk.Label(
            tab,
            text="识别会截图，微信窗口会短暂恢复约 1 秒；需要视觉模型可用。",
            wraplength=780,
            foreground="#666666",
        ).grid(row=7, column=0, columnspan=4, sticky="w", padx=8, pady=4)

    def _build_run_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="运行")
        tab.columnconfigure(1, weight=1)
        tab.columnconfigure(3, weight=1)
        ttk.Checkbutton(tab, text="打开 APP 时自动启动接管", variable=self.auto_start_var).grid(
            row=0, column=0, columnspan=4, sticky="w", padx=8, pady=4
        )
        self._check(tab, 1, "PAUSE_WHEN_ACTIVE", "用电脑时暂停", 2, col=0)
        self._check(tab, 1, "PAUSE_READ_WHEN_ACTIVE", "用电脑时连消息也不读", 2, col=2)
        self._entry(tab, 2, "ACTIVE_IDLE_SECONDS", "空闲多少秒后恢复", width=18, col=0)
        self._entry(tab, 2, "POLL_INTERVAL", "检查间隔（秒）", width=18, col=2)
        self._check(tab, 3, "PAUSE_WHEN_FULLSCREEN", "全屏游戏/视频时暂停", 4)
        self._check(tab, 4, "HIDE_WECHAT_WINDOW", "窗口移到屏幕外发送", 2, col=0)
        self._check(tab, 4, "LOW_PRIORITY", "降低进程优先级", 2, col=2)
        self._check(tab, 5, "ONLY_WHEN_UNREAD", "只处理有未读的群", 2, col=0)
        self._check(tab, 5, "KEEP_WINDOW_WIDE", "启动时临时拉宽窗口", 2, col=2)
        ttk.Label(
            tab,
            text="两个“用电脑时暂停”开关任意一个打开都会暂停；都关掉才会边用电脑边回。",
            wraplength=780,
            foreground="#666666",
        ).grid(row=6, column=0, columnspan=4, sticky="w", padx=8, pady=8)

    def _build_log(self):
        frame = ttk.LabelFrame(self.root, text="运行日志")
        frame.pack(fill="both", expand=False, padx=12, pady=(0, 10))
        self.log_text = tk.Text(frame, height=10, wrap="word", state="disabled", background="#111827", foreground="#d1d5db")
        scroll = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

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
        try:
            self.status_label.configure(fg=color)
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

