# GlmChatWeb 改造方案

> 只改 GlmChatWeb，CLI 和单文件版本不动。

---

## 一、总体改动概览

| 模块 | 改动 |
|---|---|
| 数据库 | 新增 SQLite，替代现有内存 sessions + JSON 缓存 |
| 用户系统 | 新增注册、登录、退出 |
| 人格系统 | 32 个系统人格迁入 DB；新建人格支持 AI 生成 + 随机模板；用户人格可删除 |
| 前端 | 新增登录/注册页，聊天页加用户栏和人格管理面板 |

---

## 二、数据库设计（SQLite，文件：`GlmChatWeb/chat.db`）

### 表结构

```sql
-- 用户表
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    password    TEXT    NOT NULL,           -- hashlib.sha256 哈希
    created_at  TEXT    NOT NULL
);

-- 系统人格表（启动时从 personas.py 初始化，32 个）
CREATE TABLE personas_system (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    prompt      TEXT    NOT NULL,           -- 完整人格提示词
    tag         TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);

-- 用户人格表（用户自建的人格）
CREATE TABLE personas_user (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    name        TEXT    NOT NULL,
    identity    TEXT    NOT NULL DEFAULT '',   -- 基础身份
    tone        TEXT    NOT NULL DEFAULT '',   -- 说话语气
    strengths   TEXT    NOT NULL DEFAULT '',   -- 优点
    weaknesses  TEXT    NOT NULL DEFAULT '',   -- 缺点
    habits      TEXT    NOT NULL DEFAULT '',   -- 小习惯与怪癖
    values      TEXT    NOT NULL DEFAULT '',   -- 价值观与立场
    backstory   TEXT    NOT NULL DEFAULT '',   -- 背景小故事
    prompt      TEXT    NOT NULL,              -- 由以上字段组合生成的完整提示词
    created_at  TEXT    NOT NULL,
    UNIQUE(user_id, name)
);

-- 用户已启用的人格关联表（系统人格 + 用户人格）
CREATE TABLE user_personas (
    user_id     INTEGER NOT NULL REFERENCES users(id),
    persona_type TEXT   NOT NULL,             -- 'system' 或 'user'
    persona_id  INTEGER NOT NULL,             -- 对应 personas_system.id 或 personas_user.id
    enabled_at  TEXT    NOT NULL,
    PRIMARY KEY (user_id, persona_type, persona_id)
);

-- 对话历史表（替代现有 chat_cache/ JSON 文件）
CREATE TABLE chat_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    persona_type TEXT   NOT NULL,
    persona_id  INTEGER NOT NULL,
    role        TEXT    NOT NULL,              -- 'user' 或 'assistant'
    content     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
```

### 初始化逻辑（app.py 启动时）

```
1. 检查 chat.db 是否存在，不存在则创建
2. 检查 personas_system 表是否为空
   - 空 → 从 personas.py 的 PERSONAS 字典批量插入 32 条
   - 非空 → 跳过
3. 新用户注册时，自动在 user_personas 插入 3 条默认关联：
   诗人、杠精、鲁迅（type='system'）
```

---

## 三、API 设计

### 3.1 用户相关（新增）

```
POST /api/register
  Body: { "username": "xxx", "password": "xxx" }
  返回: { "ok": true } 或 { "ok": false, "msg": "用户名已存在" }

POST /api/login
  Body: { "username": "xxx", "password": "xxx" }
  返回: { "ok": true, "username": "xxx" } 或 { "ok": false, "msg": "用户名或密码错误" }

POST /api/logout
  返回: { "ok": true }

GET  /api/me
  返回: { "username": "xxx" } 或 { "error": "未登录" }
```

### 3.2 人格相关（改造）

```
GET  /api/personas
  返回当前用户已启用的人格列表（系统 + 用户自建）

GET  /api/personas/available
  返回当前用户尚未启用的系统人格列表

POST /api/personas/enable
  Body: { "persona_id": 5 }
  返回: { "ok": true }
  说明: 启用一个系统人格，写入 user_personas

POST /api/personas/create
  Body: { "name": "海盗", "identity": "...", "tone": "...", ... }
  或   { "name": "海盗", "ai_generate": true }        ← AI 自动生成 6 个字段
  或   { "name": "海盗", "random_template": true }     ← 从预设模板随机填充
  返回: { "ok": true, "persona": { ... } }

POST /api/personas/generate
  Body: { "name": "海盗" }
  说明: 调用 GLM API 根据名字生成 identity/tone/strengths/weaknesses/habits/values/backstory
  返回: { "identity": "...", "tone": "...", ... }

DELETE /api/personas/<id>
  说明: 只能删除 user_id 匹配的用户自建人格（persona_type='user'）
  返回: { "ok": true } 或 { "ok": false, "msg": "不能删除系统人格" }
```

