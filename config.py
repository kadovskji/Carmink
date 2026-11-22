"""Environment settings and game constants (everything tunable lives here)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# ---------------------------------------------------------------- environment
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "carminkgame")
MINIAPP_SHORTNAME = os.environ.get("MINIAPP_SHORTNAME", "app")   # the /newapp short name in BotFather
WEB_HOST = os.environ.get("WEB_HOST", "127.0.0.1")               # nginx talks to this address
WEB_PORT = _int("WEB_PORT", 8081)
# Webhook mode (faster than polling): set WEBHOOK_SECRET to a long random string. Telegram then pushes
# updates to PUBLIC_URL/tg/<secret>. Leave empty to keep long polling.
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "").strip()
PUBLIC_URL = os.environ.get("PUBLIC_URL", "https://carmink.suketchi.art").rstrip("/")
DB_FILE = os.environ.get("DB_FILE", "carmink.db")
LOG_FILE = os.environ.get("LOG_FILE", "carmink.log")
RESTART_FILE = os.environ.get("RESTART_FILE", "restart.flag")
ADMIN_IDS = {int(x) for x in os.environ.get("ADMIN_ID", "").replace(" ", "").split(",")
             if x.strip().isdigit()}
# Commands that, in groups, are handled only when written as /command@CarminkBot
REQUIRE_TAG = {c.strip().lstrip("/")
               for c in os.environ.get("REQUIRE_TAG", "").split(",") if c.strip()}
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"

# ---------------------------------------------------------------- players and rounds
MIN_PLAYERS = 3             # needed to start a match
FEW_PLAYERS = 5             # below this many players everybody draws twice (so: 5+ rounds)
MIN_PLAYERS_TO_CONTINUE = 2  # a running match ends if fewer players are left

# ---------------------------------------------------------------- game modes
MODES = ("speedrun", "classic", "broken")
MODES_AVAILABLE = ("speedrun", "classic", "broken")
DEFAULT_MODE = "speedrun"

# ---------------------------------------------------------------- Broken Canva
MIN_PLAYERS_BROKEN = 4
BROKEN_MAX_STEPS = 7        # passes after the initial phrase (the chain always ends with a drawing)
BROKEN_PHRASE_SECONDS = 120
BROKEN_DESCRIBE_SECONDS = 60
BROKEN_GRACE_SECONDS = 3    # extra time for the Mini App to send the drawing when its clock hits zero
BROKEN_TEXT_MAX = 120
BROKEN_JPEG_MAX = 600_000
BROKEN_GIF_GAP = 1.0        # pause between two GIFs sent to the group (Telegram flood limits)

# ---------------------------------------------------------------- timings, in seconds
LOBBY_SECONDS = 300         # sign-up window
WAIT_MAX_MINUTES = 10       # max extension per /wait
BREAK_SECONDS = 10          # pause between two turns (the next drawer is announced)
CHOOSE_SECONDS = 10         # the drawer must pick one of the three words
START_SECONDS = 20          # then must start drawing; otherwise the turn is skipped
DRAW_SECONDS = 90           # drawing time, counted from the first stroke

# ---------------------------------------------------------------- points
GUESS_MAX = 100             # a guess at the very first second
GUESS_MIN_SHARE = 0.4       # a guess in the very last second gets this share of GUESS_MAX
DRAWER_PER_GUESS = 30       # classic mode: drawer's points for every player who guessed
DRAWER_SPEEDRUN_MAX = 50    # speedrun: drawer's points when the word is guessed at the very first second
DIFFICULTY_MULT = {1: 1.0, 2: 1.25, 3: 1.5}
MAX_HINTS = 3
HINT_PENALTY = 0.2          # every hint cuts 20% of the points (guessers' and drawer's)

# ---------------------------------------------------------------- canvas pictures
SNAPSHOT_FIRST_SECONDS = 2  # first picture in the chat, this long after the first stroke
SNAPSHOT_EDIT_SECONDS = 5   # then the picture is refreshed at most this often
SNAPSHOT_MAX_BYTES = 400_000
FINAL_SNAPSHOT_WAIT = 3.0    # after a round ends, this long to receive the drawer's finished canvas
SNAPSHOT_MIN_INTERVAL = 0.8  # the Mini App may not upload faster than this

# ---------------------------------------------------------------- live drawing and Mini App guesses
EVENTS_MAX = 30000          # drawing events kept per turn
EVENTS_PER_POST = 400
STROKE_POINTS_MAX = 2000
POST_MAX_BYTES = 600_000
GUESS_MIN_INTERVAL = 1.0    # seconds between two attempts of the same player
ATTEMPT_MAX_LEN = 60

# ---------------------------------------------------------------- words
CUSTOM_ALTS_MAX = 5            # synonyms accepted per custom word
CUSTOM_WORDS_MAX = 500      # per group
WORD_MAX_LEN = 30
CLOSE_NOTICES_PER_TURN = 2  # "you're close!" replies a player can get in one turn
