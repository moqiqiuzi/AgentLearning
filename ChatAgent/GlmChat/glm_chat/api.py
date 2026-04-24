import os
import json
import sys
import time
import urllib.request

API_KEY = os.environ.get("ZHIPU_API_KEY", "")
API_URL = "https://open.bigmodel.cn/api/anthropic/v1/messages"

MODELS = {
    "glm-4.7":      "当前默认，能力与速度均衡",
    "glm-5":        "最新旗舰，能力最强，速度较慢",
    "glm-4-plus":   "能力强，速度适中",
    "glm-4-flash":  "速度最快，适合聊天",
    "glm-4-air":    "均衡之选",
    "glm-4-airx":   "air 升级版",
    "glm-4-long":   "超长上下文（128K）",
    "glm-4":        "经典版本",
}

DEFAULT_MODEL = "glm-4.7"
DEFAULT_NAME = "智谱小A"
CACHE_DIR = os.path.join(os.path.expanduser("~"), ".glm_chat_cache")


def _cache_path(persona: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = persona.replace("/", "_").replace("\\", "_").replace(" ", "_")
    return os.path.join(CACHE_DIR, f"{safe}.json")


def _save_cache(persona: str, history: list):
    try:
        with open(_cache_path(persona), "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False)
    except Exception:
        pass


def _load_cache(persona: str) -> list:
    path = _cache_path(persona)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


class ChatSession:
    def __init__(self):
        self.persona_history = {}
        self.history = []
        self.system_prompt = ""
        self.persona_name = DEFAULT_NAME
        self.model = DEFAULT_MODEL
        self.temperature = 0.1
        self.total_input_chars = 0
        self.total_output_chars = 0
        self.start_time = time.time()

    def _stash(self):
        name = self.persona_name
        self.persona_history[name] = list(self.history)
        _save_cache(name, self.history)

    def reset(self):
        self.history.clear()
        self.system_prompt = ""
        self.persona_history.pop(self.persona_name, None)
        path = _cache_path(self.persona_name)
        if os.path.exists(path):
            os.remove(path)
        self.persona_name = DEFAULT_NAME
        self.total_input_chars = 0
        self.total_output_chars = 0
        self.start_time = time.time()

    def set_persona(self, name: str, prompt: str):
        self._stash()
        self.persona_name = name
        self.system_prompt = prompt
        if name in self.persona_history:
            self.history = list(self.persona_history[name])
        else:
            self.history = _load_cache(name)
            self.persona_history[name] = list(self.history)


def call_api_stream(session: ChatSession, prompt: str):
    messages = list(session.history)
    messages.append({"role": "user", "content": prompt})

    body = {
        "model": session.model,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": session.temperature,
        "stream": True,
    }
    if session.system_prompt:
        body["system"] = session.system_prompt

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        method="POST",
    )

    try:
        t0 = time.time()
        full_text = ""
        first_token_time = None

        try:
            resp = urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="ignore")
            print(f"\n[HTTP {e.code}] {error_body}")
            return f"[HTTP {e.code}] {error_body}", 0, 0

        buf = b""
        for chunk in iter(lambda: resp.read(1), b""):
            buf += chunk
            while b"\n" in buf:
                line_bytes, buf = buf.split(b"\n", 1)
                line = line_bytes.decode("utf-8", errors="ignore").strip()

                if not line or line.startswith("event:"):
                    continue
                if not line.startswith("data:"):
                    continue

                data_str = line[len("data:"):].strip()
                if data_str == "[DONE]":
                    break

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if "error" in data:
                    print(f"\n[API 错误] {data['error']}")
                    return f"[API 错误] {data['error']}", 0, 0

                text = _extract_delta(data)
                if text:
                    if first_token_time is None:
                        first_token_time = time.time() - t0
                    full_text += text
                    sys.stdout.write(text)
                    sys.stdout.flush()

        elapsed = time.time() - t0
        print()

        session.history.append({"role": "user", "content": prompt})
        session.history.append({"role": "assistant", "content": full_text})
        session.total_input_chars += len(prompt)
        session.total_output_chars += len(full_text)

        return full_text, elapsed, first_token_time or 0

    except Exception as e:
        print()
        return f"[请求失败] {e}", 0, 0


def _extract_delta(data: dict) -> str:
    if data.get("type") == "content_block_delta":
        delta = data.get("delta", {})
        if delta.get("type") == "text_delta":
            return delta.get("text", "")
    if data.get("type") == "message_delta":
        delta = data.get("delta", {})
        if "text" in delta:
            return delta["text"]
    if "choices" in data:
        choice = data["choices"][0]
        delta = choice.get("delta", {})
        return delta.get("content", "")
    return ""
