"""User-facing strings (Italian / English)."""

DEFAULT_LANG = "it"
LANGUAGES = ("it", "en")


def T(lang: str, key: str, **kw) -> str:
    """Return the string `key` in `lang` (falls back to the default language)."""
    entry = STRINGS[key]
    text = entry.get(lang) or entry[DEFAULT_LANG]
    return text.format(**kw) if kw else text


STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------ start / help
    "start_private": {
        "it": "🎨 <b>Carmink</b>: disegna, gli altri indovinano!\n\nAggiungimi a un gruppo e scrivi /newgame. "
              "Il disegnatore di turno ha 90 secondi per disegnare la parola che sceglie tra tre, gli altri provano a "
              "indovinarla (in chat o nella Mini App, secondo la modalità). Più sei veloce, più punti prendi; il disegnatore guadagna di più se "
              "indovinano in tanti.\n\n"
              "<b>Comandi</b>\n/newgame · /join · /ready · /wait &lt;minuti&gt; · /quit · /stop\n"
              "/addword &lt;parola&gt; [| sinonimo…] [1-3] · /deleteword &lt;parola&gt; · /stats · /mystats · /settings\n\n"
              "Nel gruppo disattiva la modalità privacy del bot o rendilo amministratore, altrimenti non vede i tentativi.",
        "en": "🎨 <b>Carmink</b>: draw, the others guess!\n\nAdd me to a group and type /newgame. "
              "The current drawer has 90 seconds to draw a word picked among three, the others try to guess it "
              "in the chat or in the Mini App, depending on the mode. The faster you guess, the more points you get; the drawer earns more when "
              "many players guess.\n\n"
              "<b>Commands</b>\n/newgame · /join · /ready · /wait &lt;minutes&gt; · /quit · /stop\n"
              "/addword &lt;word&gt; [| synonym…] [1-3] · /deleteword &lt;word&gt; · /stats · /mystats · /settings\n\n"
              "In the group, turn off the bot's privacy mode or make it an admin, or it can't see the guesses.",
    },
    "help": {
        "it": "🎨 <b>Carmink</b>: disegna, gli altri indovinano!\n\n"
              "A turno uno disegna la parola scelta tra tre (90 secondi dal primo tratto), gli altri indovinano "
              "(in chat o nella Mini App, secondo la modalità). Più sei veloce, più punti prendi; chi disegna ne prende di più se indovinano in tanti, "
              "e può dare indizi al costo di qualche punto. Servono almeno 3 giocatori.\n\n"
              "<b>Partita</b>\n/newgame · /join · /ready · /wait &lt;minuti&gt; · /quit · /stop\n"
              "<b>Dizionario del gruppo</b>\n/addword &lt;parola&gt; [| sinonimo…] [1-3] · /deleteword &lt;parola&gt;\n"
              "<b>Altro</b>\n/stats · /mystats · /settings · /help",
        "en": "🎨 <b>Carmink</b>: draw, the others guess!\n\n"
              "Players take turns drawing a word picked among three (90 seconds from the first stroke) while the others "
              "guess in the chat or in the Mini App, depending on the mode. The faster you guess, the more points you get; the drawer earns more when "
              "many players guess, and can give hints at the cost of some points. At least 3 players are needed.\n\n"
              "<b>Match</b>\n/newgame · /join · /ready · /wait &lt;minutes&gt; · /quit · /stop\n"
              "<b>Group dictionary</b>\n/addword &lt;word&gt; [| synonym…] [1-3] · /deleteword &lt;word&gt;\n"
              "<b>Other</b>\n/stats · /mystats · /settings · /help",
    },
    "start_group": {"it": "Per giocare usa /newgame in questo gruppo.",
                    "en": "To play, use /newgame in this group."},
    "group_only": {"it": "Usa questo comando in un gruppo.", "en": "Use this command in a group."},
    # ------------------------------------------------------------ lobby
    "lobby_open": {
        "it": "🎨 <b>{name}</b> ha aperto una partita {mode}! Scrivete /join per entrare, /ready per iniziare subito "
              "(minimo {min} giocatori). Le iscrizioni chiudono tra {time}: /wait &lt;minuti&gt; le prolunga.",
        "en": "🎨 <b>{name}</b> opened a {mode} match! Type /join to enter, /ready to start right away "
              "(minimum {min} players). Sign-ups close in {time}: /wait &lt;minutes&gt; extends them.",
    },
    "mode_speedrun": {"it": "🔥 Speedrun", "en": "🔥 Speedrun"},
    "mode_classic": {"it": "🕹️ Classica", "en": "🕹️ Classic"},
    "mode_broken": {"it": "☎️ Broken Canva", "en": "☎️ Broken Canva"},
    "mode_pick": {
        "it": "Scegli la modalità, <b>{name}</b>:\n"
              "🔥 <b>Speedrun</b>: indovini in chat, il primo che indovina vince il round.\n"
              "🕹️ <b>Classica</b>: si indovina nella Mini App e tutti possono continuare a provare.\n"
              "☎️ <b>Broken Canva</b>: telefono senza fili di frasi e disegni, nessun vincitore.",
        "en": "Pick the mode, <b>{name}</b>:\n"
              "🔥 <b>Speedrun</b>: guess in the chat, the first to guess wins the round.\n"
              "🕹️ <b>Classic</b>: guess in the Mini App, everybody keeps trying.\n"
              "☎️ <b>Broken Canva</b>: telephone game of phrases and drawings, nobody wins.",
    },
    "mode_soon": {"it": "Questa modalità arriva presto.", "en": "This mode is coming soon."},
    "mode_only_creator": {"it": "Solo chi ha usato /newgame può scegliere.", "en": "Only whoever used /newgame can choose."},
    "join_closed": {"it": "In questo gruppo non si può entrare a partita in corso.",
                    "en": "Joining a running match is turned off in this group."},
    "game_exists": {"it": "C'è già una partita in questo gruppo.", "en": "There is already a match in this group."},
    "already_in_game": {"it": "Sei già in una partita attiva.", "en": "You are already in an active match."},
    "no_game": {"it": "Nessuna partita in corso: usa /newgame.", "en": "No match running: use /newgame."},
    "no_lobby": {"it": "Non ci sono iscrizioni aperte.", "en": "There are no open sign-ups."},
    "join_already": {"it": "Sei già in partita.", "en": "You are already in the match."},
    "join_other": {"it": "Sei già in una partita in un altro gruppo.", "en": "You are already in a match in another group."},
    "joined": {"it": "✅ {name} è dentro! Giocatori: {n}", "en": "✅ {name} joined! Players: {n}"},
    "joined_late": {
        "it": "✅ {name} entra a partita in corso: può già indovinare e disegnerà alla fine.",
        "en": "✅ {name} joins the running match: can guess right away and will draw at the end.",
    },
    "only_players": {"it": "Solo chi è in partita può farlo (/join).", "en": "Only players can do that (/join)."},
    "ready_need": {"it": "Servono almeno {min} giocatori, ora siete {n}.", "en": "At least {min} players are needed, now there are {n}."},
    "wait_usage": {"it": "Uso: /wait &lt;minuti&gt;, ad esempio /wait 3", "en": "Usage: /wait &lt;minutes&gt;, for example /wait 3"},
    "wait_max": {"it": "Massimo {max} minuti per volta.", "en": "At most {max} minutes at a time."},
    "wait_ok": {"it": "⏳ Iscrizioni prolungate di {added}: restano {left}.", "en": "⏳ Sign-ups extended by {added}: {left} left."},
    "not_enough": {"it": "Partita annullata: servono almeno {min} giocatori.", "en": "Match cancelled: at least {min} players are needed."},
    "stop_denied": {"it": "Solo chi ha creato la partita o un admin del gruppo può annullarla.",
                    "en": "Only the match creator or a group admin can cancel it."},
    "stopped": {"it": "🛑 Partita annullata.", "en": "🛑 Match cancelled."},
    "not_in_game": {"it": "Non sei in partita.", "en": "You are not in the match."},
    "quit_ok": {"it": "👋 {name} ha lasciato la partita.", "en": "👋 {name} left the match."},
    "too_few": {"it": "Sono rimasti troppo pochi giocatori: la partita finisce qui.",
                "en": "Too few players are left: the match ends here."},
    # ------------------------------------------------------------ turns
    "game_start": {"it": "🚦 Si parte! {n} giocatori, {turns} round.", "en": "🚦 Here we go! {n} players, {turns} rounds."},
    "next_drawer": {
        "it": "🎨 Prossimo disegnatore: <b>{name}</b> (round {n}/{total}). Si comincia tra {secs} secondi.",
        "en": "🎨 Next drawer: <b>{name}</b> (round {n}/{total}). Starting in {secs} seconds.",
    },
    "btn_open": {"it": "🖌 Apri la lavagna", "en": "🖌 Open the canvas"},
    "btn_play": {"it": "🎮 Apri Carmink", "en": "🎮 Open Carmink"},
    "btn_watch": {"it": "👀 Guarda in diretta", "en": "👀 Watch live"},
    "skip_no_choice": {"it": "⏭ <b>{name}</b> non ha scelto la parola in tempo: turno saltato.",
                       "en": "⏭ <b>{name}</b> didn't pick a word in time: turn skipped."},
    "skip_no_start": {"it": "⏭ <b>{name}</b> non ha iniziato a disegnare in tempo: turno saltato.",
                      "en": "⏭ <b>{name}</b> didn't start drawing in time: turn skipped."},
    "skip_by_drawer": {"it": "⏭ <b>{name}</b> ha saltato il proprio turno.", "en": "⏭ <b>{name}</b> skipped their turn."},
    "skip_left": {"it": "⏭ <b>{name}</b> ha lasciato la partita: turno saltato.",
                  "en": "⏭ <b>{name}</b> left the match: turn skipped."},
    "drawing_started": {
        "it": "🖌 <b>{name}</b> sta disegnando! {icon} Avete {secs} secondi: scrivete qui la parola.",
        "en": "🖌 <b>{name}</b> is drawing! {icon} You have {secs} seconds: type the word here.",
    },
    "drawing_started_classic": {
        "it": "🖌 <b>{name}</b> sta disegnando! {icon} Avete {secs} secondi: indovinate nella Mini App 👇",
        "en": "🖌 <b>{name}</b> is drawing! {icon} You have {secs} seconds: guess in the Mini App 👇",
    },
    "classic_chat_notice": {
        "it": "ℹ️ {name}, in modalità Classica i tentativi si scrivono nella Mini App: questo messaggio non vale.",
        "en": "ℹ️ {name}, in Classic mode guesses are typed in the Mini App: that message doesn't count.",
    },
    "hint_given": {"it": "💡 Suggerimento: <code>{mask}</code> (punti -{pct}%)",
                   "en": "💡 Hint: <code>{mask}</code> (points -{pct}%)"},
    "guessed": {"it": "✅ <b>{name}</b> ha indovinato! +{pts}", "en": "✅ <b>{name}</b> got it! +{pts}"},
    "close": {"it": "🔥 Ci sei vicino!", "en": "🔥 So close!"},
    "result_all": {"it": "🎉 Hanno indovinato tutti! La parola era <b>{word}</b>.",
                   "en": "🎉 Everybody got it! The word was <b>{word}</b>."},
    "result_win": {"it": "🔥 Round vinto! La parola era <b>{word}</b>.",
                   "en": "🔥 Round won! The word was <b>{word}</b>."},
    "result_time": {"it": "⏰ Tempo scaduto! La parola era <b>{word}</b>.",
                    "en": "⏰ Time is up! The word was <b>{word}</b>."},
    "result_skip": {"it": "⏭ Turno concluso dal disegnatore. La parola era <b>{word}</b>.",
                    "en": "⏭ The drawer ended the turn. The word was <b>{word}</b>."},
    "result_left": {"it": "👋 Il disegnatore ha lasciato la partita. La parola era <b>{word}</b>.",
                    "en": "👋 The drawer left the match. The word was <b>{word}</b>."},
    "nobody_guessed": {"it": "Nessuno ha indovinato.", "en": "Nobody guessed."},
    "board_title": {"it": "🏆 Classifica", "en": "🏆 Scoreboard"},
    "game_over": {"it": "🏁 <b>Partita finita!</b> Classifica finale:", "en": "🏁 <b>Match over!</b> Final scoreboard:"},
    "winner": {"it": "👑 Vince {names}!", "en": "👑 {names} wins!"},
    # ------------------------------------------------------------ dictionary
    "word_usage_add": {"it": "Uso: /addword &lt;parola&gt; [| sinonimo | sinonimo…] [1-3] (1 facile, 2 media, 3 difficile)\nEsempio: /addword monopattino | scooter 3",
                       "en": "Usage: /addword &lt;word&gt; [| synonym | synonym…] [1-3] (1 easy, 2 medium, 3 hard)\nExample: /addword scooter | kick scooter 3"},
    "word_alts": {"it": "\nSinonimi accettati: {alts}", "en": "\nAccepted synonyms: {alts}"},
    "word_usage_del": {"it": "Uso: /deleteword &lt;parola&gt;", "en": "Usage: /deleteword &lt;word&gt;"},
    "word_admin": {"it": "Solo gli admin del gruppo possono modificare il dizionario (vedi /settings).",
                   "en": "Only group admins can edit the dictionary (see /settings)."},
    "word_bad": {"it": "Parola non valida: 2-30 lettere, al massimo 3 parole, niente numeri o simboli.",
                 "en": "Invalid word: 2-30 letters, at most 3 words, no digits or symbols."},
    "word_added": {"it": "✅ «{word}» aggiunta al dizionario del gruppo (difficoltà {diff}).",
                   "en": "✅ «{word}» added to the group dictionary (difficulty {diff})."},
    "word_dup": {"it": "«{word}» è già nel dizionario del gruppo.", "en": "«{word}» is already in the group dictionary."},
    "word_full": {"it": "Il dizionario del gruppo è pieno ({max} parole).", "en": "The group dictionary is full ({max} words)."},
    "word_deleted": {"it": "🗑 «{word}» tolta dal dizionario del gruppo.", "en": "🗑 «{word}» removed from the group dictionary."},
    "word_missing": {"it": "«{word}» non è nel dizionario del gruppo (si possono togliere solo le parole aggiunte con /addword).",
                     "en": "«{word}» is not in the group dictionary (only words added with /addword can be removed)."},
    # ------------------------------------------------------------ stats
    "stats_none": {"it": "Nessuna partita finita in questo gruppo, per ora.", "en": "No finished match in this group yet."},
    "stats_title": {"it": "📊 <b>Statistiche del gruppo</b> — {games} partite", "en": "📊 <b>Group statistics</b> — {games} matches"},
    "stats_wins": {"it": "🏆 Più vittorie", "en": "🏆 Most wins"},
    "stats_points": {"it": "⭐ Più punti totali", "en": "⭐ Most total points"},
    "stats_guessed": {"it": "🎯 Più parole indovinate", "en": "🎯 Most words guessed"},
    "stats_best": {"it": "🚀 Miglior partita: {name} con {pts} punti", "en": "🚀 Best match: {name} with {pts} points"},
    "mystats_none": {"it": "Non hai ancora finito nessuna partita.", "en": "You haven't finished any match yet."},
    "mystats": {
        "it": "📊 <b>{name}</b>\nPartite: {games} · Vittorie: {wins}\nPunti totali: {points} · Miglior partita: {best}\n"
              "Parole indovinate: {guessed} · Turni disegnati: {drawn}",
        "en": "📊 <b>{name}</b>\nMatches: {games} · Wins: {wins}\nTotal points: {points} · Best match: {best}\n"
              "Words guessed: {guessed} · Turns drawn: {drawn}",
    },
    # ------------------------------------------------------------ settings
    "settings_title": {"it": "⚙️ Impostazioni del gruppo", "en": "⚙️ Group settings"},
    "settings_admin": {"it": "Solo gli admin del gruppo possono cambiare le impostazioni.",
                       "en": "Only group admins can change the settings."},
    "settings_saved": {"it": "Salvato", "en": "Saved"},
    "btn_back": {"it": "⬅️ Indietro", "en": "⬅️ Back"},
    "set_lang": {"it": "Lingua", "en": "Language"},
    "set_lang_it": {"it": "🇮🇹 Italiano", "en": "🇮🇹 Italiano"},
    "set_lang_en": {"it": "🇬🇧 English", "en": "🇬🇧 English"},
    "settings_sub_lang": {"it": "Lingua dei messaggi e delle parole da disegnare. Si può cambiare anche per una sola partita con /newgame en.",
                          "en": "Language of the messages and of the words to draw. It can also be set for a single match with /newgame it."},
    "set_words": {"it": "Dizionario del gruppo", "en": "Group dictionary"},
    "set_words_admins": {"it": "Solo admin", "en": "Admins only"},
    "set_words_everyone": {"it": "Tutti", "en": "Everyone"},
    "set_latejoin": {"it": "Ingresso a partita in corso", "en": "Joining a running match"},
    "set_latejoin_on": {"it": "Consentito", "en": "Allowed"},
    "set_latejoin_off": {"it": "Vietato", "en": "Not allowed"},
    "settings_sub_latejoin": {
        "it": "Se consentito, /join funziona anche a partita iniziata (Speedrun e Classica): si indovina subito e si disegna alla fine.",
        "en": "If allowed, /join also works once a match has started (Speedrun and Classic): you guess at once and draw at the end."},
    "settings_sub_words": {"it": "Chi può usare /addword e /deleteword.", "en": "Who can use /addword and /deleteword."},
}
