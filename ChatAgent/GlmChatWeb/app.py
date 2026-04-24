import json
import time
import queue
import threading
import os
import sys
import random
import urllib.request

from flask import Flask, render_template, request, Response, jsonify, session
from flask_cors import CORS
from datetime import timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "GlmChat"))
from glm_chat.personas import PERSONAS, PERSONA_TAGS, PERSONA_ALIASES
from glm_chat.api import MODELS, API_KEY, API_URL, DEFAULT_MODEL

import db
import auth
from auth import login_required, get_current_user

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
CORS(app, supports_credentials=True)

sessions_lock = threading.Lock()
user_sessions = {}


def _get_user_session():
    user = get_current_user()
    if not user:
        return None
    uid = user["id"]
    with sessions_lock:
        if uid not in user_sessions:
            user_sessions[uid] = {
                "persona_type": None,
                "persona_id": None,
                "persona_name": "智谱小A",
                "model": DEFAULT_MODEL,
                "temperature": 0.1,
            }
        return user_sessions[uid]


def _build_prompt(name, identity, tone, strengths, weaknesses, habits, values, backstory):
    parts = [f"你是{name}。"]
    if identity:
        parts.append(f"身份：{identity}")
    if tone:
        parts.append(f"说话语气：{tone}")
    if strengths:
        parts.append(f"优点：{strengths}")
    if weaknesses:
        parts.append(f"缺点：{weaknesses}")
    if habits:
        parts.append(f"小习惯：{habits}")
    if values:
        parts.append(f"价值观：{values}")
    if backstory:
        parts.append(f"背景故事：{backstory}")
    parts.append("请严格按照以上设定进行对话。")
    return "\n".join(parts)


def _extract_delta(data):
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


def do_stream_api(messages, system_prompt, model, temperature, q):
    body = {
        "model": model,
        "messages": messages,
        "max_tokens": 1024,
        "temperature": temperature,
        "stream": True,
    }
    if system_prompt:
        body["system"] = system_prompt

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
        body_text = e.read().decode("utf-8", errors="ignore")
        q.put({"error": f"HTTP {e.code}: {body_text}"})
    except Exception as e:
        q.put({"error": str(e)})


@app.route("/")
@login_required
def index():
    user = get_current_user()
    return render_template("index.html", username=user["username"])


@app.route("/login")
def login_page():
    if get_current_user():
        return render_template("index.html", username=get_current_user()["username"])
    return render_template("login.html")


@app.route("/register")
def register_page():
    if get_current_user():
        return render_template("index.html", username=get_current_user()["username"])
    return render_template("register.html")


@app.route("/api/register", methods=["POST"])
def api_register():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    ok, msg = auth.do_register(username, password)
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.json or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")
    ok, msg = auth.do_login(username, password)
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/logout", methods=["POST"])
def api_logout():
    auth.do_logout()
    return jsonify({"ok": True})


@app.route("/api/me")
@login_required
def api_me():
    user = get_current_user()
    return jsonify({"username": user["username"]})


@app.route("/api/personas")
@login_required
def api_personas():
    user = get_current_user()
    return jsonify(db.get_enabled_personas(user["id"]))


@app.route("/api/personas/available")
@login_required
def api_personas_available():
    user = get_current_user()
    return jsonify(db.get_available_system_personas(user["id"]))


@app.route("/api/personas/enable", methods=["POST"])
@login_required
def api_personas_enable():
    user = get_current_user()
    data = request.json or {}
    persona_id = data.get("persona_id")
    if not persona_id:
        return jsonify({"ok": False, "msg": "缺少 persona_id"})
    ok = db.enable_system_persona(user["id"], persona_id)
    return jsonify({"ok": ok, "msg": "" if ok else "启用失败，可能已经启用过了"})


@app.route("/api/personas/create", methods=["POST"])
@login_required
def api_personas_create():
    user = get_current_user()
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "请输入人格名称"})
    prompt = _build_prompt(
        name,
        data.get("identity", ""),
        data.get("tone", ""),
        data.get("strengths", ""),
        data.get("weaknesses", ""),
        data.get("habits", ""),
        data.get("values", ""),
        data.get("backstory", ""),
    )
    pid = db.create_user_persona(
        user["id"], name,
        data.get("identity", ""),
        data.get("tone", ""),
        data.get("strengths", ""),
        data.get("weaknesses", ""),
        data.get("habits", ""),
        data.get("values", ""),
        data.get("backstory", ""),
        prompt,
    )
    if pid is None:
        return jsonify({"ok": False, "msg": "创建失败，人格名可能已存在"})
    return jsonify({"ok": True, "persona_id": pid})


@app.route("/api/personas/generate", methods=["POST"])
@login_required
def api_personas_generate():
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "请输入人格名称"})
    if not API_KEY:
        return jsonify({"ok": False, "msg": "未配置 ZHIPU_API_KEY，无法使用 AI 生成"})

    gen_prompt = (
        f"请为以下角色生成详细的人格设定，角色名：{name}。"
        f"请严格按以下JSON格式返回，不要返回任何其他内容：\n"
        f'{{"identity":"基础身份描述","tone":"说话语气和口头禅",'
        f'"strengths":"优点和擅长的事","weaknesses":"缺点和弱点",'
        f'"habits":"小习惯和怪癖","values":"价值观和立场","backstory":"一段背景故事"}}'
    )

    body = {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "user", "content": gen_prompt}],
        "max_tokens": 800,
        "temperature": 0.8,
    }
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
        full = resp.read().decode("utf-8")
        result = json.loads(full)
        content = result.get("content", [])
        if isinstance(content, list) and content:
            text = content[0].get("text", "")
        elif isinstance(content, str):
            text = content
        else:
            text = ""

        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(text[start:end])
            return jsonify(parsed)
        return jsonify({"ok": False, "msg": "AI 返回格式异常"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"AI 生成失败: {e}"})


@app.route("/api/personas/<int:persona_id>", methods=["DELETE"])
@login_required
def api_personas_delete(persona_id):
    user = get_current_user()
    ptype = request.args.get("type", "user")
    if ptype != "user":
        return jsonify({"ok": False, "msg": "系统人格只能移除，不能删除"})
    ok = db.delete_user_persona(user["id"], persona_id)
    return jsonify({"ok": ok, "msg": "" if ok else "删除失败，只能删除自己创建的人格"})


