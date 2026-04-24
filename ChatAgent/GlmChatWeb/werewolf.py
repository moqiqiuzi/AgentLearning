import json
import random
import time
import uuid
import copy

from werewolf_themes import ROLE_CONFIGS, ROLE_INFO, THEMES
import werewolf_prompts as prompts


WEREWOLF_SPEED = {"slow": 3.0, "medium": 1.5, "fast": 0.5}

_active_games = {}


def create_game(total, user_mode, theme=None, persona_names=None, user_persona=None, speech_mode="free"):
    if total < 6 or total > 12:
        return None, "人数必须在 6-12 之间"
    if user_mode not in ("god", "player", "observer"):
        return None, "无效用户模式"

    config = ROLE_CONFIGS.get(total)
    if not config:
        return None, f"不支持 {total} 人局"

    role_list = []
    for role_key, count in config.items():
        for _ in range(count):
            role_list.append(role_key)
    random.shuffle(role_list)

    characters = _select_characters(theme, persona_names, total)
    if characters is None:
        return None, "角色不足"

    players = []
    for i, char in enumerate(characters):
        players.append({
            "name": char["name"],
            "prompt": char["prompt"],
            "role": role_list[i],
            "alive": True,
            "seat": i + 1,
            "is_user": False,
            "gender": char.get("gender", "male"),
        })

    if user_mode == "player" and user_persona:
        target_seat = random.randint(0, total - 1)
        players[target_seat]["name"] = user_persona["name"]
        players[target_seat]["prompt"] = user_persona.get("prompt", "")
        players[target_seat]["is_user"] = True
        players[target_seat]["role"] = _assign_user_role(players[target_seat]["role"], role_list)
        players[target_seat]["gender"] = user_persona.get("gender", "male")

    game = {
        "id": uuid.uuid4().hex[:12],
        "phase": "setup",
        "sub_step": None,
        "round": 0,
        "config": {
            "total": total,
            "user_mode": user_mode,
            "theme": theme,
            "speed": "medium",
            "role_config": config,
            "speech_mode": speech_mode,
        },
        "players": players,
        "night_actions": {},
        "public_log": [],
        "secret_log": [],
        "events": [],
        "game_over": False,
        "winner": None,
        "user_action": None,
        "step_cursor": 0,
    }

    for p in players:
        if p["role"] == "werewolf":
            p["werewolf_partners"] = [
                other["name"] for other in players
                if other["role"] == "werewolf" and other["name"] != p["name"]
            ]
        if p["role"] == "seer":
            p["seer_checks"] = {}
        if p["role"] == "witch":
            p["witch_save_used"] = False
            p["witch_poison_used"] = False
            p["poison_target"] = None
        if p["role"] == "guard":
            p["guard_last"] = None

    _active_games[game["id"]] = game
    return game, None


def _assign_user_role(original_role, role_list):
    return original_role


def _select_characters(theme, persona_names, total):
    if theme and theme in THEMES:
        chars = THEMES[theme]["characters"]
        if len(chars) >= total:
            return random.sample(chars, total)
        return list(chars) + [
            {"name": f"角色{i}", "prompt": f"你是{theme}世界中的一个角色。"}
            for i in range(len(chars), total)
        ]
    if persona_names and len(persona_names) >= total:
        return [{"name": n, "prompt": ""} for n in persona_names[:total]]
    if persona_names:
        result = [{"name": n, "prompt": ""} for n in persona_names]
        for i in range(len(result), total):
            result.append({"name": f"玩家{i+1}", "prompt": ""})
        return result
    names = [f"玩家{i+1}" for i in range(total)]
    return [{"name": n, "prompt": ""} for n in names]


def get_game(game_id):
    return _active_games.get(game_id)


def remove_game(game_id):
    _active_games.pop(game_id, None)


def set_user_action(game_id, action):
    game = _active_games.get(game_id)
    if game:
        game["user_action"] = action


def set_speed(game_id, speed):
    game = _active_games.get(game_id)
    if game and speed in WEREWOLF_SPEED:
        game["config"]["speed"] = speed


def _emit(game, event_type, data):
    event = {"event": event_type, **data, "round": game["round"]}
    game["events"].append(event)
    game["secret_log"].append(event)


