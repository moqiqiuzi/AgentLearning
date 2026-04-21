# AGENTS.md

## 概述

本文档定义 AI 知识库系统的所有 Agent 规格，严格对齐 `specs/project-vision.md`。

**Agent 架构：**

```
┌─────────────────────────────────────────────────────────────┐
│                      Agent 协作流程                          │
│                                                              │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────┐ │
│  │采集Agent │───▶│提取Agent │───▶│摘要Agent │───▶│输出  │ │
│  └──────────┘    └──────────┘    └──────────┘    └──────┘ │
│       │                │                              ▲    │
│       │                └──────────┬───────────────────┘    │
│       │                           │                         │
│       ▼                           ▼                         │
│  ┌──────────┐              ┌──────────┐                    │
│  │ 过滤规则  │              │分类Agent │                    │
│  └──────────┘              └──────────┘                    │
│                                   │                         │
│                                   ▼                         │
│                            ┌──────────┐                    │
│                            │质量Agent │                    │
│                            └──────────┘                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. 采集 Agent (Collector Agent)

### 职责
从三大数据源抓取原始内容，执行 AI 相关性过滤。

### 输入
| 参数 | 类型 | 说明 |
|------|------|------|
| `source` | enum | `github` \| `hackernews` \| `arxiv` |
| `date` | string | 抓取日期 (ISO8601) |

### 输出
```typescript
interface RawContent {
  source: "github" | "hackernews" | "arxiv"
  url: string
  raw_html?: string      // GitHub/HackerNews
  raw_text?: string      // arXiv
  collected_at: string   // ISO8601
}
```

### 采集规格（对齐 spec 数据源采集规则）

#### GitHub Trending
| 配置项 | 值 |
|--------|-----|
| 抓取量 | 全量 ~25 条/天 |
| URL | `https://github.com/trending` |
| AI 判定 | Topic 包含: `machine-learning`, `ai`, `llm`, `deep-learning`, `nlp`, `computer-vision`, `agent` OR 描述匹配关键词库 |

#### Hacker News
| 配置项 | 值 |
|--------|-----|
| 抓取量 | 前 30 条/天 |
| URL | `https://news.ycombinator.com/news` |
| AI 判定 | 标题/URL 包含: `AI`, `LLM`, `GPT`, `model`, `training`, `agent` 等关键词 |

#### arXiv
| 配置项 | 值 |
|--------|-----|
| 抓取量 | 10 条/天 |
| API | `http://export.arxiv.org/api/query` |
| AI 判定 | 分类: `cs.AI`, `cs.CL`, `cs.LG` |

### 边界约束（对齐 spec 不做什么）
- ❌ 区块链/Web3 项目
- ❌ 游戏开发项目
- ❌ 纯数据可视化工具
- ❌ 非英文资源
- ⚠️ 只抓取当天发布的新内容

### 验收标准（对齐 spec MVP 验收标准）
- 采集成功率 ≥ 95%
- 失败需有重试机制
- 监控 + 失败告警（钉钉/邮件）

---

## 2. 提取 Agent (Extractor Agent)

### 职责
从原始内容中提取结构化元数据。

### 输入
```typescript
interface ExtractorInput {
  source: "github" | "hackernews" | "arxiv"
  url: string
  raw_content: string
}
```

### 输出
```typescript
interface ExtractedMetadata {
  title: string
  author: string
  description: string
  published_at: string  // ISO8601
  // GitHub 特有
  stars?: number
  language?: string
  // arXiv 特有
  authors?: string[]
  abstract?: string
  // HackerNews 特有
  points?: number
  comments_count?: number
}
```

### 字段映射规则

| 字段 | GitHub | HackerNews | arXiv |
|------|--------|------------|-------|
| title | repo 名称 | 标题 | 论文标题 |
| author | owner | 提交者 | 第一作者 |
| description | README/描述 | 描述 | 摘要 |
| published_at | pushed_at | 时间戳 | published |
| stars | ⭐ | - | - |
| points | - | ⭐ | - |

---

## 3. 摘要 Agent (Summarizer Agent)

### 职责
提炼内容的核心技术要点/创新点。

### 输入
```typescript
interface SummarizerInput {
  title: string
  description: string
  raw_content: string
  source_type: "repo" | "article" | "paper"
}
```

### 输出
```typescript
interface Summary {
  points: string[]  // 3-5 点核心要点
}
```

### 摘要规格
| 维度 | 要求 |
|------|------|
| 数量 | 3-5 点 |
| 风格 | 技术导向，突出创新点 |
| 长度 | 每点 20-50 字 |
| 语言 | 英文（MVP） |

### Prompt 模板
```
你是一个 AI 技术专家。请分析以下 {source_type}，提炼 3-5 个核心技术要点或创新点。

标题: {title}
描述: {description}

要求:
1. 每个要点 20-50 字
2. 突出技术创新或实用价值
3. 技术术语准确
4. 输出 JSON 数组格式
```

### 验收标准（对齐 spec MVP 验收标准）
- 摘要事实错误率 < 5%
- 人工抽检 10 条/天
- LLM 交叉验证

