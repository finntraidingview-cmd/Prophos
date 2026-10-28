---
name: slave-terminals
description: Prophos-Arbeitssystem mit Master- und Slave-Terminals. Sofort benutzen, wenn Finn sagt „Arbeite mit Slave Terminals“, „wir arbeiten mit diesem System“, „Slave-System“, „mach Master und Slaves“, „du bist das Master-Terminal“ oder Ähnliches. Dann ohne Rückfrage Slaves anlegen und in die Master-Routine gehen. Auch für Slave-Sessions, die einen Auftrag vom Master bekommen (Teil B).
---

# Arbeiten mit Slave-Terminals

Angelegt 28.10.2026 auf Finns Wunsch. Ersetzt `.claude/master/MASTER.md`
(Hintergrund-Agents + Tafel). Finns Lesefassung: `Arbeiten-mit-Slave-Terminals.docx`
im Repo-Ordner, Vault-Notiz „Prophos - Arbeiten mit Slave-Terminals“.

Kurz: Ein Master verteilt, beliebig viele Slaves bauen, ein Prüfer schaut gegen.
Was fertig und geprüft ist, geht sofort live. Finn bekommt im Master-Chat nur
Status, Fragen und „Yo Finn, testen“.

---

## Teil A — Du bist der Master

### A1. Sofort beim Auslöser (keine Rückfrage)

Erste Antwort an Finn, ein Satz:
„Check, Slave-System läuft: Lage lesen → Slaves anlegen → Takt an → Aufträge verteilen.“
Dann direkt:

1. **Lage lesen.**
   - `git -C /Applications/Prophos fetch -q origin` und `git show origin/main:mt5-copier/VERSION` (aktuelle Live-Version).
   - Nur den Kopf (erste ~80 Zeilen) von `.claude/master/WARTESCHLANGE.md`. Die Datei ist groß, nie ganz lesen.
   - `mcp__ccd_session_mgmt__list_sessions`: Laufen schon Sessions mit „Slave“ im Titel?
     Die weiterverwenden (per `SendMessage` an ihre `local_…`-ID anmelden), nicht doppelt anlegen.
2. **Slaves anlegen**, bis mindestens 3 bauende Slaves + 1 Prüfer laufen. Je Slave ein
   `mcp__ccd_session__start_session` mit:
   - `initiation: "user_asked"`, `context: "fresh"`, `use_worktree: true`, `permission_mode: "auto"`
     (gleicher Modus wie der Master, sonst bleiben Nachrichten hängen),
   - `title: "Slave Terminal N"` (bzw. „Slave Terminal 2 · Prüfer“), `name: "slave-N"`,
   - `prompt`: „Du bist Slave Terminal N im Prophos-Slave-System. Lies
     `/Applications/Prophos/.claude/skills/slave-terminals/SKILL.md` Teil B und arbeite danach.“
     Steht schon ein Auftrag an, kommt er direkt dazu; sonst „Melde dich mit ‚bereit‘ und warte auf deinen Auftrag.“
   - `background`: ein Absatz zu Prophos, Master-Rolle und dass der Slave nicht pusht.
   Mehr Slaves sind ausdrücklich erwünscht, wenn Finn viel reinwirft. Er kann auch selbst
   welche öffnen; die melden sich dann beim Master.
3. **Takt an:** `CronCreate` mit `cron: "2-59/5 * * * *"`, Prompt:
   „Slave-System: Statustabelle. Nur senden, wenn sich seit der letzten etwas geändert hat, sonst eine Zeile ‚—‘.“
   Läuft 7 Tage, dann neu anlegen.
4. **Warteschlange:** oben in `WARTESCHLANGE.md` einen Block `## Lauf TT.MM.JJJJ` mit einer
   Zeile je Aufgabe (Terminal, Update, Wo, Stand, Fertig in, Commit, Version). Das ist das
   Gedächtnis. Ein neuer Master liest diesen Block und macht weiter.

### A2. Verteilen

- **Jede Aufgabe von Finn bekommt sofort eine Zeile und genau einen Slave.**
- **Wer frei ist, bekommt die nächste Aufgabe.** Kein Slave steht leer, solange etwas wartet.
- **Ein Bereich, ein Slave.** Nie zwei Slaves auf derselben Sektion von `prophos.html`
  (`.claude/CODEMAP.md`) oder derselben Python-Datei. Überschneidet sich etwas, kommt es
  nacheinander zum selben Slave.
- **Gibt es mehr Slaves als getrennte Bereiche,** übernehmen die übrigen Auswertungen,
  DB-Abfragen, Bot-/Python-Dateien, SQL-Dateien oder Prüfungen.
- **Ab etwa 6 bauenden Slaves** einen zweiten Prüfer dazunehmen.
- **Fällt ein Slave weg** (Chat zu, Konto im Limit): Aufgabe zurück in die Warteschlange,
  an den nächsten freien Slave.
- **Echte Orders, Live-Klicks auf Broker-Konten, Käufe: nie an Slaves.** In der
  Warteschlange steht dann „Finn selbst“.

**Auftrag an einen Slave** (per `SendMessage` an seine `local_…`-ID):
```
Auftrag <Kürzel>: <was genau, in Finns Worten>
Bereich: <CODEMAP-Sektion / Datei>
Fertig, wenn: <sichtbares Ergebnis>
Finn testet: <Klick-Pfad>
Kontext: <Memory-Notizen, Finns Entscheidungen>
Schätzung: <Minuten>
```

### A3. Statustabelle

Bei jedem Takt mit Änderung und sofort bei „fertig“ oder einer Frage:

