"""SQLite persistence: group settings, group dictionaries, statistics, known groups."""
import sqlite3
import time

import config
import difficulty
import words

DEFAULT_SETTINGS = {"lang": "it", "words": "admins", "latejoin": "on", "drawtime": "auto", "cycles": "auto"}
ALLOWED_SETTINGS = {
    "lang": ("it", "en"),
    "words": ("admins", "everyone"),    # who can edit the group dictionary
    "latejoin": ("on", "off"),          # may players join a running speedrun / classic match?
    "drawtime": ("auto",) + tuple(str(s) for s in config.DRAW_CHOICES),   # seconds per drawing
    "cycles": ("auto",) + tuple(str(c) for c in range(1, config.BROKEN_MAX_CYCLES + 1)),  # Broken Canva
}

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat_settings (
    chat_id INTEGER PRIMARY KEY,
    lang TEXT NOT NULL DEFAULT 'it',
    words TEXT NOT NULL DEFAULT 'admins',
    latejoin TEXT NOT NULL DEFAULT 'on',
    drawtime TEXT NOT NULL DEFAULT 'auto',
    cycles TEXT NOT NULL DEFAULT 'auto');
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
    cat TEXT NOT NULL DEFAULT 'other',          -- animals / nature / ... / other (see words.CATEGORIES)
    base INTEGER NOT NULL DEFAULT 0,            -- level the statistics started from (0: same as diff)
    ea REAL NOT NULL DEFAULT 0,                 -- adaptive difficulty: weighted ease (see difficulty.py)
    eb REAL NOT NULL DEFAULT 0,                 -- ... and its weight
    shown INTEGER NOT NULL DEFAULT 0,           -- appearances counted
    locked INTEGER NOT NULL DEFAULT 0,          -- 1: an admin set the level by hand, don't adapt it
    PRIMARY KEY (chat_id, lang, word));
CREATE TABLE IF NOT EXISTS dict_ready (         -- groups whose dictionary was copied from the built-in one
    chat_id INTEGER NOT NULL, lang TEXT NOT NULL, PRIMARY KEY (chat_id, lang));
CREATE TABLE IF NOT EXISTS dict_codes (         -- "export" codes: a snapshot of a dictionary, valid for a while
    code TEXT PRIMARY KEY, chat_id INTEGER, ts INTEGER, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER, ts INTEGER, lang TEXT,
    players INTEGER, turns INTEGER, duration INTEGER);
CREATE TABLE IF NOT EXISTS game_players (
    game_id INTEGER, chat_id INTEGER, user_id INTEGER, name TEXT,
    points INTEGER, rank INTEGER, won INTEGER,
    guessed INTEGER,            -- correct guesses
    drawn INTEGER);             -- turns drawn
CREATE TABLE IF NOT EXISTS dm_users (            -- people who opened the bot in private: it may write to them
    user_id INTEGER PRIMARY KEY,
    ts INTEGER);