@app.route("/api/personas/remove", methods=["POST"])
@login_required
def api_personas_remove():
    user = get_current_user()
    data = request.json or {}
    ptype = data.get("persona_type", "")
    pid = data.get("persona_id")
    if not ptype or not pid:
        return jsonify({"ok": False, "msg": "参数缺失"})
    db.disable_persona(user["id"], ptype, pid)
    if ptype == "user":
        db.clear_chat_history(user["id"], ptype, pid)
    else:
        db.clear_chat_history(user["id"], ptype, pid)
    return jsonify({"ok": True})


@app.route("/api/models")
@login_required
def api_models():
    s = _get_user_session()
    return jsonify({
        "models": {k: v for k, v in MODELS.items()},
        "current": s["model"] if s else DEFAULT_MODEL,
    })


@app.route("/api/session")
@login_required
def api_session():
    s = _get_user_session()
    if not s:
        return jsonify({"persona": "智谱小A", "model": DEFAULT_MODEL, "history": []})
    history = []
    if s["persona_type"] and s["persona_id"]:
        history = db.get_chat_history(get_current_user()["id"], s["persona_type"], s["persona_id"])
    return jsonify({
        "persona": s["persona_name"],
        "model": s["model"],
        "history": history,
    })


@app.route("/api/config", methods=["POST"])
@login_required
def api_config():
    data = request.json or {}
    s = _get_user_session()
    if not s:
        return jsonify({"ok": False})
    user = get_current_user()

    if "persona" in data and "persona_type" in data and "persona_id" in data:
        s["persona_type"] = data["persona_type"]
        s["persona_id"] = data["persona_id"]
        s["persona_name"] = data["persona"]

    if "model" in data and data["model"] in MODELS:
        s["model"] = data["model"]

    if "temperature" in data:
        val = float(data["temperature"])
        if 0 <= val <= 1:
            s["temperature"] = val

    history = []
    if s["persona_type"] and s["persona_id"]:
        history = db.get_chat_history(user["id"], s["persona_type"], s["persona_id"])

    return jsonify({"ok": True, "history": history, "persona": s["persona_name"]})


@app.route("/api/clear", methods=["POST"])
@login_required
def api_clear():
    s = _get_user_session()
    if s and s["persona_type"] and s["persona_id"]:
        db.clear_chat_history(get_current_user()["id"], s["persona_type"], s["persona_id"])
    return jsonify({"ok": True})


