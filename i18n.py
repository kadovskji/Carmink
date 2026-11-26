"""User-facing strings (Italian / English)."""

DEFAULT_LANG = "it"
LANGUAGES = ("it", "en")


def dur(lang: str, seconds: int) -> str:
    """15 -> '15 secondi', 120 -> '2 minuti' (for the messages that name a time)."""
    if seconds % 60 == 0:
        m = seconds // 60
        return (f"{m} minut{'o' if m == 1 else 'i'}" if lang == "it" else f"{m} minute{'' if m == 1 else 's'}")
    return f"{seconds} secondi" if lang == "it" else f"{seconds} seconds"


def T(lang: str, key: str, **kw) -> str:
    """Return the string `key` in `lang` (falls back to the default language)."""
    entry = STRINGS[key]
    text = entry.get(lang) or entry[DEFAULT_LANG]
    return text.format(**kw) if kw else text


STRINGS: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------ start / help
    "start_private": {
        "it": "🎨 <b>Carmink</b>: disegna, gli altri indovinano!\n\nAggiungimi a un gruppo e scrivi /newgame. "
              "Il disegnatore di turno ha pochi minuti per disegnare la parola che sceglie tra tre, gli altri provano a "
              "indovinarla (in chat o nella Mini App, secondo la modalità). Più sei veloce, più punti prendi; il disegnatore guadagna di più se "
              "indovinano in tanti.\n\n"
              "<b>Comandi</b>\n/newgame · /join · /ready · /nextgame · /wait &lt;minuti&gt; · /quit · /stop\n"
              "/stats · /mystats · /settings\n\n"
              "Nel gruppo rendimi amministratore (con il permesso di eliminare i messaggi), altrimenti non vedo i tentativi e non posso cancellare le risposte.",
        "en": "🎨 <b>Carmink</b>: draw, the others guess!\n\nAdd me to a group and type /newgame. "
              "The current drawer has a few minutes to draw a word picked among three, the others try to guess it "
              "in the chat or in the Mini App, depending on the mode. The faster you guess, the more points you get; the drawer earns more when "
              "many players guess.\n\n"
              "<b>Commands</b>\n/newgame · /join · /ready · /nextgame · /wait &lt;minutes&gt; · /quit · /stop\n"
              "/stats · /mystats · /settings\n\n"
              "In the group make me an admin (with the permission to delete messages), or I can't see the guesses and can't delete the answers.",
    },
    "help": {
        "it": "🎨 <b>Carmink</b>: disegna, gli altri indovinano!\n\n"
              "A turno uno disegna la parola scelta tra tre (tempo dal primo tratto, regolabile in /settings: 2 minuti di default), gli altri indovinano "
              "(in chat o nella Mini App, secondo la modalità). Più sei veloce, più punti prendi; chi disegna ne prende di più se indovinano in tanti, "
              "e può dare indizi al costo di qualche punto. Servono almeno 3 giocatori (4 per Broken Canva, il telefono senza fili di frasi e disegni).\n\n"
              "<b>Modalità</b> (le sceglie chi usa /newgame)\n"
              "🔥 <b>Speedrun</b>: si indovina in chat, il primo che indovina vince il round.\n"
              "🕹️ <b>Classica</b>: si indovina nella Mini App e tutti continuano a provare.\n"
              "☎️ <b>Broken Canva</b>: telefono senza fili; ognuno scrive in privato una frase, poi frasi e disegni passano di mano in mano. "
              "Nessun vincitore, alla fine arrivano le GIF. Servono 4 giocatori che abbiano avviato il bot in privato.\n\n"
              "<b>Partita</b>\n/newgame · /join · /ready · /wait &lt;minuti&gt; · /quit · /stop\n"
              "<b>Avviso</b>\n/nextgame: ti scrivo in privato quando si apre la prossima partita (24 ore, dovrai comunque fare /join; rimandalo per annullare)\n"
              "<b>Dizionario del gruppo</b>\nIn /settings → 📚 Dizionario: aggiungi, modifica, esporta e importa le parole. Se il disegnatore scrive una parola sua e qualcuno la indovina, entra nel dizionario.\n"
              "<b>Altro</b>\n/stats · /mystats · /settings · /help",
        "en": "🎨 <b>Carmink</b>: draw, the others guess!\n\n"
              "Players take turns drawing a word picked among three (time counted from the first stroke, adjustable in /settings: 2 minutes by default) while the others "
              "guess in the chat or in the Mini App, depending on the mode. The faster you guess, the more points you get; the drawer earns more when "
              "many players guess, and can give hints at the cost of some points. At least 3 players are needed (4 for Broken Canva, the telephone game of phrases and drawings).\n\n"
              "<b>Modes</b> (picked by whoever uses /newgame)\n"
              "🔥 <b>Speedrun</b>: guess in the chat, the first to guess wins the round.\n"
              "🕹️ <b>Classic</b>: guess in the Mini App, everybody keeps trying.\n"
              "☎️ <b>Broken Canva</b>: telephone game; everybody privately writes a phrase, then phrases and drawings are passed around. "
              "Nobody wins, GIFs come at the end. Needs 4 players who have started the bot in private.\n\n"
              "<b>Match</b>\n/newgame · /join · /ready · /wait &lt;minutes&gt; · /quit · /stop\n"
              "<b>Notice</b>\n/nextgame: I message you in private when the next match opens (24 hours, you still have to /join; send it again to cancel)\n"
              "<b>Group dictionary</b>\nIn /settings → 📚 Dictionary: add, edit, export and import words. If the drawer writes a word of his own and somebody guesses it, it joins the dictionary.\n"
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
        "it": "🖌 <b>{name}</b> sta disegnando! {icon} Avete {secs}: scrivete qui la parola.",
        "en": "🖌 <b>{name}</b> is drawing! {icon} You have {secs}: type the word here.",
    },
    "drawing_started_classic": {
        "it": "🖌 <b>{name}</b> sta disegnando! {icon} Avete {secs}: indovinate nella Mini App 👇",
        "en": "🖌 <b>{name}</b> is drawing! {icon} You have {secs}: guess in the Mini App 👇",
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
    "btn_dict": {"it": "📚 Dizionario", "en": "📚 Dictionary"},
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
    "set_words": {"it": "Chi modifica il dizionario", "en": "Who edits the dictionary"},
    "set_words_admins": {"it": "Solo admin", "en": "Admins only"},
    "set_words_everyone": {"it": "Tutti", "en": "Everyone"},
    "set_latejoin": {"it": "Ingresso a partita in corso", "en": "Joining a running match"},
    "set_latejoin_on": {"it": "Consentito", "en": "Allowed"},
    "set_latejoin_off": {"it": "Vietato", "en": "Not allowed"},
    "settings_sub_latejoin": {
        "it": "Se consentito, /join funziona anche a partita iniziata (Speedrun e Classica): si indovina subito e si disegna alla fine.",
        "en": "If allowed, /join also works once a match has started (Speedrun and Classic): you guess at once and draw at the end."},
    "set_cycles": {"it": "Cicli Broken Canva", "en": "Broken Canva cycles"},
    "set_cycles_auto": {"it": "Auto (il massimo possibile, max 5)", "en": "Auto (as many as fit, max 5)"},
    "set_cycles_1": {"it": "1 ciclo", "en": "1 cycle"},
    "set_cycles_2": {"it": "2 cicli", "en": "2 cycles"},
    "set_cycles_3": {"it": "3 cicli", "en": "3 cycles"},
    "set_cycles_4": {"it": "4 cicli", "en": "4 cycles"},
    "set_cycles_5": {"it": "5 cicli", "en": "5 cycles"},
    "settings_sub_cycles": {
        "it": "Quanti cicli dura una partita di Broken Canva (un ciclo = una frase o descrizione e il suo disegno), per le partite che iniziano da ora. "
              "Auto: il massimo possibile senza che nessuno tocchi due volte la stessa catena (al massimo 5).",
        "en": "How many cycles a Broken Canva match lasts (a cycle = a phrase or description and its drawing), for matches started from now on. "
              "Auto: as many as possible without anyone touching a chain twice (at most 5)."},
    "settings_sub_words": {"it": "Chi può modificare il dizionario del gruppo (pulsante 📚 Dizionario).", "en": "Who can edit the group dictionary (the 📚 Dictionary button)."},
}