CREATE TABLE IF NOT EXISTS nextgame (            -- /nextgame: who wants a private notice when a match opens
    chat_id INTEGER, user_id INTEGER, name TEXT, ts INTEGER,
    PRIMARY KEY (chat_id, user_id));
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
        if "drawtime" not in scols:
            self.con.execute("ALTER TABLE chat_settings ADD COLUMN drawtime TEXT NOT NULL DEFAULT 'auto'")
        if "cycles" not in scols:
            self.con.execute("ALTER TABLE chat_settings ADD COLUMN cycles TEXT NOT NULL DEFAULT 'auto'")
        if "alts" not in cols:                  # database created before synonyms existed
            self.con.execute("ALTER TABLE custom_words ADD COLUMN alts TEXT NOT NULL DEFAULT ''")
        for name, ddl in (("cat", "TEXT NOT NULL DEFAULT 'other'"), ("base", "INTEGER NOT NULL DEFAULT 0"),
                          ("ea", "REAL NOT NULL DEFAULT 0"), ("eb", "REAL NOT NULL DEFAULT 0"),
                          ("shown", "INTEGER NOT NULL DEFAULT 0"), ("locked", "INTEGER NOT NULL DEFAULT 0")):
            if name not in cols:                # database created before the adaptive dictionary
                self.con.execute(f"ALTER TABLE custom_words ADD COLUMN {name} {ddl}")
        self.con.execute("UPDATE custom_words SET cat = 'other' WHERE cat = 'custom'")
        if self.con.execute("PRAGMA user_version").fetchone()[0] < 2:
            # the built-in dictionary was rebuilt with new categories: groups restart from the new one
            self.con.execute("DELETE FROM custom_words WHERE EXISTS (SELECT 1 FROM dict_ready r "
                             "WHERE r.chat_id = custom_words.chat_id AND r.lang = custom_words.lang)")
            self.con.execute("DELETE FROM dict_ready")
            self.con.execute("DELETE FROM dict_codes")
            self.con.execute("PRAGMA user_version = 2")
        self.con.commit()

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        return self.con.execute(sql, params).fetchall()

    # ------------------------------------------------------------ settings
    def get_settings(self, chat_id: int) -> dict:
        keys = tuple(DEFAULT_SETTINGS)
        rows = self.query(f"SELECT {', '.join(keys)} FROM chat_settings WHERE chat_id = ?", (chat_id,))
        return dict(zip(keys, rows[0])) if rows else dict(DEFAULT_SETTINGS)

    def get_lang(self, chat_id: int) -> str:
        return self.get_settings(chat_id)["lang"]

    def set_setting(self, chat_id: int, key: str, value: str) -> bool:
        if key not in ALLOWED_SETTINGS or value not in ALLOWED_SETTINGS[key]:
            return False
        self.con.execute("INSERT OR IGNORE INTO chat_settings (chat_id) VALUES (?)", (chat_id,))
        self.con.execute(f"UPDATE chat_settings SET {key} = ? WHERE chat_id = ?", (value, chat_id))
        self.con.commit()
        return True

    # ------------------------------------------------------------ private chats
    def add_dm(self, user_id: int) -> None:
        self.con.execute("INSERT OR IGNORE INTO dm_users (user_id, ts) VALUES (?, ?)",
                         (user_id, int(time.time())))
        self.con.commit()

    def has_dm(self, user_id: int) -> bool:
        return bool(self.query("SELECT 1 FROM dm_users WHERE user_id = ?", (user_id,)))

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

    def chat_title(self, chat_id: int) -> str:
        rows = self.query("SELECT title FROM known_chats WHERE chat_id = ?", (chat_id,))
        return (rows[0][0] if rows and rows[0][0] else "") or ""

    # ------------------------------------------------------------ /nextgame
    def nextgame_toggle(self, chat_id: int, user_id: int, name: str) -> bool:
        """Ask for the notice, or cancel it. True = now registered."""
        if self.query("SELECT 1 FROM nextgame WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)):
            self.con.execute("DELETE FROM nextgame WHERE chat_id = ? AND user_id = ?", (chat_id, user_id))
            self.con.commit()
            return False
        self.con.execute("INSERT INTO nextgame (chat_id, user_id, name, ts) VALUES (?, ?, ?, ?)",
                         (chat_id, user_id, name, int(time.time())))
        self.con.commit()
        return True

    def nextgame_take(self, chat_id: int, max_age: float) -> list[tuple[int, str]]:
        """The valid requests of a group; all of them (expired ones too) are consumed."""
        rows = self.query("SELECT user_id, name FROM nextgame WHERE chat_id = ? AND ts >= ? ORDER BY ts",
                          (chat_id, int(time.time() - max_age)))
        self.con.execute("DELETE FROM nextgame WHERE chat_id = ?", (chat_id,))
        self.con.commit()
        return [(r[0], r[1]) for r in rows]

    def chats_by_lang(self, lang: str) -> list[int]:
        rows = self.query(
            "SELECT k.chat_id FROM known_chats k LEFT JOIN chat_settings s ON s.chat_id = k.chat_id "
            "WHERE k.active = 1 AND COALESCE(s.lang, ?) = ?", (DEFAULT_SETTINGS["lang"], lang))
        return [r[0] for r in rows]

    # ------------------------------------------------------------ group dictionary
    # The first time a group plays in a language, the built-in dictionary is copied into custom_words:
    # from then on every word is the group's own (editable, with its own adaptive difficulty).
    _COLS = "word, diff, alts, cat, base, ea, eb, shown, locked"

    def ensure_dictionary(self, chat_id: int, lang: str) -> None:
        if self.query("SELECT 1 FROM dict_ready WHERE chat_id = ? AND lang = ?", (chat_id, lang)):
            return
        have = {words.compact(w) for (w,) in self.query(
            "SELECT word FROM custom_words WHERE chat_id = ? AND lang = ?", (chat_id, lang))}
        rows = []
        for e in words.load(lang):
            key = words.compact(e.word)
            if key not in have:
                have.add(key)
                rows.append((chat_id, lang, e.word, e.diff, "|".join(e.alts), e.cat, e.diff))
        self.con.executemany("INSERT OR IGNORE INTO custom_words (chat_id, lang, word, diff, alts, cat, base) "
                             "VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        self.con.execute("INSERT OR IGNORE INTO dict_ready VALUES (?, ?)", (chat_id, lang))
        self.con.commit()

    @staticmethod
    def _entry(row) -> words.Entry:
        w, d, alts, cat = row[:4]
        return words.Entry(word=w, alts=tuple(a for a in alts.split("|") if a), diff=d, cat=words.cat_of(cat))

    def custom_entries(self, chat_id: int, lang: str) -> list[words.Entry]:
        return [self._entry(r) for r in self.query(
            f"SELECT {self._COLS} FROM custom_words WHERE chat_id = ? AND lang = ?", (chat_id, lang))]

    def dictionary(self, chat_id: int, lang: str) -> list[dict]:
        """Everything the dictionary page shows, easiest words first."""
        out = []
        for w, d, alts, cat, base, ea, eb, shown, locked in self.query(
                f"SELECT {self._COLS} FROM custom_words WHERE chat_id = ? AND lang = ? "
                "ORDER BY word COLLATE NOCASE", (chat_id, lang)):
            out.append({"w": w, "alts": [a for a in alts.split("|") if a], "d": d, "cat": words.cat_of(cat),
                        "n": shown, "lock": bool(locked)})
        return out

    def count_custom(self, chat_id: int, lang: str | None = None) -> int:
        if lang:
            return self.query("SELECT COUNT(*) FROM custom_words WHERE chat_id = ? AND lang = ?",
                              (chat_id, lang))[0][0]
        return self.query("SELECT COUNT(*) FROM custom_words WHERE chat_id = ?", (chat_id,))[0][0]

    def _find(self, chat_id: int, lang: str, word: str) -> str | None:
        """The stored spelling of `word` (same letters, ignoring case, accents and spaces)."""
        key = words.compact(word)
        for (w,) in self.query("SELECT word FROM custom_words WHERE chat_id = ? AND lang = ?", (chat_id, lang)):
            if words.compact(w) == key:
                return w
        return None

    def add_word(self, chat_id: int, lang: str, word: str, diff: int, user_id: int,
                 alts: tuple[str, ...] = (), cat: str = "other", stats: tuple[float, float, int] = (0, 0, 0),
                 locked: bool = False, base: int | None = None) -> bool:
        """False if the group already has this word (same letters, ignoring case and accents)."""
        if self._find(chat_id, lang, word):
            return False
        self.con.execute("INSERT INTO custom_words (chat_id, lang, word, diff, added_by, alts, cat, base, "
                         "ea, eb, shown, locked) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                         (chat_id, lang, word, diff, user_id, "|".join(alts), words.cat_of(cat), base or diff, *stats, int(locked)))
        self.con.commit()
        return True

    def delete_word(self, chat_id: int, lang: str, word: str) -> bool:
        w = self._find(chat_id, lang, word)
        if w is None:
            return False
        self.con.execute("DELETE FROM custom_words WHERE chat_id = ? AND lang = ? AND word = ?",
                         (chat_id, lang, w))
        self.con.commit()
        return True

    def update_word(self, chat_id: int, lang: str, word: str, new_word: str | None = None,
                    alts: tuple[str, ...] | None = None, diff: int | None = None,
                    locked: bool | None = None, cat: str | None = None) -> str:
        """'ok' | 'missing' | 'dup' (the new spelling is another word). A level changed by hand restarts the
        statistics from that level; `locked` says whether it then stays fixed."""
        w = self._find(chat_id, lang, word)
        if w is None:
            return "missing"
        d, a, lk = self.query("SELECT diff, alts, locked FROM custom_words WHERE chat_id = ? AND lang = ? "
                              "AND word = ?", (chat_id, lang, w))[0]
        target = w
        if new_word and new_word != w:
            other = self._find(chat_id, lang, new_word)
            if other is not None and other != w:
                return "dup"
            target = new_word
        new_alts = "|".join(alts) if alts is not None else a
        new_diff = diff if diff in (1, 2, 3) else d
        new_lock = int(locked) if locked is not None else lk
        if cat in words.CATEGORY_ICON:
            self.con.execute("UPDATE custom_words SET cat = ? WHERE chat_id = ? AND lang = ? AND word = ?",
                             (cat, chat_id, lang, w))
        if new_diff != d:
            self.con.execute("UPDATE custom_words SET ea = 0, eb = 0, shown = 0, base = ? "
                             "WHERE chat_id = ? AND lang = ? AND word = ?", (new_diff, chat_id, lang, w))
        self.con.execute("UPDATE custom_words SET word = ?, alts = ?, diff = ?, locked = ? "
                         "WHERE chat_id = ? AND lang = ? AND word = ?",
                         (target, new_alts, new_diff, new_lock, chat_id, lang, w))
        self.con.commit()
        return "ok"

    def overwrite_word(self, chat_id: int, lang: str, word: str, alts: tuple[str, ...], diff: int, base: int,
                       stats: tuple[float, float, int], locked: bool, cat: str = "other") -> None:
        """Replace what the group knows about a word (import with "update existing")."""
        self.con.execute("UPDATE custom_words SET alts = ?, diff = ?, base = ?, ea = ?, eb = ?, shown = ?, "
                         "locked = ?, cat = ? WHERE chat_id = ? AND lang = ? AND word = ?",
                         ("|".join(alts), diff, base, *stats, int(locked), words.cat_of(cat), chat_id, lang, word))
        self.con.commit()

    def word_data(self, chat_id: int, lang: str, word: str) -> tuple | None:
        rows = self.query("SELECT diff, alts, shown, locked FROM custom_words WHERE chat_id = ? AND lang = ? "
                          "AND word = ?", (chat_id, lang, word))
        return rows[0] if rows else None

    def record_appearance(self, chat_id: int, lang: str, word: str, value: float, w: float) -> int | None:
        """Fold one finished round into the word's statistics; returns the (possibly new) level."""
        found = self._find(chat_id, lang, word)
        if found is None:
            return None
        diff, base, ea, eb, shown, locked = self.query(
            "SELECT diff, base, ea, eb, shown, locked FROM custom_words WHERE chat_id = ? AND lang = ? "
            "AND word = ?", (chat_id, lang, found))[0]
        ea, eb = difficulty.update(ea, eb, value, w)
        shown += 1
        if not locked and shown >= config.EASE_MIN_SHOWN:
            diff = difficulty.next_level(diff, difficulty.estimate(ea, eb, base or diff))
        self.con.execute("UPDATE custom_words SET ea = ?, eb = ?, shown = ?, diff = ? "
                         "WHERE chat_id = ? AND lang = ? AND word = ?", (ea, eb, shown, diff, chat_id, lang, found))
        self.con.commit()
        return diff

    def export_rows(self, chat_id: int) -> dict[str, list[dict]]:
        """The whole dictionary, every language, with what the group has learned about each word."""
        out: dict[str, list[dict]] = {}
        for lang, w, d, alts, cat, base, ea, eb, shown, locked in self.query(
                "SELECT lang, word, diff, alts, cat, base, ea, eb, shown, locked FROM custom_words "
                "WHERE chat_id = ? ORDER BY lang, word COLLATE NOCASE", (chat_id,)):
            out.setdefault(lang, []).append({
                "w": w, "alts": [a for a in alts.split("|") if a], "d": d, "c": words.cat_of(cat),
                "b": base or d, "ea": round(ea, 4), "eb": round(eb, 4), "n": shown, "l": locked})
        return out

    # ------------------------------------------------------------ share codes
    def save_code(self, code: str, chat_id: int, payload: str, now: float) -> None:
        self.con.execute("DELETE FROM dict_codes WHERE ts < ?", (int(now) - config.DICT_CODE_HOURS * 3600,))
        self.con.execute("INSERT OR REPLACE INTO dict_codes VALUES (?, ?, ?, ?)", (code, chat_id, int(now), payload))
        self.con.commit()

    def load_code(self, code: str, now: float) -> str | None:
        rows = self.query("SELECT payload FROM dict_codes WHERE code = ? AND ts >= ?",
                          (code, int(now) - config.DICT_CODE_HOURS * 3600))
        return rows[0][0] if rows else None

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
