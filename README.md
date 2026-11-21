# Carmink 🎨

A Telegram party game bot where players take turns drawing a word while everybody else types guesses in the group chat. The drawer paints on a canvas inside a Telegram Mini App; the others see the picture refreshed in the chat, or watch it live in the Mini App. Italian and English words and messages, per-group dictionaries and statistics.

## How a match works

1. Somebody sends `/newgame` and picks the **mode** with the buttons (only the creator can pick); the others `/join`. At least 3 players are needed; `/ready` starts right away, otherwise the match starts when the sign-up window (5 minutes, extendable with `/wait`) closes.
2. Every player draws in turn. With fewer than 5 players everybody draws **twice** (3 players → 6 rounds, 4 → 8); with 5 or more, once.
3. Each turn:

| Step | Time | What happens |
|:---:|:---:|---|
| Break | 10 s | The previous word is revealed with the scores, and the next drawer is announced |
| Choice | 10 s | The drawer picks one of **three words**, one per difficulty (easy, medium, hard) |
| Start | 20 s | The drawer must start drawing, otherwise the turn is skipped |
| Drawing | 90 s | The clock starts at the first stroke. The others guess by writing in the chat |

4. A correct guess is deleted from the chat (so it doesn't spoil the word). In **Speedrun** the first player who guesses wins the round and it ends at once. In **Classic** guesses are typed in the Mini App; a message with the answer written in the chat is deleted and doesn't count. The round ends when everybody has guessed or time is up.
5. When all the turns are done the final scoreboard is shown.

### Game modes

| Mode | Status | How it plays |
|---|---|---|
| 🔥 Speedrun | available | Guesses are typed in the chat. The first correct guess wins the round |
| 🕹️ Classic | available | Guesses are typed in the Mini App (everybody sees everybody's attempts live) and the others keep trying after somebody got it |
| ☎️ Broken Canva | coming soon | Telephone game of phrases and drawings, nobody wins; the bot builds a GIF of every chain |

### Points

| Who | Points |
|---|---|
| Guesser | Up to 100, falling to 40% as the 90 seconds run out; ×1 / ×1.25 / ×1.5 for easy / medium / hard words |
| Drawer | Speedrun: up to 50 when the word is guessed at once, falling to 40% of that as the time runs out. Classic: 30 for every player who guessed, with the difficulty multiplier |
| Hints | Every hint the drawer gives (max 3) cuts 20% of the points of the guesses that follow **and** of the drawer's own points |

The words come from three categories: everyday objects and places, living things (animals, plants, body parts, mythical creatures), actions and emotions. The built-in dictionary is in `data/`; every group can add its own words.

Guesses ignore case, accents, spaces and punctuation, and accept the synonyms listed in the dictionary. A guess one typo away gets a "so close!" reply. Messages that contain the answer, written by the drawer or by someone who already guessed, are deleted.

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message (in private chat) |
| `/help` | How to play and the list of commands (private chat and groups) |
| `/newgame [it\|en]` | Open a match and pick the mode; the language is the group's, unless given |
| `/join` | Join a match, also while it is running (you guess at once and draw at the end), unless the group turned it off in `/settings` |
| `/ready` | Start now (any player, with at least 3 players) |
| `/wait <minutes>` | Extend the sign-up window (max 10 per use, decimals allowed) |
| `/quit` | Leave the match |
| `/stop` | Cancel the match (its creator or a group admin) |
| `/addword <word> [\| synonym \| ...] [1-3]` | Add a word to the group dictionary, with optional accepted synonyms (up to 5) and a difficulty (default 2). Example: `/addword scooter \| kick scooter 3` |
| `/deleteword <word>` | Remove a word that was added with `/addword` |
| `/stats` | Group statistics |
| `/mystats` | Your statistics (this group, or all groups if used in private) |
| `/settings` | Group settings for admins: language, who can edit the dictionary, whether players can join a running match |
| `/admin` | **Bot owner only**, private chat only: announcements, restart, git pull, log. Not shown in the command menu |

## The canvas (Mini App)

Pen, eraser, fill, filled and empty circle, filled and empty rectangle, 16 colours, 4 brush sizes, undo / redo, wipe, **Hint** (shows the word as `_ a _ _ o` and reveals one more random letter each time, up to 3 times, always leaving at least half of the letters hidden) and **Skip** (gives up the turn).

The drawer opens it with the button under the "next drawer" message. The drawer's strokes are streamed to the server as small events (`web/board.js`, `strokes.py`) and replayed by everybody else, so the canvas is live for all the viewers. In Speedrun everybody else gets a **Watch live** button, opened in compact mode so the chat stays visible; in Classic the button opens the full app, where players type their guesses under the canvas, see everybody's attempts (a correct one is shown without the word) and get a private "so close!" for near misses (one attempt per second at most). While the Mini App is closed, the group chat shows one photo that the bot refreshes in place every few seconds, so the chat is not flooded.

## How it is built

One Python process runs the bot (long polling) and the Mini App backend, side by side.

| File | Role |
|---|---|
| `carmink.py` | Entry point: bot + uvicorn in one event loop |
| `engine.py` | The match: lobby, turns, timers, guesses, hints, scoring. It knows nothing about Telegram or HTTP |
| `game.py`, `words.py` | Model and pure rules; dictionary, matching, hint masks |
| `handlers.py`, `tg_io.py`, `admin.py` | Telegram side: commands, messages and timers, `/admin` |
| `webserver.py`, `auth.py` | Mini App API (Starlette) and validation of Telegram's `initData` |
| `web/` | The Mini App: `index.html`, `app.js`, `fill.js`, `style.css` |
| `db.py`, `i18n.py`, `config.py`, `logs.py` | SQLite, texts, settings and constants, logging |

The server owns every rule and every timer; the Mini App only draws, sends the pictures, and shows what `/api/state` tells it. Matches live in memory: a restart ends the running ones. Everything in `config.py` (timings, points, snapshot rate) can be tuned.

## Setup

**1. BotFather** (for @carminkgame)
- `/setprivacy` → *Disable*, so the bot can read the guesses (or make the bot a group admin).
- In the groups, give the bot the *Delete messages* permission.
- `/newapp` → pick the bot, short name `app`, Web App URL `https://carmink.suketchi.art`. The direct link is `t.me/carminkgame/app`.

**2. DNS** — an `A` record `carmink` pointing to the server's IP.

**3. Server** (Debian/Ubuntu)

```bash
sudo apt install nginx certbot python3-certbot-nginx python3-venv git
sudo useradd -r -m -d /opt/carmink -s /usr/sbin/nologin carmink
sudo -u carmink git clone <repo url> /opt/carmink      # or copy the files
cd /opt/carmink
sudo -u carmink python3 -m venv venv
sudo -u carmink venv/bin/pip install -r requirements.txt
sudo -u carmink cp .env.example .env                   # then fill in BOT_TOKEN and ADMIN_ID
sudo chmod 600 .env

sudo cp deploy/nginx-carmink.conf /etc/nginx/sites-available/carmink
sudo ln -s /etc/nginx/sites-available/carmink /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d carmink.suketchi.art           # HTTPS is mandatory for Mini Apps

sudo cp deploy/carmink.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now carmink
journalctl -u carmink -f
```

Ports 80 and 443 must be open; the backend listens only on `127.0.0.1:8081`. It can share the server with other bots: it has its own user, folder, token and database.

**Local run:** `pip install -r requirements.txt`, set `BOT_TOKEN`, `python carmink.py`. The Mini App needs a public HTTPS address to be opened from Telegram.

## Dictionary

About 450 words per language. The objects and living things come largely from the category names of Google's [Quick, Draw!](https://github.com/googlecreativelab/quickdraw-dataset) dataset (345 things that people could draw in 20 seconds, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)), translated and sorted by difficulty; the actions and emotions, and the rest, were added by hand.

`data/words_it.json` and `data/words_en.json`: category → difficulty (`"1"` easy, `"2"` medium, `"3"` hard) → list of words. A word can list accepted alternatives after `|` (`"frigorifero|frigo"`). The tests check that there are no duplicates and that every category/difficulty has enough words.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

They cover the engine with a fake clock (a whole match, timeouts, hints, spoilers, players leaving), the HTTP API, `initData` validation, the command handlers, and (when Node.js is installed) the canvas flood fill.


Additional words were curated (filtered for drawability and translated) from user [nick-aschenbach's game-words repository](https://github.com/nick-aschenbach/game-words/tree/master). 
