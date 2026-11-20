"""SQLite persistence: group settings, group dictionaries, statistics, known groups."""
import sqlite3
import time

import words

DEFAULT_SETTINGS = {"lang": "it", "words": "admins", "latejoin": "on"}
ALLOWED_SETTINGS = {
    "lang": ("it", "en"),
    "words": ("admins", "everyone"),    # who can use /addword and /deleteword
    "latejoin": ("on", "off"),          # may players join a running speedrun / classic match?
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_settings (
    chat_id INTEGER PRIMARY KEY,
    lang TEXT NOT NULL DEFAULT 'it',
    words TEXT NOT NULL DEFAULT 'admins',
    latejoin TEXT NOT NULL DEFAULT 'on');
CREATE TABLE IF NOT EXISTS known_chats (        -- groups where the bot is (or was) present
    chat_id INTEGER PRIMARY KEY,
    title TEXT,
    active INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS custom_words (       -- the group's own dictionary
    chat_id INTEGER NOT NULL,
    lang TEXT NOT NULL,
    word TEXT NOT NULL,
    diff INTEGER NOT NULL DEFAULT 2,
    added_by INTEGER,
    alts TEXT NOT NULL DEFAULT '',              -- synonyms, separated by |
    PRIMARY KEY (chat_id, lang, word));
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER, ts INTEGER, lang TEXT,
    players INTEGER, turns INTEGER, duration INTEGER);
CREATE TABLE IF NOT EXISTS game_players (
    game_id INTEGER, chat_id INTEGER, user_id INTEGER, name TEXT,
    points INTEGER, rank INTEGER, won INTEGER,
    guessed INTEGER,            -- correct guesses
    drawn INTEGER);             -- turns drawn
CREATE INDEX IF NOT EXISTS idx_games_chat ON games(chat_id);
CREATE INDEX IF NOT EXISTS idx_gp_chat ON game_players(chat_id);
CREATE INDEX IF NOT EXISTS idx_gp_user ON game_players(user_id);
"""


class Database:
    def __init__(self, path: str = "carmink.db") -> None:
        self.con = sqlite3.connect(path, check_same_thread=False)   # one event loop uses it; tests use threads
        self.con.executescript(SCHEMA)
        cols = [r[1] for r in self.con.execute("PRAGMA table_info(custom_words)")]
        scols = [r[1] for r in self.con.execute("PRAGMA table_info(chat_settings)")]
        if "latejoin" not in scols:             # database created before this setting existed
            self.con.execute("ALTER TABLE chat_settings ADD COLUMN latejoin TEXT NOT NULL DEFAULT 'on'")
        if "alts" not in cols:                  # database created before synonyms existed
            self.con.execute("ALTER TABLE custom_words ADD COLUMN alts TEXT NOT NULL DEFAULT ''")
        self.con.commit()

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        return self.con.execute(sql, params).fetchall()

    # ------------------------------------------------------------ settings
    def get_settings(self, chat_id: int) -> dict:
        rows = self.query("SELECT lang, words, latejoin FROM chat_settings WHERE chat_id = ?",
                          (chat_id,))
        return dict(zip(("lang", "words", "latejoin"), rows[0])) if rows else dict(DEFAULT_SETTINGS)

    def get_lang(self, chat_id: int) -> str:
        return self.get_settings(chat_id)["lang"]

    def set_setting(self, chat_id: int, key: str, value: str) -> bool:
        if key not in ALLOWED_SETTINGS or value not in ALLOWED_SETTINGS[key]:
            return False
        self.con.execute("INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)", (chat_id,))
        self.con.execute(f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
        self.con.commit()
        return True

    # ------------------------------------------------------------ known groups
    def track_chat(self, chat_id: int, title: str | None) -> None:
        self.con.execute(
            "INSERT INTO known_chats (chat_id, title, active) VALUES (?, ?, 1) "
            "ON CONFLICT(chat_id) DO UPDATE SET title = excluded.title", (chat_id, title))
        self.con.commit()

    def set_chat_active(self, chat_id: int, active: bool, title: str | None = None) -> None:
        self.con.execute(
            "INSERT INTO known_chats (chat_id, title, active) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET active = excluded.active, "
            "title = COALESCE(excluded.title, title)", (chat_id, title, int(active)))
        self.con.commit()

    def chats_by_lang(self, lang: str) -> list[int]:
        rows = self.query(
            "SELECT k.chat_id FROM known_chats k LEFT JOIN chat_settings s ON s.chat_id = k.chat_id "
            "WHERE k.active = 1 AND COALESCE(s.lang, ?) = ?", (DEFAULT_SETTINGS["lang"], lang))
        return [r[0] for r in rows]

    # ------------------------------------------------------------ group dictionary
    def custom_entries(self, chat_id: int, lang: str) -> list[words.Entry]:
        rows = self.query("SELECT word, diff, alts FROM custom_words WHERE chat_id = ? AND lang = ?",
                          (chat_id, lang))
        return [words.Entry(word=w, alts=tuple(a for a in alts.split("|") if a), diff=d, cat="custom")
                for w, d, alts in rows]

    def count_custom(self, chat_id: int) -> int:
        return self.query("SELECT COUNT(*) FROM custom_words WHERE chat_id = ?", (chat_id,))[0][0]

    def add_word(self, chat_id: int, lang: str, word: str, diff: int, user_id: int,
                 alts: tuple[str, ...] = ()) -> bool:
        """False if the group already has this word (same letters, ignoring case and accents)."""
        key = words.compact(word)
        for (w,) in self.query("SELECT word FROM custom_words WHERE chat_id = ? AND lang = ?",
                               (chat_id, lang)):
            if words.compact(w) == key:
                return False
        self.con.execute("INSERT INTO custom_words (chat_id, lang, word, diff, added_by, alts) "
                         "VALUES (?, ?, ?, ?, ?, ?)",
                         (chat_id, lang, word, diff, user_id, "|".join(alts)))
        self.con.commit()
        return True

    def delete_word(self, chat_id: int, lang: str, word: str) -> bool:
        key = words.compact(word)
        for (w,) in self.query("SELECT word FROM custom_words WHERE chat_id = ? AND lang = ?",
                               (chat_id, lang)):
            if words.compact(w) == key:
                self.con.execute("DELETE FROM custom_words WHERE chat_id = ? AND lang = ? "
                                 "AND word = ?", (chat_id, lang, w))
                self.con.commit()
                return True
        return False

    # ------------------------------------------------------------ statistics
    def save_game(self, chat_id: int, lang: str, turns: int, duration: int,
                  rows: list[tuple[int, int, str, int, int, int, int]]) -> None:
        """rows: (rank, user_id, name, points, won, guessed, drawn)."""
        cur = self.con.execute(
            "INSERT INTO games (chat_id, ts, lang, players, turns, duration) VALUES (?,?,?,?,?,?)",
            (chat_id, int(time.time()), lang, len(rows), turns, duration))
        gid = cur.lastrowid
        self.con.executemany(
            "INSERT INTO game_players VALUES (?,?,?,?,?,?,?,?,?)",
            [(gid, chat_id, uid, name, pts, rank, won, guessed, drawn)
             for rank, uid, name, pts, won, guessed, drawn in rows])
        self.con.commit()

    def group_stats(self, chat_id: int, limit: int = 5) -> dict:
        def top(expr: str) -> list[tuple[str, int]]:
            return self.query(
                f"SELECT name, {expr} AS v FROM game_players WHERE chat_id = ? "
                f"GROUP BY user_id ORDER BY v DESC, name LIMIT ?", (chat_id, limit))
        games = self.query("SELECT COUNT(*) FROM games WHERE chat_id = ?", (chat_id,))[0][0]
        best = self.query("SELECT name, MAX(points) FROM game_players WHERE chat_id = ? "
                          "GROUP BY user_id ORDER BY MAX(points) DESC, name LIMIT 1", (chat_id,))
        return {"games": games, "wins": top("SUM(won)"), "points": top("SUM(points)"),
                "guessed": top("SUM(guessed)"), "best_game": best[0] if best else None}

    def user_stats(self, user_id: int, chat_id: int | None = None) -> dict | None:
        where, params = ("user_id = ?", (user_id,))
        if chat_id is not None:
            where, params = ("user_id = ? AND chat_id = ?", (user_id, chat_id))
        row = self.query(
            f"SELECT COUNT(*), COALESCE(SUM(won),0), COALESCE(SUM(points),0), "
            f"COALESCE(SUM(guessed),0), COALESCE(SUM(drawn),0), COALESCE(MAX(points),0) "
            f"FROM game_players WHERE {where}", params)[0]
        if not row[0]:
            return None
        return dict(zip(("games", "wins", "points", "guessed", "drawn", "best"), row))
