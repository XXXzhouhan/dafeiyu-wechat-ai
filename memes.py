import json
import logging
import os
import re
import threading
import time
import urllib.parse
from html import unescape

import requests

import config

log = logging.getLogger("wxbot.memes")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 10

BLOCKED_WORDS = (
    "台独",
    "港独",
    "藏独",
    "疆独",
    "六四",
    "法轮",
    "习近平",
    "共产党",
    "政治",
    "色情",
    "约炮",
    "裸聊",
    "腐剧",
    "女仆",
    "催眠",
    "擦边",
    "成人影片",
    "换脸",
    "软色情",
    "后宫",
)

AI_HINTS = (
    "ai",
    "人工智能",
    "大模型",
    "模型",
    "智能体",
    "agent",
    "提示词",
    "算力",
    "gpu",
    "机器人",
    "赛博",
    "蒸馏",
    "token",
    "幻觉",
    "对齐",
    "开源",
    "chatgpt",
    "deepseek",
    "豆包",
    "claude",
    "gemini",
    "sora",
    "mcp",
    "rag",
    "显卡",
    "越狱",
    "生成式",
    "多模态",
    "具身智能",
    "vibe coding",
    "copilot",
    "cursor",
    "llm",
    "数据标注",
)

BAD_TITLE_HINTS = (
    "登录",
    "注册",
    "下载",
    "广告",
    "优惠",
    "最新视频已上线",
    "快来围观",
    "本视频ai生成",
    "官网",
    "直播回放",
    "招聘",
    "招商",
)

EVENT_WORDS = (
    "开箱",
    "回应",
    "官宣",
    "宣布",
    "曝光",
    "结婚",
    "离婚",
    "分手",
    "去世",
    "夺冠",
    "击败",
    "战胜",
    "开播",
    "定档",
    "杀青",
    "演唱会",
    "红毯",
    "盛典",
    "发布会",
    "涨价",
    "降价",
    "暴跌",
    "上涨",
    "获批",
    "出台",
    "政策",
    "通报",
    "比分",
    "集锦",
    "首秀",
    "新歌",
    "新单",
    "测评",
    "教程",
    "攻略",
    "挑战",
)

FILTER_PROMPT = """你在维护一个中文群聊机器人的“网络热梗语料库”。
这个机器人要和 20 岁左右的年轻人（大学生、刚工作）聊天，最好多懂一点 AI 圈的梗。
下面是刚抓到的实时热榜，以及 B站、Hacker News 上 AI 相关的热梗、黑话、翻车和整活内容。请从中提炼真正能复用的热梗、流行语、固定句式、黑话，最多 {max_items} 条，AI 相关优先。

收词口味：
1. 面向 20 岁左右：校园、职场新人、游戏、二次元、追星、恋爱、发疯、抽象、赛博、AI 圈黑话都可以。
2. 优先 AI 相关：AI味、活人感、vibe coding、赛博许愿、AI算命、AI翻车、AI整活、提示词、Agent、大模型、机器人等。
3. 不收：养生、财经、时政、中年家庭、明星八卦、体育比分、社会新闻、政策、灾难。
4. 不收 AI 擦边短剧、软色情、AI换脸、猎奇血腥；这些不是群聊里能用的梗。

怎么提炼：
1. 必须能离开当前这条热搜，在别的群聊里自然复用；不能复用就跳过。
2. 从标题里提炼更短的核心说法。例如：
   - “【梗知识】AI梗盘点” -> 从中提炼具体的“AI味”“赛博许愿”等说法，不要把栏目名当梗
   - “‘喝大水’火了” -> “喝大水”
   - “被某段画面硬控8秒” -> “硬控”
   - “医学生锐评某综艺” -> 节目内容，不收
   - “某队4:2某队” -> 比赛结果，不收
3. term 尽量 2-12 个字；meaning 一句话解释（不超过 40 字）；usage 给一个 20 岁左右群聊里的短例句（不超过 30 字）。
4. category 只能是 "AI" 或 "生活"；和 AI、大模型、机器人、赛博、提示词相关的一律标 "AI"。
5. 只写你确定真实流行、能解释清楚的说法；不确定就跳过。宁少不编，最多 {max_items} 条，可以只给 0-3 条。
6. 输出前自查：不能复用、只是新闻标题、太像中年号、擦边的，全删。

只输出 JSON 数组，不要 Markdown，不要解释；没有就输出 []。
格式：[{{"term":"...","meaning":"...","usage":"...","category":"AI"}}]

热榜标题：
{titles}
"""