# ---------------------------------------------------------------- Broken Canva
STRINGS.update({
    "btn_start_bot": {"it": "▶️ Avvia il bot", "en": "▶️ Start the bot"},
    "btn_open_bot": {"it": "💬 Apri il bot", "en": "💬 Open the bot"},
    "btn_draw": {"it": "🎨 Disegna", "en": "🎨 Draw"},
    "bk_lobby_note": {
        "it": "☎️ <b>Broken Canva</b>: ognuno scrive al bot, in privato, una frase buffa; poi le frasi diventano "
              "disegni e i disegni descrizioni, passando di mano in mano. Nessun vincitore, alla fine arrivano le GIF!\n"
              "Per entrare bisogna aver avviato il bot in privato: se /join non basta, usa il pulsante.",
        "en": "☎️ <b>Broken Canva</b>: everybody privately sends the bot a funny phrase; then phrases turn into "
              "drawings and drawings into descriptions, passed from hand to hand. Nobody wins, GIFs come at the end!\n"
              "To join you must have started the bot in private: if /join isn't enough, use the button.",
    },
    "nextgame_on": {
        "it": "🔔 {name}, ti scriverò in privato quando si aprirà la prossima partita in questo gruppo (dovrai comunque fare /join). "
              "Rimanda /nextgame per annullare. (Valido per {hours} ore.)",
        "en": "🔔 {name}, I'll message you in private when the next match opens in this group (you'll still need to /join). "
              "Send /nextgame again to cancel. (Valid for {hours} hours.)",
    },
    "nextgame_off": {"it": "↩️ {name}, l'avviso per la prossima partita è annullato.",
                     "en": "↩️ {name}, the notification for the next match is cancelled."},
    "nextgame_lobby_open": {"it": "C'è già una partita in attesa di giocatori: usa /join.",
                            "en": "A match is already waiting for players: use /join."},
    "nextgame_dm": {
        "it": "🔔 Sta aprendo una nuova partita {mode} in «{chat}»! Le iscrizioni durano {minutes} minuti: vai nel gruppo e scrivi /join.",
        "en": "🔔 A new {mode} match is opening in “{chat}”! Sign-ups last {minutes} minutes: go to the group and send /join.",
    },
    "nextgame_need_dm": {
        "it": "🔔 Per ricevere l'avviso devo poterti scrivere in privato: tocca il pulsante, premi <b>Avvia</b> e poi rimanda /nextgame.",
        "en": "🔔 To send you the notice I must be able to write to you in private: tap the button, press <b>Start</b>, then send /nextgame again.",
    },
    "bk_need_dm": {
        "it": "☎️ Per Broken Canva ogni giocatore deve prima aprire il bot in privato (altrimenti non posso scrivergli). "
              "Tocca il pulsante, premi <b>Avvia</b> e torna qui.",
        "en": "☎️ For Broken Canva every player must first open the bot in private (or I can't write to them). "
              "Tap the button, press <b>Start</b> and come back here.",
    },
    "bk_start_ok": {"it": "✅ Perfetto, ora posso scriverti. Torna nel gruppo!",
                    "en": "✅ Great, now I can write to you. Go back to the group!"},
    "join_closed_broken": {"it": "Broken Canva non si può iniziare o raggiungere a partita iniziata.",
                           "en": "Nobody can join Broken Canva once it has started."},
    "bk_dm_failed": {
        "it": "Non riesco a scrivere in privato a: {names}. Devono avviare il bot: per ora restano fuori.",
        "en": "I can't write privately to: {names}. They must start the bot: they are out for now.",
    },
    "bk_aborted": {"it": "☎️ Partita annullata: troppi pochi giocatori.", "en": "☎️ Match cancelled: too few players."},
    "bk_dropped": {"it": "{names} non ha mandato la frase in tempo: fuori dalla partita.",
                   "en": "{names} didn't send a phrase in time: out of the match."},
    "bk_write_dm": {
        "it": "☎️ <b>Broken Canva</b>\nScrivimi qui, in un messaggio, una frase buffa o stravagante (max {max} caratteri). "
              "Hai {time}. Gli altri dovranno disegnarla!\nPuoi cambiarla rimandandone un'altra, finché non hanno scritto tutti.",
        "en": "☎️ <b>Broken Canva</b>\nWrite me here, in one message, a funny or peculiar phrase (max {max} characters). "
              "You have {time}. The others will have to draw it!\nYou can change it by sending another, until everybody has written.",
    },
    "bk_status_write": {
        "it": "☎️ <b>Broken Canva</b> — frasi iniziali ({n}/{total}), {secs} secondi.\nScrivete al bot in privato!\n{rows}",
        "en": "☎️ <b>Broken Canva</b> — first phrases ({n}/{total}), {secs} seconds.\nWrite to the bot in private!\n{rows}",
    },
    "bk_status_draw": {
        "it": "☎️ <b>Passo {step}/{steps}</b> — 🎨 si disegna ({n}/{total}):\n{rows}",
        "en": "☎️ <b>Pass {step}/{steps}</b> — 🎨 drawing ({n}/{total}):\n{rows}",
    },
    "bk_status_describe": {
        "it": "☎️ <b>Passo {step}/{steps}</b> — ✍️ si descrive il disegno ({n}/{total}):\n{rows}",
        "en": "☎️ <b>Pass {step}/{steps}</b> — ✍️ describing the drawing ({n}/{total}):\n{rows}",
    },
    "bk_draw_dm": {
        "it": "🎨 <b>Passo {step}/{steps}</b> — disegna questa frase, hai {secs}:\n\n«{text}»",
        "en": "🎨 <b>Pass {step}/{steps}</b> — draw this phrase, you have {secs}:\n\n«{text}»",
    },
    "bk_describe_dm": {
        "it": "✍️ <b>Passo {step}/{steps}</b> — descrivi questo disegno con una frase: rispondimi con un messaggio, hai {secs}.",
        "en": "✍️ <b>Pass {step}/{steps}</b> — describe this drawing with a phrase: answer with one message, you have {secs}.",
    },
    "bk_saved": {"it": "✅ Ricevuta!", "en": "✅ Got it!"},
    "bk_replaced": {"it": "✅ Sostituita con la nuova.", "en": "✅ Replaced with the new one."},
    "bk_too_long": {"it": "Troppo lunga: massimo {max} caratteri.", "en": "Too long: {max} characters at most."},
    "bk_use_app": {"it": "Ora si disegna: usa il pulsante del messaggio con la frase.",
                   "en": "Now it's drawing time: use the button of the message with the phrase."},
    "bk_over": {"it": "☎️ <b>Broken Canva</b> finito! Ecco come si sono trasformate le frasi:",
                "en": "☎️ <b>Broken Canva</b> is over! Here is how the phrases turned out:"},
    "bk_chain_caption": {"it": "☎️ Catena partita da <b>{name}</b>", "en": "☎️ Chain started by <b>{name}</b>"},
    "bk_drawing": {"it": "(disegno)", "en": "(drawing)"},
    "bk_gif_start": {"it": "Frase di {name}", "en": "Phrase by {name}"},
    "bk_gif_draw": {"it": "Disegno di {name}", "en": "Drawing by {name}"},
    "bk_gif_describe": {"it": "{name} ha scritto", "en": "{name} wrote"},
})


