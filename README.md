# Carmink 🎨

A Telegram party game bot where players take turns drawing a word while everybody else types guesses in the group chat. The drawer paints on a canvas inside a Telegram Mini App; the others see the picture refreshed in the chat, or watch it live in the Mini App. Italian and English words and messages, per-group dictionaries and statistics.

## How a match works

1. Somebody sends `/newgame` and picks the **mode** with the buttons (only the creator can pick); the others `/join`. At least 3 players are needed (4 for Broken Canva, Carmeleon and Code Stroke); `/ready` starts right away, otherwise the match starts when the sign-up window (5 minutes, extendable with `/wait`) closes.
2. Every player draws in turn. With fewer than 5 players everybody draws **twice** (3 players → 6 rounds, 4 → 8); with 5 or more, once.
3. Each turn:

| Step | Time | What happens |
|:---:|:---:|---|
| Break | 10 s | The previous word is revealed with the scores, and the next drawer is announced |
| Choice | 10 s | The drawer picks one of **three words**, one per difficulty (easy, medium, hard) |
| Start | 20 s | The drawer must start drawing, otherwise the turn is skipped |
| Drawing | 2 min (3 min in Broken Canva), adjustable in `/settings`: 60 s, 90 s, 2, 3, 4 or 5 min | The clock starts at the first stroke. The others guess by writing in the chat |

