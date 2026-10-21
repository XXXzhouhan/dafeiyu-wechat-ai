import argparse
import ctypes
import json
import logging
import logging.handlers
import os
import random
import re
import sys
import tempfile
import threading
import time
import traceback
from collections import deque

import win32gui

import config
import memes
from llm import LLM, LLMError

# 必须在导入 wechatauto 的 gui/uia 之前关掉 OCR
from wechatauto.param import WxParam

WxParam.ENABLE_OCR = False

from wechatauto import db as wxdb  # noqa: E402
from wechatauto.uia_driver import WeChatUIA  # noqa: E402

log = logging.getLogger("wxbot")
PID_FILE = os.path.join(config.BASE_DIR, "bot.pid")


def _pid_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        try:
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


def _claim_pid():
    for _ in range(2):
        try:
            fd = os.open(PID_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            os.close(fd)
            return True
        except FileExistsError:
            try:
                with open(PID_FILE, encoding="utf-8") as f:
                    pid = int(f.read().strip())
            except Exception:
                pid = 0
            if pid and _pid_alive(pid):
                return False
            try:
                os.remove(PID_FILE)
            except OSError:
                return False
        except OSError:
            return False
    return False


def _release_pid():
    try:
        with open(PID_FILE, encoding="utf-8") as f:
            pid = int(f.read().strip())
        if pid == os.getpid():
            os.remove(PID_FILE)
    except Exception:
        pass


BLANK = re.compile(r"[\u2005\u00a0\u200b\u3000\u2002\u2003]")
IMAGE_HINTS = ("图", "截图", "照片", "界面", "屏幕", "画面", "报错", "错误", "日志")
STICKER_HINTS = ("表情包", "发表情", "来个表情", "来张图", "发张图", "发个图", "发图", "斗图", "发个表情")
STICKER_WEIGHTS = {
    "害羞": 9,
    "卖萌": 8,
    "傲娇": 6,
    "御姐": 5,
    "可爱": 5,
    "比心": 4,
    "猫爪": 3,
    "花痴": 3,
    "偷看": 3,
    "开心": 3,
    "玩梗": 3,
    "赞": 2,
    "摸鱼": 2,
    "吃瓜": 2,
    "打工人": 2,
    "日常": 2,
    "吐槽": 1,
    "抽象": 1,
    "搞笑": 1,
    "得意": 1,
    "飘了": 1,
    "早安": 1,
    "无语": 1,
    "嫌弃": 1,
    "拒绝": 1,
    "生气": 1,
    "震惊": 1,
    "哭": 1,
    "晕": 1,
    "吓": 1,
    "求饶": 1,
    "加班": 1,
    "求打赏": 1,
    "加载": 1,
    "干饭": 1,
    "躺平": 1,
}
STICKER_TRIGGERS = ("发个表情", "来个表情", "来张表情", "发表情包", "斗图", "整点表情")


def norm(text):
    return BLANK.sub(" ", text or "").strip()


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def user_idle_seconds():
    try:
        info = _LASTINPUTINFO()
        info.cbSize = ctypes.sizeof(info)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
            return 9999.0
        elapsed = ctypes.windll.kernel32.GetTickCount() - info.dwTime
        return max(0.0, elapsed / 1000.0)
    except Exception:
        return 9999.0


def fullscreen_active():
    try:
        state = ctypes.c_int()
        if ctypes.windll.shell32.SHQueryUserNotificationState(ctypes.byref(state)) != 0:
            return False
        return state.value in (2, 3, 4)
    except Exception:
        return False


def set_low_priority():
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ctypes.windll.kernel32.SetPriorityClass(handle, 0x00004000)
    except Exception:
        pass


def setup_logging():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%H:%M:%S")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        "bot.log", maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    logging.getLogger("wechatauto").setLevel(logging.INFO)


def _seq(row):
    return (
        row.get("sort_seq") or (row.get("create_time") or 0) * 1000 + (row.get("local_id") or 0),
        row.get("local_id") or 0,
    )


class GroupState:
    def __init__(self):
        self.history = deque(maxlen=config.CONTEXT_SIZE)
        self.last_seq = None
        self.last_reply = 0.0
        self.recent_at = {}
        self.recent_question = {}
        self.pending_image = {}
        self.last_image = None
        self.last_bot_at = 0.0
        self.last_bot_sender = ""
        self.follow_left = 0
        self.last_sticker_at = 0.0


class Bot:
    def __init__(self, db, uia, llm, dry_run=False, vision=None):
        self.db = db
        self.uia = uia
        self.llm = llm
        self.vision = vision
        self.media = None
        self.image_key_missing = False
        self.dry_run = dry_run
        self.main_hwnd = 0
        self.orig_rect = None
        self.hidden = False
        self.meme_corpus = None
        self.meme_prompt = ""
        if getattr(config, "MEME_ENABLE", False):
            self.meme_corpus = memes.Corpus()
            self.meme_prompt = self.meme_corpus.prompt_block()
            log.info("热梗语料：%s", memes.status(self.meme_corpus))

        info = db.get_self_info() or {}
        self.self_wxid = info.get("username") or getattr(db, "wxid", "")
        self.self_nick = info.get("nick_name") or ""
        self.names = [n for n in config.BOT_NAMES if n] or [self.self_nick]
        self.bot_name = self.names[0]

        all_groups = {g.get("name"): g.get("username") for g in (db.get_groups() or [])}
        self.groups = {}
        for name in config.GROUPS:
            username = all_groups.get(name)
            if username:
                self.groups[name] = username
            else:
                log.error("数据库里找不到群「%s」", name)
        if not self.groups:
            raise RuntimeError("没有可监听的群")

        self.nick_cache = {}
        self.states = {name: GroupState() for name in self.groups}
        self.stickers = self.load_stickers()
        self.sticker_groups = self.load_sticker_groups()
        if self.stickers:
            log.info("表情包标签：%s", "、".join(sorted(self.stickers)))
        else:
            log.warning("没有表情包文件（stickers/），发图功能不可用")
        self.warm_up()

    def current_prompt(self):
        if self.meme_prompt:
            return config.SYSTEM_PROMPT + "\n\n" + self.meme_prompt
        return config.SYSTEM_PROMPT

    def start_meme_refresh(self):
        if self.meme_corpus is None:
            return

        def worker():
            time.sleep(15)
            meme_llm = LLM(
                config.LLM_BASE_URL,
                config.LLM_API_KEY,
                config.LLM_MODEL,
                config.LLM_TIMEOUT,
                config.LLM_TEMPERATURE,
            )
            while True:
                try:
                    if self.meme_corpus.needs_refresh():
                        log.info("热梗语料过期，开始联网搜集...")
                        result = memes.update(self.meme_corpus, meme_llm)
                        self.meme_prompt = self.meme_corpus.prompt_block()
                        if result is None:
                            log.warning("热梗更新失败，稍后重试")
                        else:
                            added, found = result
                            log.info("热梗更新完成：提炼 %d 条，新增 %d 条", found, added)
                except Exception:
                    log.error("热梗更新异常:\n%s", traceback.format_exc())
                time.sleep(1800)

        threading.Thread(target=worker, daemon=True, name="meme-refresh").start()

    def sender_name(self, wxid):
        if not wxid:
            return "群友"
        if wxid == self.self_wxid:
            return self.bot_name
        if wxid in self.nick_cache:
            return self.nick_cache[wxid]
        try:
            name = self.db.get_nickname(wxid) or ""
        except Exception:
            name = ""
        if not name or name.startswith("wxid_"):
            name = wxid
        self.nick_cache[wxid] = name
        return name

    def clean_content(self, row):
        text = row.get("content") or ""
        sender = row.get("sender_username") or ""
        if sender and text.startswith(sender + ":"):
            text = text[len(sender) + 1 :]
        return norm(text.lstrip("\r\n"))

    def warm_up(self):
        for name, username in self.groups.items():
            rows = self.db.get_messages(username, limit=max(config.CONTEXT_SIZE, 20)) or []
            rows.sort(key=_seq)
            state = self.states[name]
            for row in rows:
                if row.get("type") != "文本":
                    continue
                text = self.clean_content(row)
                if text:
                    state.history.append((self.sender_name(row.get("sender_username")), text))
            if rows:
                state.last_seq = _seq(rows[-1])
            log.info("[%s] 基线 %s，历史 %d 条", name, state.last_seq, len(state.history))

    def is_at_me(self, text):
        for name in self.names:
            if f"@{name}" in text:
                return True
        return False

    def strip_at(self, text):
        for name in self.names:
            text = text.replace("@" + name, "")
        return text.strip()

    def strip_trigger(self, text):
        text = self.strip_at(text).strip()
        words = sorted(set(self.names + list(config.KEYWORDS)), key=len, reverse=True)
        lower = text.lower()
        if lower in {word.lower() for word in words}:
            return ""
        for word in words:
            key = word.lower()
            if key and lower.startswith(key):
                rest = text[len(key) :]
                if rest[:1] in (" ", "\t", ",", "，", ":", "：", "、"):
                    return rest.lstrip(" \t,，:：、").strip()
        return text

    def is_name_trigger(self, text):
        if not getattr(config, "TRIGGER_BY_NAME", True):
            return False
        return any(name and name in text for name in self.names)

    @staticmethod
    def ascii_keyword_hit(text, word):
        pattern = r"(?<![A-Za-z0-9]){}(?![A-Za-z0-9])".format(re.escape(word))
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            return False
        prefix = text[: match.start()].strip()
        if prefix and not prefix.endswith(("，", ",", "。", ".", "！", "!", "？", "?", "：", ":", "、", "@")):
            return False
        rest = text[match.end() :]
        if rest and rest[0] not in (" ", "\t", ",", "，", ".", "。", "!", "！", "?", "？", ":", "：", "、"):
            direct = ("在", "帮", "看", "来", "说", "你", "问", "能", "可以", "怎么", "啥", "什么", "吗", "呢", "呀", "呗")
            if not rest.startswith(direct):
                return False
        return True

    def is_keyword_trigger(self, text):
        for word in config.KEYWORDS:
            if not word:
                continue
            if word.isascii():
                if self.ascii_keyword_hit(text, word):
                    return True
            elif word in text:
                return True
        return False

    @staticmethod
    def looks_like_followup(text):
        text = (text or "").strip()
        if not text or len(text) > 120:
            return False
        if text.startswith(("http://", "https://")):
            return False
        if "?" in text or "？" in text:
            return True
        if text.startswith(
            ("那", "这", "然后", "还有", "继续", "所以", "可是", "但是", "不过", "不对", "不是")
        ):
            return True
        hints = getattr(config, "FOLLOW_UP_HINTS", [])
        for hint in hints:
            if hint == "你":
                if "你" in text and len(text) <= 40:
                    return True
                continue
            if hint and hint in text:
                return True
        return False

    def is_follow_up(self, state, sender_wxid, text):
        if config.TRIGGER_MODE != "smart" or state is None:
            return False
        if state.follow_left <= 0 or not state.last_bot_sender:
            return False
        if sender_wxid != state.last_bot_sender:
            return False
        seconds = float(getattr(config, "FOLLOW_UP_SECONDS", 0) or 0)
        if seconds <= 0 or time.time() - state.last_bot_at > seconds:
            return False
        return self.looks_like_followup(text)

    def trigger_reason(self, text, sender_wxid="", state=None):
        if self.is_at_me(text):
            return "at"
        if config.TRIGGER_MODE in ("at_or_keyword", "smart"):
            if self.is_name_trigger(text):
                return "name"
            if self.is_keyword_trigger(text):
                return "keyword"
            if any(hint in text for hint in STICKER_TRIGGERS):
                return "sticker"
        if self.is_follow_up(state, sender_wxid, text):
            return "follow"
        return ""

    def should_trigger(self, text):
        return bool(self.trigger_reason(text))

    @staticmethod
    def looks_like_image_question(text):
        return any(hint in (text or "") for hint in IMAGE_HINTS)

    @staticmethod
    def wants_sticker(text):
        text = text or ""
        if any(hint in text for hint in STICKER_HINTS):
            return True
        return "表情" in text and any(verb in text for verb in ("发", "来", "整", "斗", "换"))

    def wait_for_image(self, username, sender_wxid, after_seq):
        wait = float(getattr(config, "IMAGE_WAIT_SECONDS", 2.0))
        if wait <= 0:
            return None
        time.sleep(wait)
        try:
            rows = self.db.get_messages(username, limit=30) or []
        except Exception:
            return None
        rows.sort(key=_seq)
        found = None
        for row in rows:
            if _seq(row) <= after_seq:
                continue
            if row.get("sender_username") != sender_wxid:
                continue
            if "图片" in (row.get("type") or ""):
                found = row
        return found

    @staticmethod
    def load_stickers():
        folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stickers")
        mapping = {}
        exts = (".png", ".jpg", ".jpeg", ".gif", ".webp")
        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if not os.path.isfile(path):
                    continue
                if os.path.splitext(name)[1].lower() not in exts:
                    continue
                tag = name.split("_", 1)[0] if "_" in name else os.path.splitext(name)[0]
                mapping.setdefault(tag, []).append(path)
        except FileNotFoundError:
            pass
        return mapping

    @staticmethod
    def load_sticker_groups():
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stickers", "categories.json")
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            return {k: v for k, v in data.items() if isinstance(v, list)}
        except Exception:
            return {}

    @staticmethod
    def extract_sticker(text):
        match = re.search(r"\[表情[:：]\s*([^\]]+)\]", text or "")
        if not match:
            return "", text
        tag = match.group(1).strip()
        clean = re.sub(r"\[表情[:：]\s*[^\]]+\]", "", text).strip()
        return tag, clean

    def send_attachment(self, group, path):
        try:
            win = self.uia._win
            if win is None:
                if not self.uia.ensure_window():
                    return False
                win = self.uia._win
            if win is None:
                return False

            if self.uia.current_chat() != group:
                if not self.uia.open_chat(group):
                    return False
                time.sleep(0.3)
                win = self.uia._win
                if win is None:
                    return False

            if config.HIDE_WECHAT_WINDOW:
                self.hide_window()
            edit = self.uia._chat_input(win)
            if edit is None:
                return False

            from wechatauto.guia import WeChatGUI

            if not WeChatGUI.copy_files_to_clipboard([path]):
                log.error("写入图片剪贴板失败：%s", path)
                return False

            prev = win32gui.GetForegroundWindow()
            edit.SetFocus()
            time.sleep(0.2)
            if win32gui.GetForegroundWindow() != win.NativeWindowHandle:
                log.warning("发送图片：没抢到输入焦点")
                if prev:
                    try:
                        win32gui.SetForegroundWindow(prev)
                    except Exception:
                        pass
                return False

            try:
                edit.SendKeys("{Ctrl}a{Delete}")
                time.sleep(0.1)
                edit.SendKeys("{Ctrl}v")
                time.sleep(1.5)
                edit.SendKeys("{Enter}")
            finally:
                time.sleep(0.2)
                if prev and prev != win.NativeWindowHandle:
                    try:
                        win32gui.SetForegroundWindow(prev)
                    except Exception:
                        pass
            if config.HIDE_WECHAT_WINDOW:
                self.hide_window()
            return True
        except Exception:
            log.error("发送图片异常:\n%s", traceback.format_exc())
            return False

    def should_send_sticker(self, text):
        if not self.stickers:
            return False
        chance = float(getattr(config, "STICKER_CHANCE", 0.0) or 0.0)
        if chance <= 0 or random.random() >= chance:
            return False
        if len(text or "") > int(getattr(config, "STICKER_MAX_REPLY_CHARS", 120)):
            return False
        serious = ("报错", "错误", "代码", "命令", "步骤", "安装", "配置", "风险", "警告", "故障", "教程")
        return not any(word in (text or "") for word in serious)

    def pick_sticker_tag(self, text):
        rules = (
            ("开心", ("哈哈", "笑", "开心", "乐", "逗", "好玩")),
            ("无语", ("无语", "离谱", "服了", "麻了", "绝了")),
            ("赞", ("厉害", "牛", "赞", "优秀", "可以啊")),
            ("摸鱼", ("摸鱼", "躺", "累", "上班", "下班")),
            ("问号", ("?", "？", "啥", "怎么", "啊这")),
            ("吃瓜", ("瓜", "八卦", "听说", "真的假的")),
        )
        for tag, words in rules:
            if tag in self.stickers and any(word in (text or "") for word in words):
                return tag
        tags = list(self.stickers)
        if not tags:
            return ""
        weights = [STICKER_WEIGHTS.get(t, 1) for t in tags]
        return random.choices(tags, weights=weights, k=1)[0]

    def send_sticker(self, group, tag, sender, state, quiet=False):
        candidates = []
        if tag:
            for key, paths in self.stickers.items():
                if tag in key or key in tag:
                    candidates.extend(paths)
            if not candidates and tag in self.sticker_groups:
                for sub in self.sticker_groups[tag]:
                    candidates.extend(self.stickers.get(sub, []))
            if not candidates:
                for group_name, subs in self.sticker_groups.items():
                    if tag in group_name or group_name in tag:
                        for sub in subs:
                            candidates.extend(self.stickers.get(sub, []))
        if not candidates:
            if tag and quiet:
                return False
            candidates = [p for paths in self.stickers.values() for p in paths]

        if not candidates:
            if not quiet:
                self.say(group, "我这儿没表情包，往 stickers 文件夹放几张？", sender, state, force=True)
            return False

        if tag:
            path = random.choice(candidates)
        else:
            weights = []
            for sub, paths in self.stickers.items():
                weights.extend([STICKER_WEIGHTS.get(sub, 1)] * len(paths))
            if len(weights) == len(candidates):
                path = random.choices(candidates, weights=weights, k=1)[0]
            else:
                path = random.choice(candidates)
        if self.dry_run:
            log.info("[dry-run] 发表情包 -> %s", os.path.basename(path))
            return True

        ok = self.send_attachment(group, path)
        if ok:
            log.info("已发表情包：%s", os.path.basename(path))
        else:
            log.error("表情包发送失败：%s", path)
        return ok

    def media_downloader(self):
        if self.media is None:
            from wechatauto import MediaDownloader

            cache = os.path.join(os.path.dirname(os.path.abspath(__file__)), "media_cache")
            os.makedirs(cache, exist_ok=True)
            self.media = MediaDownloader(self.db, save_dir=cache)
        return self.media

    def download_image(self, username, row):
        md = self.media_downloader()
        scan = getattr(md, "_scan_aes_key", None)
        if scan is not None:
            md._scan_aes_key = lambda *a, **k: None
        try:
            return md.download_image(
                username, row.get("local_id"), shard=row.get("shard")
            )
        except Exception as exc:
            text = str(exc)
            if "密钥" in text or "AES" in text or "key" in text.lower():
                self.image_key_missing = True
            log.error("下载图片失败:\n%s", traceback.format_exc())
            return None
        finally:
            if scan is not None:
                md._scan_aes_key = scan

    def capture_key_from_image(self, group, username, row):
        try:
            return self.media_downloader().download_image_original(
                username,
                row.get("local_id"),
                chat_name=group,
                shard=row.get("shard"),
                timeout=25,
            )
        except Exception:
            log.error("自动抓图片密钥失败:\n%s", traceback.format_exc())
            return None

    def capture_sticker(self, group):
        if not getattr(config, "REACT_TO_STICKERS", True):
            return None
        prev = win32gui.GetForegroundWindow()
        was_hidden = self.hidden
        if was_hidden:
            self.restore_window()
            time.sleep(0.25)
        try:
            if not self.uia.ensure_window():
                return None
            if self.uia.current_chat() != group:
                if not self.uia.open_chat(group):
                    return None
                time.sleep(0.5)
            found = self.uia.find_in_message_list(
                lambda cls, name: name == "动画表情"
                or (cls == "mmui::ChatBubbleItemView" and "[动画表情" in name),
                match_last=True,
                max_scrolls=20,
            )
            if not found:
                return None
            _, _, rect = found
            if rect.right - rect.left < 20 or rect.bottom - rect.top < 20:
                return None

            from PIL import ImageGrab
            from wechatauto.msgs.mtype import EmojiMessage

            row_image = ImageGrab.grab(
                bbox=(rect.left, rect.top, rect.right, rect.bottom)
            )
            bubble = EmojiMessage._crop_bubble_from_row(None, row_image, want_left=True)
            if bubble is None or min(bubble.size) < 40:
                bubble = EmojiMessage._content_bbox_crop(row_image)
            if bubble is None or min(bubble.size) < 20:
                return None

            cache = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "media_cache"
            )
            os.makedirs(cache, exist_ok=True)
            path = os.path.join(cache, "emoji_%d.png" % int(time.time() * 1000))
            bubble.save(path)
            return path
        except Exception:
            log.error("表情包截图失败:\n%s", traceback.format_exc())
            return None
        finally:
            if was_hidden:
                self.hide_window()
            if prev:
                try:
                    win32gui.SetForegroundWindow(prev)
                except Exception:
                    pass

    def sticker_in_conversation(self, state, sender_wxid):
        if (
            state.follow_left > 0
            and state.last_bot_sender == sender_wxid
            and time.time() - state.last_bot_at
            <= float(getattr(config, "FOLLOW_UP_SECONDS", 0) or 0)
        ):
            return True
        recent = float(getattr(config, "IMAGE_FOLLOW_SECONDS", 60) or 0)
        return time.time() - state.recent_at.get(sender_wxid, 0) <= recent

    def handle_sticker(self, group, sender, state, sender_wxid, conversing):
        if not getattr(config, "REACT_TO_STICKERS", True):
            return
        if not conversing:
            chance = float(getattr(config, "STICKER_REACT_CHANCE", 0.0) or 0.0)
            if chance <= 0 or random.random() >= chance:
                return
        if self.vision is None:
            if conversing:
                self.say(
                    group,
                    "这个表情包我看不懂，直接说事？",
                    sender,
                    state,
                    sender_wxid=sender_wxid,
                    mention=False,
                )
            return

        path = self.capture_sticker(group)
        if not path:
            log.info("表情包没截到，跳过")
            return
        try:
            log.info("[%s] %s: [表情包]", group, sender)
            answer = self.vision.reply_with_image(
                self.current_prompt(),
                list(state.history),
                "群友发了个表情包。先看懂它表达的情绪或梗；如果上文在问这个表情，就用一两句解释；否则像群友一样接一句（10-30 字）。不要每句都提表情包。",
                path,
                self.bot_name,
            )
        except LLMError as exc:
            log.error("表情包识别失败: %s", exc)
            return
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        answer = (answer or "").strip()
        tag, answer = self.extract_sticker(answer)
        if not answer:
            if tag and self.send_sticker(group, tag, sender, state, quiet=True):
                state.last_bot_at = time.time()
                state.last_bot_sender = sender_wxid
                state.history.append((self.bot_name, "[表情]" + tag))
            return
        if len(answer) > config.MAX_REPLY_CHARS:
            answer = answer[: config.MAX_REPLY_CHARS] + "…"

        state.history.append((self.bot_name, answer))
        sent = self.say(
            group,
            answer,
            sender,
            state,
            force=conversing,
            sender_wxid=sender_wxid,
            mention=False,
        )
        if sent and tag:
            time.sleep(random.uniform(0.6, 1.2))
            if self.send_sticker(group, tag, sender, state, quiet=True):
                state.history.append((self.bot_name, "[表情]" + tag))

    def handle_image(
        self, group, username, row, sender, question, state, sender_wxid="", mention=False
    ):
        if not config.ENABLE_VISION or self.vision is None:
            self.say(
                group,
                "图片我看不了，用文字描述一下？",
                sender,
                state,
                force=True,
                sender_wxid=sender_wxid,
                mention=mention,
            )
            state.history.append((sender, ("[图片] " + question).strip()))
            return

        path = self.download_image(username, row)
        if not path and self.image_key_missing and getattr(config, "AUTO_CAPTURE_IMAGE_KEY", True):
            log.info("图片密钥未就绪，尝试自动打开这张图抓取...")
            path = self.capture_key_from_image(group, username, row)
            if path:
                self.image_key_missing = False
                log.info("图片密钥已抓取，继续识别")
        if not path:
            log.error(
                "图片下载失败：%s/%s（可能还没抓图片密钥，先运行 python bot.py --capture-image-key）",
                username,
                row.get("local_id"),
            )
            self.say(
                group,
                "图片没读出来，稍后再发一次？",
                sender,
                state,
                force=True,
                sender_wxid=sender_wxid,
                mention=mention,
            )
            return

        try:
            log.info("[%s] %s: [图片] %s", group, sender, question or "(无文字)")
            answer = self.vision.reply_with_image(
                self.current_prompt(), list(state.history), question, path, self.bot_name
            )
        except LLMError as exc:
            log.error("视觉模型调用失败: %s", exc)
            return
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        answer = (answer or "").strip()
        tag, answer = self.extract_sticker(answer)
        if not answer:
            if tag and self.send_sticker(group, tag, sender, state, quiet=True):
                state.last_bot_at = time.time()
                state.last_bot_sender = sender_wxid or ""
                state.history.append((self.bot_name, "[表情]" + tag))
            return
        if len(answer) > config.MAX_REPLY_CHARS:
            answer = answer[: config.MAX_REPLY_CHARS] + "…"

        state.history.append((sender, ("[图片] " + question).strip()))
        state.history.append((self.bot_name, answer))
        sent = self.say(
            group,
            answer,
            sender,
            state,
            force=True,
            sender_wxid=sender_wxid,
            mention=mention,
        )
        if sent and tag:
            time.sleep(random.uniform(0.6, 1.2))
            if self.send_sticker(group, tag, sender, state, quiet=True):
                state.history.append((self.bot_name, "[表情]" + tag))

    def poll_once(self):
        for name, username in self.groups.items():
            state = self.states[name]
            rows = self.db.get_messages(username, limit=max(100, config.CONTEXT_SIZE)) or []
            if not rows:
                continue
            rows.sort(key=_seq)
            for row in rows:
                seq = _seq(row)
                if state.last_seq is not None and seq <= state.last_seq:
                    continue
                state.last_seq = seq

                mtype = (row.get("type") or "").strip()
                sender_wxid = row.get("sender_username") or ""
                sender = self.sender_name(sender_wxid)

                if "表情" in mtype:
                    if sender_wxid == self.self_wxid:
                        continue
                    state.history.append((sender, "[表情包]"))
                    now = time.time()
                    cooldown = float(getattr(config, "STICKER_MIN_INTERVAL", 3.0) or 0)
                    if now - state.last_sticker_at < cooldown:
                        continue
                    state.last_sticker_at = now
                    conversing = self.sticker_in_conversation(state, sender_wxid)
                    if conversing:
                        state.follow_left = max(0, state.follow_left - 1)
                    self.handle_sticker(name, sender, state, sender_wxid, conversing)
                    continue

                if "图片" in mtype:
                    if sender_wxid == self.self_wxid:
                        continue
                    now = time.time()
                    state.pending_image[sender_wxid] = (row, now)
                    state.last_image = (row, now, sender_wxid)
                    if now - state.recent_at.get(sender_wxid, 0) <= config.IMAGE_FOLLOW_SECONDS:
                        state.pending_image.pop(sender_wxid, None)
                        state.last_image = None
                        self.handle_image(
                            name,
                            username,
                            row,
                            sender,
                            state.recent_question.get(sender_wxid, ""),
                            state,
                            sender_wxid,
                            False,
                        )
                    continue

                if mtype != "文本":
                    continue

                text = self.clean_content(row)
                if not text:
                    continue
                state.history.append((sender, text))

                if sender_wxid == self.self_wxid:
                    continue

                reason = self.trigger_reason(text, sender_wxid, state)
                if not reason:
                    continue
                if reason == "follow":
                    state.follow_left = max(0, state.follow_left - 1)
                else:
                    state.follow_left = int(getattr(config, "FOLLOW_UP_TURNS", 3) or 0)

                question = self.strip_trigger(text)
                now = time.time()
                state.recent_at[sender_wxid] = now
                state.recent_question[sender_wxid] = question
                mention = reason == "at" and config.REPLY_WITH_AT

                if self.wants_sticker(question):
                    tag = next((t for t in self.stickers if t in question), "")
                    if not tag:
                        tag = next((g for g in self.sticker_groups if g in question), "")
                    if not tag and "恶搞" in question:
                        tag = "搞笑"
                    if self.send_sticker(name, tag, sender, state):
                        state.last_bot_at = time.time()
                        state.last_bot_sender = sender_wxid
                    state.history.append((sender, ("[表情]" + (tag or ""))))
                    continue

                pending = state.pending_image.get(sender_wxid)
                if pending:
                    if now - pending[1] <= config.IMAGE_FOLLOW_SECONDS:
                        state.pending_image.pop(sender_wxid, None)
                        state.last_image = None
                        self.handle_image(
                            name, username, pending[0], sender, question, state, sender_wxid, mention
                        )
                        continue
                    state.pending_image.pop(sender_wxid, None)

                last = state.last_image
                if (
                    last
                    and now - last[1] <= config.IMAGE_FOLLOW_SECONDS
                    and self.looks_like_image_question(question)
                ):
                    state.last_image = None
                    self.handle_image(
                        name, username, last[0], sender, question, state, sender_wxid, mention
                    )
                    continue

                if self.looks_like_image_question(question):
                    found = self.wait_for_image(username, sender_wxid, seq)
                    if found:
                        state.last_image = None
                        state.last_seq = max(state.last_seq, _seq(found))
                        self.handle_image(
                            name, username, found, sender, question, state, sender_wxid, mention
                        )
                        continue

                if not question:
                    if config.EMPTY_AT_REPLY:
                        self.say(
                            name,
                            config.EMPTY_AT_REPLY,
                            sender,
                            state,
                            sender_wxid=sender_wxid,
                            mention=mention,
                        )
                    continue

                if question in ("重置", "/reset", "#重置"):
                    state.history.clear()
                    self.say(
                        name,
                        "上下文已清空",
                        sender,
                        state,
                        sender_wxid=sender_wxid,
                        mention=mention,
                    )
                    continue

                if time.time() - state.last_reply < config.MIN_INTERVAL:
                    log.info("限流跳过")
                    continue

                log.info("[%s] %s: %s", name, sender, question)
                history = list(state.history)[:-1]
                try:
                    answer = self.llm.reply(
                        self.current_prompt(), history, f"{sender}：{question}", self.bot_name
                    )
                except LLMError as exc:
                    log.error("模型调用失败: %s", exc)
                    continue

                answer = (answer or "").strip()
                tag, answer = self.extract_sticker(answer)
                if not answer:
                    if tag and self.send_sticker(name, tag, sender, state, quiet=True):
                        state.last_bot_at = time.time()
                        state.last_bot_sender = sender_wxid
                        state.history.append((self.bot_name, "[表情]" + tag))
                    continue
                if len(answer) > config.MAX_REPLY_CHARS:
                    answer = answer[: config.MAX_REPLY_CHARS] + "…"

                state.history.append((self.bot_name, answer))
                sent = self.say(
                    name,
                    answer,
                    sender,
                    state,
                    sender_wxid=sender_wxid,
                    mention=mention,
                )
                if not sent:
                    continue

                sticker_tag = tag
                if not sticker_tag and self.should_send_sticker(answer):
                    sticker_tag = self.pick_sticker_tag(answer)
                if sticker_tag:
                    time.sleep(random.uniform(0.6, 1.2))
                    if self.send_sticker(name, sticker_tag, sender, state, quiet=True):
                        state.history.append((self.bot_name, "[表情]" + sticker_tag))

    def prepare_background(self):
        if not config.HIDE_WECHAT_WINDOW:
            return
        prev = win32gui.GetForegroundWindow()
        try:
            if self.uia._win is None and not self.uia.ensure_window():
                log.warning("UIA 不可用，回复会走前台发送")
                return
            win = self.uia._win
            if win is None:
                return
            self.main_hwnd = win.NativeWindowHandle
            rect = win32gui.GetWindowRect(self.main_hwnd)
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            if rect[0] <= -30000 or w < 500 or h < 400:
                self.orig_rect = (100, 80, 1100, 800)
            else:
                self.orig_rect = rect

            name = next(iter(self.groups))
            try:
                if self.uia.current_chat() != name:
                    self.uia.open_chat(name)
                    time.sleep(0.3)
            except Exception:
                pass

            self.hide_window()
            if prev and prev != self.main_hwnd:
                try:
                    win32gui.SetForegroundWindow(prev)
                except Exception:
                    pass
            log.info("后台发送已启用：微信窗口在屏幕外，回复不弹窗")
        except Exception:
            log.error("后台发送初始化失败:\n%s", traceback.format_exc())

    def hide_window(self):
        if not self.main_hwnd:
            return
        try:
            rect = self.orig_rect or win32gui.GetWindowRect(self.main_hwnd)
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            if w < 500 or h < 400:
                w, h = 1100, 800
            vx = ctypes.windll.user32.GetSystemMetrics(76)
            vy = ctypes.windll.user32.GetSystemMetrics(77)
            win32gui.MoveWindow(self.main_hwnd, vx - w - 200, vy, w, h, True)
            self.hidden = True
        except Exception:
            pass

    def restore_window(self):
        if not self.hidden or not self.main_hwnd:
            return
        try:
            x, y, right, bottom = self.orig_rect or (100, 80, 1200, 880)
            win32gui.MoveWindow(self.main_hwnd, x, y, right - x, bottom - y, True)
            win32gui.ShowWindow(self.main_hwnd, 5)
            self.hidden = False
            log.info("微信窗口已恢复")
        except Exception:
            pass

    def _foreground_send(self, text, group):
        prev = win32gui.GetForegroundWindow()
        try:
            ok = self.uia.send_text_to(text, group)
        except Exception:
            log.error("前台发送异常:\n%s", traceback.format_exc())
            return False
        if ok and config.HIDE_WECHAT_WINDOW:
            self.hide_window()
        if prev and prev != win32gui.GetForegroundWindow():
            try:
                win32gui.SetForegroundWindow(prev)
            except Exception:
                pass
        return ok

    def background_send(self, text, group):
        if not config.HIDE_WECHAT_WINDOW:
            return self._foreground_send(text, group)
        try:
            prev = win32gui.GetForegroundWindow()
            win = self.uia._win
            if win is None:
                if not self.uia.ensure_window():
                    return self._foreground_send(text, group)
                win = self.uia._win
            if win is None:
                return self._foreground_send(text, group)

            if self.uia.current_chat() != group:
                if not self.uia.open_chat(group):
                    return self._foreground_send(text, group)
                time.sleep(0.3)
                win = self.uia._win
                if win is None:
                    return self._foreground_send(text, group)

            self.hide_window()
            edit = self.uia._chat_input(win)
            if edit is None:
                return self._foreground_send(text, group)
            try:
                value = edit.GetValuePattern()
            except Exception:
                value = None
            if value is None:
                return self._foreground_send(text, group)

            value.SetValue("")
            time.sleep(0.1)
            value.SetValue(text)
            time.sleep(0.2)
            got = (value.Value or "").strip()
            if text.strip()[:20] not in got:
                log.warning("后台发送：文字没落进输入框，改前台发送")
                return self._foreground_send(text, group)

            edit.SetFocus()
            time.sleep(0.2)
            if win32gui.GetForegroundWindow() != win.NativeWindowHandle:
                log.warning("后台发送：没抢到输入焦点，改前台发送")
                if prev:
                    try:
                        win32gui.SetForegroundWindow(prev)
                    except Exception:
                        pass
                return self._foreground_send(text, group)

            try:
                edit.SendKeys("{Enter}")
            finally:
                time.sleep(0.15)
                if prev and prev != win.NativeWindowHandle:
                    try:
                        win32gui.SetForegroundWindow(prev)
                    except Exception:
                        pass
            self.hide_window()
            return True
        except Exception:
            log.error("后台发送异常:\n%s", traceback.format_exc())
            return self._foreground_send(text, group)

    def say(self, group, text, sender, state, force=False, sender_wxid=None, mention=None):
        now = time.time()
        if not force and now - state.last_reply < config.MIN_INTERVAL:
            log.info("限流跳过")
            return False
        state.last_reply = now

        if mention is None:
            mention = config.REPLY_WITH_AT
        if (
            mention
            and sender
            and sender != "群友"
            and not sender.startswith("wxid_")
        ):
            text = f"@{sender} {text}"

        if self.dry_run:
            log.info("[dry-run] -> %s", text)
            state.last_bot_at = time.time()
            state.last_bot_sender = sender_wxid or ""
            return True

        for attempt in (1, 2):
            try:
                if self.background_send(text, group):
                    log.info("已回复")
                    state.last_bot_at = time.time()
                    state.last_bot_sender = sender_wxid or ""
                    return True
                log.warning("发送失败（第 %d 次）", attempt)
            except Exception:
                log.error("发送异常:\n%s", traceback.format_exc())
            time.sleep(1)
        return False

    def run(self):
        interval = max(0.5, float(config.POLL_INTERVAL))
        stop_file = os.path.join(config.BASE_DIR, "bot.stop")
        if os.path.exists(stop_file):
            log.info("启动前收到停止信号，不接管")
            try:
                os.remove(stop_file)
            except OSError:
                pass
            return
        log.info("监听群：%s", "、".join(self.groups))
        log.info("检查间隔：%.1fs（数据库，不碰界面）", interval)
        self.prepare_background()
        self.start_meme_refresh()
        try:
            while True:
                if os.path.exists(stop_file):
                    log.info("收到停止信号，退出接管")
                    break
                pause_active = config.PAUSE_WHEN_ACTIVE or getattr(
                    config, "PAUSE_READ_WHEN_ACTIVE", False
                )
                busy = pause_active and user_idle_seconds() < config.ACTIVE_IDLE_SECONDS
                if busy or (config.PAUSE_WHEN_FULLSCREEN and fullscreen_active()):
                    time.sleep(interval)
                    continue
                try:
                    self.poll_once()
                except Exception:
                    log.error("轮询出错:\n%s", traceback.format_exc())
                time.sleep(interval)
        finally:
            self.restore_window()
            try:
                os.remove(stop_file)
            except OSError:
                pass


