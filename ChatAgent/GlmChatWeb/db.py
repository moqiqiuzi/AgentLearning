import os
import sys
import json
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "chat.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    password    TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS personas_system (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    prompt      TEXT    NOT NULL,
    tag         TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS personas_user (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    name        TEXT    NOT NULL,
    identity    TEXT    NOT NULL DEFAULT '',
    tone        TEXT    NOT NULL DEFAULT '',
    strengths   TEXT    NOT NULL DEFAULT '',
    weaknesses  TEXT    NOT NULL DEFAULT '',
    habits      TEXT    NOT NULL DEFAULT '',
    core_values TEXT    NOT NULL DEFAULT '',
    backstory   TEXT    NOT NULL DEFAULT '',
    prompt      TEXT    NOT NULL,
    created_at  TEXT    NOT NULL,
    UNIQUE(user_id, name)
);

CREATE TABLE IF NOT EXISTS user_personas (
    user_id     INTEGER NOT NULL REFERENCES users(id),
    persona_type TEXT   NOT NULL,
    persona_id  INTEGER NOT NULL,
    enabled_at  TEXT    NOT NULL,
    PRIMARY KEY (user_id, persona_type, persona_id)
);

CREATE TABLE IF NOT EXISTS chat_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    persona_type TEXT   NOT NULL,
    persona_id  INTEGER NOT NULL,
    role        TEXT    NOT NULL,
    content     TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS werewolf_replays (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    config      TEXT NOT NULL,
    events      TEXT NOT NULL,
    winner      TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS werewolf_themes_custom (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER REFERENCES users(id),
    name        TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    characters  TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS werewolf_user_scores (
    user_id         INTEGER PRIMARY KEY REFERENCES users(id),
    total_points    INTEGER DEFAULT 0,
    games_played    INTEGER DEFAULT 0,
    games_won       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS werewolf_char_scores (
    character_name  TEXT PRIMARY KEY,
    total_points    INTEGER DEFAULT 0,
    games_played    INTEGER DEFAULT 0,
    games_won       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS werewolf_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER REFERENCES users(id),
    game_id         TEXT    NOT NULL,
    character_name  TEXT    NOT NULL,
    role            TEXT    NOT NULL,
    team            TEXT    NOT NULL,
    won             INTEGER NOT NULL,
    points          INTEGER NOT NULL,
    is_mvp          INTEGER DEFAULT 0,
    created_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS werewolf_emotions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name     TEXT    NOT NULL,
    target_name     TEXT    NOT NULL,
    trust           INTEGER DEFAULT 0,
    hate            INTEGER DEFAULT 0,
    suspect         INTEGER DEFAULT 0,
    games_ago       INTEGER DEFAULT 0,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL,
    UNIQUE(source_name, target_name)
);
"""


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    return c


def init_db():
    c = _conn()
    c.executescript(_SCHEMA)

    count = c.execute("SELECT COUNT(*) FROM personas_system").fetchone()[0]
    if count == 0:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "GlmChat"))
        from glm_chat.personas import PERSONAS, PERSONA_TAGS

        now = datetime.now().isoformat()
        for name, prompt in PERSONAS.items():
            c.execute(
                "INSERT INTO personas_system (name, prompt, tag, created_at) VALUES (?,?,?,?)",
                (name, prompt, PERSONA_TAGS.get(name, ""), now),
            )
        c.commit()
    c.close()


def get_user_by_name(username):
    c = _conn()
    row = c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    c.close()
    return dict(row) if row else None


def create_user(username, password_hash):
    c = _conn()
    now = datetime.now().isoformat()
    try:
        c.execute(
            "INSERT INTO users (username, password, created_at) VALUES (?,?,?)",
            (username, password_hash, now),
        )
        uid = c.execute("SELECT last_insert_rowid()").fetchone()[0]

        defaults = ["诗人", "杠精", "鲁迅"]
        for name in defaults:
            row = c.execute(
                "SELECT id FROM personas_system WHERE name=?", (name,)
            ).fetchone()
            if row:
                c.execute(
                    "INSERT INTO user_personas (user_id, persona_type, persona_id, enabled_at) VALUES (?,?,?,?)",
                    (uid, "system", row["id"], now),
                )
        c.commit()
        return uid
    except sqlite3.IntegrityError:
        return None
    finally:
        c.close()


def get_enabled_personas(user_id):
    c = _conn()
    up_rows = c.execute(
        "SELECT persona_type, persona_id FROM user_personas WHERE user_id=?",
        (user_id,),
    ).fetchall()

    result = []
    for up in up_rows:
        if up["persona_type"] == "system":
            row = c.execute(
                "SELECT id, name, prompt, tag FROM personas_system WHERE id=?",
                (up["persona_id"],),
            ).fetchone()
            if row:
                result.append({
                    "persona_id": row["id"],
                    "persona_type": "system",
                    "name": row["name"],
                    "prompt": row["prompt"],
                    "tag": row["tag"] if row["tag"] else "",
                    "is_user_created": False,
                })
        else:
            row = c.execute(
                "SELECT id, name, prompt FROM personas_user WHERE id=? AND user_id=?",
                (up["persona_id"], user_id),
            ).fetchone()
            if row:
                result.append({
                    "persona_id": row["id"],
                    "persona_type": "user",
                    "name": row["name"],
                    "prompt": row["prompt"],
                    "tag": "自定义",
                    "is_user_created": True,
                })
    c.close()
    return result


def get_available_system_personas(user_id):
    c = _conn()
    rows = c.execute(
        """SELECT s.id, s.name, s.tag FROM personas_system s
           WHERE s.id NOT IN (
               SELECT persona_id FROM user_personas
               WHERE user_id=? AND persona_type='system'
           )""",
        (user_id,),
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def enable_system_persona(user_id, persona_id):
    c = _conn()
    now = datetime.now().isoformat()
    try:
        c.execute(
            "INSERT INTO user_personas (user_id, persona_type, persona_id, enabled_at) VALUES (?,?,?,?)",
            (user_id, "system", persona_id, now),
        )
        c.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        c.close()


def disable_persona(user_id, persona_type, persona_id):
    c = _conn()
    c.execute(
        "DELETE FROM user_personas WHERE user_id=? AND persona_type=? AND persona_id=?",
        (user_id, persona_type, persona_id),
    )
    c.commit()
    c.close()


def create_user_persona(user_id, name, identity, tone, strengths, weaknesses,
                         habits, values, backstory, prompt):
    c = _conn()
    now = datetime.now().isoformat()
    try:
        c.execute(
            """INSERT INTO personas_user
               (user_id, name, identity, tone, strengths, weaknesses, habits, core_values, backstory, prompt, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (user_id, name, identity, tone, strengths, weaknesses, habits, values, backstory, prompt, now),
        )
        pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.execute(
            "INSERT INTO user_personas (user_id, persona_type, persona_id, enabled_at) VALUES (?,?,?,?)",
            (user_id, "user", pid, now),
        )
        c.commit()
        return pid
    except sqlite3.IntegrityError:
        return None
    finally:
        c.close()


def delete_user_persona(user_id, persona_id):
    c = _conn()
    row = c.execute(
        "SELECT id FROM personas_user WHERE id=? AND user_id=?",
        (persona_id, user_id),
    ).fetchone()
    if not row:
        c.close()
        return False
    c.execute(
        "DELETE FROM user_personas WHERE user_id=? AND persona_type='user' AND persona_id=?",
        (user_id, persona_id),
    )
    c.execute("DELETE FROM chat_history WHERE persona_type='user' AND persona_id=?", (persona_id,))
    c.execute("DELETE FROM personas_user WHERE id=? AND user_id=?", (persona_id, user_id))
    c.commit()
    c.close()
    return True


def get_persona_details(persona_type, persona_id, user_id=None):
    c = _conn()
    if persona_type == "system":
        row = c.execute("SELECT * FROM personas_system WHERE id=?", (persona_id,)).fetchone()
    else:
        row = c.execute(
            "SELECT * FROM personas_user WHERE id=? AND user_id=?",
            (persona_id, user_id),
        ).fetchone()
    c.close()
    return dict(row) if row else None


def save_chat_message(user_id, persona_type, persona_id, role, content):
    c = _conn()
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO chat_history (user_id, persona_type, persona_id, role, content, created_at) VALUES (?,?,?,?,?,?)",
        (user_id, persona_type, persona_id, role, content, now),
    )
    c.commit()
    c.close()


def get_chat_history(user_id, persona_type, persona_id):
    c = _conn()
    rows = c.execute(
        "SELECT role, content FROM chat_history WHERE user_id=? AND persona_type=? AND persona_id=? ORDER BY id",
        (user_id, persona_type, persona_id),
    ).fetchall()
    c.close()
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def clear_chat_history(user_id, persona_type, persona_id):
    c = _conn()
    c.execute(
        "DELETE FROM chat_history WHERE user_id=? AND persona_type=? AND persona_id=?",
        (user_id, persona_type, persona_id),
    )
    c.commit()
    c.close()


def undo_last_turn(user_id, persona_type, persona_id):
    c = _conn()
    ids = c.execute(
        "SELECT id FROM chat_history WHERE user_id=? AND persona_type=? AND persona_id=? ORDER BY id DESC LIMIT 2",
        (user_id, persona_type, persona_id),
    ).fetchall()
    if len(ids) < 2:
        c.close()
        return False
    c.execute("DELETE FROM chat_history WHERE id IN (?,?)", (ids[0]["id"], ids[1]["id"]))
    c.commit()
    c.close()
    return True


def save_werewolf_replay(user_id, replay_id, config, events, winner):
    c = _conn()
    now = datetime.now().isoformat()
    c.execute(
        "INSERT INTO werewolf_replays (id, user_id, config, events, winner, created_at) VALUES (?,?,?,?,?,?)",
        (replay_id, user_id, json.dumps(config, ensure_ascii=False), json.dumps(events, ensure_ascii=False), winner, now),
    )
    c.commit()
    c.close()


def get_werewolf_replays(user_id):
    c = _conn()
    rows = c.execute(
        "SELECT id, config, winner, created_at FROM werewolf_replays WHERE user_id=? ORDER BY created_at DESC LIMIT 20",
        (user_id,),
    ).fetchall()
    c.close()
    result = []
    for r in rows:
        cfg = json.loads(r["config"])
        result.append({
            "id": r["id"],
            "total": cfg.get("total"),
            "theme": cfg.get("theme"),
            "winner": r["winner"],
            "created_at": r["created_at"],
        })
    return result


def get_werewolf_replay_detail(replay_id, user_id):
    c = _conn()
    row = c.execute(
        "SELECT * FROM werewolf_replays WHERE id=? AND user_id=?",
        (replay_id, user_id),
    ).fetchone()
    c.close()
    if not row:
        return None
    return {
        "id": row["id"],
        "config": json.loads(row["config"]),
        "events": json.loads(row["events"]),
        "winner": row["winner"],
        "created_at": row["created_at"],
    }


def save_custom_theme(user_id, name, description, characters):
    c = _conn()
    now = datetime.now().isoformat()
    try:
        c.execute(
            "INSERT INTO werewolf_themes_custom (user_id, name, description, characters, created_at) VALUES (?,?,?,?,?)",
            (user_id, name, description, json.dumps(characters, ensure_ascii=False), now),
        )
        tid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        c.commit()
        return tid
    except Exception:
        c.close()
        return None
    finally:
        c.close()


def get_custom_themes(user_id):
    c = _conn()
    rows = c.execute(
        "SELECT id, name, description, characters FROM werewolf_themes_custom WHERE user_id=?",
        (user_id,),
    ).fetchall()
    c.close()
    return [{"id": r["id"], "name": r["name"], "description": r["description"], "characters": json.loads(r["characters"])} for r in rows]


def save_werewolf_scores(user_id, game_id, score_list, user_mode, user_char_name=None):
    c = _conn()
    now = datetime.now().isoformat()
    for s in score_list:
        name = s["character_name"]
        if user_mode == "player" and name == user_char_name:
            continue
        pts = s["points"]
        won = int(s["won"])
        row = c.execute("SELECT total_points, games_played, games_won FROM werewolf_char_scores WHERE character_name=?", (name,)).fetchone()
        if row:
            c.execute("UPDATE werewolf_char_scores SET total_points=?, games_played=?, games_won=? WHERE character_name=?",
                      (row["total_points"] + pts, row["games_played"] + 1, row["games_won"] + won, name))
        else:
            c.execute("INSERT INTO werewolf_char_scores (character_name, total_points, games_played, games_won) VALUES (?,?,?,?)",
                      (name, pts, 1, won))
        c.execute(
            "INSERT INTO werewolf_results (user_id, game_id, character_name, role, team, won, points, is_mvp, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (user_id, game_id, name, s["role"], s["team"], won, pts, int(s.get("is_mvp", 0)), now),
        )
    if user_mode == "player" and user_char_name:
        user_score = next((s for s in score_list if s["character_name"] == user_char_name), None)
        if user_score:
            pts = user_score["points"]
            won = int(user_score["won"])
            row = c.execute("SELECT total_points, games_played, games_won FROM werewolf_user_scores WHERE user_id=?", (user_id,)).fetchone()
            if row:
                c.execute("UPDATE werewolf_user_scores SET total_points=?, games_played=?, games_won=? WHERE user_id=?",
                          (row["total_points"] + pts, row["games_played"] + 1, row["games_won"] + won, user_id))
            else:
                c.execute("INSERT INTO werewolf_user_scores (user_id, total_points, games_played, games_won) VALUES (?,?,?,?)",
                          (user_id, pts, 1, won))
    c.commit()
    c.close()


def get_user_ww_score(user_id):
    c = _conn()
    row = c.execute("SELECT total_points, games_played, games_won FROM werewolf_user_scores WHERE user_id=?", (user_id,)).fetchone()
    c.close()
    if row:
        return {"total_points": row["total_points"], "games_played": row["games_played"], "games_won": row["games_won"]}
    return {"total_points": 0, "games_played": 0, "games_won": 0}


def get_char_rankings(limit=20):
    c = _conn()
    rows = c.execute("SELECT character_name, total_points, games_played, games_won FROM werewolf_char_scores ORDER BY total_points DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_user_rankings(limit=20):
    c = _conn()
    rows = c.execute(
        "SELECT u.username, w.total_points, w.games_played, w.games_won "
        "FROM werewolf_user_scores w JOIN users u ON w.user_id=u.id "
        "ORDER BY w.total_points DESC LIMIT ?", (limit,)
    ).fetchall()
    c.close()
    return [dict(r) for r in rows]


def reset_user_ww_stats(user_id):
    c = _conn()
    c.execute("DELETE FROM werewolf_results WHERE user_id=?", (user_id,))
    c.execute("DELETE FROM werewolf_user_scores WHERE user_id=?", (user_id,))
    c.commit()
    c.close()
    return True


def reset_char_scores():
    c = _conn()
    c.execute("DELETE FROM werewolf_char_scores")
    c.commit()
    c.close()
    return True


def save_game_emotions(event_list, players):
    c = _conn()
    now = datetime.now().isoformat()
    votes = {}
    deaths = []
    for evt in event_list:
        if evt.get("event") == "vote_cast":
            votes[evt.get("from", "")] = evt.get("to", "")
        elif evt.get("event") == "death" and evt.get("players"):
            for p in evt["players"]:
                deaths.append((p, evt.get("cause", "")))
    vote_tally = {}
    for voter, target in votes.items():
        vote_tally[target] = vote_tally.get(target, 0) + 1
    for voter, target in votes.items():
        if voter == target:
            continue
        _update_emotion(c, voter, target, trust=-5, hate=10, suspect=0, now=now)
    for target, count in vote_tally.items():
        for voter, v_target in votes.items():
            if v_target == target and voter != target:
                pass
    for dead_name, cause in deaths:
        for voter, target in votes.items():
            if target == dead_name and voter != dead_name:
                _update_emotion(c, dead_name, voter, trust=-8, hate=15, suspect=10, now=now)
        if cause == "werewolf":
            pass
    for dead_name, _ in deaths:
        for p in players:
            if p["name"] != dead_name:
                _update_emotion(c, p["name"], dead_name, trust=3, hate=0, suspect=-2, now=now)
    c.execute("UPDATE werewolf_emotions SET games_ago = games_ago + 1")
    c.commit()
    c.close()


def _update_emotion(c, source, target, trust, hate, suspect, now):
    row = c.execute("SELECT trust, hate, suspect FROM werewolf_emotions WHERE source_name=? AND target_name=?", (source, target)).fetchone()
    if row:
        c.execute("UPDATE werewolf_emotions SET trust=?, hate=?, suspect=?, games_ago=0, updated_at=? WHERE source_name=? AND target_name=?",
                  (row["trust"] + trust, row["hate"] + hate, row["suspect"] + suspect, now, source, target))
    else:
        c.execute("INSERT INTO werewolf_emotions (source_name, target_name, trust, hate, suspect, games_ago, created_at, updated_at) VALUES (?,?,?,?,?,0,?,?)",
                  (source, target, trust, hate, suspect, now, now))


def decay_emotions(rate=0.1):
    c = _conn()
    c.execute("UPDATE werewolf_emotions SET trust = CAST(trust * ? AS INTEGER), hate = CAST(hate * ? AS INTEGER), suspect = CAST(suspect * ? AS INTEGER) WHERE games_ago > 0",
              (1 - rate, 1 - rate, 1 - rate))
    c.execute("DELETE FROM werewolf_emotions WHERE trust = 0 AND hate = 0 AND suspect = 0")
    c.commit()
    c.close()


def get_emotions_for_player(player_name):
    c = _conn()
    rows = c.execute("SELECT target_name, trust, hate, suspect FROM werewolf_emotions WHERE source_name=?", (player_name,)).fetchall()
    c.close()
    return [{"target": r["target_name"], "trust": r["trust"], "hate": r["hate"], "suspect": r["suspect"]} for r in rows]


def get_emotion_prompt(player_name):
    emotions = get_emotions_for_player(player_name)
    if not emotions:
        return ""
    lines = []
    for e in emotions:
        parts = []
        if e["trust"] > 10:
            parts.append(f"信任(+{e['trust']})")
        elif e["trust"] < -10:
            parts.append(f"不信任({e['trust']})")
        if e["hate"] > 10:
            parts.append(f"厌恶(+{e['hate']})")
        if e["suspect"] > 10:
            parts.append(f"怀疑(+{e['suspect']})")
        if parts:
            lines.append(f"  对【{e['target']}】：{', '.join(parts)}")
    if not lines:
        return ""
    return "你对以下玩家的印象（来自之前游戏的记忆）：\n" + "\n".join(lines)
