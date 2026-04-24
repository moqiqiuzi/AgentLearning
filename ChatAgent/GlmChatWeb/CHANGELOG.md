# GlmChatWeb 改动日志

## v5.3.0 — 狼人杀视觉增强

### 新增功能

1. **动画引擎**
   - 统一的 requestAnimationFrame 循环管理所有画布动画
   - fx-canvas 粒子系统（死亡火花、幽灵上浮、守护光环、查验粒子）

2. **天体系统**
   - 夜晚：月亮（CSS radial-gradient + 月坑伪元素）
   - 白天：太阳（CSS radial-gradient + box-shadow 光晕）
   - 阶段切换时平滑过渡（opacity + transform 2s）

3. **天气效果**
   - 夜雾叠加层（linear-gradient 半透明蓝灰）
   - 日光叠加层（radial-gradient 暖黄）

4. **死亡特效**
   - 全屏白色闪光（fixed overlay + CSS animation）
   - 屏幕抖动（CSS shake keyframes）
   - 粒子火花 + 幽灵上浮动画（fx-canvas）

5. **烟花系统**
   - 独立 fireworks-canvas（fixed 全屏）
   - 多波次发射、重力下落、随机色相
   - 游戏结束时自动触发

6. **角色 SVG 动画**
   - 5 种角色的内联 SVG 图标（狼人/预言家/女巫/猎人/守卫）
   - 角色行动时居中弹出 + 彩色辉光滤镜
   - 1.2s 后自动消失

7. **发言气泡 + 打字效果**
   - 语音气泡样式：头像 + 说话人 + 内容
   - 逐字打字机效果（20ms/字）+ 闪烁光标
   - 打字完成时光标自动消失

8. **投票视觉增强**
   - 投票箭头动画（CSS arrow-slide）
   - 侧边栏投票计数徽章（红色数字角标）

9. **男女头像系统**
   - 玩家分配随机性别（male/female）
   - 男：蓝色渐变圆圈 + 👨
   - 女：粉色渐变圆圈 + 👩
   - 玩家卡片 + 翻牌 + 发言气泡 + 结算面板统一展示

10. **发言模式选择**
    - 三档：唠叨（150-300字）/ AI自由（50-150字）/ 简洁（30-60字）
    - Setup 面板新增选择器，传到后端 prompt 模板

11. **音效系统**
    - Web Audio API 程序化生成（无音频文件）
    - 6 种音效：夜晚低沉、白天明亮、死亡冲击、发言通知、投票咔嗒、胜利欢呼/失败低落
    - Header 音效开关按钮，一键静音

### 技术变更

- `templates/werewolf.html`：完全重写，~780 行（CSS 动画 + Canvas + Web Audio）
- `werewolf.py`：`create_game` 新增 `speech_mode` 参数，玩家数据新增 `gender` 字段
- `werewolf.py`：`build_speech_prompt` 根据 `speech_mode` 计算 `length_hint`
- `werewolf_prompts.py`：`DAY_SPEECH_FIRST` / `DAY_SPEECH` 模板新增 `{length_hint}` 占位符
- `app.py`：start API 接收 `speech_mode` 并传递，返回玩家含 `gender` 字段

## v5.1.0 — 多人格群聊

### 新增功能

1. **多人格群聊**
   - 侧边栏点「👥 多人格群聊」进入选择模式，勾选 2+ 人格开始
   - 三种模式：自由讨论（所有人回应）、轮流发言（逐个回应）、指定发言（点击头像指定）
   - 用户是参与者，可随时插话
   - Header 显示轮数计数器，每条消息标注发言人

2. **频率限制**
   - 每场群聊上限 30 轮
   - 人格之间发言间隔 2 秒
   - 达上限后提示，可继续发言或结束

### 技术变更

- 新增后端路由：`/api/group/start|chat|stop|status|mode`
- 群聊历史存内存（session 级），不持久化
- 每个人格独立的 system prompt 注入多人对话上下文
- SSE 事件新增 `speaker`、`speaker_start`、`group_done` 字段
- 前端人格列表支持复选框模式切换

### Bug 修复

- 修复 `get_enabled_personas` SQL UNION 导致系统人格和用户人格 id 冲突的问题（改为按 type 分别查询）
- 系统人格新增「移除」按钮（从列表隐藏，数据库保留），可重新启用
- 用户人格「删除」按钮只删用户自建人格
- 修复 `login_required` 对页面请求返回 JSON 401 而非重定向的问题
- 添加 session permanent（7 天）和前端登录状态检查

## v5.0.0 — 用户系统 + 人格管理改造

### 新增功能

1. **用户系统**
   - 注册（用户名 + 密码，SHA256 哈希存储）
   - 登录 / 退出
   - 未登录自动跳转登录页

2. **人格管理**
   - 新用户注册后默认启用 3 个人格：诗人、杠精、鲁迅
   - 可从系统人格中启用更多
   - 新建人格：填写名字 → AI 生成 / 随机模板填充 6 个维度 → 可编辑 → 确认创建
     - 基础身份、说话语气、优点、缺点、小习惯与怪癖、价值观与立场、背景故事
   - 系统人格可移除（隐藏），用户自建人格可删除

3. **SQLite 本地数据库**
   - 替代原来的内存 sessions + JSON 缓存文件
   - 5 张表：users、personas_system、personas_user、user_personas、chat_history
   - 数据库文件：`chat.db`

### 技术变更

- 去掉随机 sid，改用用户名绑定会话
- 对话历史存 SQLite，废弃 `chat_cache/` 目录（已清理 65 个遗留 JSON 文件）
- 新增 `db.py`（数据库封装）、`auth.py`（认证逻辑）
- 新增 `templates/login.html`、`templates/register.html`
- 改造 `templates/index.html`（用户栏、人格管理面板、新建人格弹窗）
- 重写 `app.py` 路由

### 设计文档

详见 `REDESIGN.md`