@app.route("/api/undo", methods=["POST"])
@login_required
def api_undo():
    s = _get_user_session()
    if s and s["persona_type"] and s["persona_id"]:
        ok = db.undo_last_turn(get_current_user()["id"], s["persona_type"], s["persona_id"])
        return jsonify({"ok": ok})
    return jsonify({"ok": False})


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    data = request.json or {}
    prompt = data.get("prompt", "").strip()
    if not prompt:
        return jsonify({"error": "空消息"}), 400

    user = get_current_user()
    s = _get_user_session()
    if not s:
        return jsonify({"error": "会话错误"}), 400

    if prompt.startswith("/"):
        return jsonify({"text": handle_command(s, prompt, user["id"])})

    if not s["persona_type"] or not s["persona_id"]:
        return jsonify({"text": "请先选择一个人格再开始聊天"})

    persona_detail = db.get_persona_details(s["persona_type"], s["persona_id"], user["id"])
    system_prompt = persona_detail["prompt"] if persona_detail else ""

    history = db.get_chat_history(user["id"], s["persona_type"], s["persona_id"])
    messages = list(history)
    messages.append({"role": "user", "content": prompt})

    def generate():
        q = queue.Queue()
        t = threading.Thread(
            target=do_stream_api,
            args=(messages, system_prompt, s["model"], s["temperature"], q),
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
                db.save_chat_message(user["id"], s["persona_type"], s["persona_id"], "user", prompt)
                db.save_chat_message(user["id"], s["persona_type"], s["persona_id"], "assistant", full_text)
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


GROUP_MAX_ROUNDS = 30
GROUP_DELAY_SECONDS = 2


def _init_group_session(uid, persona_keys, group_mode, model, temperature):
    with sessions_lock:
        if uid not in user_sessions:
            user_sessions[uid] = {}
        s = user_sessions[uid]
        s["group_active"] = True
        s["group_mode"] = group_mode
        s["group_personas"] = persona_keys
        s["group_history"] = []
        s["group_round"] = 0
        s["model"] = model
        s["temperature"] = temperature


def _get_group_session(uid):
    with sessions_lock:
        s = user_sessions.get(uid)
        if s and s.get("group_active"):
            return s
    return None


def _build_group_system_prompt(persona_name, persona_prompt, all_names):
    others = [n for n in all_names if n != persona_name]
    header = (
        f"你正在参与一个多人对话。你的角色是【{persona_name}】。\n"
        f"其他参与者：{', '.join(others)}。\n"
        f"请严格保持你的人格设定，自然地参与讨论。发言要简短（50-150字），"
        f"像真实聊天一样，不要一次说太多。直接说内容，不要加引号或角色名前缀。\n\n"
        f"你的完整人格设定：\n{persona_prompt}"
    )
    return header


def _build_group_messages(history, speaking_name):
    messages = []
    for msg in history:
        speaker = msg["speaker"]
        content = msg["content"]
        if speaker == "user":
            messages.append({"role": "user", "content": content})
        elif speaker == speaking_name:
            messages.append({"role": "assistant", "content": content})
        else:
            messages.append({"role": "user", "content": f"【{speaker}】：{content}"})
    return messages


@app.route("/api/group/start", methods=["POST"])
@login_required
def api_group_start():
    user = get_current_user()
    data = request.json or {}
    persona_keys = data.get("personas", [])
    group_mode = data.get("mode", "free")
    model = data.get("model", DEFAULT_MODEL)
    temperature = data.get("temperature", 0.3)

    if len(persona_keys) < 2:
        return jsonify({"ok": False, "msg": "至少选择2个人格"})

    valid_keys = []
    for key in persona_keys:
        parts = key.split(":", 1)
        if len(parts) == 2:
            ptype, pid_str = parts
            pid = int(pid_str)
            detail = db.get_persona_details(ptype, pid, user["id"])
            if detail:
                valid_keys.append({
                    "persona_type": ptype,
                    "persona_id": pid,
                    "name": detail["name"],
                    "prompt": detail["prompt"],
                })

    if len(valid_keys) < 2:
        return jsonify({"ok": False, "msg": "有效人格不足2个"})

    _init_group_session(user["id"], valid_keys, group_mode, model, temperature)

    return jsonify({
        "ok": True,
        "personas": [{"name": p["name"]} for p in valid_keys],
        "mode": group_mode,
    })


@app.route("/api/group/status")
@login_required
def api_group_status():
    user = get_current_user()
    s = _get_group_session(user["id"])
    if not s:
        return jsonify({"active": False})
    return jsonify({
        "active": True,
        "mode": s["group_mode"],
        "round": s["group_round"],
        "max_rounds": GROUP_MAX_ROUNDS,
        "personas": [{"name": p["name"]} for p in s["group_personas"]],
    })


@app.route("/api/group/stop", methods=["POST"])
@login_required
def api_group_stop():
    user = get_current_user()
    with sessions_lock:
        s = user_sessions.get(user["id"])
        if s:
            s["group_active"] = False
            s["group_history"] = []
            s["group_round"] = 0
            s["group_personas"] = []
    return jsonify({"ok": True})


@app.route("/api/group/chat", methods=["POST"])
@login_required
def api_group_chat():
    user = get_current_user()
    s = _get_group_session(user["id"])
    if not s:
        return jsonify({"error": "未开启群聊"})

    data = request.json or {}
    prompt = data.get("prompt", "").strip()
    target_name = data.get("target", "")

    if not prompt and not target_name:
        return jsonify({"error": "空消息"})

    if prompt:
        s["group_history"].append({"speaker": "user", "content": prompt})

    if s["group_round"] >= GROUP_MAX_ROUNDS:
        return jsonify({"error": f"已达最大轮数 {GROUP_MAX_ROUNDS} 轮，请结束群聊"})

    if target_name:
        speakers = [p for p in s["group_personas"] if p["name"] == target_name]
    elif s["group_mode"] == "free":
        speakers = list(s["group_personas"])
    elif s["group_mode"] == "round_robin":
        idx = s["group_round"] % len(s["group_personas"])
        speakers = [s["group_personas"][idx]]
    else:
        speakers = list(s["group_personas"])

    all_names = [p["name"] for p in s["group_personas"]]
    username = user["username"]

    def generate():
        for persona in speakers:
            if s["group_round"] >= GROUP_MAX_ROUNDS:
                yield f"data: {json.dumps({'group_done': True, 'round': s['group_round'], 'max': GROUP_MAX_ROUNDS, 'reason': 'max_rounds'})}\n\n"
                return

            sys_prompt = _build_group_system_prompt(persona["name"], persona["prompt"], all_names)
            messages = _build_group_messages(s["group_history"], persona["name"])

            q = queue.Queue()
            t = threading.Thread(
                target=do_stream_api,
                args=(messages, sys_prompt, s["model"], s["temperature"], q),
                daemon=True,
            )
            t.start()

            full_text = ""
            t0 = time.time()
            first_token = None

            yield f"data: {json.dumps({'speaker_start': persona['name']})}\n\n"

            while True:
                try:
                    item = q.get(timeout=60)
                except queue.Empty:
                    yield f"data: {json.dumps({'speaker': persona['name'], 'error': '超时'})}\n\n"
                    break

                if "error" in item:
                    yield f"data: {json.dumps({'speaker': persona['name'], 'error': item['error']})}\n\n"
                    break
                if "done" in item:
                    elapsed = time.time() - t0
                    if full_text.strip():
                        s["group_history"].append({"speaker": persona["name"], "content": full_text.strip()})
                        s["group_round"] += 1
                    meta = {
                        "speaker": persona["name"],
                        "done": True,
                        "elapsed": round(elapsed, 1),
                        "chars": len(full_text),
                        "round": s["group_round"],
                    }
                    if first_token:
                        meta["first_token"] = round(first_token, 1)
                    yield f"data: {json.dumps(meta)}\n\n"
                    break
                if "text" in item:
                    if first_token is None:
                        first_token = time.time() - t0
                    full_text += item["text"]
                    yield f"data: {json.dumps({'speaker': persona['name'], 'text': item['text']})}\n\n"

            if persona != speakers[-1]:
                time.sleep(GROUP_DELAY_SECONDS)

        yield f"data: {json.dumps({'group_done': True, 'round': s['group_round'], 'max': GROUP_MAX_ROUNDS})}\n\n"

    return Response(generate(), mimetype="text/event-stream")


@app.route("/api/group/mode", methods=["POST"])
@login_required
def api_group_mode():
    user = get_current_user()
    s = _get_group_session(user["id"])
    if not s:
        return jsonify({"ok": False, "msg": "未开启群聊"})
    data = request.json or {}
    mode = data.get("mode")
    if mode in ("free", "round_robin", "directed"):
        s["group_mode"] = mode
        return jsonify({"ok": True})
    return jsonify({"ok": False, "msg": "无效模式"})


import werewolf
from werewolf_themes import THEMES as WEREWOLF_THEMES, ROLE_CONFIGS as WEREWOLF_ROLE_CONFIGS, ROLE_INFO as WEREWOLF_ROLE_INFO
import werewolf_config


def _call_llm_json(prompt_text, model=None, temperature=0.5):
    if not API_KEY:
        return None
    body = {
        "model": model or DEFAULT_MODEL,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 500,
        "temperature": temperature,
    }
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
        resp = urllib.request.urlopen(req, timeout=30)
        full = resp.read().decode("utf-8")
        result = json.loads(full)
        content = result.get("content", [])
        if isinstance(content, list) and content:
            text = content[0].get("text", "")
        elif isinstance(content, str):
            text = content
        else:
            text = ""
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            return json.loads(text[start:end])
        return None
    except Exception:
        return None


def _call_llm_text(prompt_text, model=None, temperature=0.5):
    if not API_KEY:
        return ""
    body = {
        "model": model or DEFAULT_MODEL,
        "messages": [{"role": "user", "content": prompt_text}],
        "max_tokens": 400,
        "temperature": temperature,
    }
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
        resp = urllib.request.urlopen(req, timeout=30)
        full = resp.read().decode("utf-8")
        result = json.loads(full)
        content = result.get("content", [])
        if isinstance(content, list) and content:
            return content[0].get("text", "").strip()
        if isinstance(content, str):
            return content.strip()
        return ""
    except Exception:
        return ""


@app.route("/werewolf")
@login_required
def werewolf_page():
    user = get_current_user()
    return render_template("werewolf.html", username=user["username"])


@app.route("/api/werewolf/themes")
@login_required
def api_werewolf_themes():
    user = get_current_user()
    preset = [{"name": k, "description": v["description"], "count": len(v["characters"])} for k, v in WEREWOLF_THEMES.items()]
    custom = db.get_custom_themes(user["id"])
    return jsonify({"preset": preset, "custom": custom, "free": {"name": "自由模式", "description": "从已启用的人格中随机选"}})


@app.route("/api/werewolf/role_configs")
@login_required
def api_werewolf_role_configs():
    return jsonify({"configs": {str(k): v for k, v in WEREWOLF_ROLE_CONFIGS.items()}, "roles": WEREWOLF_ROLE_INFO})


@app.route("/api/werewolf/start", methods=["POST"])
@login_required
def api_werewolf_start():
    user = get_current_user()
    data = request.json or {}
    total = data.get("total", 9)
    user_mode = data.get("user_mode", "god")
    theme = data.get("theme")
    persona_names = data.get("personas")
    speech_mode = data.get("speech_mode", "free")

    if theme and theme in WEREWOLF_THEMES:
        pass
    elif theme == "自由模式" or theme == "free":
        theme = None
        if not persona_names:
            enabled = db.get_enabled_personas(user["id"])
            random.shuffle(enabled)
            persona_names = [p["name"] for p in enabled[:total]]
    elif theme:
        custom_themes = db.get_custom_themes(user["id"])
        ct = next((t for t in custom_themes if t["name"] == theme), None)
        if ct:
            WEREWOLF_THEMES[theme] = {"description": ct["description"], "characters": ct["characters"]}
        else:
            theme = None

    if not persona_names and not theme:
        enabled = db.get_enabled_personas(user["id"])
        random.shuffle(enabled)
        persona_names = [p["name"] for p in enabled[:total]]

    user_persona = None
    if user_mode == "player":
        user_persona = {"name": user["username"], "prompt": f"你是{user['username']}，一个参与狼人杀游戏的玩家。"}

    game, err = werewolf.create_game(total, user_mode, theme, persona_names, user_persona, speech_mode=speech_mode)
    if err:
        return jsonify({"ok": False, "msg": err})

    if werewolf_config.WEREWOLF_CONFIG.get("enable_role_memory"):
        game["config"]["use_emotions"] = True

    if user_mode == "player":
        up = next((p for p in game["players"] if p["is_user"]), None)
        if up:
            user_role = up["role"]
            ri = WEREWOLF_ROLE_INFO.get(user_role, {})
            return jsonify({
                "ok": True,
                "game_id": game["id"],
                "players": [{"name": p["name"], "seat": p["seat"], "gender": p.get("gender", "male")} for p in game["players"]],
                "user_role": user_role,
                "user_role_icon": ri.get("icon", "👤"),
                "user_role_name": ri.get("name", "村民"),
            })

    return jsonify({
        "ok": True,
        "game_id": game["id"],
        "players": [{"name": p["name"], "seat": p["seat"], "role": p["role"], "gender": p.get("gender", "male")} for p in game["players"]],
    })


@app.route("/api/werewolf/status")
@login_required
def api_werewolf_status():
    game_id = request.args.get("game_id")
    if not game_id:
        return jsonify({"ok": False, "msg": "缺少 game_id"})
    game = werewolf.get_game(game_id)
    if not game:
        return jsonify({"ok": False, "msg": "游戏不存在"})
    user = get_current_user()
    state = werewolf.get_public_state(game, game["config"]["user_mode"])
    return jsonify({"ok": True, "state": state})


@app.route("/api/werewolf/action", methods=["POST"])
@login_required
def api_werewolf_action():
    user = get_current_user()
    data = request.json or {}
    game_id = data.get("game_id")
    action = data.get("action")
    target = data.get("target")
    if not game_id:
        return jsonify({"ok": False, "msg": "缺少 game_id"})
    game = werewolf.get_game(game_id)
    if not game:
        return jsonify({"ok": False, "msg": "游戏不存在"})
    werewolf.set_user_action(game_id, {"action": action, "target": target})
    return jsonify({"ok": True})


@app.route("/api/werewolf/stop", methods=["POST"])
@login_required
def api_werewolf_stop():
    data = request.json or {}
    game_id = data.get("game_id")
    if game_id:
        game = werewolf.get_game(game_id)
        if game and not game.get("game_over"):
            game["abandoned"] = True
            werewolf.end_game(game, "cancelled")
    return jsonify({"ok": True})


@app.route("/api/werewolf/save", methods=["POST"])
@login_required
def api_werewolf_save():
    user = get_current_user()
    data = request.json or {}
    game_id = data.get("game_id")
    if not game_id:
        return jsonify({"ok": False, "msg": "缺少 game_id"})
    game = werewolf.get_game(game_id)
    if not game or not game["game_over"]:
        return jsonify({"ok": False, "msg": "游戏未结束，无法保存"})
    replay = werewolf.get_replay_data(game)
    db.save_werewolf_replay(user["id"], replay["id"], replay["config"], replay["events"], replay["winner"])
    return jsonify({"ok": True, "replay_id": replay["id"]})


@app.route("/api/werewolf/speed", methods=["POST"])
@login_required
def api_werewolf_speed():
    data = request.json or {}
    game_id = data.get("game_id")
    speed = data.get("speed", "medium")
    if game_id:
        werewolf.set_speed(game_id, speed)
    return jsonify({"ok": True})


@app.route("/api/werewolf/replays")
@login_required
def api_werewolf_replays():
    user = get_current_user()
    return jsonify({"replays": db.get_werewolf_replays(user["id"])})


@app.route("/api/werewolf/replay/<replay_id>")
@login_required
def api_werewolf_replay_detail(replay_id):
    user = get_current_user()
    detail = db.get_werewolf_replay_detail(replay_id, user["id"])
    if not detail:
        return jsonify({"ok": False, "msg": "回放不存在"})
    return jsonify({"ok": True, "replay": detail})


@app.route("/api/werewolf/theme/create", methods=["POST"])
@login_required
def api_werewolf_theme_create():
    user = get_current_user()
    data = request.json or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "主题名称不能为空"})
    characters = data.get("characters", [])
    if len(characters) < 6:
        return jsonify({"ok": False, "msg": "至少需要6个角色"})
    tid = db.save_custom_theme(user["id"], name, data.get("description", ""), characters)
    if tid is None:
        return jsonify({"ok": False, "msg": "创建失败"})
    return jsonify({"ok": True, "theme_id": tid})


