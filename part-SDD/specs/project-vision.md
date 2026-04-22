# AI 知识库·项目愿景 v1.0

## 要做什么

- 每天抓取GitHub Trending Top 30条（Today维度）
  - AI关键词预筛选：AI/ML/LLM/NLP/CV等相关标签和描述
  - Agent二次确认：判断项目是否真的是AI相关
  - 兜底策略：预筛选后不足30条则按实际数量抓取

- 用Agent分析内容
  - 分析维度（5个，1-5分评分）：技术价值、实用性、易用性、活跃度、整体推荐度
  - 输出：结构化JSON（评分+简短理由+优先级标签high/medium/low）

- 输出知识条目（统一JSON格式）
  - 基础信息：name, description, url, author
  - 统计数据：stars, forks, updated_at, language
  - 分类标签：tags, tech_stack, use_cases
  - 分析结果：analysis（嵌套评分对象）
  - 元数据：id, collected_at, source

## 不做什么

- 不做用户注册/登录系统
- 不做网页端展示（专注邮件推送）
- 不做实时交互（定时推送模式）

## 边界 & 验收

- 边界：仅处理GitHub Trending AI相关项目
- 验收标准：每日成功抓取≥30条（或全部可用项目），Agent分析成功率≥95%，知识条目JSON结构完整

## 怎么验证

- 验证Agent分析准确性：随机抽样10条，人工复核评分和理由
- 验证去重效果：连续3天运行，检查是否有重复项目进入推送
- 验证邮件推送：测试邮件内容排版、链接有效性、移动端显示效果