def _emit_public(game, event_type, data):
    event = {"event": event_type, **data, "round": game["round"]}
    game["events"].append(event)
    game["public_log"].append(event)


def _alive_players(game):
    return [p for p in game["players"] if p["alive"]]


def _alive_wolves(game):
    return [p for p in game["players"] if p["alive"] and p["role"] == "werewolf"]


def _alive_good(game):
    return [p for p in game["players"] if p["alive"] and p["role"] != "werewolf"]


def check_win(game):
    wolves = _alive_wolves(game)
    good = _alive_good(game)
    if len(wolves) == 0:
        return "village"
    if len(wolves) >= len(good):
        return "werewolf"
    return None


def start_night(game):
    game["round"] += 1
    game["phase"] = "night"
    game["sub_step"] = "guard_check"
    game["night_actions"] = {
        "guard_target": None,
        "werewolf_target": None,
        "seer_target": None,
        "seer_result": None,
        "witch_save": False,
        "witch_poison": None,
        "killed": None,
    }
    _emit_public(game, "phase_change", {"phase": "night"})
    return _build_night_steps(game)


def _build_night_steps(game):
    config = game["config"]["role_config"]
    steps = []
    if config.get("guard", 0) > 0:
        steps.append(("guard", "guard_action"))
    steps.append(("werewolf", "werewolf_action"))
    if config.get("seer", 0) > 0:
        steps.append(("seer", "seer_action"))
    if config.get("witch", 0) > 0:
        steps.append(("witch_save", "witch_save_action"))
        steps.append(("witch_poison", "witch_poison_action"))
    steps.append(("resolve", "resolve_night"))
    return steps


def build_guard_prompt(game):
    guard = next((p for p in game["players"] if p["alive"] and p["role"] == "guard"), None)
    if not guard:
        return None, None
    alive = [p["name"] for p in _alive_players(game) if p["name"] != guard["name"]]
    last_info = ""
    if guard.get("guard_last"):
        last_info = f"注意：你上一晚守护的是【{guard['guard_last']}】，不能再守他。"
    prompt = prompts.NIGHT_GUARD.format(
        name=guard["name"],
        round=game["round"],
        persona_prompt=guard["prompt"],
        alive_players="\n".join(f"  {i+1}. {n}" for i, n in enumerate(alive)),
        last_guard_info=last_info,
    )
    return guard, prompt


def resolve_guard(game, target_name):
    guard = next((p for p in game["players"] if p["alive"] and p["role"] == "guard"), None)
    if not guard:
        return
    game["night_actions"]["guard_target"] = target_name
    guard["guard_last"] = target_name
    _emit(game, "action_result", {"role": "guard", "player": guard["name"], "target": target_name})


def build_werewolf_prompt(game):
    wolves = _alive_wolves(game)
    if not wolves:
        return [], []
    targets = [p["name"] for p in _alive_players(game) if p["role"] != "werewolf"]
    wolf_names = [w["name"] for w in wolves]
    partner_map = {w["name"]: [n for n in wolf_names if n != w["name"]] for w in wolves}
    result_prompts = []
    for w in wolves:
        partners_str = "、".join(partner_map[w["name"]]) if partner_map[w["name"]] else "无（你是独狼）"
        p = prompts.NIGHT_WEREWOLF_SINGLE.format(
            name=w["name"],
            round=game["round"],
            persona_prompt=w["prompt"],
            partners=partners_str,
            targets="\n".join(f"  {i+1}. {n}" for i, n in enumerate(targets)),
        )
        result_prompts.append((w, p))
    return wolves, result_prompts


def resolve_werewolf(game, target_name, speech=None):
    game["night_actions"]["werewolf_target"] = target_name
    wolves = _alive_wolves(game)
    if speech:
        _emit(game, "action_text", {"role": "werewolf", "speech": speech})
    _emit(game, "action_result", {
        "role": "werewolf",
        "players": [w["name"] for w in wolves],
        "target": target_name,
    })


