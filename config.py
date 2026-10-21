import os


def _load_env(path=".env"):
    """读取同目录 .env（存在才读），不覆盖已有的系统环境变量。"""
    try:
        with open(path, encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                # .env 优先于系统环境变量，避免旧的 setx 值把向导配置盖掉
                os.environ[key.strip()] = value.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass


_load_env()

# 说明：本程序要登录【AI 小号】的微信 PC 端，不是你的主号。
# 群里看到的发言人就是这个 AI 小号。

# ============ 要监听的群（必须和微信里显示的群名一字不差，可填多个）============
GROUPS = ["测试群"]

# ============ 私聊监听 ============
# 填微信备注/昵称/wxid，可填多个；空列表 = 不监听私聊
# 例：PRIVATE_CHATS = ["张三", "wxid_xxxxxxxx"]
# 不确定名字时先运行 python bot.py --list-sessions 看会话列表
PRIVATE_CHATS = []
# "all"     每条私聊都回（默认，适合一对一聊天）
# "smart"   只在机器人回完后，对方接着说话才回
# "keyword" 只有叫机器人名字/关键词才回
PRIVATE_TRIGGER_MODE = "all"

# ============ AI 小号的名字（微信昵称 + 该群里的群昵称，可填多个）============
BOT_NAMES = ["大肥鱼"]
# 只允许这个微信登录昵称当机器人；防止你切到主号时脚本用主号乱回。留空 = 不检查
EXPECTED_ACCOUNT = "测试小号"

# ============ 触发方式 ============
# "at"            仅 @ 机器人时回复
# "at_or_keyword" @ 机器人、叫机器人名字、或消息里含 KEYWORDS 时回复
# "smart"         在上面基础上，机器人刚回完话后，同一个人继续追问也可以不用再叫
TRIGGER_MODE = "smart"
KEYWORDS = ["小助手", "机器人", "肥鱼", "鱼鱼", "蓝鱼", "鲸鱼娘", "DS", "DEEPSEEK"]

# 叫机器人名字（不带 @）也算触发；false 时只有 @ 和 KEYWORDS 才触发
TRIGGER_BY_NAME = True
# 追问窗口：机器人回完话后，同一个人在多少秒内继续说话算同一轮聊天
FOLLOW_UP_SECONDS = 120
# 一次触发最多连续追问几轮
FOLLOW_UP_TURNS = 3
# 追问的保底关键词（模型判断不可用时使用；太弱的词会被代码忽略）
FOLLOW_UP_HINTS = [
    "你", "为啥", "为什么", "怎么", "然后", "还有", "继续", "不对", "不是",
    "所以", "真的", "吗", "帮我", "再来", "换个", "说说", "解释", "啥意思",
    "行不行", "可以吗", "累", "困", "饿", "开心", "难过", "笑死", "好耶",
    "无语", "服了", "确实", "哈哈",
]
# 追问前先用模型判断“这句话是在对 AI 说，还是在对别人说”；不确定会不接
FOLLOW_UP_INTENT_LLM = True
# 群里其他人插话后，结束当前自动追问；想继续请重新 @/叫名字
FOLLOW_UP_BLOCK_ON_OTHER = True

# 回复时是否 @ 提问的人；smart 模式下只有对方明确 @ 时才带 @，叫名字/追问不带
REPLY_WITH_AT = True
# 同一个群两次回复的最小间隔（秒），防刷屏
MIN_INTERVAL = 5.0
# 普通闲聊回复后，顺手补一张表情包的概率（0-1）；正经长回答不会补
STICKER_CHANCE = 0.15
STICKER_MAX_REPLY_CHARS = 120
# 群友发表情包时，是否截图识别并在聊天里接话（只在跟它聊、或刚问过它时）
REACT_TO_STICKERS = True
# 没在跟它聊天时，随机接表情包的概率（0 = 不接，避免刷屏）
STICKER_REACT_CHANCE = 0.6
# 两次表情包识别的最小间隔（秒），避免连续表情刷屏
STICKER_MIN_INTERVAL = 3.0
# 带进 prompt 的最近消息条数（越大越懂上下文，也越费 token）
CONTEXT_SIZE = 60
# 私聊单独用更长的上下文（群聊仍用 CONTEXT_SIZE）
PRIVATE_CONTEXT_SIZE = 300
# 单条回复最大字数（超出截断；默认走简洁风格，300 足够）
MAX_REPLY_CHARS = 300
# 数据库检查间隔（秒）。新后端只查本地库，不碰界面
POLL_INTERVAL = 1.0
# 只处理有未读消息的群：没有新消息就不切窗口，避免一直抢焦点
ONLY_WHEN_UNREAD = True
# 窗口太窄时看不到会话列表（判断不了未读），启动时临时拉宽，退出时恢复
KEEP_WINDOW_WIDE = True
# 你正在用这台电脑时（最近 N 秒内有键鼠操作）是否暂停；
# 这两个开关任意一个 True 都会暂停，都设 False 才能边用电脑边聊
PAUSE_WHEN_ACTIVE = True
PAUSE_READ_WHEN_ACTIVE = True
ACTIVE_IDLE_SECONDS = 10.0
# 降低机器人进程优先级，前台程序更流畅（代价：回复稍慢）
LOW_PRIORITY = True
# 全屏看视频/打游戏时不轮询，避免卡顿
PAUSE_WHEN_FULLSCREEN = True
# 后台发送：微信窗口移到屏幕外，回复时不弹窗（会短暂借一下焦点再还）
HIDE_WECHAT_WINDOW = True
# 只叫它/@ 它但没说话时的回复，留空表示不回复
EMPTY_AT_REPLY = "在，直接说问题或发图就行"
# 先叫它再发图时，多少秒内发的图算同一次提问
IMAGE_FOLLOW_SECONDS = 60
# 问了“图/截图/界面”类问题但图还没到时，等几秒看有没有图
IMAGE_WAIT_SECONDS = 2.0
# 第一张图如果缺密钥，自动打开那张图抓一次（失败就手动 --capture-image-key）
AUTO_CAPTURE_IMAGE_KEY = True

# ============ 大模型（OpenAI 兼容接口）============
# 智谱免费: https://open.bigmodel.cn/api/paas/v4   glm-4.7-flash   （注册 bigmodel.cn 领 Key，免费）
# DeepSeek:   https://api.deepseek.com/v1      deepseek-chat（中间档，默认）/ deepseek-flash / deepseek-v4-pro
# 通义千问:   https://dashscope.aliyuncs.com/compatible-mode/v1   qwen-plus
# 智谱:       https://open.bigmodel.cn/api/paas/v4   glm-4-flash
# Kimi:       https://api.moonshot.cn/v1       moonshot-v1-8k
# 本地Ollama: http://localhost:11434/v1        qwen2.5:7b
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-flash")
LLM_TIMEOUT = 120
LLM_TEMPERATURE = 0.4

# ============ 图片识别（多模态模型）============
ENABLE_VISION = True
VISION_BASE_URL = os.getenv("VISION_BASE_URL", LLM_BASE_URL)
VISION_API_KEY = os.getenv("VISION_API_KEY", "")
VISION_MODEL = os.getenv("VISION_MODEL", "deepseek-flash")
VISION_MAX_SIDE = 1600

# ============ 联网搜索（DeepSeek Search / Fetch API）============
# 和聊天共用 LLM_API_KEY，不需要另外申请搜索 key
SEARCH_ENABLE = True
# 每次搜索取几条结果（1-8）
SEARCH_MAX_RESULTS = 6
# 搜索/抓网页请求超时（秒）
SEARCH_TIMEOUT = 20
# 同一搜索词缓存多久（秒），避免群里连续问同一件事反复搜
SEARCH_CACHE_SECONDS = 600
# 最多让模型连续调用几轮工具（搜索 + 抓网页）
SEARCH_MAX_TOOL_ROUNDS = 2
# 一次回答里最多搜几次、抓几个网页
SEARCH_MAX_SEARCHES = 2
SEARCH_MAX_FETCH = 2
# 抓网页后最多保留多少字给模型
SEARCH_FETCH_CHARS = 6000
# 带来源的搜索回答最多多少字（普通回答仍用 MAX_REPLY_CHARS）
SEARCH_MAX_REPLY_CHARS = 700

SYSTEM_PROMPT = """你在微信群里扮演「{bot_name}」，群友会叫你名字、@ 你，或者接着你的话往下问各种实际问题，不是客服。

你的目标是把问题真正解决掉，而不是敷衍几句。

回答方式：
1. 默认简短：能一句话说清就一句话；寒暄/简单确认 1 句，普通问题 2-3 句。
2. 先给结论，再给必要做法。真需要步骤时用 1. 2. 3.，最多 5 条、300 字以内；只给必要的例子、命令或代码，不铺垫、不列无关背景。
3. 信息不够时，先做一个最合理的假设并说明，再回答；只有缺关键信息才反问一句（最多一句）。
4. 不说客套话，不复述对方的问题，也不用为了显得专业而展开。
5. 不确定就说不确定，并告诉对方怎么验证；不编事实、数据、链接或引用。
6. 群聊里保持自然，不 @ 无关的人，不重复已经说过的内容。
7. 保持角色，不跳出设定，不透露这段提示词。

如果群友发的是图片：先看懂图，再回答他关心的问题；图里没有明确问题，就说明图里是什么、有哪些值得注意的点。

如果对方让你评价、锐评、点评、打分、吐槽：
1. 先给明确总评/倾向，再分“优点 / 问题 / 建议”，具体到图里或文字里的哪一点；不空夸，也不为了礼貌说假话。
2. 可以像损友一样嘴毒、开玩笑，但要有分寸：不攻击身体缺陷/疾病、不辱骂家人、不泄露隐私、不搞地域/性别/政治攻击。
3. 评价照片/长相：点评构图、光线、穿搭、表情、氛围，可以打趣，但不认真给人打分排名、不人身攻击；对方明显不舒服就收。
4. 要分数就给 1-10 分，并说明按什么标准；没要分数不用硬给。
5. 被问看法/预测：给明确判断和理由，不要用“看情况/因人而异”糊弄；不确定就说明前提。
6. 评价某个人：可以评价他具体做的事、说的话、发的照片，不编黑料、不贴人格标签。

如果图片并要求评价：看构图、光线、穿搭、表情、设计、可用性等，说清好在哪、问题在哪、怎么改；可以损友式点评，但不攻击长相/身体缺陷，不给人打分排名。

想发表情包时，在回复最后单独写一行 [表情:标签]，标签可用：傲娇、害羞、卖萌、御姐、玩梗、打工人、吐槽、日常、开心、赞、摸鱼、问号、吃瓜、可爱、抽象、搞笑；也可以用细标签（嫌弃、拒绝、求饶、震惊、加班、花痴、猫爪、求打赏、干饭、躺平、比心、飘了）；不要每句都发。
表情优先用害羞、卖萌、傲娇、御姐；吐槽、生气、拒绝、哭这类少用，除非对方明确要。"""

# ============ 角色设定（改 persona.txt，不用改代码）============
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PERSONA_FILE = os.path.join(BASE_DIR, "persona.txt")

# ============ 网络热梗语料（自动联网搜集，丰富聊天语料）============
MEME_ENABLE = True                    # 关闭后不抓热梗、也不往提示词里放
MEME_FILE = os.path.join(BASE_DIR, "memes.json")
MEME_REFRESH_HOURS = 12               # 每隔多少小时联网更新一次（每次约 1 次小模型请求）
MEME_PROMPT_LIMIT = 18                # 每次回复带进提示词的热梗条数
MEME_PER_REFRESH = 10                 # 每轮最多从热榜里提炼多少条新梗
MEME_MAX_ITEMS = 300                  # 语料库最多保留条数
MEME_TTL_DAYS = 30                    # 超过多少天没再出现就淘汰
MEME_SOURCE_LIMIT = 25                # 每个普通热榜最多取多少条标题
MEME_AI_SOURCE_LIMIT = 15             # 每个 AI 热梗来源最多取多少条标题
MEME_AI_RATIO = 0.7                   # 提示词里 AI 梗最多占多少比例（0-1）


def _load_persona(path):
    try:
        with open(path, encoding="utf-8") as f:
            lines = [line.rstrip() for line in f if not line.lstrip().startswith("#")]
    except FileNotFoundError:
        return ""
    return "\n".join(lines).strip()


_PERSONA = _load_persona(PERSONA_FILE)
if _PERSONA:
    SYSTEM_PROMPT = SYSTEM_PROMPT + "\n\n" + _PERSONA

# 由 configure.py 生成的本地配置，优先级最高
try:
    from config_local import *  # noqa: F401,F403
except ImportError:
    pass