@app.route("/api/werewolf/step", methods=["POST"])
@login_required
def api_werewolf_step():
    user = get_current_user()
    data = request.json or {}
    game_id = data.get("game_id")
    if not game_id:
        return jsonify({"ok": False, "msg": "缺少 game_id"})
    game = werewolf.get_game(game_id)
    if not game:
        return jsonify({"ok": False, "msg": "游戏不存在"})
    if game["game_over"]:
        return jsonify({"ok": False, "msg": "游戏已结束"})

    max_rounds = werewolf_config.WEREWOLF_CONFIG.get("max_rounds", 12)
    if game["round"] >= max_rounds:
        return jsonify({"ok": False, "msg": f"已达最大轮数 {max_rounds}，请结束游戏"})

    def generate():
        if game["phase"] == "setup":
            steps = werewolf.start_night(game)
            for role, action in steps:
                if game["game_over"]:
                    break
                yield from _execute_night_step(game, role, action)
            if not game["game_over"]:
                yield from _execute_day_cycle(game)
        elif game["phase"] == "night":
            steps = werewolf._build_night_steps(game)
            for role, action in steps:
                if game["game_over"]:
                    break
                yield from _execute_night_step(game, role, action)
            if not game["game_over"]:
                yield from _execute_day_cycle(game)
        elif game["phase"] == "day":
            yield from _execute_day_cycle(game)

        w = werewolf.check_win(game)
        if w:
            werewolf.end_game(game, w)
            scores = werewolf.calculate_game_scores(game)
            try:
                user_mode = game["config"].get("user_mode")
                user_char = None
                if user_mode == "player":
                    up = next((p for p in game["players"] if p.get("is_user")), None)
                    if up:
                        user_char = up["name"]
                db.save_werewolf_scores(user["id"], game["id"], scores, user_mode, user_char)
                if werewolf_config.WEREWOLF_CONFIG.get("enable_role_memory"):
                    db.save_game_emotions(game["events"], game["players"])
                    decay_rate = werewolf_config.WEREWOLF_CONFIG.get("memory_decay_rate", 0.1)
                    db.decay_emotions(decay_rate)
            except Exception:
                pass
            yield _sse(game, {'event': 'game_over', 'winner': w, 'winner_label': '好人阵营' if w == 'village' else '狼人阵营', 'scores': scores})
        yield _sse(game, {'event': 'step_done', 'phase': game['phase'], 'round': game['round']})

    return Response(generate(), mimetype="text/event-stream")


