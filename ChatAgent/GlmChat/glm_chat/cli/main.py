import sys
import random
import time
import json
from datetime import datetime

from glm_chat.api import ChatSession, call_api_stream, MODELS
from glm_chat.personas import PERSONAS, PERSONA_ALIASES, PERSONA_TAGS


def print_banner():
    colors = ["\033[9" + str(random.randint(1, 7)) + "m" for _ in range(5)]
    reset = "\033[0m"
    banner = f"""
{colors[0]}  ╔══════════════════════════════════════╗
{colors[1]}  ║     🤖  GLM 聊天机器人 v4.0         ║
{colors[2]}  ║   /list 查看人格  /人格名 切换       ║
{colors[3]}  ║        输入 q 退出                   ║
{colors[4]}  ╚══════════════════════════════════════╝{reset}
"""
    print(banner)


def print_persona_list():
    print("\n🎭 可用人格（输入 /人格名 切换）：")
    print("─" * 45)
    for i, (name, _desc) in enumerate(PERSONAS.items(), 1):
        tag = PERSONA_TAGS.get(name, "")
        print(f"  {i:>2}. /{name:<5s} {tag}")
    print("─" * 45)
    print(f"  共 {len(PERSONAS)} 个 · /随机 随机切换\n")


def print_help():
    print("""
可用命令：
  /人格名           直接切换（如 /鲁迅 /海盗 /猫娘）
  /list             查看所有可用人格
  /随机             随机切换一个人格
  /model            查看所有可用模型
  /model <模型名>   切换模型（如 /model glm-4-flash）
  /sys <提示词>     自定义系统人格
  /temp <0.0~1.0>   调节温度
  /clear            清空对话记忆
  /save             导出聊天记录
  /undo             撤销上一轮对话
  /stats            查看本轮统计
  q / quit / exit   退出
""".strip())


def handle_command(session: ChatSession, user_input: str) -> bool | None:
    cmd = user_input.strip()
    parts = cmd.split(maxsplit=1)
    command = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if command in ("q", "quit", "exit"):
        print("再见！")
        sys.exit(0)

    if command == "/help":
        print_help()
        return True

    if command in ("/list", "/人格", "/列表"):
        print_persona_list()
        return True

    if command in ("/随机", "/random"):
        name = random.choice(list(PERSONAS.keys()))
        old_count = len(session.history)
        session.set_persona(name, PERSONAS[name])
        rounds = len(session.history) // 2
        msg = f"🎭 已切换为【{name}】模式"
        if rounds > 0:
            msg += f"，已恢复 {rounds} 轮历史对话"
        print(msg)
        return True

    if command in PERSONA_ALIASES:
        name = PERSONA_ALIASES[command]
        session.set_persona(name, PERSONAS[name])
        rounds = len(session.history) // 2
        msg = f"🎭 已切换为【{name}】模式"
        if rounds > 0:
            msg += f"，已恢复 {rounds} 轮历史对话"
        print(msg)
        return True

    if command == "/model":
        if not arg:
            print("\n📋 可用模型：")
            print("─" * 45)
            for name, desc in MODELS.items():
                marker = " ◀ 当前" if name == session.model else ""
                print(f"  {name:<16s} {desc}{marker}")
            print("─" * 45)
            print("  用法：/model glm-4-flash\n")
        elif arg in MODELS:
            session.model = arg
            print(f"🔧 模型已切换为 {arg}（{MODELS[arg]}）")
        else:
            print(f"⚠️ 未知模型：{arg}")
            print(f"   可用：{', '.join(MODELS.keys())}")
        return True

    if command == "/sys":
        if not arg:
            print(f"当前系统提示词：{session.system_prompt or '(未设置)'}")
        else:
            session.set_persona("自定义", arg)
            print(f"✅ 系统人格已设置：{arg}")
        return True

    if command == "/temp":
        try:
            val = float(arg)
            if 0 <= val <= 1:
                session.temperature = val
                print(f"🌡️ 温度已设为 {val}")
            else:
                print("⚠️ 温度范围 0.0 ~ 1.0")
        except ValueError:
            print("⚠️ 请输入数字，如 /temp 0.7")
        return True

    if command == "/clear":
        session.reset()
        print("🗑️ 对话已清空")
        return True

    if command == "/undo":
        if len(session.history) >= 2:
            session.history.pop()
            session.history.pop()
            print("↩️ 已撤销上一轮")
        else:
            print("⚠️ 没有可以撤销的对话")
        return True

    if command == "/save":
        filename = f"chat_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump({
                "persona": session.persona_name,
                "system": session.system_prompt,
                "messages": session.history,
                "saved_at": datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)
        print(f"💾 聊天记录已保存到 {filename}")
        return True

    if command == "/stats":
        elapsed = time.time() - session.start_time
        rounds = len(session.history) // 2
        print(f"""
📊 本轮统计：
  当前模型：{session.model}
  当前人格：{session.persona_name}
  对话轮数：{rounds}
  输入总字数：{session.total_input_chars}
  输出总字数：{session.total_output_chars}
  持续时间：{elapsed:.0f} 秒
  当前温度：{session.temperature}
""".strip())
        return True

    print(f"⚠️ 未知命令：{command}，输入 /help 查看可用命令")
    return True


def main():
    from glm_chat.api import API_KEY

    if not API_KEY:
        print("⚠️ 请设置环境变量 ZHIPU_API_KEY")
        print("   方法：set ZHIPU_API_KEY=你的密钥")
        sys.exit(1)

    session = ChatSession()
    print_banner()

    while True:
        if session.persona_name != "智谱小A":
            prompt_label = f"\n{session.persona_name}·你："
        else:
            prompt_label = "\n你："
        try:
            user_input = input(prompt_label)
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input.strip():
            continue

        if user_input.strip().startswith("/"):
            handle_command(session, user_input)
            continue

        print(f"\n{session.persona_name}：", end="", flush=True)
        response, elapsed, first_token = call_api_stream(session, user_input)

        parts = []
        if first_token > 0:
            parts.append(f"⚡ 首字 {first_token:.1f}s")
        parts.append(f"⏱ 总计 {elapsed:.1f}s")
        if elapsed > 0 and len(response) > 0:
            speed = len(response) / elapsed
            parts.append(f"📝 {len(response)}字  {speed:.0f}字/s")
        print(f"  {'  '.join(parts)}")
