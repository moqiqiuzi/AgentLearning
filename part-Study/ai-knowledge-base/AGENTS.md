# AI 知识库助手 — Agent 操作指南

## 1. 项目概述

本系统是一个 AI 驱动的技术知识库助手，自动从 GitHub Trending 和 Hacker News 采集 AI/LLM/Agent 领域的技术动态，经 AI 分析后结构化存储为 JSON，并通过 Telegram、飞书等多渠道分发给用户，帮助开发者高效追踪前沿技术趋势。

## 2. 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.12 |
| Agent 框架 | LangGraph |
| AI 模型 | OpenCode + 国产大模型（DeepSeek / Qwen / GLM） |
| 数据采集 | OpenClaw |
| 通知渠道 | Telegram Bot API / 飞书开放平台 |

## 3. 编码规范

- **代码风格**：遵循 PEP 8
- **命名规则**：变量与函数使用 `snake_case`，类使用 `PascalCase`
- **文档字符串**：使用 Google 风格 docstring

  ```python
  def fetch_trending(topic: str, limit: int = 10) -> list[dict]:
      """从 GitHub Trending 获取指定主题的热门仓库。

      Args:
          topic: 主题关键词，如 "llm" 或 "agent"。
          limit: 返回条目的最大数量。

      Returns:
          包含仓库信息的字典列表。
      """
  ```

- **日志规范**：禁止裸 `print()`，统一使用 `logging` 模块

  ```python
  import logging

  logger = logging.getLogger(__name__)
  logger.info("采集完成，共 %d 条", len(items))
  ```

- **类型注解**：所有公开函数必须标注参数和返回值类型
- **错误处理**：所有外部调用（网络请求、文件 IO）必须使用 `try/except` 包裹

## 4. 项目结构

```
ai-knowledge-base/
├── AGENTS.md                    # 本文件：Agent 操作指南
├── .opencode/
│   ├── agents/                  # Agent 角色定义
│   │   ├── collector.py         # 采集 Agent
│   │   ├── analyzer.py          # 分析 Agent
│   │   └── organizer.py         # 整理 Agent
│   └── skills/                  # 可复用技能
│       ├── github_trending.py   # GitHub Trending 采集技能
│       ├── hacker_news.py       # Hacker News 采集技能
│       └── notify.py            # 多渠道通知技能
├── knowledge/
│   ├── raw/                     # 原始采集数据（HTML / API 响应）
│   └── articles/                # 结构化知识条目（JSON）
├── config/
│   └── settings.yaml            # 项目配置（源地址、调度频率等）
├── requirements.txt
└── main.py                      # 入口文件
```

## 5. 知识条目 JSON 格式

每条知识以独立 JSON 文件存储于 `knowledge/articles/` 目录下，文件名为 `{id}.json`。

```json
{
  "id": "gh-20260421-001",
  "title": "LangGraph v0.3 发布：支持子图与并行执行",
  "source_url": "https://github.com/langchain-ai/langgraph/releases/tag/v0.3.0",
  "source": "github_trending",
  "summary": "LangGraph v0.3 引入子图（subgraph）和并行节点执行能力，大幅提升复杂工作流编排的灵活性。",
  "tags": ["langgraph", "agent", "release"],
  "status": "draft",
  "created_at": "2026-04-21T10:30:00+08:00",
  "updated_at": "2026-04-21T10:30:00+08:00"
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `id` | string | 是 | 唯一标识，格式：`{来源缩写}-{日期}-{序号}` |
| `title` | string | 是 | 条目标题 |
| `source_url` | string | 是 | 原始链接 |
| `source` | string | 是 | 来源标识：`github_trending` / `hacker_news` |
| `summary` | string | 是 | AI 生成的中文摘要，100-300 字 |
| `tags` | list[string] | 是 | 标签列表，2-5 个 |
| `status` | string | 是 | 状态：`draft` → `reviewed` → `published` |
| `created_at` | string | 是 | ISO 8601 格式创建时间 |
| `updated_at` | string | 是 | ISO 8601 格式更新时间 |

**状态流转：**

```
draft → reviewed → published
  │                   │
  └─── rejected ←─────┘
```

## 6. Agent 角色概览

| 角色 | 职责 | 输入 | 输出 | 关键能力 |
|------|------|------|------|----------|
| **采集 Agent** (Collector) | 从数据源抓取技术动态 | 配置的数据源列表 | `knowledge/raw/` 下的原始数据 | 网页解析、API 调用、定时调度、去重过滤 |
| **分析 Agent** (Analyzer) | 对原始内容进行 AI 分析 | `knowledge/raw/` 中的原始数据 | `knowledge/articles/` 中的 JSON 条目 | 内容理解、摘要生成、标签分类、质量评估 |
| **整理 Agent** (Organizer) | 管理知识条目状态并分发 | `status=draft` 的条目 | Telegram / 飞书推送消息 | 状态流转、模板渲染、多渠道推送、批量归档 |

**Agent 协作流程：**

```
Collector → raw/ → Analyzer → articles/(draft) → Organizer → 通知渠道
                       ↑                            │
                       └──── rejected / 需补充 ←─────┘
```

## 7. 红线（绝对禁止的操作）

- **禁止提交密钥**：任何 API Key、Token、Secret 不允许出现在代码中，统一通过环境变量或 `.env` 文件加载（`.env` 必须加入 `.gitignore`）
- **禁止裸 `print()`**：所有输出必须通过 `logging` 模块
- **禁止硬编码路径**：文件路径和 URL 必须通过 `config/settings.yaml` 管理
- **禁止跳过异常处理**：所有网络请求、文件读写、外部 API 调用必须有 `try/except`
- **禁止直接操作主分支**：所有变更通过功能分支 + Pull Request 合入
- **禁止存储重复条目**：写入前必须按 `source_url` 去重
- **禁止推送未经审核的内容**：`status=draft` 的条目不得分发到通知渠道