def _wait_user_target(game, timeout=120):
    game["user_action"] = None
    waited = 0
    while game["user_action"] is None and waited < timeout:
        time.sleep(0.3)
        waited += 0.3
    ua = game.get("user_action") or {}
    game["user_action"] = None
    return ua.get("target")


def _sse(game, data, secret=False):
    """Yield SSE data line and also record event in game for replay."""
    evt_type = data.get("event", "")
    payload = {k: v for k, v in data.items() if k != "event"}
    if secret:
        werewolf._emit(game, evt_type, payload)
    else:
        werewolf._emit_public(game, evt_type, payload)
    return f"data: {json.dumps(data)}\n\n"


def _execute_night_step(game, role, action):
    user_mode = game["config"].get("user_mode")

    if role == "guard":
        guard, prompt = werewolf.build_guard_prompt(game)
        if guard:
            yield _sse(game, {'event': 'action_start', 'role': 'guard', 'player': guard['name']}, secret=True)
            if guard.get("is_user") and user_mode == "player":
                alive_names = [p["name"] for p in werewolf._alive_players(game) if p["name"] != guard["name"]]
                last = guard.get("guard_last")
                if last and last in alive_names:
                    alive_names.remove(last)
                yield _sse(game, {'event': 'user_night_action', 'action_type': 'guard', 'targets': alive_names}, secret=True)
                target = _wait_user_target(game)
                if target and target != guard.get("guard_last"):
                    werewolf.resolve_guard(game, target)
                    yield _sse(game, {'event': 'action_text', 'role': 'guard', 'player': guard['name'], 'text': f'守护【{target}】'}, secret=True)
            else:
                result = _call_llm_json(prompt, temperature=0.5)
                if result and result.get("target"):
                    target = result["target"]
                    alive_names = [p["name"] for p in werewolf._alive_players(game) if p["name"] != guard["name"]]
                    target = _fuzzy_match(target, alive_names)
                    if target:
                        if target != guard.get("guard_last"):
                            werewolf.resolve_guard(game, target)
                            if user_mode == "god":
                                yield _sse(game, {'event': 'action_text', 'role': 'guard', 'player': guard['name'], 'text': f'守护【{target}】'}, secret=True)

    elif role == "werewolf":
        wolves, wolf_prompts = werewolf.build_werewolf_prompt(game)
        if wolves:
            yield _sse(game, {'event': 'action_start', 'role': 'werewolf', 'players': [w['name'] for w in wolves]}, secret=True)
            targets = [p["name"] for p in werewolf._alive_players(game) if p["role"] != "werewolf"]
            user_wolf = next((w for w in wolves if w.get("is_user")), None)
            if user_wolf and user_mode == "player":
                yield _sse(game, {'event': 'user_night_action', 'action_type': 'werewolf', 'targets': targets}, secret=True)
                user_target = _wait_user_target(game)
                if user_target:
                    werewolf.resolve_werewolf(game, user_target)
                    yield _sse(game, {'event': 'action_text', 'role': 'werewolf', 'player': user_wolf['name'], 'text': f'选择击杀【{user_target}】'}, secret=True)
                elif targets:
                    werewolf.resolve_werewolf(game, random.choice(targets))
            else:
                from concurrent.futures import ThreadPoolExecutor, as_completed
                all_targets = []
                speeches = []
                def _wolf_call(w, wp):
                    r = _call_llm_json(wp, temperature=0.6)
                    return w, r
                with ThreadPoolExecutor(max_workers=min(len(wolf_prompts), 3)) as pool:
                    futs = {pool.submit(_wolf_call, w, wp): w for w, wp in wolf_prompts}
                    for fut in as_completed(futs):
                        w, result = fut.result()
                        if result and result.get("target"):
                            t = _fuzzy_match(result["target"], targets)
                            if t:
                                all_targets.append(t)
                            if result.get("speech"):
                                speeches.append(f"【{w['name']}】：{result['speech']}")
                            if user_mode == "god":
                                yield _sse(game, {'event': 'action_text', 'role': 'werewolf', 'player': w['name'], 'text': result.get('reason', '选择目标')}, secret=True)
                if speeches:
                    for s in speeches:
                        yield _sse(game, {'event': 'wolf_discuss', 'text': s}, secret=True)
                if all_targets:
                    from collections import Counter
                    most_common = Counter(all_targets).most_common(1)[0][0]
                    speech_str = "；".join(speeches)
                    werewolf.resolve_werewolf(game, most_common, speech_str)
                elif targets:
                    werewolf.resolve_werewolf(game, random.choice(targets))

    elif role == "seer":
        seer, prompt = werewolf.build_seer_prompt(game)
        if seer:
            yield _sse(game, {'event': 'action_start', 'role': 'seer', 'player': seer['name']}, secret=True)
            if seer.get("is_user") and user_mode == "player":
                checked = list(seer.get("seer_checks", {}).keys())
                checkable = [p["name"] for p in werewolf._alive_players(game) if p["name"] != seer["name"] and p["name"] not in checked]
                yield _sse(game, {'event': 'user_night_action', 'action_type': 'seer', 'targets': checkable}, secret=True)
                target = _wait_user_target(game)
                if target:
                    werewolf.resolve_seer(game, target)
                    is_wolf = game["night_actions"].get("seer_result") == "werewolf"
                    yield _sse(game, {'event': 'seer_result_user', 'target': target, 'is_wolf': is_wolf}, secret=True)
            else:
                result = _call_llm_json(prompt, temperature=0.5)
                if result and result.get("target"):
                    checked = list(seer.get("seer_checks", {}).keys())
                    checkable = [p["name"] for p in werewolf._alive_players(game) if p["name"] != seer["name"] and p["name"] not in checked]
                    target = _fuzzy_match(result["target"], checkable)
                    if target:
                        werewolf.resolve_seer(game, target)
                        is_wolf = game["night_actions"].get("seer_result") == "werewolf"
                        label = "🐺 狼人" if is_wolf else "✅ 好人"
                        if user_mode == "god":
                            yield _sse(game, {'event': 'action_text', 'role': 'seer', 'player': seer['name'], 'text': f'查验【{target}】：{label}'}, secret=True)

    elif role == "witch_save":
        witch, prompt = werewolf.build_witch_save_prompt(game)
        if witch:
            killed = game["night_actions"].get("werewolf_target")
            yield _sse(game, {'event': 'action_start', 'role': 'witch', 'player': witch['name'], 'sub': 'save'}, secret=True)
            if witch.get("is_user") and user_mode == "player":
                if not witch.get("witch_save_used") and killed:
                    yield _sse(game, {'event': 'user_night_action', 'action_type': 'witch_save', 'targets': [killed]}, secret=True)
                    target = _wait_user_target(game)
                    do_save = target == killed
                    werewolf.resolve_witch_save(game, do_save)
                    yield _sse(game, {'event': 'action_text', 'role': 'witch', 'player': witch['name'], 'text': '使用解药救了【' + killed + '】' if do_save else '不使用解药'}, secret=True)
            else:
                if not witch.get("witch_save_used"):
                    result = _call_llm_json(prompt, temperature=0.4)
                    do_save = result and result.get("save") is True if result else False
                    werewolf.resolve_witch_save(game, do_save)
                    if user_mode == "god":
                        if do_save:
                            yield _sse(game, {'event': 'action_text', 'role': 'witch', 'player': witch['name'], 'text': f'使用解药救了【{killed}】'}, secret=True)
                        else:
                            yield _sse(game, {'event': 'action_text', 'role': 'witch', 'player': witch['name'], 'text': '不使用解药'}, secret=True)

    elif role == "witch_poison":
        witch, prompt = werewolf.build_witch_poison_prompt(game)
        if witch:
            yield _sse(game, {'event': 'action_start', 'role': 'witch', 'player': witch['name'], 'sub': 'poison'}, secret=True)
            if witch.get("is_user") and user_mode == "player":
                if not witch.get("witch_poison_used"):
                    targets = [p["name"] for p in werewolf._alive_players(game) if p["name"] != witch["name"]]
                    yield _sse(game, {'event': 'user_night_action', 'action_type': 'witch_poison', 'targets': targets}, secret=True)
                    target = _wait_user_target(game)
                    if target:
                        werewolf.resolve_witch_poison(game, target)
                        yield _sse(game, {'event': 'action_text', 'role': 'witch', 'player': witch['name'], 'text': f'使用毒药毒了【{target}】'}, secret=True)
                    else:
                        yield _sse(game, {'event': 'action_text', 'role': 'witch', 'player': witch['name'], 'text': '不使用毒药'}, secret=True)
            else:
                if not witch.get("witch_poison_used"):
                    result = _call_llm_json(prompt, temperature=0.4)
                    if result and result.get("poison") and result["poison"] != "null":
                        targets = [p["name"] for p in werewolf._alive_players(game) if p["name"] != witch["name"]]
                        target = _fuzzy_match(result["poison"], targets)
                        if target:
                            werewolf.resolve_witch_poison(game, target)
                            if user_mode == "god":
                                yield _sse(game, {'event': 'action_text', 'role': 'witch', 'player': witch['name'], 'text': f'使用毒药毒了【{target}】'}, secret=True)

    elif role == "resolve":
        deaths = werewolf.resolve_night(game)
        yield _sse(game, {'event': 'phase_change', 'phase': 'day', 'round': game['round']})
        if deaths:
            names = [d["name"] for d in deaths]
            yield _sse(game, {'event': 'death', 'players': names, 'cause': 'night'})
        else:
            yield _sse(game, {'event': 'death', 'players': [], 'cause': 'night', 'peace': True})

        for d in deaths:
            cause = f"在夜晚被狼人杀害" if d["cause"] == "werewolf" else "被女巫毒杀"
            lw_prompt = werewolf.build_last_words_prompt(game, d["name"], cause)
            if lw_prompt:
                lw = _call_llm_text(lw_prompt, temperature=0.6)
                if lw:
                    yield _sse(game, {'event': 'last_words', 'player': d['name'], 'text': lw})

        w = werewolf.check_win(game)
        if w:
            werewolf.end_game(game, w)
            yield _sse(game, {'event': 'game_over', 'winner': w, 'winner_label': '好人阵营' if w == 'village' else '狼人阵营'})


