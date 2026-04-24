# AGENTS.md

## What this repo is

Learning project for AI-assisted development with OpenCode + GLM. Not production code. Three independent sub-projects.

## Repository layout

```
ChatAgent/          ← Multi-personality GLM chatbot (3 implementations)
  glm_chat.py         Single-file CLI (no deps beyond stdlib)
  GlmChat/            pip-installable package (pip install -e .)
  GlmChatWeb/         Flask web UI (depends on GlmChat/ via sys.path)

part-SDD/           ← Design docs only, nothing implemented
  AGENTS.md            Multi-agent spec for a future knowledge-base project
  CODING.md            Coding standards for the future project (does NOT apply to ChatAgent)

part-Study/         ← Learning notes
  step.txt             Step-by-step SDD tutorial
```

## ChatAgent — how to run

```bash
# Single-file (needs ZHIPU_API_KEY env var)
python ChatAgent/glm_chat.py

# Package CLI
cd ChatAgent/GlmChat && pip install -e .
set ZHIPU_API_KEY=<key>
glm-chat

# Web (must run from GlmChatWeb/ so sys.path to ../GlmChat resolves)
cd ChatAgent/GlmChatWeb
pip install flask flask-cors
set ZHIPU_API_KEY=<key>
python app.py
# → http://127.0.0.1:5000
```

## Architecture — things not obvious from filenames

- GlmChatWeb imports `glm_chat.personas` and `glm_chat.api` from the sibling GlmChat/ package via `sys.path.insert` (`app.py:11`). GlmChat must be present for GlmChatWeb to work.
- All three implementations share the same core: persona system + streaming GLM API calls via stdlib `urllib` (no `requests`, no `openai` SDK, no `langchain`).
- API endpoint: `https://open.bigmodel.cn/api/anthropic/v1/messages` (Anthropic-compatible format).
- SSE delta parsing handles 3 response formats: `content_block_delta`, `message_delta`, OpenAI-style `choices`.
- `glm_chat.py` clears history on persona switch. GlmChat and GlmChatWeb preserve per-persona history and cache to disk (`~/.glm_chat_cache/` and `GlmChatWeb/chat_cache/` respectively).
- GlmChatWeb uses `threading` + `queue.Queue` for SSE streaming, not async.
- 32 personas defined in `GlmChat/glm_chat/personas.py` (also inlined in `glm_chat.py`).

## Gotchas

- `ZHIPU_API_KEY` env var is required for all three implementations. `glm_chat.py` has a key baked in — do not replicate that pattern.
- No tests, no linter, no type checking, no CI anywhere in this repo. It is exploratory code.
- `part-SDD/AGENTS.md` specifies ruff + mypy + pytest for a future project. Those tools are **not configured** and do not apply to ChatAgent.
- `part-SDD/CODING.md` mentions TypeScript and a different toolchain — irrelevant to the current codebase.
- Python 3.10+ (enforced in GlmChat's `pyproject.toml`). Windows environment (`set` not `export` for env vars).

## Key constraints

- Python only. No Node.js tooling in this repo.
- No `pyproject.toml` at repo root — each sub-project manages its own config.
- Only external deps: `flask` + `flask-cors` (GlmChatWeb only). Everything else is stdlib.
- `.gitignore` covers `__pycache__/`, `*.pyc`, `dist/`, `build/`, `*.egg-info/`, `chat_log_*.json`, `.env`