def build_seer_prompt(game):
    seer = next((p for p in game["players"] if p["alive"] and p["role"] == "seer"), None)
    if not seer:
        return None, None
    checked = list(seer.get("seer_checks", {}).keys())
    checkable = [p["name"] for p in _alive_players(game) if p["name"] != seer["name"] and p["name"] not in checked]
    history_lines = []
    for name, result in seer.get("seer_checks", {}).items():
        icon = "🐺" if result == "werewolf" else "✅"
        history_lines.append(f"  {name}：{icon} {'狼人' if result == 'werewolf' else '好人'}")
    history_str = "\n".join(history_lines) if history_lines else "  （尚未查验任何人）"
    prompt = prompts.NIGHT_SEER.format(
        name=seer["name"],
        round=game["round"],
        persona_prompt=seer["prompt"],
        checkable_players="\n".join(f"  {i+1}. {n}" for i, n in enumerate(checkable)),
        seer_history=history_str,
    )
    return seer, prompt


def resolve_seer(game, target_name):
    seer = next((p for p in game["players"] if p["alive"] and p["role"] == "seer"), None)
    if not seer:
        return
    target = next((p for p in game["players"] if p["name"] == target_name), None)
    if not target:
        return
    is_wolf = target["role"] == "werewolf"
    seer.setdefault("seer_checks", {})[target_name] = "werewolf" if is_wolf else "good"
    game["night_actions"]["seer_target"] = target_name
    game["night_actions"]["seer_result"] = "werewolf" if is_wolf else "good"
    _emit(game, "action_result", {
        "role": "seer",
        "player": seer["name"],
        "target": target_name,
        "result": "狼人" if is_wolf else "好人",
    })


def build_witch_save_prompt(game):
    witch = next((p for p in game["players"] if p["alive"] and p["role"] == "witch"), None)
    if not witch:
        return None, None
    killed = game["night_actions"].get("werewolf_target")
    if not killed:
        return None, None
    save_status = "已使用❌" if witch.get("witch_save_used") else "可用✅"
    poison_status = "已使用❌" if witch.get("witch_poison_used") else "可用✅"
    prompt = prompts.NIGHT_WITCH_SAVE.format(
        name=witch["name"],
        round=game["round"],
        persona_prompt=witch["prompt"],
        killed=killed,
        save_status=save_status,
        poison_status=poison_status,
    )
    return witch, prompt


def resolve_witch_save(game, do_save):
    witch = next((p for p in game["players"] if p["alive"] and p["role"] == "witch"), None)
    if not witch:
        return
    if do_save and not witch.get("witch_save_used"):
        game["night_actions"]["witch_save"] = True
        witch["witch_save_used"] = True
        _emit(game, "action_result", {"role": "witch", "action": "save", "target": game["night_actions"]["werewolf_target"]})
    else:
        _emit(game, "action_result", {"role": "witch", "action": "no_save"})


def build_witch_poison_prompt(game):
    witch = next((p for p in game["players"] if p["alive"] and p["role"] == "witch"), None)
    if not witch:
        return None, None
    if witch.get("witch_poison_used"):
        return None, None
    targets = [p["name"] for p in _alive_players(game) if p["name"] != witch["name"]]
    save_info = ""
    if game["night_actions"].get("witch_save"):
        save_info = f"你已使用解药救了【{game['night_actions']['werewolf_target']}】。"
    else:
        killed = game["night_actions"].get("werewolf_target")
        if killed:
            save_info = f"你没有救【{killed}】。"
    prompt = prompts.NIGHT_WITCH_POISON.format(
        name=witch["name"],
        round=game["round"],
        persona_prompt=witch["prompt"],
        save_info=save_info,
        poison_status="可用✅",
        targets="\n".join(f"  {i+1}. {n}" for i, n in enumerate(targets)),
    )
    return witch, prompt


def resolve_witch_poison(game, target_name):
    witch = next((p for p in game["players"] if p["alive"] and p["role"] == "witch"), None)
    if not witch or witch.get("witch_poison_used"):
        return
    if target_name:
        game["night_actions"]["witch_poison"] = target_name
        witch["witch_poison_used"] = True
        witch["poison_target"] = target_name
        _emit(game, "action_result", {"role": "witch", "action": "poison", "target": target_name})
    else:
        _emit(game, "action_result", {"role": "witch", "action": "no_poison"})


