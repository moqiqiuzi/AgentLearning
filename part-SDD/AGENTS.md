# AGENTS.md

## Agent架构概述

基于项目愿景 v1.0，本系统采用多Agent协作架构，完成从GitHub Trending数据抓取到结构化知识条目输出的全流程。

---

## 1. Collector Agent（采集Agent）

### 职责
每天抓取GitHub Trending Today维度的AI相关项目

### 功能规范
- **抓取目标**：GitHub Trending Today页面
- **抓取数量**：Top 30条（或全部可用项目）
- **筛选策略**：
  1. **预筛选阶段**：基于关键词过滤
     - 关键词列表：`["AI", "ML", "Machine Learning", "Deep Learning", "LLM", "NLP", "Computer Vision", "GPT", "Claude", "Transformer", "PyTorch", "TensorFlow"]`
     - 过滤位置：项目标签（topics）、描述（description）、项目名称
  2. **兜底策略**：预筛选后不足30条，按实际数量抓取

### 输出格式
```json
{
  "projects": [
    {
      "name": "项目名称",
      "url": "https://github.com/owner/repo",
      "description": "项目描述",
      "author": "owner",
      "language": "Python",
      "stars": 3500,
      "forks": 280,
      "updated_at": "2024-04-21T10:30:00Z",
      "topics": ["AI", "LLM", "transformers"],
      "source": "github_trending"
    }
  ],
  "collected_at": "2024-04-21T12:00:00Z",
  "total_count": 30
}
```

### 验收标准
- 每日成功抓取≥30条（或全部可用项目）
- 预筛选准确率≥90%（排除明显非AI项目）

---

## 2. Analyzer Agent（分析Agent）

### 职责
用AI对采集到的项目进行深度分析和评分

### 功能规范
- **二次确认**：判断项目是否真的是AI相关（避免关键词误判）
- **多维度评分**：5个维度，每个维度1-5分
  1. **技术价值**：是否提供新算法/新思路/实用工具
  2. **实用性**：是否可以直接应用到生产环境
  3. **易用性**：文档完善度、上手难度、依赖复杂度
  4. **活跃度**：Star/Fork数、维护活跃度、社区响应
  5. **整体推荐度**：综合评分（前4项的平均值或加权）
- **输出内容**：
  - 5个维度的评分（1-5分）
  - 简短分析理由（100-200字）
  - 优先级标签（high/medium/low）
  - 技术标签提取（tags）
  - 技术栈识别（tech_stack）
  - 应用场景（use_cases）

### 输出格式
```json
{
  "analysis": {
    "tech_value": 5,
    "practicality": 4,
    "usability": 4,
    "activity": 5,
    "overall": 4.5,
    "reason": "提供新的LLM微调方法，文档完善，已在GitHub获得3.5k stars，适合快速上手",
    "priority": "high",
    "tags": ["LLM", "微调", "开源", "大模型"],
    "tech_stack": ["PyTorch", "Transformers", "PEFT"],
    "use_cases": ["模型训练", "推理优化", "个性化微调"]
  },
  "is_ai_related": true,
  "analyzed_at": "2024-04-21T12:05:00Z"
}
```

### 验收标准
- Agent分析成功率≥95%（排除API失败等异常）
- AI相关性判断准确率≥90%（人工复核）
- 评分合理性：整体推荐度与前4项评分逻辑一致

---

## 3. Organizer Agent（整理Agent）

### 职责
将采集的基础数据和分析结果合并，输出统一JSON格式的知识条目

### 功能规范
- **数据合并**：将Collector和Agent的输出合并
- **ID生成**：为每个项目生成唯一ID（基于URL或时间戳）
- **字段补全**：确保所有必填字段完整
- **数据验证**：验证JSON结构完整性

### 输出格式（严格对齐spec）
```json
{
  "id": "github_owner_repo_20240421",
  "name": "项目名称",
  "description": "项目简介",
  "url": "https://github.com/owner/repo",
  "author": "owner",
  "stars": 3500,
  "forks": 280,
  "updated_at": "2024-04-21T10:30:00Z",
  "language": "Python",
  "tags": ["LLM", "微调", "开源"],
  "tech_stack": ["PyTorch", "Transformers"],
  "use_cases": ["模型训练", "推理优化"],
  "analysis": {
    "tech_value": 5,
    "practicality": 4,
    "usability": 4,
    "activity": 5,
    "overall": 4.5,
    "reason": "提供新的LLM微调方法，文档完善，已在GitHub获得3.5k stars，适合快速上手",
    "priority": "high"
  },
  "collected_at": "2024-04-21T12:00:00Z",
  "source": "github_trending"
}
```

