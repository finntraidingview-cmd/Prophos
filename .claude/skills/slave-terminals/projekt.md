# Projekt-Profil: Prophos

Name des Nutzers: Finn        (für „Yo Finn, testen“ und „Frage an Finn“)
Sprache: Deutsch, Kommentare im Code auf Deutsch (warum, mit Datum und Anlass)
Haupt-Checkout: /Applications/Prophos (hängt weit hinter origin. Dort nie committen, nur Regeln, Skripte und sql/-Dateien ablegen)
Haupt-Branch: main (origin/main = live)
Mindestzahl Slaves: 3 bauende + 1 Prüfer (Slave Terminal 2 = Prüfer)
Takt Statustabelle: 5 min
Warteschlange: /Applications/Prophos/.claude/master/WARTESCHLANGE.md (groß, nur den Kopf lesen)
Berichte: /Applications/Prophos/.claude/master/berichte/

## Projekt in 3 Sätzen
Prophos ist Finns Trading-Infrastruktur: Prop-Firm-Konten verwalten, Trades zwischen Plattformen spiegeln
und auslösen (Puls = Order-Bot, Echo = MT5-Copier, Orbit/Polar = Futures-Wege) und Finanzen tracken.
Frontend ist eine einzige Datei `prophos.html` (~20.000 Zeilen, Cloudflare Pages), das Backend `app.py`
(Flask auf Railway), Daten liegen in Supabase (`gxhkannmzpyuepxlepta`). Jeder Push mit Frontend oder Bot lädt
die PC-Tabs auf allen Windows-PCs neu, die echte Orders klicken.

## Pflichtlektüre für Slaves
- `/Applications/Prophos/CLAUDE.md` (Projektregeln)
- `.claude/CODEMAP.md` in der eigenen Kopie, bevor `prophos.html` angefasst wird. `prophos.html` nie am Stück lesen,
  nur den Zeilenbereich aus dem CODEMAP.
- `/Applications/Prophos/.claude/master/ARBEITER.md` §1–§3 (Start, Arbeiten, Prüfen).
  **§4, §4b und §5 gelten nicht:** Slaves pushen nie und fassen `mt5-copier/VERSION` und `OS_TAB_BUILD` nicht an.
- Die Memory-Notizen, die der Auftrag nennt: `/Users/finnhermann/.claude/projects/-Applications-Prophos/memory/<name>.md`

## Bereichs-Schnitt
- `prophos.html`: je Sektion aus `.claude/CODEMAP.md` ein Slave. Nie zwei Slaves in derselben Sektion.
- Python: je Datei ein Slave (`app.py`, `mt5-copier/*.py`, `order-bot/*`, `topstep-agent/*`).
- `sql/`: jede Änderung als eigene Datei `sql/JJJJ-MM-TT_thema.sql`. Konfliktfrei, kann jeder Slave.
- Konflikt-Dateien: `mt5-copier/VERSION` und `OS_TAB_BUILD` in `prophos.html` setzt nur der Master beim Ausliefern.

## Slave-Start
Bei `start_session` mit `use_worktree: true` liegt der Worktree schon da. Sonst selbst einen anlegen:
```bash
git -C /Applications/Prophos worktree add --detach /Applications/Prophos/.claude/worktrees/slave-N origin/main
```
Dann im eigenen Worktree:
```bash
git fetch -q origin
git switch --detach origin/main        # vom echten Live-Stand starten, nicht vom alten lokalen main
mkdir -p .claude && cp /Applications/Prophos/.claude/codemap.sh .claude/ && bash .claude/codemap.sh
```

## Prüfen
- JS in `prophos.html` geändert: `bash /Applications/Prophos/.claude/jscheck.sh prophos.html` muss `OK` liefern (sonst Exit 1).
- Python geändert: `python3 -m py_compile <datei>`.
- Frontend geändert: Boot-Check im Browser. `preview_start` mit `{name: "worktrees"}` (ein gemeinsamer Server
  für alle Kopien, Port 5400), dann einen EIGENEN Tab (`tabs_create`) auf
  `http://localhost:5400/<basename des Worktrees>/prophos.html`. `read_console_messages` muss frei von SyntaxError sein.
  Die berührten Pfade durchklicken, Screenshot machen, eigenen Tab am Ende schließen.
- Stub-/Vorschau-Seiten gegen die Live-DB: auch Realtime abfangen (`supabase.channel`), nicht nur REST.
  Offene Realtime-Abos zählen aufs Supabase-Kontingent (Ausfall 30.09.2026).

## Auslieferung
Modus: **direkt auf main pushen, ohne Rückfrage** (Finn, dauerhaft freigegeben am 28.10.2026). Nur der Master,
immer einer nach dem anderen:
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
git -C /Applications/Prophos worktree remove <scratchpad>/push-wt
```
- Versionsregel: Jeder Push mit `prophos.html` oder Bot-Dateien bekommt VERSION + OS_TAB_BUILD = origin + 1
  (sonst laden die PC-Tabs nie neu). Reine `app.py`-, `sql/`- oder `.claude/`-Pushes gehen ohne Bump.
- Python geändert: `python3 -m py_compile <datei>` vor dem Push.
- Push abgelehnt (jemand war schneller): fetch, neu cherry-picken, Nummer neu setzen, alle Checks, nochmal.
- Blockt die Berechtigungsprüfung den Push: Finn einmal um „push“ im Chat bitten. Finn nie einen
  Push-Befehl zum Selbst-Ausführen geben, nie an eine andere Session weiterreichen.
- Danach: „Yo Finn, testen: .NNNN — <was> — <Klick-Pfad>“, Version frisch aus origin nennen.
- SQL-Dateien gegen die Live-DB nur auf Finns Wort ausführen (DDL per `apply_migration`, DML per `execute_sql`).

## Prüfer-Pflicht
Vor dem Ausliefern sieht der Prüfer:
- Order-Klick-Pfade: Puls, Polar, Echo (Öffnen und Schließen, TP/SL setzen)
- alles, was Copier oder Panel auf den PCs neu startet (`app.py`, `panel.py`, `provision.py`, `copier.py`)
- DB-Schreiblogik (Trigger, Planer, Auto-Bestätigen, Abhaken)
Kleine Lese- und Anzeige-Fixes ohne diese Pfade gehen direkt raus.

## Nie an Slaves
- echte Orders auslösen, Live-Klicks auf Broker- oder Trading-Konten, Käufe
- Permission-, Settings- oder CLAUDE.md-Dateien ändern
In der Warteschlange steht dann „Finn selbst“.

## Sperrzeiten
- Nie mitten in einen laufenden Polar-Lauf pushen (`polar_lauf` aktiv).
- Sonst keine Startfenster abwarten (alte §4/§4b-Sperren seit 16.10.2026 aufgehoben).

## Nachkontrolle
- Nach einem `app.py`-Push: 15–30 min später das Railway-HTTP-Log auf 5xx der berührten Pfade ansehen
  (Railway-MCP `get-logs`, types `["http"]`, filter `@status:500`). Ein neuer 500er auf einem berührten Pfad = sofort fixen.
- Nach einem Frontend-Push: PC-Tabs zeigen die neue Version unten (~20 s Bot, Neulade-Wächter).
