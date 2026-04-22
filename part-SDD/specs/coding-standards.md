# AI 知识库 · 编码规范 v1.0

> 本文档为 AGENTS.md "编码规范" 段的源 spec，两处保持同步。

## 要做什么

### 工具链

| 工具 | 用途 | 配置 |
|---|---|---|
| ruff | lint + format + import sort | 行长度 88，规则集 E/F/W/D100/D103/D417/TD001 |
| mypy | 类型检查 | `--strict` |
| uv | 依赖管理 | 替代 pip/poetry |
| pre-commit | 本地检查 | ruff format + ruff check + mypy |

### Python 规范

- **格式化**: ruff（行长度 88），不单独用 black
- **import 排序**: ruff 内置 isort，profile=black
- **类型注解**: 所有函数参数和返回值必须有类型注解，mypy strict 模式
- **文档字符串**: 公开函数（不以 `_` 开头）必须有 Google Style docstring
- **字符串常量**: 关键词列表放配置文件，枚举值用 `StrEnum`，JSON 结构用 `dataclass` / `TypedDict`
- **TODO 管理**: 必须带 issue 编号 `# TODO(#42): 说明`，不允许无主 TODO

### 测试策略

| Agent | 覆盖率目标 | 策略 |
|---|---|---|
| Organizer | ≥ 90% | 纯函数单测 |
| Collector / Publisher | ≥ 80% | mock 外部依赖 |
| Analyzer | ≥ 80% | mock LLM + snapshot 测试 |
| 端到端 | 1 条冒烟 | 4 Agent 串联不报错即可 |

- 覆盖率检查：**增量 block**（新代码 ≥ 80%），**全量仅报告**
- 测试框架：pytest + pytest-asyncio

### CI 流水线

```
PR 触发:          lint + 单测（快，几分钟）
每天 08:00 触发:  lint + 单测 + 覆盖率报告 + 端到端（全量）
```

- lint 失败则跳过单测，串行执行
- Python 版本锁定 3.11，只跑一个版本
- pre-commit hook 本地兜底（ruff + mypy，与 CI 规则一致）

## 不做什么

- **不引入 TypeScript** — 本项目不做网页端展示；如未来增加前端模块，届时单独制定前端编码规范
- **不用 black / flake8 / isort / pylint** — 全部由 ruff 替代
- **不写无法机器检查的规范** — 每条规则都有对应的工具执行（ruff D/TD 规则、mypy、pytest-cov）

## 变更记录

| 版本 | 日期 | 变更内容 |
|---|---|---|
| v0.1 | 2024-04-21 | 初稿 |
| v1.0 | 2024-04-21 | grill 审订：ruff 替代 black+flake8；砍 TypeScript；分层测试策略；CI 双触发；TODO 带编号 |
