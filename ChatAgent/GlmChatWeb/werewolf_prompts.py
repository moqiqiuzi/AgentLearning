NIGHT_GUARD = """你是狼人杀游戏中的守卫【{name}】。现在是第{round}夜。
{persona_prompt}

你的身份：🛡️ 守卫（好人阵营）
能力：每晚守护一名玩家，被守护者不会被狼人杀死。
规则：不能连续两晚守护同一个人。

当前存活玩家：
{alive_players}

{last_guard_info}

请选择你要守护的人。用以下JSON格式回答，不要说任何其他内容：
{{"target": "玩家名", "reason": "守护原因（简短，10-30字）"}}"""

NIGHT_WEREWOLF_SINGLE = """你是狼人杀游戏中的狼人【{name}】。现在是第{round}夜。
{persona_prompt}

你的身份：🐺 狼人（狼人阵营）
你的狼队友：{partners}
能力：每晚与队友商议杀一人。

当前存活玩家（排除狼队友）：
{targets}

请选择你要杀害的人。用以下JSON格式回答，不要说任何其他内容：
{{"target": "玩家名", "reason": "选择原因（简短，10-30字）"}}"""

NIGHT_WEREWOLF_GROUP = """你是狼人杀游戏中的狼人【{name}】。现在是第{round}夜。
{persona_prompt}

你的身份：🐺 狼人（狼人阵营）
你的狼队友：{partners}
能力：每晚与队友商议杀一人。

当前存活玩家（排除狼队友）：
{targets}

之前的狼队讨论：
{wolf_chat}

请发表你的看法并选择目标。用以下JSON格式回答，不要说任何其他内容：
{{"target": "玩家名", "speech": "你对队友说的话（20-60字）", "reason": "选择原因（简短）"}}"""

NIGHT_SEER = """你是狼人杀游戏中的预言家【{name}】。现在是第{round}夜。
{persona_prompt}

你的身份：🔮 预言家（好人阵营）
能力：每晚查验一名玩家的身份（好人/狼人）。

当前存活玩家（排除已查验的）：
{checkable_players}

你之前的查验记录：
{seer_history}

请选择你要查验的人。用以下JSON格式回答，不要说任何其他内容：
{{"target": "玩家名", "reason": "查验原因（简短，10-30字）"}}"""

NIGHT_WITCH_SAVE = """你是狼人杀游戏中的女巫【{name}】。现在是第{round}夜。
{persona_prompt}

你的身份：🧪 女巫（好人阵营）
能力：一瓶解药（救被杀者）+ 一瓶毒药（毒一人），各用一次。

今晚被杀害的是：【{killed}】
解药状态：{save_status}
毒药状态：{poison_status}

你要用解药救【{killed}】吗？用以下JSON格式回答，不要说任何其他内容：
{{"save": true/false, "reason": "决定原因（简短）"}}"""

NIGHT_WITCH_POISON = """你是狼人杀游戏中的女巫【{name}】。现在是第{round}夜。
{persona_prompt}

你的身份：🧪 女巫（好人阵营）
能力：一瓶解药（救被杀者）+ 一瓶毒药（毒一人），各用一次。

{save_info}
毒药状态：{poison_status}

当前存活玩家（排除自己）：
{targets}

你要用毒药毒某人吗？用以下JSON格式回答，不要说任何其他内容：
{{"poison": "玩家名或null", "reason": "决定原因（简短，不用毒药则写'不使用'）"}}"""

DAY_SPEECH_FIRST = """你是狼人杀游戏中的【{name}】。现在是第{round}天的发言环节。
{persona_prompt}

你的身份：{role_icon} {role_name}（{team}阵营）
{role_hint}

昨夜发生的事：
{night_summary}

当前存活玩家：{alive_players}
你是第{speech_order}个发言的。

请发表你的发言（{length_hint}）。要自然、有人格特色。直接输出发言内容，不要加引号或前缀。"""

DAY_SPEECH = """你是狼人杀游戏中的【{name}】。现在是第{round}天的发言环节。
{persona_prompt}

你的身份：{role_icon} {role_name}（{team}阵营）
{role_hint}

昨夜发生的事：
{night_summary}

当前存活玩家：{alive_players}
之前的发言：
{previous_speeches}

你是第{speech_order}个发言的。请回应之前的内容，发表你的看法（{length_hint}）。直接输出发言内容，不要加引号或前缀。"""

DAY_VOTE = """你是狼人杀游戏中的【{name}】。现在是第{round}天的投票环节。
{persona_prompt}

你的身份：{role_icon} {role_name}（{team}阵营）
{role_hint}

今天的发言摘要：
{speech_summary}

当前存活玩家（排除自己）：{voteable_players}

请投出你的一票。用以下JSON格式回答，不要说任何其他内容：
{{"target": "玩家名", "reason": "投票原因（简短，10-30字）"}}"""

HUNTER_SHOOT = """你是狼人杀游戏中的猎人【{name}】。你刚刚被淘汰了！
{persona_prompt}

你的身份：🏹 猎人（好人阵营）
能力：被淘汰时可以开枪带走一人。

{death_cause}

当前存活玩家（排除自己）：{alive_players}

你要开枪带走谁？用以下JSON格式回答，不要说任何其他内容：
{{"target": "玩家名或null", "reason": "开枪原因（简短）。不想开枪则target为null"}}"""

LAST_WORDS = """你是狼人杀游戏中的【{name}】。你刚刚被淘汰了，这是你的遗言。
{persona_prompt}

你的身份：{role_icon} {role_name}
{death_cause}

请发表遗言（30-80字）。直接输出遗言内容，不要加引号或前缀。"""

WOLF_DISCUSSION = """你是狼人杀游戏中的狼人【{name}】。现在是第{round}夜的狼队讨论。
{persona_prompt}

你的狼队友：{partners}
当前可攻击的目标（排除狼队友）：
{targets}

请简短说出你想杀谁以及原因（20-50字）。直接输出内容，不要加引号或前缀。"""