def current_system_prompt():
    prompt = config.SYSTEM_PROMPT
    if getattr(config, "MEME_ENABLE", False):
        try:
            block = memes.Corpus().prompt_block()
        except Exception:
            block = ""
        if block:
            prompt += "\n\n" + block
    return prompt


def make_vision():
    if not config.ENABLE_VISION:
        return None
    vkey = config.VISION_API_KEY or (
        config.LLM_API_KEY
        if config.VISION_BASE_URL.rstrip("/") == config.LLM_BASE_URL.rstrip("/")
        else ""
    )
    if not vkey:
        log.warning("没有视觉模型 Key，图片识别已关闭")
        return None
    return LLM(
        config.VISION_BASE_URL,
        vkey,
        config.VISION_MODEL,
        config.LLM_TIMEOUT,
        0.3,
    )


def capture_image_key(db):
    from wechatauto import MediaDownloader

    print("请在微信里点开任意一张图片（查看大图），正在等待抓取图片密钥，最多 120 秒...")
    md = MediaDownloader(db)
    key = md.detect_image_key(refresh=True)
    if key:
        print("图片密钥已抓取并缓存，之后就能识别群里的图片了。")
    else:
        print("没抓到图片密钥。确认微信已登录，并在等待期间点开一张图片后重试。")


