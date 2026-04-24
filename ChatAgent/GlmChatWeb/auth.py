import hashlib
import os
from functools import wraps
from flask import request, jsonify, redirect, session

import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent / ".." / "GlmChat"))

from db import get_user_by_name, create_user


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def do_register(username, password):
    if not username or not password:
        return False, "用户名和密码不能为空"
    if len(username) < 2 or len(username) > 20:
        return False, "用户名长度 2-20 个字符"
    if len(password) < 4:
        return False, "密码至少 4 位"
    if get_user_by_name(username):
        return False, "用户名已存在"
    uid = create_user(username, hash_password(password))
    if uid is None:
        return False, "注册失败"
    return True, "注册成功"


def do_login(username, password):
    user = get_user_by_name(username)
    if not user:
        return False, "用户名或密码错误"
    if user["password"] != hash_password(password):
        return False, "用户名或密码错误"
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session.permanent = True
    return True, "登录成功"


def do_logout():
    session.clear()


def get_current_user():
    uid = session.get("user_id")
    uname = session.get("username")
    if uid and uname:
        return {"id": uid, "username": uname}
    return None


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_current_user():
            if request.accept_mimetypes.accept_html and not request.path.startswith("/api/"):
                return redirect("/login")
            return jsonify({"error": "未登录"}), 401
        return f(*args, **kwargs)
    return decorated
