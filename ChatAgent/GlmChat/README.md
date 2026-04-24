# glm-chat

终端 AI 聊天工具，支持人格切换、流式输出、多模型选择。基于智谱 GLM API。

## 安装

```bash
pip install glm-chat
```

## 使用

先设置 API Key：

```bash
# Windows
set ZHIPU_API_KEY=你的密钥

# Linux / macOS
export ZHIPU_API_KEY=你的密钥
```

启动聊天：

```bash
glm-chat
```

## 功能

- **32 个人格** — 输入 `/鲁迅` `/海盗` `/杰克` 等直接切换
- **流式输出** — 实时逐字显示，不用干等
- **多模型切换** — `/model glm-4-flash` 等随时切换
- **多轮记忆** — 自动保留上下文
- **聊天导出** — `/save` 导出为 JSON

## 命令

| 命令 | 说明 |
|---|---|
| `/人格名` | 直接切换（如 `/鲁迅` `/妲己` `/杰克`） |
| `/list` | 查看所有人格 |
| `/随机` | 随机切换 |
| `/model` | 查看可用模型 |
| `/model glm-4-flash` | 切换模型 |
| `/temp 0.7` | 调节温度（0~1） |
| `/undo` | 撤销上一轮 |
| `/save` | 导出聊天记录 |
| `/clear` | 清空记忆 |
| `/stats` | 查看统计 |

## 从源码安装

```bash
git clone https://github.com/yourname/glm-chat.git
cd glm-chat
pip install -e .
```

## License

MIT