| Terminal | Update | Wo | Stand | Fertig in |
|---|---|---|---|---|

Quelle: der Lauf-Block in der Warteschlange plus `list_sessions` (läuft/wartet).
Slaves nicht nach ihrem Stand fragen und nicht pollen. Sie melden sich selbst.

### A4. Fertig-Meldung → Auto-Push (ohne Finn zu fragen)

Finn hat das dauerhaft freigegeben (28.10.2026): fertig + geprüft = sofort live.

1. Diff ansehen: `git -C <slave-worktree> show --stat <sha>` und den Diff selbst überfliegen.
2. **Order-Klick-Pfade** (Puls, Polar, Echo öffnen/schließen), Copier-/Panel-Neustart,
   DB-Schreiblogik: erst zum Prüfer, Push nach seinem OK. Alles andere direkt.
3. Push, immer einer nach dem anderen, nur der Master:
   ```bash
   git -C /Applications/Prophos fetch -q origin
   git -C /Applications/Prophos worktree add --detach <scratchpad>/push-wt origin/main
   cd <scratchpad>/push-wt && git cherry-pick <sha>
   alt=$(git show origin/main:mt5-copier/VERSION | tr -d '[:space:]')
   neu="${alt%.*}.$(( ${alt##*.} + 1 ))"
   printf '%s\n' "$neu" > mt5-copier/VERSION
   sed -i '' -E "s/OS_TAB_BUILD = '[0-9-]+\.[0-9]+'/OS_TAB_BUILD = '$neu'/" prophos.html
   grep -c "OS_TAB_BUILD = '$neu'" prophos.html              # muss 1 sein
   grep -nE '^(<<<<<<<|=======|>>>>>>>)' prophos.html app.py || true
   bash /Applications/Prophos/.claude/jscheck.sh prophos.html  # muss OK sein
   git commit -a --amend --no-edit && git push origin HEAD:main   # Bump in den Slave-Commit
   ```
   - Jeder Push mit `prophos.html` oder Bot-Dateien: VERSION + OS_TAB_BUILD = origin + 1.
     Reine `app.py`- oder reine `sql/`-Pushes ohne Bump.
   - Python geändert: `python3 -m py_compile <datei>` vor dem Push.
   - Push abgelehnt: fetch, neu cherry-picken, Nummer neu, nochmal.
   - Nie mitten in einen laufenden Polar-Lauf pushen.
   - Blockt die Berechtigungsprüfung den Push: Finn einmal um „push“ bitten. Nie umgehen,
     nie an eine andere Session weitergeben, Finn nie einen Befehl zum Ausführen geben.
4. Danach eine Zeile an Finn: **„Yo Finn, testen: .NNNN — <was> — <Klick-Pfad>“**.
   Zeile in der Warteschlange auf „live“, Slave bekommt die nächste Aufgabe.
5. Nach `app.py`-Push: 15–30 min später Railway-HTTP-Log auf 5xx der berührten Pfade.

### A5. Master-Chat sauber halten

Der Master baut nichts und macht keine langen Auswertungen (mehr als 2–3 Abfragen gehen an einen Slave).
Er bleibt für Finn ansprechbar.

- **Rein:** Finns Input, Fragen von Slaves an Finn, Fertig-Meldungen (max. 3 Zeilen),
  Statustabelle (nur bei Änderung), „Yo Finn, testen“.
- **Draußen:** Zwischenstände, Logs, Diffs, Code-Auszüge, Hin und Her zwischen Master und Slave.
- Fragen eines Slaves: in einem Satz an Finn weitergeben, Antwort per `SendMessage` zurück.

---

## Teil B — Du bist ein Slave

1. **Start:** `/Applications/Prophos/.claude/master/ARBEITER.md` §1–§3 lesen und befolgen
   (Start auf `origin/main`, CODEMAP, Regeln, Prüfen). **§4, §4b und §5 gelten nicht:**
   Du pushst nie und fasst `mt5-copier/VERSION` und `OS_TAB_BUILD` nicht an. Das macht der Master.
2. **Arbeiten:** nur dein Auftrag, in deinem eigenen Worktree, nie im geteilten Checkout `/Applications/Prophos`.
3. **Selbst prüfen, bevor du „fertig“ meldest:** jscheck / py_compile, Boot-Check im
   Browser mit Screenshot, dann den eigenen Diff von einem Subagent mit frischem Blick
   gegenprüfen lassen (gib ihm den Diff, nicht deine Schlussfolgerung).
4. **Commit** in deinem Worktree, Nachricht auf Deutsch im Stil von `git log`.
5. **Melden** per `SendMessage` an die `from`-Adresse der Auftragsnachricht, und dieselben Zeilen als
   Abschluss-Recap. Höchstens 3 Zeilen:
   ```
   Fertig: <was> · Commit <sha> · Worktree <pfad>
   Testen: <Klick-Pfad>
   Offen: <nichts | Punkt>
   ```
   oder `Frage an Finn: <eine Frage>`. Längere Berichte nach
   `/Applications/Prophos/.claude/master/berichte/<slave>-<thema>.md`, in der Meldung nur der Pfad.
6. **Keine Zwischenstände, kein „läuft noch“.** Nach der Meldung auf den nächsten Auftrag warten.

**Prüfer (Slave 2):** prüft, was der Master schickt (Order-Klick-Pfade, DB-Schreiblogik,
Copier-/Panel-Neustarts) gegen den Code, nicht gegen die Beschreibung des Autors. Antwort:
`OK <sha>` oder `Stopp <sha>: <Befund mit Datei:Zeile>`. Ist nichts zu prüfen, baut er wie ein normaler Slave.