def resolve_night(game):
    na = game["night_actions"]
    killed = na.get("werewolf_target")
    saved = False
    deaths = []

    if killed:
        guarded = na.get("guard_target")
        witch_saved = na.get("witch_save", False)
        if guarded == killed:
            saved = True
        elif witch_saved:
            saved = True

        if not saved:
            target = next((p for p in game["players"] if p["name"] == killed), None)
            if target and target["alive"]:
                target["alive"] = False
                deaths.append({"name": killed, "cause": "werewolf"})

    poisoned = na.get("witch_poison")
    if poisoned:
        target = next((p for p in game["players"] if p["name"] == poisoned), None)
        if target and target["alive"]:
            target["alive"] = False
            deaths.append({"name": poisoned, "cause": "poison"})

    game["phase"] = "day"
    game["sub_step"] = "announce"
    game["night_deaths"] = deaths
    game["night_saved"] = saved

    if deaths:
        names = [d["name"] for d in deaths]
        _emit_public(game, "death", {"players": names, "cause": "night"})
    else:
        _emit_public(game, "death", {"players": [], "cause": "night", "peace": True})

    return deaths


def start_day(game):
    game["phase"] = "day"
    game["sub_step"] = "speech"
    _emit_public(game, "phase_change", {"phase": "day"})
    return _build_day_steps(game)


def _build_day_steps(game):
    steps = []
    deaths = game.get("night_deaths", [])
    for d in deaths:
        steps.append(("last_words", d["name"]))
    config = game["config"]["role_config"]
    alive = _alive_players(game)
    for p in alive:
        steps.append(("speech", p["name"]))
    steps.append(("vote", None))
    return steps


def build_speech_prompt(game, player_name, speech_order, total_speakers):
    player = next((p for p in game["players"] if p["name"] == player_name), None)
    if not player:
        return None
    ri = ROLE_INFO.get(player["role"], {})
    role_hint = _get_role_hint(player, game)
    emotion_hint = _get_emotion_hint(player_name, game)
    night_summary = _get_night_summary_for_player(game, player)
    alive = [p["name"] for p in _alive_players(game)]
    speech_mode = game.get("config", {}).get("speech_mode", "free")
    length_hint = {"verbose": "150-300字", "concise": "30-60字"}.get(speech_mode, "50-150字")
    extra_hint = ""
    if emotion_hint:
        extra_hint = f"\n{emotion_hint}"
    if speech_order == 1:
        return prompts.DAY_SPEECH_FIRST.format(
            name=player_name,
            round=game["round"],
            persona_prompt=player["prompt"],
            role_icon=ri.get("icon", "👤"),
            role_name=ri.get("name", "村民"),
            team="狼人" if player["role"] == "werewolf" else "好人",
            role_hint=role_hint + extra_hint,
            night_summary=night_summary,
            alive_players="、".join(alive),
            speech_order=speech_order,
            length_hint=length_hint,
        )
    speeches = game.get("day_speeches", [])
    prev = "\n".join(f"  【{s['speaker']}】：{s['content']}" for s in speeches)
    return prompts.DAY_SPEECH.format(
        name=player_name,
        round=game["round"],
        persona_prompt=player["prompt"],
        role_icon=ri.get("icon", "👤"),
        role_name=ri.get("name", "村民"),
        team="狼人" if player["role"] == "werewolf" else "好人",
        role_hint=role_hint + extra_hint,
        night_summary=night_summary,
        alive_players="、".join(alive),
        previous_speeches=prev,
        speech_order=speech_order,
        length_hint=length_hint,
    )


def _get_role_hint(player, game):
    role = player["role"]
    if role == "werewolf":
        partners = player.get("werewolf_partners", [])
        if partners:
            return f"你的狼队友是：{'、'.join(partners)}。你要隐藏身份，引导投票淘汰好人。"
        return "你是独狼。你要隐藏身份，引导投票淘汰好人。"
    if role == "seer":
        checks = player.get("seer_checks", {})
        if checks:
            lines = [f"  {n}：{'🐺狼人' if r == 'werewolf' else '✅好人'}" for n, r in checks.items()]
            return f"你查验过的结果：\n" + "\n".join(lines)
        return "你还没有查验过任何人。"
    if role == "witch":
        save = "已用" if player.get("witch_save_used") else "未用"
        poison = "已用" if player.get("witch_poison_used") else "未用"
        return f"解药：{save}，毒药：{poison}"
    if role == "guard":
        last = player.get("guard_last")
        if last:
            return f"你昨晚守护了【{last}】。"
        return "你还没守护过任何人。"
    return ""