# ---------------------------------------------------------------- drawing time, admin rights
STRINGS.update({
    "set_drawtime": {"it": "Tempo per disegno", "en": "Drawing time"},
    "set_drawtime_auto": {"it": "Auto (2 min, Broken Canva 3 min)", "en": "Auto (2 min, Broken Canva 3 min)"},
    "set_drawtime_60": {"it": "60 secondi", "en": "60 seconds"},
    "set_drawtime_90": {"it": "90 secondi", "en": "90 seconds"},
    "set_drawtime_120": {"it": "2 minuti", "en": "2 minutes"},
    "set_drawtime_180": {"it": "3 minuti", "en": "3 minutes"},
    "set_drawtime_240": {"it": "4 minuti", "en": "4 minutes"},
    "set_drawtime_300": {"it": "5 minuti", "en": "5 minutes"},
    "settings_sub_drawtime": {
        "it": "Quanto dura ogni disegno, per le partite che iniziano da ora. Auto: 2 minuti in Speedrun e Classica, 3 in Broken Canva.",
        "en": "How long each drawing lasts, for matches started from now on. Auto: 2 minutes in Speedrun and Classic, 3 in Broken Canva."},
    "btn_make_admin": {"it": "👑 Rendimi amministratore", "en": "👑 Make me an admin"},
    "welcome_group": {
        "it": "🎨 Ciao! Sono <b>Carmink</b>: si disegna, gli altri indovinano. Scrivete /newgame per iniziare, /help per le regole.\n\n"
              "Per funzionare al meglio ho bisogno di essere <b>amministratore</b> con il permesso di <b>eliminare i messaggi</b>: "
              "così vedo i tentativi e posso cancellare le risposte esatte prima che le legga qualcuno. Tocca il pulsante e conferma.",
        "en": "🎨 Hi! I'm <b>Carmink</b>: one draws, the others guess. Type /newgame to start, /help for the rules.\n\n"
              "To work at my best I need to be an <b>admin</b> with the permission to <b>delete messages</b>: "
              "that way I can see the guesses and delete correct answers before anyone reads them. Tap the button and confirm."},
    "admin_ok": {"it": "✅ Perfetto, ora ho i permessi che mi servono. Scrivete /newgame!",
                 "en": "✅ Great, I now have the permissions I need. Type /newgame!"},
    "admin_missing": {
        "it": "⚠️ Sono amministratore ma mi manca il permesso di <b>eliminare i messaggi</b>: senza non posso nascondere le risposte esatte.",
        "en": "⚠️ I'm an admin but I'm missing the permission to <b>delete messages</b>: without it I can't hide correct answers."},
    "need_admin_note": {
        "it": "⚠️ Per Speedrun e Classica mi serve essere amministratore con il permesso di eliminare i messaggi: altrimenti le risposte esatte restano visibili e potrei non vedere i tentativi.",
        "en": "⚠️ For Speedrun and Classic I need to be an admin with the permission to delete messages: otherwise correct answers stay visible and I may not see the guesses."},
})