def _get_json(url, referer=""):
    headers = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    if referer:
        headers["Referer"] = referer
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _get_text(url, referer=""):
    headers = {
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if referer:
        headers["Referer"] = referer
    resp = requests.get(url, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _weibo():
    data = _get_json("https://weibo.com/ajax/side/hotSearch", "https://weibo.com/")
    words = []
    for row in (data.get("data") or {}).get("realtime") or []:
        if row.get("is_ad") or row.get("ad_type"):
            continue
        if row.get("word"):
            words.append(row["word"])
    return words


def _baidu():
    data = _get_json("https://top.baidu.com/api/board?platform=wise&tab=realtime", "https://top.baidu.com/")
    words = []

    def walk(node):
        if isinstance(node, dict):
            word = node.get("word")
            if isinstance(word, str):
                words.append(word)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(data)
    return words


def _douyin():
    data = _get_json("https://www.iesdouyin.com/web/api/v2/hotsearch/billboard/word/")
    return [row.get("word") for row in data.get("word_list") or [] if row.get("word")]


def _bilibili():
    data = _get_json(
        "https://api.bilibili.com/x/web-interface/search/square?limit=40",
        "https://www.bilibili.com/",
    )
    rows = ((data.get("data") or {}).get("trending") or {}).get("list") or []
    return [row.get("keyword") or row.get("show_name") for row in rows if row.get("keyword") or row.get("show_name")]


def _toutiao():
    data = _get_json(
        "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
        "https://www.toutiao.com/",
    )
    return [row.get("Title") for row in data.get("data") or [] if row.get("Title")]


def _bilibili_search(keyword):
    url = "https://search.bilibili.com/all?keyword={}&order=totalrank".format(
        urllib.parse.quote(keyword)
    )
    html = _get_text(url, "https://www.bilibili.com/")
    titles = []
    for raw in re.findall(r'title="([^"]{4,80})"', html):
        title = re.sub(r"\s+", " ", unescape(raw)).strip()
        if not title or any(hint in title.lower() for hint in BAD_TITLE_HINTS):
            continue
        titles.append(title)
    return titles


def _hn_ai():
    data = _get_json("https://hn.algolia.com/api/v1/search?query=AI&tags=story&hitsPerPage=25")
    return [row.get("title") for row in data.get("hits") or [] if row.get("title")]


FETCHERS = (
    ("微博", _weibo),
    ("百度", _baidu),
    ("抖音", _douyin),
    ("B站", _bilibili),
    ("头条", _toutiao),
)

AI_FETCHERS = (
    ("B站AI热梗", lambda: _bilibili_search("AI热梗")),
    ("B站AI黑话", lambda: _bilibili_search("AI黑话")),
    ("B站赛博梗", lambda: _bilibili_search("赛博 梗")),
    ("B站AI翻车", lambda: _bilibili_search("AI翻车")),
    ("HN·AI", _hn_ai),
)


def _add_titles(dest, name, titles, limit):
    count = 0
    for title in titles:
        title = re.sub(r"\s+", " ", str(title or "")).strip()
        if len(title) < 2 or len(title) > 80:
            continue
        if any(hint in title.lower() for hint in BAD_TITLE_HINTS):
            continue
        dest.append({"source": name, "title": title})
        count += 1
        if count >= limit:
            break
    log.info("热榜 %s：%d 条", name, count)


def collect_hot(limit_per_source=None, ai_limit_per_source=None):
    limit = int(limit_per_source or getattr(config, "MEME_SOURCE_LIMIT", 25))
    ai_limit = int(
        ai_limit_per_source or getattr(config, "MEME_AI_SOURCE_LIMIT", 15)
    )
    results = []
    for name, fetcher in FETCHERS:
        try:
            titles = fetcher() or []
        except Exception as exc:  # noqa: BLE001
            log.warning("热榜抓取失败（%s）：%s", name, exc)
            continue
        _add_titles(results, name, titles, limit)

    for name, fetcher in AI_FETCHERS:
        try:
            titles = fetcher() or []
        except Exception as exc:  # noqa: BLE001
            log.warning("AI 热梗抓取失败（%s）：%s", name, exc)
            continue
        _add_titles(results, name, titles, ai_limit)

    unique = []
    seen = set()
    for row in results:
        key = _key(row["title"])
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def _key(text):
    return re.sub(r"[\s\u3000“”\"'‘’《》「」【】\[\]()（）:：,，.。!！?？、·~～-]+", "", (text or "").lower())


def _clean_term(text):
    term = str(text or "").strip().strip("“”\"'‘’《》「」【】[]()（）:：,，.。!！?？、")
    return term.replace("{", "（").replace("}", "）").strip()


def _category(row):
    raw = str(row.get("category") or "").strip().upper()
    if raw in ("AI", "人工智能"):
        return "AI"
    text = "{} {} {}".format(
        row.get("term") or "", row.get("meaning") or "", row.get("usage") or ""
    ).lower()
    if any(hint in text for hint in AI_HINTS):
        return "AI"
    return "生活"


def _parse_items(answer):
    text = (answer or "").strip()
    if not text:
        return []
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).replace("```", "").strip()
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end <= start:
        return []
    raw = text[start : end + 1]
    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        raw = re.sub(r",\s*([\]}])", r"\1", raw)
        try:
            data = json.loads(raw)
        except Exception:
            log.warning("热梗结果不是合法 JSON：%s", raw[:200])
            return []
    if not isinstance(data, list):
        return []

    items = []
    seen = set()
    for row in data:
        if not isinstance(row, dict):
            continue
        term = _clean_term(row.get("term"))
        meaning = re.sub(r"\s+", " ", str(row.get("meaning") or "")).strip()[:100]
        usage = re.sub(r"\s+", " ", str(row.get("usage") or "")).strip()[:100]
        meaning = meaning.replace("{", "（").replace("}", "）")
        usage = usage.replace("{", "（").replace("}", "）")
        if not term or len(term) > 16 or not meaning:
            continue
        if any(word in term for word in EVENT_WORDS):
            continue
        joined = term + meaning + usage
        if any(word in joined for word in BLOCKED_WORDS):
            continue
        key = _key(term)
        if not key or key in seen:
            continue
        seen.add(key)
        items.append(
            {
                "term": term,
                "meaning": meaning,
                "usage": usage,
                "category": _category(
                    {"term": term, "meaning": meaning, "usage": usage, "category": row.get("category")}
                ),
            }
        )
    return items


class Corpus:
    def __init__(
        self,
        path=None,
        prompt_limit=None,
        per_refresh=None,
        max_items=None,
        ttl_days=None,
        refresh_hours=None,
    ):
        self.path = path or getattr(config, "MEME_FILE", "memes.json")
        self.prompt_limit = int(
            getattr(config, "MEME_PROMPT_LIMIT", 18) if prompt_limit is None else prompt_limit
        )
        self.per_refresh = int(
            getattr(config, "MEME_PER_REFRESH", 10) if per_refresh is None else per_refresh
        )
        self.max_items = int(
            getattr(config, "MEME_MAX_ITEMS", 300) if max_items is None else max_items
        )
        self.ttl_days = float(
            getattr(config, "MEME_TTL_DAYS", 30) if ttl_days is None else ttl_days
        )
        self.refresh_hours = float(
            getattr(config, "MEME_REFRESH_HOURS", 12) if refresh_hours is None else refresh_hours
        )
        self.ai_ratio = float(getattr(config, "MEME_AI_RATIO", 0.7))
        self.items = []
        self.updated_at = 0.0
        self._prompt = ""
        self._lock = threading.RLock()
        self.load()

    def load(self):
        data = {}
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            pass
        except Exception as exc:  # noqa: BLE001
            log.warning("读取热梗语料失败（%s）：%s", self.path, exc)
        with self._lock:
            raw = data.get("items") if isinstance(data, dict) else None
            self.items = [row for row in (raw or []) if isinstance(row, dict) and row.get("term")]
            for row in self.items:
                row["category"] = _category(row)
            try:
                self.updated_at = float((data or {}).get("updated_at") or 0)
            except (TypeError, ValueError):
                self.updated_at = 0.0
            self._prune()
            self._rebuild_prompt()

    def _prune(self):
        cutoff = time.time() - self.ttl_days * 86400
        keep = []
        for row in self.items:
            try:
                seen = float(row.get("last_seen") or 0)
            except (TypeError, ValueError):
                seen = 0.0
            if seen and seen < cutoff:
                continue
            keep.append(row)
        keep.sort(key=lambda row: float(row.get("last_seen") or 0), reverse=True)
        self.items = keep[: self.max_items]

    def _rebuild_prompt(self):
        if not self.items or self.prompt_limit <= 0:
            self._prompt = ""
            return

        limit = min(self.prompt_limit, len(self.items))
        ai_rows = [row for row in self.items if row.get("category") == "AI"]
        life_rows = [row for row in self.items if row.get("category") != "AI"]
        ai_slots = min(len(ai_rows), max(1, int(round(limit * self.ai_ratio)))) if ai_rows else 0

        selected = list(ai_rows[:ai_slots])
        selected.extend(life_rows[: max(0, limit - len(selected))])
        if len(selected) < limit:
            selected.extend(ai_rows[ai_slots : limit - len(selected) + ai_slots])

        def safe(value):
            return str(value or "").replace("{", "（").replace("}", "）")

        lines = []
        for row in selected:
            tag = "[AI] " if row.get("category") == "AI" else ""
            line = "- {}{}：{}".format(tag, safe(row.get("term")), safe(row.get("meaning")))
            if row.get("usage"):
                line += "（例：{}）".format(safe(row.get("usage")))
            lines.append(line)
        self._prompt = (
            "【最近网上的热梗/热词（面向 20 岁左右，AI 相关优先），只用来理解语境】\n"
            + "\n".join(lines)
            + "\n用法：聊天时可以像年轻人一样自然用，但别硬塞、别为了玩梗影响回答问题；不确定意思就别用，也不用主动解释这些梗。"
        )

    def prompt_block(self):
        with self._lock:
            return self._prompt

    def count(self):
        with self._lock:
            return len(self.items)

    def needs_refresh(self):
        return time.time() - self.updated_at >= self.refresh_hours * 3600

    def merge(self, rows):
        now = time.time()
        added = 0
        with self._lock:
            index = {_key(row.get("term")): row for row in self.items}
            for row in rows:
                term = _clean_term(row.get("term"))
                key = _key(term)
                if not key:
                    continue
                old = index.get(key)
                if old:
                    old["last_seen"] = now
                    old["hits"] = int(old.get("hits") or 1) + 1
                    if row.get("meaning"):
                        old["meaning"] = row["meaning"]
                    if row.get("usage"):
                        old["usage"] = row["usage"]
                    old["category"] = row.get("category") or old.get("category") or "生活"
                    continue
                item = {
                    "term": term,
                    "meaning": row.get("meaning") or "",
                    "usage": row.get("usage") or "",
                    "category": row.get("category") or "生活",
                    "first_seen": now,
                    "last_seen": now,
                    "hits": 1,
                }
                self.items.append(item)
                index[key] = item
                added += 1
            self.updated_at = now
            self._prune()
            self._rebuild_prompt()
            self.save()
        return added

    def save(self):
        data = {"updated_at": self.updated_at, "items": self.items}
        folder = os.path.dirname(os.path.abspath(self.path))
        try:
            os.makedirs(folder, exist_ok=True)
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except Exception as exc:  # noqa: BLE001
            log.error("保存热梗语料失败：%s", exc)


def update(corpus, llm, force=False):
    if not force and not corpus.needs_refresh():
        return 0, 0

    hot = collect_hot()
    if not hot:
        log.warning("所有热榜都没抓到，本次不更新")
        return None

    titles = "\n".join("- {}（{}）".format(row["title"], row["source"]) for row in hot)
    prompt = FILTER_PROMPT.format(max_items=corpus.per_refresh, titles=titles)
    try:
        answer = llm.chat(
            [
                {"role": "system", "content": "你是中文网络热梗编辑，只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ]
        )
    except Exception as exc:  # noqa: BLE001
        log.error("热梗提炼失败：%s", exc)
        return None

    rows = _parse_items(answer)
    added = corpus.merge(rows)
    log.info(
        "热梗更新完成：热榜 %d 条，提炼 %d 条，新增 %d 条，库内 %d 条",
        len(hot),
        len(rows),
        added,
        corpus.count(),
    )
    return added, len(rows)


def status(corpus=None):
    corpus = corpus or Corpus()
    if not corpus.count():
        return "空（运行 python bot.py --update-memes 联网搜集）"
    if not corpus.updated_at:
        when = "更新时间未知"
    else:
        age = time.time() - corpus.updated_at
        if age < 3600:
            when = "%.0f 分钟前" % (age / 60)
        elif age < 86400:
            when = "%.1f 小时前" % (age / 3600)
        else:
            when = "%.1f 天前" % (age / 86400)
    ai_count = sum(1 for row in corpus.items if row.get("category") == "AI")
    return "{} 条（AI {} 条），{}更新（进入提示词 {} 条）".format(
        corpus.count(), ai_count, when, min(corpus.count(), corpus.prompt_limit)
    )


def list_text(corpus=None):
    corpus = corpus or Corpus()
    lines = ["热梗语料：{}".format(status(corpus))]
    for row in corpus.items:
        tag = "[AI] " if row.get("category") == "AI" else ""
        lines.append(
            "- {}{}：{}（例：{}）".format(
                tag, row.get("term"), row.get("meaning") or "", row.get("usage") or ""
            )
        )
    return "\n".join(lines)