def _execute_day_cycle(game):
    game["day_speeches"] = []
    alive = werewolf._alive_players(game)

    from concurrent.futures import ThreadPoolExecutor, as_completed

    if game["game_over"]:
        return

    speeches_data = []
    speech_prompts = []
    user_speech_idx = None
    for i, p in enumerate(alive):
        prompt = werewolf.build_speech_prompt(game, p["name"], i + 1, len(alive))
        if not prompt:
            speeches_data.append(None)
            continue
        speech_prompts.append((i, p, prompt))
        speeches_data.append(None)
        if p.get("is_user") and game["config"].get("user_mode") == "player":
            user_speech_idx = i

    def _gen_speech(idx, p, prompt):
        return idx, _call_llm_text(prompt, temperature=0.7)

    if user_speech_idx is not None:
        for i, p, prompt in speech_prompts:
            if i == user_speech_idx:
                game["user_action"] = None
                yield _sse(game, {'event': 'speech_start', 'player': p['name'], 'order': i + 1})
                yield _sse(game, {'event': 'user_speech_request', 'player': p['name']})
                waited = 0
                while game["user_action"] is None and waited < 120:
                    time.sleep(0.3)
                    waited += 0.3
                ua = game.get("user_action") or {}
                game["user_action"] = None
                if ua.get("action") == "user_speech" and ua.get("text", "").strip():
                    speech = ua["text"].strip()
                else:
                    speech = _call_llm_text(prompt, temperature=0.7)
                speeches_data[i] = (p, speech)
                break

    non_user_prompts = [(i, p, pr) for i, p, pr in speech_prompts if i != user_speech_idx]
    if non_user_prompts:
        with ThreadPoolExecutor(max_workers=min(len(non_user_prompts), 4)) as pool:
            futs = {pool.submit(_gen_speech, i, p, pr): i for i, p, pr in non_user_prompts}
            for fut in as_completed(futs):
                i, speech = fut.result()
                p = non_user_prompts[[x[0] for x in non_user_prompts].index(i)][1]
                speeches_data[i] = (p, speech)

    for i, sd in enumerate(speeches_data):
        if game["game_over"]:
            break
        if sd is None:
            continue
        p, speech = sd
        yield _sse(game, {'event': 'speech_start', 'player': p['name'], 'order': i + 1})
        if speech:
            werewolf.add_speech(game, p["name"], speech)
            yield _sse(game, {'event': 'speech', 'player': p['name'], 'text': speech})

    if game["game_over"]:
        return

    vote_map = {}
    vote_prompts = []
    user_vote_idx = None
    for i, p in enumerate(alive):
        if game["game_over"]:
            break
        if p.get("is_user") and game["config"].get("user_mode") == "player":
            user_vote_idx = i
        else:
            vp = werewolf.build_vote_prompt(game, p["name"])
            if vp:
                vote_prompts.append((i, p, vp))

    if user_vote_idx is not None:
        p = alive[user_vote_idx]
        game["user_action"] = None
        voteable = [pp["name"] for pp in werewolf._alive_players(game) if pp["name"] != p["name"]]
        yield _sse(game, {'event': 'user_vote_request', 'player': p['name'], 'targets': voteable})
        waited = 0
        while game["user_action"] is None and waited < 120:
            time.sleep(0.3)
            waited += 0.3
        ua = game.get("user_action") or {}
        game["user_action"] = None
        if ua.get("action") == "user_vote" and ua.get("target"):
            target = ua["target"]
            if target in voteable:
                vote_map[p["name"]] = target
                yield _sse(game, {'event': 'vote_cast', 'from': p['name'], 'to': target, 'reason': '你的选择'})

    def _gen_vote(i, p, vp):
        result = _call_llm_json(vp, temperature=0.5)
        if result and result.get("target"):
            voteable_names = [pp["name"] for pp in werewolf._alive_players(game) if pp["name"] != p["name"]]
            target = _fuzzy_match(result["target"], voteable_names)
            return i, p, target, result.get('reason', '')
        return i, p, None, None

    if vote_prompts:
        with ThreadPoolExecutor(max_workers=min(len(vote_prompts), 4)) as pool:
            futs = {pool.submit(_gen_vote, i, p, vp): i for i, p, vp in vote_prompts}
            for fut in as_completed(futs):
                i, p, target, reason = fut.result()
                if game["game_over"]:
                    break
                if target:
                    vote_map[p["name"]] = target
                    yield _sse(game, {'event': 'vote_cast', 'from': p['name'], 'to': target, 'reason': reason})

    if game["game_over"]:
        return

    eliminated = werewolf.resolve_votes(game, vote_map)
    if eliminated:
        yield _sse(game, {'event': 'vote_result', 'eliminated': eliminated})

        hunter = next((p for p in game["players"] if p["name"] == eliminated and p["role"] == "hunter" and not p["alive"]), None)
        if hunter:
            hp = werewolf.build_hunter_prompt(game, hunter["name"], "被投票出局")
            if hp:
                result = _call_llm_json(hp, temperature=0.5)
                if result and result.get("target") and result["target"] != "null":
                    targets = [pp["name"] for pp in werewolf._alive_players(game)]
                    shoot_target = _fuzzy_match(result["target"], targets)
                    if shoot_target:
                        werewolf.resolve_hunter(game, shoot_target)
                        yield _sse(game, {'event': 'hunter_shoot', 'player': hunter['name'], 'target': shoot_target})

        w = werewolf.check_win(game)
        if w:
            werewolf.end_game(game, w)
            yield _sse(game, {'event': 'game_over', 'winner': w, 'winner_label': '好人阵营' if w == 'village' else '狼人阵营'})
            return
    else:
        yield _sse(game, {'event': 'vote_result', 'eliminated': None, 'reason': '平票'})

    if not game["game_over"]:
        game["phase"] = "night"
        game["sub_step"] = "pending"
        steps = werewolf.start_night(game)
        for role, action in steps:
            if game["game_over"]:
                break
            yield from _execute_night_step(game, role, action)


