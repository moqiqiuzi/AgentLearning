# AGENTS.md

## 项目定位

OpenCode + GLM 的 AI 辅助开发学习项目。非生产代码。三个独立子项目。

## 目录结构

```
ChatAgent/          ← 多人格 GLM 聊天机器人（3 套实现）
  glm_chat.py         单文件 CLI（仅依赖标准库）
  GlmChat/            可 pip install -e . 安装的包
  GlmChatWeb/         Flask Web UI（通过 sys.path 依赖 GlmChat/）

part-SDD/           ← 仅为设计文档，无任何已实现代码
  AGENTS.md            未来知识库项目的多 Agent 规格说明
  CODING.md            未来项目的编码规范（不适用于 ChatAgent）

part-Study/         ← 学习笔记
  step.txt             SDD 教程步骤
```

## ChatAgent — 运行方式

```bash
# 单文件版（需要 ZHIPU_API_KEY 环境变量）
python ChatAgent/glm_chat.py

# 包版 CLI
cd ChatAgent/GlmChat && pip install -e .
set ZHIPU_API_KEY=<密钥>
glm-chat

# Web 版（必须在 GlmChatWeb/ 目录运行，sys.path 才能找到 ../GlmChat）
cd ChatAgent/GlmChatWeb
pip install flask flask-cors
set ZHIPU_API_KEY=<密钥>
python app.py
# → http://127.0.0.1:5000
```

## 架构 — 光看文件名看不出来的事

- GlmChatWeb 通过 `sys.path.insert`（`app.py:11`）从同级 GlmChat/ 包导入 `glm_chat.personas` 和 `glm_chat.api`。GlmChat 必须存在，Web 版才能运行。
- 三套实现共用同一核心：人格系统 + 通过标准库 `urllib` 调用 GLM 流式 API（不依赖 `requests`、`openai` SDK、`langchain`）。
- API 端点：`https://open.bigmodel.cn/api/anthropic/v1/messages`（Anthropic 兼容格式）。
- SSE delta 解析兼容 3 种响应格式：`content_block_delta`、`message_delta`、OpenAI 风格的 `choices`。
- `glm_chat.py` 切换人格时清空历史。GlmChat 和 GlmChatWeb 保留各人格的对话历史并缓存到磁盘（`~/.glm_chat_cache/` 和 `GlmChatWeb/chat_cache/`）。
- GlmChatWeb 用 `threading` + `queue.Queue` 做 SSE 流式传输，没用 async。
- 32 个人格定义在 `GlmChat/glm_chat/personas.py`（`glm_chat.py` 内也有内联副本）。

## 踩坑提醒

- 三个实现都依赖 `ZHIPU_API_KEY` 环境变量。`glm_chat.py` 里硬编码了一个密钥——不要复制这种做法。
- 本仓库没有测试、没有 linter、没有类型检查、没有 CI。纯探索性代码。
- `part-SDD/AGENTS.md` 为未来项目指定了 ruff + mypy + pytest，但**当前仓库未配置**，不适用于 ChatAgent。
- `part-SDD/CODING.md` 涉及 TypeScript 和另一套工具链——与当前代码库无关。
- Python 3.10+（GlmChat 的 `pyproject.toml` 限定）。Windows 环境（环境变量用 `set` 而非 `export`）。

## 关键约束

- 纯 Python。仓库中没有 Node.js 工具链。
- 仓库根目录无 `pyproject.toml`——各子项目自行管理。
- 唯一的外部依赖：`flask` + `flask-cors`（仅 GlmChatWeb）。其余均为标准库。
- `.gitignore` 覆盖：`__pycache__/`、`*.pyc`、`dist/`、`build/`、`*.egg-info/`、`chat_log_*.json`、`.env`
