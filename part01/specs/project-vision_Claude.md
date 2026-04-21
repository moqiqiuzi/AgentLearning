# AI 知识库·项目愿景 v1.0

## 要做什么

- 每天抓取 GitHub Trending（全量~25条）、Hacker News（前30条）、arXiv（10条），过滤AI相关内容

- 用多Agent协作分析内容：
  - **提取Agent**：提取标题、作者、描述、star数等元数据
  - **摘要Agent**：提炼3-5点技术要点/创新点
  - **分类Agent**：打标签（NLP/CV/RL/Agent/工具/数据集等）
  - **质量Agent**：综合技术深度、影响力、新颖性打分（0-100）

- 输出知识条目（JSON存储 + Markdown展示）：
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

## 不做什么（项目边界）

| 边界类型 | 排除内容 |
|---------|---------|
| 内容边界 | 区块链/Web3、游戏开发、纯数据可视化 |
| 内容边界 | 非英文资源 |
| 功能边界 | 用户评论/社区互动 |
| 功能边界 | 个性化推荐算法 |
| 功能边界 | 付费订阅 |
| 时间边界 | 只抓取当天发布的新内容 |

## 数据源采集规则

| 数据源 | 抓取量 | AI判定规则 |
|--------|--------|------------|
| GitHub Trending | 全量~25条/天 | Topic包含: `machine-learning`, `ai`, `llm`, `deep-learning`, `nlp`, `computer-vision`, `agent` OR 描述匹配关键词库 |
| Hacker News | 前30条/天 | 标题/URL包含: `AI`, `LLM`, `GPT`, `model`, `training`, `agent` 等关键词 |
| arXiv | 10条/天 | 分类: `cs.AI`, `cs.CL`, `cs.LG` |

## MVP验收标准

| 维度 | 标准 | 说明 |
|-----|------|------|
| 稳定性 | 连续7天无故障运行 | 证明系统可靠性 |
| 产出量 | 每天≥15条有效知识条目 | 三源合计，去重后 |
| 质量门槛 | 质量分>60的内容占比≥80% | 过滤低质量内容 |
| 准确性 | 摘要事实错误率<5% | 人工抽检验证 |
| 分类准确率 | ≥85% | 一级分类准确 |
| 采集成功率 | ≥95% | 失败需有重试机制 |

## 怎么验证

| 验证项 | 方法 | 频次 |
|-------|------|------|
| 摘要质量 | 人工抽检10条/天 + LLM交叉验证 | 每日 |
| 分类准确率 | 人工抽检20条/周，标注对比 | 每周 |
| 采集成功率 | 日志监控 + 失败告警（钉钉/邮件） | 实时 |
| 用户价值 | 10个种子用户试用 + NPS调研 | MVP后 |