def _fuzzy_match(name, candidates):
    if not name or not candidates:
        return None
    name = name.strip()
    for c in candidates:
        if c == name:
            return c
    for c in candidates:
        if name in c or c in name:
            return c
    return None


def handle_command(s, cmd, user_id):
    parts = cmd.strip().split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("/list", "/人格", "/列表"):
        lines = ["可用人格："]
        for p in db.get_enabled_personas(user_id):
            tag = p.get("tag", "")
            lines.append(f"  /{p['name']} - {tag}")
        return "\n".join(lines)

    if command in ("/随机", "/random"):
        personas = db.get_enabled_personas(user_id)
        if not personas:
            return "没有可用的人格"
        p = random.choice(personas)
        s["persona_name"] = p["name"]
        s["persona_type"] = p["persona_type"]
        s["persona_id"] = p["persona_id"]
        return f"🎭 已切换为【{p['name']}】模式"

    if command in PERSONA_ALIASES:
        name = PERSONA_ALIASES[command]
        enabled = db.get_enabled_personas(user_id)
        match = [p for p in enabled if p["name"] == name]
        if match:
            p = match[0]
            s["persona_name"] = p["name"]
            s["persona_type"] = p["persona_type"]
            s["persona_id"] = p["persona_id"]
            return f"🎭 已切换为【{name}】模式"
        return f"人格【{name}】未启用，请先在左侧启用"

    if command == "/model":
        if not arg:
            lines = ["可用模型："]
            for name, desc in MODELS.items():
                marker = " ◀" if name == s["model"] else ""
                lines.append(f"  {name} - {desc}{marker}")
            return "\n".join(lines)
        if arg in MODELS:
            s["model"] = arg
            return f"🔧 模型已切换为 {arg}"
        return f"未知模型：{arg}"

    if command == "/temp":
        try:
            val = float(arg)
            if 0 <= val <= 1:
                s["temperature"] = val
                return f"🌡️ 温度已设为 {val}"
            return "温度范围 0.0 ~ 1.0"
        except ValueError:
            return "请输入数字，如 /temp 0.7"

    if command == "/stats":
        if s["persona_type"] and s["persona_id"]:
            history = db.get_chat_history(user_id, s["persona_type"], s["persona_id"])
            rounds = len(history) // 2
        else:
            rounds = 0
        return (
            f"📊 当前人格：{s['persona_name']}\n"
            f"   当前模型：{s['model']}\n"
            f"   对话轮数：{rounds}\n"
            f"   当前温度：{s['temperature']}"
        )

    return f"未知命令：{command}，输入 /list 查看人格"