4. A correct guess is deleted from the chat (so it doesn't spoil the word). In **Speedrun** guesses can be written in the chat or in the Mini App text field; the first player who guesses wins the round and it ends at once. In **Classic** guesses are typed in the Mini App; a message with the answer written in the chat is deleted and doesn't count. The round ends when everybody has guessed or time is up.
5. When all the turns are done the final scoreboard is shown.

### Game modes

| Mode | Status | How it plays |
|---|---|---|
| 🔥 Speedrun | available | Guesses are typed in the chat. The first correct guess wins the round |
| 🕹️ Classic | available | Guesses are typed in the Mini App (everybody sees everybody's attempts live) and the others keep trying after somebody got it |
| ☎️ Broken Canva | available | Telephone game of phrases and drawings, nobody wins; the bot builds a GIF of every chain (see below) |
| 🦎 Carmeleon | **beta** | Everybody knows the key word except the Chameleon: draw something linked to it, then vote (see below) |
| 🕵️ Code Stroke | **beta** | Two teams, a 5×5 grid of words, spy masters who give clues by drawing (see below) |

#### Broken Canva

Needs 4+ players, and every player must have opened the bot in private first (the group message has a *Start the bot* button; without it the bot can't write to them, so `/join` is refused). Nobody can join once it has started, and there are no points or winners: only the match counts in the statistics.

1. Everybody privately sends the bot a funny phrase (2 minutes, up to 120 characters; sending another replaces it). The group message shows who has written. Whoever sends nothing is dropped.
2. Pass after pass, each player receives the last item of somebody else's chain: a phrase to **draw** in the Mini App (3 minutes by default, from receipt; the same `/settings` option, *Done* ends it early) or a drawing to **describe** (60 seconds), with a private message or from the text field under the canvas in the Mini App. A pass closes as soon as everybody has answered; a missing drawing becomes the last draft or a blank canvas, a missing description becomes "…".
3. A *cycle* is a description and its drawing. `/settings` sets the number of cycles (default: as many as fit, max 5). Everybody works on each chain only once, so there are at most *players − 1* passes and the cycles are capped at *players ÷ 2* (4–5 players: 2, 6–7: 3, 10+: 5): a higher setting is lowered to what fits. Every chain ends with a drawing.
4. At the end the bot posts one GIF per chain (each frame has the caption and the drawing made from it, with both authors). It needs Pillow and a font (`fonts-dejavu-core`); without Pillow it posts a text recap.

#### Carmeleon (beta)

4+ players, nobody can join once it has started. The table has 15, 21 or 30 words (`/settings`, default 15) from three different categories of the group's dictionary; one of them is the **key**. Everybody sees the key in the Mini App except one random player, the **Chameleon**.

1. In turn (random order, 90 s by default, the *Drawing time* setting) everybody draws something linked to the key in the Mini App; every drawing is posted in the chat at once. The *Table* tab shows the words (and the key) without losing the drawing.
2. When everybody has drawn, the group votes with two buttons in the chat: another lap (only once, majority needed) or the vote.
3. The vote: the bot posts every player's drawing with a button under it (you can't vote for yourself). A tie, or a wrong most-voted player, means the Chameleon wins and the key is revealed (**3 points**).
4. If the Chameleon is the most voted it can still win by naming the key among the table words (buttons, only the Chameleon can press): then it wins alone (**2 points**). Otherwise every other player gets **2 points**.

#### Code Stroke (beta)

4+ players, nobody can join once it has started, split into two teams: 🔵 blue starts (9 words) and 🔴 red follows (8 words); with an odd number of players red gets the extra one. The 5×5 grid has the team words, 7 neutral words and one assassin ⬛; the words come from the whole group dictionary (all levels).

- Each team has a random **spy master**, the only one who sees the key (Mini App). It draws a clue and picks a number (1–9, the *Number* menu next to *Done*); the drawing is posted in the chat with the number.
- The teammates tap words, in the chat (25 buttons) or in the *Grid* tab of the Mini App, up to *number + 1* tries, with *Pass* after at least one word. A word of the other team or a neutral one ends the turn (the other team's words still count for them); the assassin makes the team lose at once; the first team that finds all its words wins (1 point each, the win counts in the statistics).
- No clue within the drawing time, or no pick within 2 minutes: the turn passes.

### Points

| Who | Points |
|---|---|
| Guesser | Up to 100, falling to 40% as the drawing time runs out; ×1 / ×1.25 / ×1.5 for easy / medium / hard words |
| Drawer | Speedrun: up to 50 when the word is guessed at once, falling to 40% of that as the time runs out. Classic: 30 for every player who guessed, with the difficulty multiplier |
| Hints | Every hint the drawer gives (max 3) cuts 20% of the points of the guesses that follow **and** of the drawer's own points |

The words are sorted into categories (animals and creatures, nature and places, plants, body and clothing, food and drinks, jobs and characters, buildings and landmarks, vehicles, objects and devices, actions and emotions, sports and games, music, other); each word shows its category icon and the category can be changed in the dictionary page. The built-in dictionary is in `data/`; the first time a group plays in a language it is **copied into the group**, which from then on edits it freely (see *Group dictionary* below).

Guesses ignore case, accents, spaces and punctuation, and accept the synonyms listed in the dictionary. A guess one typo away gets a "so close!" reply. Messages that contain the answer, written by the drawer or by someone who already guessed, are deleted.

## Commands

| Command | Description |
|---|---|
| `/start` | Welcome message (in private chat) |
| `/help` | How to play and the list of commands (private chat and groups) |
| `/newgame [it\|en]` | Open a match and pick the mode; the language is the group's, unless given |
| `/join` | Join a match, also while it is running (you guess at once and draw at the end), unless the group turned it off in `/settings` |
| `/ready` | Start now (any player, with at least 3 players) |
| `/nextgame` | Get a private notice when the next match opens in the group, without being signed up (valid 24 hours; send it again to cancel; needs the bot started in private) |
| `/wait <minutes>` | Extend the sign-up window (max 10 per use, decimals allowed) |
| `/quit` | Leave the match |
| `/stop` | Cancel the match (its creator or a group admin) |
| `/stats` | Group statistics |
| `/mystats` | Your statistics (this group, or all groups if used in private) |
| `/settings` | Group settings for admins: language, who can edit the dictionary, whether players can join a running match, drawing time, Broken Canva cycles, and the **📚 Dictionary** button |
| `/admin` | **Bot owner only**, private chat only: announcements, restart, git pull, log, 🧪 test match. Not shown in the command menu |
| `/t <n> <text>` | **Bot owner only**, private chat: during a test match, writes `<text>` as fake player *n* (guess in Speedrun/Classic, phrase or description in Broken Canva, a button's data such as `cm:v:3` or `cs:pass` in Carmeleon and Code Stroke) |

## The canvas (Mini App)

Pen, eraser, fill, filled and empty circle, filled and empty rectangle, 16 colours, 4 brush sizes, undo / redo, wipe, **Hint** (shows the word as `_ a _ _ o` and reveals one more random letter each time, up to 3 times, always leaving at least half of the letters hidden) and **Skip** (gives up the turn).

The drawer opens it with the button under the "next drawer" message. The drawer's strokes are streamed to the server as small events (`web/board.js`, `strokes.py`) and replayed by everybody else, so the canvas is live for all the viewers. In Speedrun everybody else gets a **Watch live** button, opened in compact mode so the chat stays visible; in Classic the button opens the full app, where players type their guesses under the canvas, see everybody's attempts (a correct one is shown without the word) and get a private "so close!" for near misses (one attempt per second at most). While the Mini App is closed, the group chat shows one photo that the bot refreshes in place every few seconds, so the chat is not flooded.

## How it is built

One Python process runs the bot (long polling) and the Mini App backend, side by side.

| File | Role |
|---|---|
| `carmink.py` | Entry point: bot + uvicorn in one event loop |
| `engine.py` | The match: lobby, turns, timers, guesses, hints, scoring. It knows nothing about Telegram or HTTP |
| `game.py`, `words.py`, `difficulty.py` | Model and pure rules; dictionary, matching, hint masks; adaptive difficulty |
| `dictionary.py`, `dictio.py` | Group dictionary page: permissions and edits; export/import file, pasted list, share codes |
| `carmeleon.py`, `codestroke.py` | The two beta party modes (state in `game.py`, strings in `i18n_party.py`, tests in `tests/test_party.py`) |
| `broken.py`, `gifmaker.py` | Broken Canva: passes, private messages, drawings; GIF of every chain (Pillow) |
| `handlers.py`, `tg_io.py`, `admin.py` | Telegram side: commands, messages and timers, `/admin` |
| `webserver.py`, `auth.py` | Mini App API (Starlette) and validation of Telegram's `initData` |
| `web/` | The Mini App: `index.html`, `app.js` (game), `dict.js` (dictionary page), `fill.js`, `style.css` |
| `db.py`, `i18n.py`, `config.py`, `logs.py` | SQLite, texts, settings and constants, logging |

The server owns every rule and every timer; the Mini App only draws, sends the pictures, and shows what `/api/state` tells it. Matches live in memory: a restart ends the running ones. Everything in `config.py` (timings, points, snapshot rate) can be tuned.

## Setup

**1. BotFather** (for @carminkgame)
- `/setprivacy` → *Disable*, so the bot can read the guesses (or make the bot a group admin).
- At startup the bot also registers its *default administrator rights* (delete messages), so Telegram suggests them when it is added as an admin. When added to a group it says hello and shows a button that asks for those rights (`t.me/<bot>?startgroup=true&admin=delete_messages`); `/newgame` repeats the reminder for Speedrun and Classic if the right is missing.
- In the groups, give the bot the *Delete messages* permission.
- `/newapp` → pick the bot, short name `app`, Web App URL `https://carmink.suketchi.art`. The direct link is `t.me/carminkgame/app`.

**2. DNS** — an `A` record `carmink` pointing to the server's IP.

**3. Server** (Debian/Ubuntu)

```bash
sudo apt install nginx certbot python3-certbot-nginx python3-venv git fonts-dejavu-core
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

About 1,900 words per language. The objects and living things come largely from the category names of Google's [Quick, Draw!](https://github.com/googlecreativelab/quickdraw-dataset) dataset (345 things that people could draw in 20 seconds, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)), translated and sorted by difficulty; the actions and emotions, and the rest, were added by hand.

`data/words_it.json` and `data/words_en.json`: category (`animals`, `nature`, `plants`, `body`, `food`, `people`, `places`, `vehicles`, `objects`, `actions`, `sport`, `music`, `other`) → difficulty (`"1"` easy, `"2"` medium, `"3"` hard) → list of words. A word can list accepted alternatives after `|` (`"frigorifero|frigo"`). The tests check that there are no duplicates and that every main category/difficulty has enough words. The group dictionary holds up to 3,000 words **per language**. When the categories were introduced (database version 2) the dictionaries already copied by groups were reset once, so every group restarts from the new built-in one.

## Group dictionary

**Copy.** The first time a group plays in a language, the built-in dictionary is copied into the database for that group (`custom_words`); from then on the group's words are its own. Test matches use the built-in words and never touch this.

**Adaptive difficulty** (`difficulty.py`, constants in `config.py`). After every real round (somebody drew, at least two could guess) the word gets an *ease* from 0 to 1: Classic, the share of guessers who got it; Speedrun, 0 if nobody did, otherwise 0.3–1 depending on how fast; discounted 20% per hint. A decaying weighted average, pulled towards what the word's starting level predicts (it counts as 3 rounds), estimates how easy it really is; the level moves to easy at ≥ 0.65 (back below 0.55) or to hard at ≤ 0.25 (back above 0.35), after at least 2 rounds. In practice a word needs about 5 rounds to change. A level an admin sets by hand is locked 🔒 and never adapted until they turn the automatic level back on.

**Your own word.** In Speedrun and Classic the drawer can tap *✏️ Write your own word or phrase* next to the three words (2–40 characters, letters only, up to 6 words, synonyms with `word | synonym`). Tapping gives him 30 seconds instead of 10, once. A word the dictionary already has is used with its level; a new one scores like a medium word and joins the group's dictionary only if somebody guesses it, with the level that follows from how many did.

**The page** (`/settings` → 📚 Dictionary, a Mini App page; admins, or every member if the group chose so): search, filter by level, add, edit (word, synonyms, level, automatic/locked) and delete words, per language. A group cannot go below 30 words per language.

**Export and import.**
- *File*: **Export** sends a `.json` with every word, its level and what the group learned about it, in private to whoever asks. **Import** takes that file, or a pasted list (`word | synonym | 2`, one per line).
- *Code*: **Code** creates a short code (`XXXX-XXXX`, valid 24 hours, reusable) that another group's admin enters under **Import**: the quickest way to copy a dictionary from one group to another.
- Import shows a preview first. Words the group already has are left alone, unless *update words already there* is ticked (then level, synonyms and statistics become the file's: tick it when importing into a group that has just started).

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest
```

They cover the engine with a fake clock (a whole match, timeouts, hints, spoilers, players leaving), the HTTP API, `initData` validation, the command handlers, and (when Node.js is installed) the canvas flood fill.


Additional words were curated (filtered for drawability and translated) from user [nick-aschenbach's game-words repository](https://github.com/nick-aschenbach/game-words/tree/master). 

## Test matches (bot owner)

`/admin` → **🧪 Partita di test**: pick a mode and 3–8 fake players ("Test 1…N", 4+ for Broken Canva). The match runs in your private chat: group messages and the DMs of Broken Canva all arrive there, labelled with the player. `/c` shows a panel of buttons for the running test: ❌/✅ wrong or correct guess per player (Speedrun, Classic), 🎲 a made-up phrase and 🖼 a quick random drawing per player or for all (Broken Canva), plus buttons to pick the word and start drawing. Write as a player with `/t <n> <text>`; to draw or guess in the Mini App open it from the 🎨 button and pick the player from the yellow bar at the top. Test matches don't touch the statistics and can be ended any time from the same menu.