def _get_emotion_hint(player_name, game):
    if not game.get("config", {}).get("use_emotions"):
        return ""
    try:
        import db as _db
        return _db.get_emotion_prompt(player_name)
    except Exception:
        return ""


def _get_night_summary_for_player(game, player):
    deaths = game.get("night_deaths", [])
    saved = game.get("night_saved", False)
    if not deaths and saved:
        return "昨夜是平安夜（无人死亡）。有人被救了。"
    if not deaths:
        return "昨夜是平安夜（无人死亡）。"
    names = "、".join(d["name"] for d in deaths)
    return f"昨夜【{names}】死亡。"


def add_speech(game, speaker, content):
    if "day_speeches" not in game:
        game["day_speeches"] = []
    game["day_speeches"].append({"speaker": speaker, "content": content})
    _emit_public(game, "speech", {"player": speaker, "text": content})


def build_vote_prompt(game, player_name):
    player = next((p for p in game["players"] if p["name"] == player_name and p["alive"]), None)
    if not player:
        return None
    ri = ROLE_INFO.get(player["role"], {})
    role_hint = _get_role_hint(player, game)
    night_summary = _get_night_summary_for_player(game, player)
    speeches = game.get("day_speeches", [])
    speech_summary = "\n".join(f"  【{s['speaker']}】：{s['content'][:60]}..." for s in speeches)
    voteable = [p["name"] for p in _alive_players(game) if p["name"] != player_name]
    return prompts.DAY_VOTE.format(
        name=player_name,
        round=game["round"],
        persona_prompt=player["prompt"],
        role_icon=ri.get("icon", "👤"),
        role_name=ri.get("name", "村民"),
        team="狼人" if player["role"] == "werewolf" else "好人",
        role_hint=role_hint,
        speech_summary=speech_summary,
        voteable_players="、".join(voteable),
    )


def resolve_votes(game, vote_map):
    tally = {}
    for voter, target in vote_map.items():
        tally[target] = tally.get(target, 0) + 1
        _emit_public(game, "vote_cast", {"from": voter, "to": target})

    game["day_speeches"] = []

    if not tally:
        _emit_public(game, "vote_result", {"eliminated": None, "votes": {}, "reason": "无人投票"})
        return None

    max_votes = max(tally.values())
    top = [name for name, count in tally.items() if count == max_votes]

    if len(top) > 1:
        _emit_public(game, "vote_result", {
            "eliminated": None,
            "votes": tally,
            "reason": f"平票（{', '.join(top)}各{max_votes}票）",
        })
        return None

    eliminated_name = top[0]
    player = next((p for p in game["players"] if p["name"] == eliminated_name), None)
    if player:
        player["alive"] = False
        _emit_public(game, "vote_result", {
            "eliminated": eliminated_name,
            "votes": tally,
        })
    return eliminated_name


def build_hunter_prompt(game, hunter_name, cause):
    hunter = next((p for p in game["players"] if p["name"] == hunter_name), None)
    if not hunter:
        return None
    alive = [p["name"] for p in _alive_players(game) if p["name"] != hunter_name]
    return prompts.HUNTER_SHOOT.format(
        name=hunter_name,
        persona_prompt=hunter["prompt"],
        death_cause=cause,
        alive_players="、".join(alive),
    )


def resolve_hunter(game, target_name):
    if not target_name:
        return
    target = next((p for p in game["players"] if p["name"] == target_name), None)
    if target and target["alive"]:
        target["alive"] = False
        _emit_public(game, "death", {"players": [target_name], "cause": "hunter"})


def build_last_words_prompt(game, player_name, cause):
    player = next((p for p in game["players"] if p["name"] == player_name), None)
    if not player:
        return None
    ri = ROLE_INFO.get(player["role"], {})
    return prompts.LAST_WORDS.format(
        name=player_name,
        persona_prompt=player["prompt"],
        role_icon=ri.get("icon", "👤"),
        role_name=ri.get("name", "村民"),
        death_cause=cause,
    )


def end_game(game, winner):
    game["game_over"] = True
    game["winner"] = winner
    game["phase"] = "ended"
    _emit_public(game, "game_over", {
        "winner": winner,
        "winner_label": "好人阵营" if winner == "village" else "狼人阵营",
    })