---

## 4. 分类 Agent (Classifier Agent)

### 职责
为内容打标签，进行领域分类。

### 输入
```typescript
interface ClassifierInput {
  title: string
  description: string
  summary: string[]
}
```

### 输出
```typescript
interface Classification {
  tags: string[]  // 如: ["NLP", "LLM", "工具"]
}
```

### 标签体系（对齐 spec）
| 一级分类 | 二级标签示例 |
|---------|-------------|
| NLP | LLM, Transformer, Tokenizer, Embedding |
| CV | 图像生成, 目标检测, Segmentation |
| RL | 强化学习, 多智能体, 策略优化 |
| Agent | Agent框架, Tool Use, Multi-Agent |
| 工具 | 训练框架, 数据处理, 部署工具 |
| 数据集 | 文本, 图像, 多模态 |

### 分类规则
- 每条内容 1-3 个标签
- 优先匹配一级分类，必要时加二级标签
- 标签从预定义词表中选择，不随意创造

### 验收标准（对齐 spec MVP 验收标准）
- 分类准确率 ≥ 85%（一级分类）
- 人工抽检 20 条/周

---

## 5. 质量 Agent (Quality Agent)

### 职责
综合评估内容质量，打分 0-100。

### 输入
```typescript
interface QualityInput {
  source: "github" | "hackernews" | "arxiv"
  title: string
  description: string
  summary: string[]
  tags: string[]
  metadata: ExtractedMetadata
}
```

### 输出
```typescript
interface QualityScore {
  score: number  // 0-100
  reason: string // 打分理由（可选）
}
```

### 打分维度
| 维度 | 权重 | 指标 |
|------|------|------|
| 技术深度 | 40% | 创新性、技术含量、实现难度 |
| 影响力 | 30% | stars/points、引用数、讨论热度 |
| 新颖性 | 20% | 时间新近度、内容独特性 |
| 完整性 | 10% | 文档完善度、代码质量 |

### 质量阈值（对齐 spec MVP 验收标准）
| 分数区间 | 含义 | 处理 |
|---------|------|------|
| 80-100 | 高质量 | 优先展示 |
| 60-79 | 良好 | 正常展示 |
| < 60 | 低质量 | 过滤或降权 |

**MVP 目标**: 质量分 > 60 的内容占比 ≥ 80%

---

## 6. 输出 Agent (Output Agent)

### 职责
整合所有 Agent 结果，输出最终知识条目。

### 输入
```typescript
interface OutputInput {
  extracted: ExtractedMetadata
  summary: Summary
  classification: Classification
  quality: QualityScore
  source: "github" | "hackernews" | "arxiv"
}
```

### 输出（对齐 spec 知识条目格式）
```json
{
  "id": "uuid",
  "title": "string",
  "source": "github|hackernews|arxiv",
  "source_type": "repo|article|paper",
  "url": "string",
  "author": "string",
  "summary": ["要点1", "要点2", "要点3"],
  "tags": ["NLP", "LLM", "工具"],
  "quality_score": 85,
  "published_at": "ISO8601",
  "collected_at": "ISO8601",
  "raw_content": "string"
}
```

### 存储策略
| 格式 | 用途 |
|------|------|
| JSON | 数据库存储，便于查询过滤 |
| Markdown | 人类阅读展示 |

### 去重规则
- 相同 URL 视为重复
- 标题相似度 > 90% 视为重复
- 保留质量分更高的版本

---

## Agent 协作流程

```
1. 采集 Agent
   │
   ├─▶ AI 相关性过滤 (关键词/Topic/分类)
   │   └─▶ 不相关 → 丢弃
   │
2. 提取 Agent
   │
   └─▶ 结构化元数据
       │
3. 摘要 Agent ←───────────────┐
   │                          │
   └─▶ 3-5 点要点             │
       │                      │
4. 分类 Agent ◀───────────────┤
   │                          │
   └─▶ 1-3 个标签             │
       │                      │
5. 质量 Agent ◀───────────────┘
   │
   └─▶ 质量分 (0-100)
       │
6. 输出 Agent
   │
   ├─▶ JSON 存储数据库
   └─▶ Markdown 展示
```

---

## 全局验收标准汇总

| 标准 | 目标值 | 验证方式 |
|------|--------|----------|
| 稳定性 | 连续 7 天无故障运行 | 监控日志 |
| 产出量 | 每天 ≥ 15 条有效知识条目 | 计数器 |
| 质量门槛 | 质量分 > 60 占比 ≥ 80% | 统计分析 |
| 摘要准确性 | 事实错误率 < 5% | 人工抽检 10 条/天 + LLM 交叉验证 |
| 分类准确率 | ≥ 85% | 人工抽检 20 条/周 |
| 采集成功率 | ≥ 95% | 日志监控 + 失败告警 |

---

## 待确认事项

- [ ] Agent 之间的消息传递协议
- [ ] Agent 失败重试策略
- [ ] 并发执行顺序（串行 vs 并行）
- [ ] LLM 模型选择（摘要/分类/质量 Agent）
- [ ] 成本控制（Token 预算）
