实操二换成了智谱的API，大概意思我清楚了，就是用编排器和没有用编排器差别很大，强调了编排器的作用，没有编排器，就是个QA问答器

url：https://open.bigmodel.cn/api/coding/paas/v4   返回404 NotFound

url：https://open.bigmodel.cn/api/paas/v3/model-api/chatglm_lite/sse-invoke  返回余额不足

![image07](E:\AgentLearning\AgentLearning\part01\IMAGE\image07.png)

---

一、环境

![image01](E:\AgentLearning\AgentLearning\part01\IMAGE\image01.png)

二、双路并行

​	A路·Vibe

​	你是一位技术产品经理。我在做一个AI知识库系统，自动抓GitHubTrending/HackerNews/arXiv的AI相关内容，用Agent协作完成采集→分析→整理→发布。请帮我写一份项目愿景文档。

​	claudecode表现：

​	直接生成了一篇愿景文档

​	opencode表现：

​	询问细节后再针对性的生成一篇愿景文档

![image06](E:\AgentLearning\AgentLearning\part01\IMAGE\image06.png)

​	B路·SDD闭环

​	按三阶段走：**Specify→Clarify→Implement**。