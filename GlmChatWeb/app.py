import json
import time
import queue
import threading
from flask import Flask, render_template, request, Response, jsonify, send_from_directory
from flask_cors import CORS
import urllib.request
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "GlmChat"))
from glm_chat.personas import PERSONAS, PERSONA_TAGS, PERSONA_ALIASES
from glm_chat.api import MODELS, API_KEY, API_URL, DEFAULT_MODEL

app = Flask(__name__)
CORS(app)

sessions = {}
sessions_lock = threading.Lock()


def get_session(sid: str) -> dict:
    with sessions_lock:
        if sid not in sessions:
            sessions[sid] = {
                "history": [],
                "system_prompt": "",
                "persona_name": "智谱小A",
                "model": DEFAULT_MODEL,
                "temperature": 0.1,
            }
        return sessions[sid]


def do_stream_api(messages: list, system: str, model: str, temperature: float, q: queue.Queue):
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": temperature,
        "stream": True,
    }
    if system:
        body["system"] = system

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
        resp = urllib.request.urlopen(req)
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
                    q.put({"done": True})
                    return

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if "error" in data:
                    q.put({"error": str(data["error"])})
                    return

                text = _extract_delta(data)
                if text:
                    q.put({"text": text})

        q.put({"done": True})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        q.put({"error": f"HTTP {e.code}: {body}"})
    except Exception as e:
        q.put({"error": str(e)})


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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/personas", methods=["GET"])
def list_personas():
    result = []
    for name, prompt in PERSONAS.items():
        result.append({
            "name": name,
            "tag": PERSONA_TAGS.get(name, ""),
            "prompt": prompt,
        })
    return jsonify(result)


@app.route("/api/models", methods=["GET"])
def list_models():
    sid = request.args.get("sid", "default")
    session = get_session(sid)
    return jsonify({
        "models": {k: v for k, v in MODELS.items()},
        "current": session["model"],
    })


@app.route("/api/session", methods=["GET"])
def get_session_info():
    sid = request.args.get("sid", "default")
    session = get_session(sid)
    return jsonify({
        "persona": session["persona_name"],
        "model": session["model"],
        "temperature": session["temperature"],
    })


@app.route("/api/config", methods=["POST"])
def set_config():
    data = request.json or {}
    sid = data.get("sid", "default")
    session = get_session(sid)

    if "persona" in data:
        name = data["persona"]
        if name in PERSONAS:
            session["persona_name"] = name
            session["system_prompt"] = PERSONAS[name]
    if "model" in data and data["model"] in MODELS:
        session["model"] = data["model"]
    if "temperature" in data:
        val = float(data["temperature"])
        if 0 <= val <= 1:
            session["temperature"] = val

    return jsonify({"ok": True})


@app.route("/api/clear", methods=["POST"])
def clear_history():
    data = request.json or {}
    sid = data.get("sid", "default")
    session = get_session(sid)
    session["history"].clear()
    return jsonify({"ok": True})


@app.route("/api/undo", methods=["POST"])
def undo():
    data = request.json or {}
    sid = data.get("sid", "default")
    session = get_session(sid)
    if len(session["history"]) >= 2:
        session["history"].pop()
        session["history"].pop()
        return jsonify({"ok": True})
    return jsonify({"ok": False, "msg": "没有可撤销的对话"})


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json or {}
    sid = data.get("sid", "default")
    prompt = data.get("prompt", "").strip()

    if not prompt:
        return jsonify({"error": "空消息"}), 400

    session = get_session(sid)

    if prompt.startswith("/"):
        return jsonify({"text": handle_command(session, prompt)})

    messages = list(session["history"])
    messages.append({"role": "user", "content": prompt})

    def generate():
        q = queue.Queue()
        t = threading.Thread(
            target=do_stream_api,
            args=(messages, session["system_prompt"], session["model"], session["temperature"], q),
            daemon=True,
        )
        t.start()

        full_text = ""
        t0 = time.time()
        first_token = None

        while True:
            try:
                item = q.get(timeout=60)
            except queue.Empty:
                yield f"data: {json.dumps({'error': '超时'})}\n\n"
                break

            if "error" in item:
                yield f"data: {json.dumps(item)}\n\n"
                break
            if "done" in item:
                elapsed = time.time() - t0
                session["history"].append({"role": "user", "content": prompt})
                session["history"].append({"role": "assistant", "content": full_text})
                meta = {"done": True, "elapsed": round(elapsed, 1), "chars": len(full_text)}
                if first_token:
                    meta["first_token"] = round(first_token, 1)
                yield f"data: {json.dumps(meta)}\n\n"
                break
            if "text" in item:
                if first_token is None:
                    first_token = time.time() - t0
                full_text += item["text"]
                yield f"data: {json.dumps(item)}\n\n"

    return Response(generate(), mimetype="text/event-stream")


def handle_command(session: dict, cmd: str) -> str:
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("/list", "/人格", "/列表"):
        lines = ["可用人格："]
        for name in PERSONAS:
            tag = PERSONA_TAGS.get(name, "")
            lines.append(f"  /{name} - {tag}")
        return "\n".join(lines)

    if command in ("/随机", "/random"):
        import random
        name = random.choice(list(PERSONAS.keys()))
        session["persona_name"] = name
        session["system_prompt"] = PERSONAS[name]
        return f"🎭 已切换为【{name}】模式"

    if command in PERSONA_ALIASES:
        name = PERSONA_ALIASES[command]
        session["persona_name"] = name
        session["system_prompt"] = PERSONAS[name]
        return f"🎭 已切换为【{name}】模式"

    if command == "/model":
        if not arg:
            lines = ["可用模型："]
            for name, desc in MODELS.items():
                marker = " ◀" if name == session["model"] else ""
                lines.append(f"  {name} - {desc}{marker}")
            return "\n".join(lines)
        if arg in MODELS:
            session["model"] = arg
            return f"🔧 模型已切换为 {arg}"
        return f"未知模型：{arg}"

    if command == "/temp":
        try:
            val = float(arg)
            if 0 <= val <= 1:
                session["temperature"] = val
                return f"🌡️ 温度已设为 {val}"
            return "温度范围 0.0 ~ 1.0"
        except ValueError:
            return "请输入数字，如 /temp 0.7"

    if command == "/stats":
        rounds = len(session["history"]) // 2
        return (
            f"📊 当前人格：{session['persona_name']}\n"
            f"   当前模型：{session['model']}\n"
            f"   对话轮数：{rounds}\n"
            f"   当前温度：{session['temperature']}"
        )

    return f"未知命令：{command}，输入 /list 查看人格"


if __name__ == "__main__":
    if not API_KEY:
        print("⚠️ 请设置环境变量 ZHIPU_API_KEY")
        sys.exit(1)
    print("🌐 GlmChat Web 启动中...")
    print("   访问 http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