### 输出文件
- 文件路径：`data/knowledge_items/YYYY-MM-DD.json`
- 文件格式：每行一个JSON对象（JSON Lines）
- 每日运行生成一个新文件

### 验收标准
- 知识条目JSON结构100%完整
- 所有必填字段非空
- 数据类型正确（数值型字段为数字，时间戳为ISO 8601格式）

---

## 4. Publisher Agent（发布Agent）

### 职责
将知识条目通过邮件推送形式发布给用户

### 功能规范
- **筛选逻辑**：基于analysis.priority筛选推送内容
  - high：优先推送
  - medium：视邮件容量决定
  - low：通常不推送（除非high+medium不足）
- **邮件数量**：每日推送10-15篇（确保信息密度适中）
- **邮件格式**：Markdown格式，移动端友好
- **邮件内容**：
  - 标题：AI知识日报 - YYYY-MM-DD
  - 摘要：今日Top N项目速览
  - 正文：每个项目包含：
    - 项目名称 + 链接
    - 评分（overall评分）
    - 简短理由
    - 关键标签
    - Star数统计

### 输出格式（邮件模板）
```markdown
# AI知识日报 - 2024-04-21

## 今日精选 Top 10

### [1] 项目名称 - overall: 4.5/5
🔗 [GitHub链接](https://github.com/owner/repo)
⭐ Stars: 3.5k | 🍴 Forks: 280

提供新的LLM微调方法，文档完善，已在GitHub获得3.5k stars，适合快速上手

**标签**: LLM, 微调, 开源
**技术栈**: PyTorch, Transformers
**应用场景**: 模型训练, 推理优化

---

### [2] 项目名称 - overall: 4.3/5
...
```

### 验收标准
- 邮件内容排版美观、链接有效
- 移动端显示正常
- 邮件送达率≥98%
- 用户阅读反馈评分≥4.0/5.0

---

## Agent协作流程

```
[定时触发] 每天00:00
    ↓
[Collector] 抓取GitHub Trending Today
    ↓ (原始项目列表)
[Analyzer] AI分析 + 评分 + 标签提取
    ↓ (分析结果)
[Organizer] 合并数据 + 生成知识条目JSON
    ↓ (知识条目文件)
[Publisher] 筛选 + 生成邮件 + 推送
    ↓
[用户接收邮件]
```

---

## 系统边界（严格对齐spec）

### 只做
- ✅ GitHub Trending AI相关项目抓取和分析
- ✅ 邮件推送（定时模式）

### 不做
- ❌ 用户注册/登录系统
- ❌ 网页端展示
- ❌ 实时交互（定时推送模式）
- ❌ Hacker News / arXiv（仅GitHub Trending）

---

## 验证方法

### 1. 验证Agent分析准确性
- 随机抽样10条，人工复核评分和理由
- 人工判断AI相关性是否准确
- 目标：分析准确率≥95%

### 2. 验证去重效果
- 连续3天运行，检查是否有重复项目进入推送
- 基于URL去重，同一项目3天内只推送一次
- 目标：重复率≤5%

### 3. 验证邮件推送
- 测试邮件内容排版
- 测试链接有效性
- 测试移动端显示效果
- 目标：邮件送达率≥98%，移动端显示正常

---

## 技术实现建议

### 推荐技术栈
- **Agent框架**: LangChain / AutoGen
- **LLM**: GPT-4 / Claude API
- **数据库**: PostgreSQL + pgvector（存储知识条目）
- **邮件服务**: SendGrid / AWS SES
- **任务调度**: Celery / Redis
- **爬虫**: requests + BeautifulSoup / Selenium
- **部署**: Docker + K8s

### 数据流
```
GitHub API → Collector → Raw Data → Analyzer → Analysis → Organizer → Knowledge Items → Publisher → Email
```

---

## 编码规范

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

### 技术栈边界

- 本项目不做网页端展示，**不引入 TypeScript**
- 如未来增加前端模块，届时单独制定前端编码规范

---

## 版本信息
- **文档版本**: v1.1
- **对齐spec**: specs/project-vision_OpenCode.md v1.0
- **创建日期**: 2024-04-21
- **维护者**: 产品经理 + 技术负责人