@app.route("/api/werewolf/generate_speech", methods=["POST"])
@login_required
def api_werewolf_generate_speech():
    user = get_current_user()
    data = request.json or {}
    game_id = data.get("game_id")
    if not game_id:
        return jsonify({"ok": False, "msg": "缺少 game_id"})
    game = werewolf.get_game(game_id)
    if not game:
        return jsonify({"ok": False, "msg": "游戏不存在"})
    user_player = next((p for p in game["players"] if p.get("is_user")), None)
    if not user_player:
        return jsonify({"ok": False, "msg": "你不是玩家"})
    alive = werewolf._alive_players(game)
    order = next((i + 1 for i, p in enumerate(alive) if p["name"] == user_player["name"]), 1)
    prompt = werewolf.build_speech_prompt(game, user_player["name"], order, len(alive))
    if not prompt:
        return jsonify({"ok": False, "msg": "无法生成发言"})
    speech = _call_llm_text(prompt, temperature=0.7)
    return jsonify({"ok": True, "speech": speech})


@app.route("/api/werewolf/scores")
@login_required
def api_werewolf_scores():
    user = get_current_user()
    return jsonify({"ok": True, "score": db.get_user_ww_score(user["id"])})


@app.route("/api/werewolf/rankings")
@login_required
def api_werewolf_rankings():
    limit = int(request.args.get("limit", 20))
    return jsonify({
        "ok": True,
        "characters": db.get_char_rankings(limit),
        "users": db.get_user_rankings(limit),
    })


@app.route("/api/werewolf/reset_stats", methods=["POST"])
@login_required
def api_werewolf_reset_stats():
    user = get_current_user()
    ok = db.reset_user_ww_stats(user["id"])
    msg = "已清空你的玩家积分数据" if ok else "操作失败"
    return jsonify({"ok": ok, "msg": msg})


@app.route("/api/werewolf/config")
@login_required
def api_werewolf_config():
    import werewolf_config
    return jsonify({"ok": True, "config": werewolf_config.WEREWOLF_CONFIG})


if __name__ == "__main__":
    db.init_db()
    if not API_KEY:
        print("⚠️ 请设置环境变量 ZHIPU_API_KEY")
        sys.exit(1)
    print("🌐 GlmChat Web v5.2 启动中...")
    print("   访问 http://127.0.0.1:5000")
    app.run(debug=True, host="127.0.0.1", port=5000)