### 3.3 聊天相关（改造）

```
- 去掉 sid 参数，所有接口通过 session/cookie 识别用户
- POST /api/chat 的对话记录写入 chat_history 表
- GET /api/session 从 DB 读取当前状态
- POST /api/clear 清除 chat_history 中对应记录
- POST /api/undo 删除 chat_history 最后两条
```

---

## 四、前端页面流程

### 4.1 页面结构

```
/login          登录页（含"去注册"链接）
/register       注册页（含"去登录"链接）
/               聊天主页（需登录，未登录自动跳转 /login）
```

### 4.2 登录/注册页

- 用户名 + 密码两个输入框
- 登录页底部有"没有账号？注册"
- 注册页底部有"已有账号？登录"
- 登录成功后跳转到聊天主页

### 4.3 聊天主页改造

- **顶部用户栏**：左侧显示用户名，右侧"退出"按钮
- **人格管理面板**（在现有人格列表基础上扩展）：
  - "新建人格"按钮 → 弹出创建面板
  - "启用更多"按钮 → 展示未启用的系统人格列表
  - 用户自建人格旁边显示"删除"按钮
  - 系统人格无删除按钮

### 4.4 新建人格面板（弹窗）

```
┌─────────────────────────────────┐
│  新建人格                        │
│                                 │
│  人格名称：[__________]          │
│                                 │
│  [AI 生成]  [随机模板]           │
│                                 │
│  基础身份：  [______________]    │
│  说话语气：  [______________]    │
│  优点：      [______________]    │
│  缺点：      [______________]    │
│  小习惯/怪癖：[______________]   │
│  价值观/立场：[______________]   │
│  背景故事：  [______________]    │
│                                 │
│         [确认创建]               │
└─────────────────────────────────┘
```

- 点"AI 生成"：调 `/api/personas/generate`，GLM 根据名字自动填入 6 个字段
- 点"随机模板"：从预设模板列表中随机选一个填入（模板在后端维护，约 10-15 个）
- 用户可逐字段编辑后点"确认创建"
- 创建时后端将 6 个字段拼接成完整 prompt 存入 `personas_user.prompt`

---

## 五、随机模板样例（后端维护 10-15 个）

```python
TEMPLATES = [
    {
        "identity": "一位退休的宇宙飞船船长，曾在银河系边境航行三十年",
        "tone": "沉稳、略带怀旧，偶尔蹦出几个航海术语，说话像在讲故事",
        "strengths": "见多识广，冷静果断，善于在危机中找到出路",
        "weaknesses": "固执，不容易信任新人，对过去的遗憾放不下",
        "habits": "喜欢用星星的位置比喻时间，喝咖啡时一定要搅拌三下",
        "values": "相信探索精神比安全更重要，认为每个人心中都有一片星海",
        "backstory": "曾经在一次深空任务中失去了最好的副手，从此提前退休。如今在地球上开了一家太空主题小酒馆"
    },
    {
        "identity": "一位生活在宋代市井的卖花姑娘，每天清晨去西湖边采摘鲜花",
        # ...
    },
    # ... 10-15 个模板
]
```

---

## 六、prompt 拼接规则

创建用户人格时，6 个字段按以下模板拼接为完整 system prompt：

```
你是{name}。
身份：{identity}
说话语气：{tone}
优点：{strengths}
缺点：{weaknesses}
小习惯：{habits}
价值观：{values}
背景故事：{backstory}
请严格按照以上设定进行对话。
```

---

## 七、文件改动清单

| 文件 | 改动 |
|---|---|
| `GlmChatWeb/app.py` | 重写：加数据库初始化、用户路由、人格路由改造、聊天路由改造 |
| `GlmChatWeb/db.py` | **新建**：SQLite 封装（建表、CRUD 操作） |
| `GlmChatWeb/auth.py` | **新建**：注册/登录/退出逻辑、密码哈希、session 管理 |
| `GlmChatWeb/templates/login.html` | **新建**：登录页 |
| `GlmChatWeb/templates/register.html` | **新建**：注册页 |
| `GlmChatWeb/templates/index.html` | **改造**：加用户栏、人格管理面板、新建人格弹窗 |
| `GlmChatWeb/templates/persona_create.html` | **新建**（或内嵌弹窗）：新建人格表单 |
| `GlmChatWeb/static/` | 样式更新 |
| `GlmChatWeb/chat_cache/` | **废弃**：历史记录迁移到 SQLite |

---

## 八、不动的部分

- `glm_chat.py` 单文件版 — 不动
- `GlmChat/` 包 — 不动
- `GlmChat/glm_chat/personas.py` — 不动，Web 版启动时从中读取初始化系统人格表
- `part-SDD/`、`part-Study/` — 不动
