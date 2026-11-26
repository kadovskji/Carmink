"""Strings of the party modes: Carmeleon and Code Stroke (both beta). Merged into i18n.STRINGS."""
STRINGS: dict[str, dict[str, str]] = {
    "mode_carmeleon": {"it": "🦎 Carmeleon (beta)", "en": "🦎 Carmeleon (beta)"},
    "mode_codestroke": {"it": "🕵️ Code Stroke (beta)", "en": "🕵️ Code Stroke (beta)"},
    "carmeleon_lobby_note": {
        "it": "🦎 Modalità <b>beta</b>. Una volta partita non ci si può più unire. Si gioca nella Mini App e nei pulsanti in chat.",
        "en": "🦎 <b>Beta</b> mode. Nobody can join once it has started. You play in the Mini App and with the buttons in the chat."},
    "codestroke_lobby_note": {
        "it": "🕵️ Modalità <b>beta</b>. Due squadre (pari, o una in più se i giocatori sono dispari). Una volta partita non ci si può più unire.",
        "en": "🕵️ <b>Beta</b> mode. Two teams (equal, or one player more if the number is odd). Nobody can join once it has started."},
    "join_closed_party": {"it": "Questa modalità non permette di entrare a partita avviata.",
                          "en": "This mode doesn't allow joining once the match has started."},
    "set_cmwords": {"it": "Parole Carmeleon", "en": "Carmeleon words"},
    "set_cmwords_15": {"it": "15 parole (5 per categoria)", "en": "15 words (5 per category)"},
    "set_cmwords_21": {"it": "21 parole (7 per categoria)", "en": "21 words (7 per category)"},
    "set_cmwords_30": {"it": "30 parole (10 per categoria)", "en": "30 words (10 per category)"},
    "settings_sub_cmwords": {
        "it": "Quante parole ci sono sulla tabella di Carmeleon (tre categorie diverse), per le partite che iniziano da ora. "
              "Il tempo per disegnare si regola con \"Tempo di disegno\" (Auto: 90 secondi in Carmeleon).",
        "en": "How many words are on the Carmeleon table (three different categories), for matches started from now on. "
              "The drawing time follows \"Drawing time\" (Auto: 90 seconds in Carmeleon)."},
    # ---------------------------------------------------------------- Carmeleon
    "cm_no_words": {"it": "Il dizionario non ha abbastanza parole in tre categorie diverse: partita annullata.",
                    "en": "The dictionary doesn't have enough words in three different categories: match cancelled."},
    "cm_start": {
        "it": "🦎 <b>Carmeleon</b> (beta) — {n} giocatori\n\nLa tabella:\n{table}\n\n"
              "Una di queste parole è la <b>chiave</b>: la conoscono tutti tranne il <b>Camaleonte</b>. "
              "A turno disegnate qualcosa collegato alla chiave, nella Mini App: il Camaleonte deve mimetizzarsi!",
        "en": "🦎 <b>Carmeleon</b> (beta) — {n} players\n\nThe table:\n{table}\n\n"
              "One of these words is the <b>key</b>: everybody knows it except the <b>Chameleon</b>. "
              "Take turns drawing something linked to the key, in the Mini App: the Chameleon has to blend in!"},
    "cm_turn": {"it": "🖌 Giro {lap} — tocca a <b>{name}</b> ({n}/{total}), {secs} secondi.",
                "en": "🖌 Lap {lap} — it's <b>{name}</b>'s turn ({n}/{total}), {secs} seconds."},
    "cm_drawn": {"it": "🖌 <b>{name}</b> (giro {lap})", "en": "🖌 <b>{name}</b> (lap {lap})"},
    "cm_decide": {
        "it": "Tutti hanno disegnato. Un altro giro di disegni (una sola volta) o si vota? Decide la maggioranza, {secs} secondi.",
        "en": "Everybody has drawn. Another lap of drawings (only once) or time to vote? The majority decides, {secs} seconds."},
    "cm_btn_more": {"it": "🔁 Altro giro", "en": "🔁 Another lap"},
    "cm_btn_vote": {"it": "🗳 Votiamo", "en": "🗳 Let's vote"},
    "cm_lap2": {"it": "🔁 Si fa un altro giro!", "en": "🔁 Another lap!"},
    "cm_noted": {"it": "Ricevuto ✅", "en": "Noted ✅"},
    "cm_vote": {
        "it": "🗳 <b>Chi è il Camaleonte?</b> Votate con il pulsante sotto il disegno ({secs} secondi).\n{table}",
        "en": "🗳 <b>Who is the Chameleon?</b> Vote with the button under the drawing ({secs} seconds).\n{table}"},
    "cm_btn_suspect": {"it": "🗳 {name}", "en": "🗳 {name}"},
    "cm_self_vote": {"it": "Non puoi votare te stesso.", "en": "You can't vote for yourself."},
    "cm_voted": {"it": "Hai votato {name} ✅", "en": "You voted {name} ✅"},
    "cm_no_votes": {"it": "Nessun voto.", "en": "No votes."},
    "cm_tie": {"it": "Pareggio: il Camaleonte non è stato scoperto!", "en": "A tie: the Chameleon was not unmasked!"},
    "cm_wrong_suspect": {"it": "{name} è il più votato, ma non è il Camaleonte!", "en": "{name} got the most votes, but is not the Chameleon!"},
    "cm_chameleon_wins": {"it": "🦎 Vince il Camaleonte: <b>{name}</b>!", "en": "🦎 The Chameleon wins: <b>{name}</b>!"},
    "cm_caught": {
        "it": "{votes}\n\n🦎 <b>{name}</b> è il Camaleonte! Ma può ancora vincere: deve indovinare la parola chiave ({secs} secondi). Solo lui può premere.",
        "en": "{votes}\n\n🦎 <b>{name}</b> is the Chameleon! But can still win by naming the key word ({secs} seconds). Only they can press."},
    "cm_only_chameleon": {"it": "Solo il Camaleonte può scegliere.", "en": "Only the Chameleon can choose."},
    "cm_guessed": {"it": "🦎 <b>{name}</b> ha indovinato la parola chiave (<b>{word}</b>) e vince da solo!",
                   "en": "🦎 <b>{name}</b> named the key word (<b>{word}</b>) and wins alone!"},
    "cm_missed": {"it": "🦎 <b>{name}</b> non ha indovinato la chiave (era <b>{word}</b>): vincono gli altri!",
                  "en": "🦎 <b>{name}</b> missed the key word (it was <b>{word}</b>): the others win!"},
    "cm_reveal": {"it": "🔑 Chiave: <b>{word}</b> — 🦎 Camaleonte: <b>{name}</b>", "en": "🔑 Key: <b>{word}</b> — 🦎 Chameleon: <b>{name}</b>"},
    "cm_chameleon_left": {"it": "🦎 Il Camaleonte <b>{name}</b> è scappato: vincono gli altri!",
                          "en": "🦎 The Chameleon <b>{name}</b> ran away: the others win!"},
    "cm_aborted": {"it": "Troppi giocatori hanno lasciato: partita annullata.", "en": "Too many players left: match cancelled."},
    "cm_prompt_key": {"it": "Disegna qualcosa legato a: {word}", "en": "Draw something linked to: {word}"},
    "cm_prompt_chameleon": {"it": "🦎 Sei il Camaleonte! Disegna qualcosa che non ti smascheri", "en": "🦎 You are the Chameleon! Draw something that won't give you away"},
    # ---------------------------------------------------------------- Code Stroke
    "cs_start": {
        "it": "🕵️ <b>Code Stroke</b> (beta)\n\n🔵 Blu (inizia, {nb} parole): {blue}\n🔴 Rossa ({nr} parole): {red}\n\n"
              "Ogni capo spia (🕵️) vede la chiave nella Mini App e dà un indizio disegnando, con un numero. "
              "I compagni toccano le parole della griglia (qui o nella Mini App). Attenti all'assassino ⬛!",
        "en": "🕵️ <b>Code Stroke</b> (beta)\n\n🔵 Blue (starts, {nb} words): {blue}\n🔴 Red ({nr} words): {red}\n\n"
              "Each spy master (🕵️) sees the key in the Mini App and gives a clue by drawing, with a number. "
              "Teammates tap the words of the grid (here or in the Mini App). Beware of the assassin ⬛!"},
    "cs_status_clue": {"it": "{head} disegna l'indizio ({secs} secondi).\n{score}", "en": "{head} is drawing the clue ({secs} seconds).\n{score}"},
    "cs_status_guess": {"it": "{head} — indizio: <b>{n}</b>, tentativi rimasti: {left}\n{score}\nLa squadra tocca le parole.",
                        "en": "{head} — clue: <b>{n}</b>, guesses left: {left}\n{score}\nThe team taps the words."},
    "cs_turn_over": {"it": "Turno concluso. {score}", "en": "Turn over. {score}"},
    "cs_btn_pass": {"it": "⏭ Passa", "en": "⏭ Pass"},
    "cs_clue": {"it": "{icon} Indizio di <b>{name}</b>: <b>{n}</b>", "en": "{icon} Clue by <b>{name}</b>: <b>{n}</b>"},
    "cs_no_clue": {"it": "⏱ {name} non ha dato l'indizio: tocca all'altra squadra.", "en": "⏱ {name} gave no clue: the other team plays."},
    "cs_time_up": {"it": "⏱ {icon} Tempo scaduto: tocca all'altra squadra.", "en": "⏱ {icon} Time's up: the other team plays."},
    "cs_wait_clue": {"it": "Aspetta l'indizio del capo spia.", "en": "Wait for the spy master's clue."},
    "cs_not_your_turn": {"it": "Non tocca alla tua squadra.", "en": "It's not your team's turn."},
    "cs_spy_no_pick": {"it": "Il capo spia non sceglie le parole.", "en": "The spy master doesn't pick words."},
    "cs_taken": {"it": "Parola già scoperta.", "en": "Word already revealed."},
    "cs_pick_one": {"it": "Scegli almeno una parola.", "en": "Pick at least one word."},
    "cs_passed": {"it": "{icon} {name} passa il turno.", "en": "{icon} {name} passes."},
    "cs_wrong_word": {"it": "❌ Parola sbagliata: il turno passa.", "en": "❌ Wrong word: the turn passes."},
    "cs_no_more": {"it": "Tentativi finiti: il turno passa.", "en": "No guesses left: the turn passes."},
    "cs_assassin": {"it": "💀 {name} ha toccato <b>{word}</b>: è l'assassino!", "en": "💀 {name} touched <b>{word}</b>: it's the assassin!"},
    "cs_over": {"it": "🏁 Vince la squadra {icon}: {names}", "en": "🏁 Team {icon} wins: {names}"},
    "cs_aborted": {"it": "Un capo spia (o troppi giocatori) ha lasciato: partita annullata.", "en": "A spy master (or too many players) left: match cancelled."},
    "cs_prompt": {"it": "{icon} Disegna l'indizio e scegli il numero", "en": "{icon} Draw the clue and pick the number"},
}