def get_public_state(game, user_mode):
    state = {
        "id": game["id"],
        "phase": game["phase"],
        "sub_step": game["sub_step"],
        "round": game["round"],
        "game_over": game["game_over"],
        "winner": game["winner"],
        "speed": game["config"]["speed"],
        "total": game["config"]["total"],
        "user_mode": user_mode,
        "theme": game["config"].get("theme"),
    }

    players_info = []
    for p in game["players"]:
        info = {
            "name": p["name"],
            "seat": p["seat"],
            "alive": p["alive"],
            "is_user": p["is_user"],
        }
        if user_mode == "god":
            info["role"] = p["role"]
            ri = ROLE_INFO.get(p["role"], {})
            info["role_icon"] = ri.get("icon", "👤")
            info["role_name"] = ri.get("name", "村民")
        elif user_mode == "player" and p["is_user"]:
            info["role"] = p["role"]
            ri = ROLE_INFO.get(p["role"], {})
            info["role_icon"] = ri.get("icon", "👤")
            info["role_name"] = ri.get("name", "村民")
        players_info.append(info)
    state["players"] = players_info

    if user_mode == "god":
        state["secret_log"] = game["secret_log"][-50:]
    state["public_log"] = game["public_log"][-50:]

    return state


def get_replay_data(game):
    return {
        "id": game["id"],
        "config": {
            "total": game["config"]["total"],
            "theme": game["config"].get("theme"),
            "role_config": game["config"]["role_config"],
            "players": [{"name": p["name"], "role": p["role"], "seat": p["seat"]} for p in game["players"]],
        },
        "events": game["events"],
        "winner": game["winner"],
            "rounds": game["round"],
    }


ROLE_WIN_POINTS = {"werewolf": 150, "seer": 120, "witch": 110, "hunter": 110, "guard": 110, "villager": 80}
ROLE_LOSE_POINTS = -30
MVP_BONUS = 50
DEATH_PENALTY = {"voted_out": -40, "poisoned": -20, "werewolf_kill": -10, "hunter_shoot": -20}


def calculate_game_scores(game):
    winner = game.get("winner", "")
    if not winner or winner == "cancelled":
        return []
    results = []
    mvp_candidate = None
    mvp_score = -999
    dead_set = set()
    for evt in game.get("events", []):
        if evt.get("event") == "death" and evt.get("players"):
            for name in evt["players"]:
                cause = evt.get("cause", "")
                if cause == "night":
                    for d in game.get("night_deaths", []):
                        if d["name"] == name:
                            dead_set.add((name, d.get("cause", "werewolf")))
                            break
                elif cause == "vote" or cause == "voted":
                    dead_set.add((name, "voted_out"))
                elif cause == "hunter":
                    dead_set.add((name, "hunter_shoot"))
                else:
                    dead_set.add((name, cause))
    for p in game["players"]:
        role = p["role"]
        team = "wolf" if role == "werewolf" else "good"
        won = (winner == "village" and team == "good") or (winner == "werewolf" and team == "wolf")
        base = ROLE_WIN_POINTS.get(role, 100) if won else ROLE_LOSE_POINTS
        bonus = 0
        if role == "hunter" and not p["alive"]:
            for evt in game.get("events", []):
                if evt.get("event") == "hunter_shoot" and evt.get("player") == p["name"]:
                    tgt = next((pp for pp in game["players"] if pp["name"] == evt.get("target")), None)
                    if tgt and tgt["role"] == "werewolf":
                        bonus += 30
                    break
        if role == "seer":
            bonus += sum(1 for v in p.get("seer_checks", {}).values() if v == "werewolf") * 20
        death_pen = 0
        if not p["alive"] and not won:
            for dead_name, dead_cause in dead_set:
                if dead_name == p["name"]:
                    death_pen = DEATH_PENALTY.get(dead_cause, 0)
                    break
        total = base + bonus + death_pen
        if won and total > mvp_score:
            mvp_score = total
            mvp_candidate = p["name"]
        results.append({"character_name": p["name"], "role": role, "team": team, "won": won, "points": total, "is_mvp": False})
    if mvp_candidate:
        for r in results:
            if r["character_name"] == mvp_candidate:
                r["is_mvp"] = True
                r["points"] += MVP_BONUS
                break
    return results
