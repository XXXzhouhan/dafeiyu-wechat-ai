import json
import logging
import time

import requests

import config

log = logging.getLogger("wxbot")


class SearchError(RuntimeError):
    def __init__(self, message, retryable=False):
        super().__init__(message)
        self.retryable = retryable


class DeepSeekSearch:
    """DeepSeek 官方 Search / Fetch API（和聊天共用同一个 key）。"""

    def __init__(self, base_url=None, api_key=None, timeout=None):
        self.base_url = (
            base_url
            or getattr(config, "SEARCH_BASE_URL", "")
            or config.LLM_BASE_URL
        ).rstrip("/")
        self.api_key = api_key or getattr(config, "SEARCH_API_KEY", "") or config.LLM_API_KEY
        self.timeout = float(
            timeout or getattr(config, "SEARCH_TIMEOUT", 20) or 20
        )
        self.cache_seconds = float(getattr(config, "SEARCH_CACHE_SECONDS", 600) or 0)
        self._cache = {}
        self.session = requests.Session()

    @property
    def available(self):
        return bool(self.api_key)

    def _post(self, path, payload, retries=2):
        if not self.api_key:
            raise SearchError("没有可用的 DeepSeek API Key")
        url = self.base_url + path
        headers = {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }
        last_error = None
        for attempt in range(retries + 1):
            try:
                resp = self.session.post(
                    url,
                    headers=headers,
                    data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                    timeout=self.timeout,
                )
                if resp.status_code in (408, 429, 500, 502, 503, 504):
                    raise SearchError("HTTP %s" % resp.status_code, retryable=True)
                if resp.status_code != 200:
                    raise SearchError(
                        "HTTP %s: %s" % (resp.status_code, resp.text[:200]),
                        retryable=False,
                    )
                return resp.json()
            except SearchError as exc:
                last_error = exc
                if not exc.retryable:
                    break
                if attempt < retries:
                    time.sleep(1.0 * (attempt + 1))
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retries:
                    time.sleep(1.0 * (attempt + 1))
        raise SearchError("搜索请求失败：%s" % last_error)

    def search(self, query, count=6, ori_question="", need_content=False):
        query = (query or "").strip()
        if not query:
            raise SearchError("搜索词为空")
        query = query[:128]
        count = max(1, min(8, int(count or 6)))
        key = ("search", query, count, bool(need_content), (ori_question or "")[:128])
        cached = self._cache.get(key)
        if cached and self.cache_seconds > 0:
            age = time.time() - cached[0]
            if age <= self.cache_seconds:
                return [dict(item) for item in cached[1]]

        payload = {"query": query, "count": count, "need_content": bool(need_content)}
        if ori_question:
            payload["ori_question"] = (ori_question or "")[:128]
        data = self._post("/tools/search", payload)
        results = []
        for item in data.get("results") or []:
            results.append(
                {
                    "title": (item.get("title") or "").strip(),
                    "url": (item.get("url") or "").strip(),
                    "snippet": (item.get("snippet") or "").strip(),
                    "summary": (item.get("summary") or "").strip()[:1600],
                    "date": item.get("date") or "",
                    "site_name": item.get("site_name") or "",
                    "authority": item.get("authority"),
                    "content": (item.get("content") or "").strip()[:8000],
                }
            )
        if self.cache_seconds > 0:
            self._cache[key] = (time.time(), [dict(item) for item in results])
        log.info("联网搜索：%s -> %d 条", query[:60], len(results))
        return results

    def fetch(self, url):
        url = (url or "").strip()
        if not url.startswith(("http://", "https://")):
            raise SearchError("只能抓 http/https 链接")
        data = self._post("/tools/fetch", {"url": url})
        return {
            "url": url,
            "title": (data.get("title") or "").strip(),
            "content": (data.get("content") or "").strip(),
        }