def test_vision(vision):
    if vision is None:
        log.error("图片识别未启用，或没有视觉模型 Key")
        return

    from PIL import Image, ImageDraw, ImageFont

    path = os.path.join(tempfile.gettempdir(), "wxvision_test.png")
    img = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 64)
    except Exception:
        font = ImageFont.load_default()
    draw.ellipse([30, 30, 120, 120], fill="red")
    draw.text((160, 140), "大肥鱼 123", fill="black", font=font)
    img.save(path)

    try:
        answer = vision.reply_with_image(
            config.SYSTEM_PROMPT,
            [],
            "图片里写了什么？只回答文字内容。",
            path,
            config.BOT_NAMES[0],
        )
        log.info("视觉模型回复：%s", answer)
    except LLMError as exc:
        log.error("视觉模型调用失败：%s", exc)
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


def warm_model():
    try:
        warm = LLM(
            config.LLM_BASE_URL,
            config.LLM_API_KEY,
            config.LLM_MODEL,
            config.LLM_TIMEOUT,
            config.LLM_TEMPERATURE,
        )
        warm.reply(config.SYSTEM_PROMPT, [], "只回复：好", config.BOT_NAMES[0])
        log.info("模型预热完成")
    except Exception as exc:
        log.debug("模型预热失败：%s", exc)


