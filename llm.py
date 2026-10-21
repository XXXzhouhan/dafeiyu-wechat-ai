import base64
import io
import json
import os
import time

import requests


class LLMError(RuntimeError):
    pass


def encode_image(path, max_side=1600):
    """把图片压成 base64。装了 Pillow 就缩放+转 JPEG，没装就原样读。"""
    try:
        from PIL import Image  # type: ignore

        image = Image.open(path).convert("RGB")
        w, h = image.size
        if max(w, h) > max_side:
            ratio = max_side / max(w, h)
            image = image.resize((max(1, int(w * ratio)), max(1, int(h * ratio))))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode(), "image/jpeg"
    except Exception:  # noqa: BLE001
        with open(path, "rb") as f:
            data = f.read()
        ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
        mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"
        return base64.b64encode(data).decode(), mime


class LLM:
    def __init__(self, base_url, api_key, model, timeout=90, temperature=0.4):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.session = requests.Session()

        # DeepSeek 默认开启深度思考（high），群里聊天会又慢又贵，默认关掉。
        # 想开启：设置环境变量 LLM_THINKING=on
        mode = os.getenv("LLM_THINKING", "").strip().lower()
        if mode in ("on", "enabled", "1", "true"):
            self.thinking = "enabled"
        elif mode in ("off", "disabled", "0", "false"):
            self.thinking = "disabled"
        elif "deepseek.com" in self.base_url:
            self.thinking = "disabled"
        else:
            self.thinking = None

    @property
    def endpoint(self):
        return self.base_url + "/chat/completions"

    def chat_message(self, messages, model=None, retries=2, tools=None, tool_choice=None):
        if not self.api_key:
            raise LLMError("API Key 为空，请检查 .env 或 config.py")

        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": self.temperature,
            "stream": False,
        }
        if self.thinking:
            payload["thinking"] = {"type": self.thinking}
        if tools:
            payload["tools"] = tools
            if tool_choice is not None:
                payload["tool_choice"] = tool_choice
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(retries + 1):
            try:
                resp = self.session.post(
                    self.endpoint,
                    headers=headers,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    timeout=self.timeout,
                )
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code != 200:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text[:300]}")

                data = resp.json()
                return data["choices"][0]["message"]
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))

        raise LLMError(f"调用模型失败：{last_error}")

    def chat(self, messages, model=None, retries=2):
        message = self.chat_message(messages, model=model, retries=retries)
        return (message.get("content") or "").strip()

    def history_messages(self, system_prompt, history, bot_name):
        messages = [{"role": "system", "content": system_prompt.format(bot_name=bot_name)}]
        for sender, text in history:
            if sender == bot_name:
                messages.append({"role": "assistant", "content": text})
            else:
                messages.append({"role": "user", "content": f"{sender}：{text}"})
        return messages

    def reply(self, system_prompt, history, question, bot_name):
        messages = self.history_messages(system_prompt, history, bot_name)
        messages.append({"role": "user", "content": question})
        return self.chat(messages)

    def reply_with_image(self, system_prompt, history, question, image_path, bot_name):
        b64, mime = encode_image(image_path)
        text = question or "请说明这张图里是什么，有什么值得注意的信息。"
        content = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
        ]
        messages = self.history_messages(system_prompt, history, bot_name)
        messages.append({"role": "user", "content": content})
        return self.chat(messages)