def test_llm():
    setup_logging()
    llm = LLM(
        config.LLM_BASE_URL,
        config.LLM_API_KEY,
        config.LLM_MODEL,
        config.LLM_TIMEOUT,
        config.LLM_TEMPERATURE,
    )
    log.info("接口：%s  模型：%s", llm.endpoint, llm.model)
    try:
        answer = llm.reply(config.SYSTEM_PROMPT, [], "用一句话介绍你自己", config.BOT_NAMES[0])
    except LLMError as exc:
        log.error("%s", exc)
        return
    log.info("模型回复：%s", answer)


def list_sessions(db):
    mapping = {}
    try:
        mapping.update(db.nickname_map() or {})
    except Exception:
        pass
    try:
        for group in db.get_groups() or []:
            if group.get("username"):
                mapping[group["username"]] = group.get("name") or group["username"]
    except Exception:
        pass

    for row in db.get_sessions(limit=30) or []:
        username = row.get("username") or ""
        name = mapping.get(username) or username
        log.info("%s | %s | 未读 %s", name, username, row.get("unread") or 0)


def doctor(db, uia):
    info = db.get_self_info() or {}
    log.info("=" * 50)
    log.info("账号：%s（%s）", info.get("nick_name") or "?", info.get("username") or "?")
    log.info("数据库密钥：%d 个", len(getattr(db, "_keys", {}) or {}))
    log.info("监听群：%s", "、".join(config.GROUPS))
    log.info(
        "触发方式：%s（关键词：%s；追问 %s 秒 / %s 轮）",
        config.TRIGGER_MODE,
        "、".join(config.KEYWORDS) or "无",
        getattr(config, "FOLLOW_UP_SECONDS", 0),
        getattr(config, "FOLLOW_UP_TURNS", 0),
    )
    if config.ENABLE_VISION:
        log.info("图片识别：已启用（%s）", config.VISION_MODEL)
    else:
        log.info("图片识别：未启用")
    if getattr(config, "MEME_ENABLE", False):
        log.info("热梗语料：%s", memes.status())
    else:
        log.info("热梗语料：未启用")
    key_cache = os.path.join(getattr(db, "workdir", ""), "image_keys.json")
    key_state = "未抓取（图片读不出来时运行 python bot.py --capture-image-key）"
    if os.path.exists(key_cache):
        key_state = "已缓存"
    else:
        try:
            from wechatauto import MediaDownloader

            md = MediaDownloader(db)
            derive = getattr(md, "_derive_cfg_key", None)
            if derive and derive():
                key_state = "可用（自动派生）"
        except Exception:
            pass
    log.info("图片密钥：%s", key_state)

    groups = {g.get("name"): g.get("username") for g in (db.get_groups() or [])}
    for name in config.GROUPS:
        username = groups.get(name)
        if not username:
            log.warning("群「%s」：数据库里没有", name)
            continue
        rows = db.get_messages(username, limit=5) or []
        log.info("群「%s」：%d 条最新消息", name, len(rows))
        for row in rows[-3:]:
            log.info(
                "  %s: %s",
                row.get("sender_username") or "?",
                norm(row.get("content") or "")[:60],
            )

    try:
        ok = uia.ensure_window()
        log.info("UIA 控件树：%s", "可用" if ok else "不可用（发送会失败）")
        if ok:
            log.info("当前会话：%s", uia.current_chat())
    except Exception as exc:
        log.error("UIA 检查失败：%s", exc)

    log.info("=" * 50)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只读消息、只打印回复，不发送")
    parser.add_argument("--test-llm", action="store_true", help="只测试大模型连通性")
    parser.add_argument("--list-sessions", action="store_true", help="打印数据库会话列表")
    parser.add_argument("--doctor", action="store_true", help="体检：账号、数据库、群、UIA")
    parser.add_argument("--fix-window", action="store_true", help="激活 UIA 控件树并恢复微信窗口")
    parser.add_argument("--capture-image-key", action="store_true", help="抓取微信图片 AES 密钥（先点开一张图）")
    parser.add_argument("--test-vision", action="store_true", help="用生成的图片测试视觉模型")
    parser.add_argument("--show-prompt", action="store_true", help="打印系统提示词")
    parser.add_argument("--list-stickers", action="store_true", help="列出表情包分类和数量")
    parser.add_argument("--update-memes", action="store_true", help="联网搜集热梗，更新 memes.json")
    parser.add_argument("--show-memes", action="store_true", help="查看已收集的热梗语料")
    parser.add_argument("--mode", choices=["auto", "listen", "poll"], default="auto")
    args = parser.parse_args()

    setup_logging()
    if getattr(config, "LOW_PRIORITY", False):
        set_low_priority()

    if args.show_prompt:
        name = (config.BOT_NAMES or ["大肥鱼"])[0]
        prompt = current_system_prompt()
        try:
            print(prompt.format(bot_name=name))
        except (KeyError, IndexError):
            print(prompt)
        return

    if args.show_memes:
        print(memes.list_text())
        return

    if args.update_memes:
        corpus = memes.Corpus()
        llm = LLM(
            config.LLM_BASE_URL,
            config.LLM_API_KEY,
            config.LLM_MODEL,
            config.LLM_TIMEOUT,
            config.LLM_TEMPERATURE,
        )
        log.info("开始联网搜集热梗...")
        result = memes.update(corpus, llm, force=True)
        if result is None:
            log.error("更新失败：热榜抓取或模型调用出错，详见上面的日志")
            return
        added, found = result
        log.info("完成：提炼 %d 条，新增 %d 条", found, added)
        print(memes.list_text(corpus))
        return

    if args.test_llm:
        test_llm()
        return

    if args.test_vision:
        test_vision(make_vision())
        return

    if args.list_stickers:
        stickers = Bot.load_stickers()
        groups = Bot.load_sticker_groups()
        if groups:
            for group, subs in groups.items():
                count = sum(len(stickers.get(t, [])) for t in subs)
                print(f"{group}: {count} 张（{'、'.join(subs)}）")
        else:
            for tag, paths in sorted(stickers.items()):
                print(f"{tag}: {len(paths)}")
        return

    db = wxdb.WeChatDB()
    info = db.get_self_info() or {}
    nick = info.get("nick_name") or ""
    log.info("账号：%s", nick or "未知")

    expected = getattr(config, "EXPECTED_ACCOUNT", "")
    if expected and nick != expected:
        log.error("当前登录的微信是「%s」，不是机器人小号「%s」", nick, expected)
        log.error("已停止。请切回小号，或改 config.py 的 EXPECTED_ACCOUNT")
        return

    if args.list_sessions:
        list_sessions(db)
        return

    if args.capture_image_key:
        capture_image_key(db)
        return

    uia = WeChatUIA()

    if args.fix_window:
        ok = uia.ensure_window()
        if ok and uia._win is not None:
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
        log.info("UIA 控件树：%s", "已就绪" if ok else "激活失败")
        return

    if args.doctor:
        doctor(db, uia)
        return

    if not config.GROUPS or not config.BOT_NAMES:
        log.error("请先在 config.py 里填好 GROUPS 和 BOT_NAMES")
        return

    if not _claim_pid():
        log.error("已经有一个机器人在运行（%s），先停掉它再启动", PID_FILE)
        return

    try:
        llm = LLM(
            config.LLM_BASE_URL,
            config.LLM_API_KEY,
            config.LLM_MODEL,
            config.LLM_TIMEOUT,
            config.LLM_TEMPERATURE,
        )

        vision = make_vision()
        log.info("模型预热中（第一次请求可能较慢）")
        threading.Thread(target=warm_model, daemon=True).start()

        bot = Bot(db, uia, llm, dry_run=args.dry_run, vision=vision)
        try:
            bot.run()
        except KeyboardInterrupt:
            log.info("退出")
    finally:
        _release_pid()


if __name__ == "__main__":
    main()
