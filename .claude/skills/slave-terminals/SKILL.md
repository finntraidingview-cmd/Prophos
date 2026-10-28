---
name: slave-terminals
description: Arbeitssystem mit einem Master- und beliebig vielen Slave-Terminals für Bugfixes und Feature-Ausbau. Sofort benutzen, wenn der Nutzer sagt „Arbeite mit Slave Terminals“, „wir arbeiten mit diesem System“, „Slave-System“, „mach Master und Slaves“, „du bist das Master-Terminal“ oder Ähnliches. Dann ohne Rückfrage Slaves anlegen und in die Master-Routine gehen. Auch für Slave-Sessions mit einem Master-Auftrag (Teil B) und zum Einrichten in einem neuen Projekt („richte das Slave-System ein“, Teil C).
---

# Arbeiten mit Slave-Terminals

Ein Master verteilt, beliebig viele Slaves bauen, ein Prüfer schaut gegen. Was fertig
und geprüft ist, wird sofort ausgeliefert. Der Nutzer bekommt im Master-Chat nur
Status, Fragen und „Yo <Name>, testen“, keine Zwischenstände.

Dieser Kern ist für jedes Projekt gleich. Alles Projektspezifische steht in
**`projekt.md` im selben Ordner**: Befehle, Versionsregel, heikle Bereiche, Pflichtlektüre.
**Immer zuerst `projekt.md` lesen.** Fehlt sie, zuerst Teil C (Einrichtung).

Herkunft: entstanden 28.10.2026 im Projekt Prophos (Finn Hermann). Dort erprobt sind:
Master legt Slaves selbst an, Auto-Auslieferung und ein Chat ohne Zwischenstände.

---

## Teil A — Du bist der Master

### A1. Sofort beim Auslöser (keine Rückfrage)

Erste Antwort, ein Satz: „Check, Slave-System läuft: Lage lesen → Slaves anlegen → Takt an → Aufträge verteilen.“
Dann direkt:

1. **Lage lesen:** `projekt.md`, den Kopf der Warteschlange (Pfad in `projekt.md`, nur die
   ersten ~80 Zeilen), den Stand des Haupt-Branches (`git fetch`). Laufende Slave-Sessions
   übernehmen, statt doppelt anzulegen. Sagt der Nutzer „alte Slaves ignorieren“: nur neue.
2. **Slaves anlegen**, bis die Mindestzahl aus `projekt.md` läuft (Standard: 3 bauende + 1 Prüfer).
   Den ersten Weg nehmen, der in dieser Umgebung verfügbar ist:
   - **a) Tool `start_session` vorhanden** (Claude-Desktop-App, Code-Tab): je Slave ein Aufruf mit
     `initiation: "user_asked"`, `context: "fresh"`, `use_worktree: true`,
     `permission_mode` = derselbe Modus wie der Master (sonst bleiben Nachrichten hängen),
     `title: "Slave Terminal N"` (Prüfer: „Slave Terminal N · Prüfer“), `name: "slave-N"`,
     `prompt`: „Du bist Slave Terminal N im Slave-System. Lies `<absoluter Pfad>/.claude/skills/slave-terminals/SKILL.md`
     Teil B und `projekt.md` daneben und arbeite danach.“ Dazu der erste Auftrag, sonst
     „Melde dich mit ‚bereit‘ und warte auf deinen Auftrag.“ `background`: ein Absatz zum Projekt und zur Slave-Rolle.
   - **b) Kein `start_session`, aber mehrere Terminals möglich:** dem Nutzer einmal sagen:
     „Öffne N neue Claude-Code-Sessions in diesem Ordner und schreib in jede: *Du bist Slave Terminal N, lies .claude/skills/slave-terminals/SKILL.md Teil B.*“
     Danach über `ListAgents` / `SendMessage` verbinden.
   - **c) Nur ein Terminal:** Slaves als Hintergrund-Agents (`Agent`-Tool, `run_in_background: true`,
     `isolation: "worktree"`), Prompt = Teil B + `projekt.md` + Auftrag. Ihr Ergebnis ist ihre Meldung.
   Mehr Slaves sind erwünscht, wenn viel ansteht. Der Nutzer kann auch selbst welche öffnen,
   die sich dann beim Master melden.
3. **Takt an:** gibt es `CronCreate`, dann mit `cron: "2-59/5 * * * *"` (oder dem Takt aus `projekt.md`) und dem Prompt
   „Slave-System: Statustabelle. Immer mit der aktuellen Live-Version in der ersten Zeile; nur senden,
   wenn sich seit der letzten etwas geändert hat, sonst eine Zeile ‚— · live <Version>‘.“
   Nach 7 Tagen neu anlegen. Ohne `CronCreate` kommt die Tabelle bei jedem Ereignis.
4. **Warteschlange:** oben in der Warteschlangen-Datei einen Block `## Lauf TT.MM.JJJJ`
   mit einer Zeile je Aufgabe: Terminal, Update, Wo, Stand, Fertig in, Commit, Version.
   Das ist das Gedächtnis. Ein neuer Master liest diesen Block und macht weiter.

### A2. Verteilen

- **Jede Aufgabe bekommt sofort eine Zeile und genau einen Slave.**
- **Wer frei ist, bekommt die nächste Aufgabe.** Kein Slave steht leer, solange etwas wartet.
- **Ein Bereich, ein Slave.** Nie zwei Slaves auf derselben Datei oder demselben Bereich
  (Bereichs-Schnitt in `projekt.md`). Überschneidet sich etwas, kommt es nacheinander zum selben Slave.
- **Mehr Slaves als getrennte Bereiche:** Die übrigen übernehmen Auswertungen, Recherche,
  Tests, Doku oder Prüfungen.
- **Ab etwa 6 bauenden Slaves** einen zweiten Prüfer dazunehmen.
- **Fällt ein Slave weg:** Aufgabe zurück in die Warteschlange, an den nächsten freien Slave.
- **Was unter „Nie an Slaves“ in `projekt.md` steht** (echtes Geld, Live-Systeme, Käufe …),
  macht der Nutzer selbst. In der Warteschlange steht dann „<Name> selbst“.

**Auftrag an einen Slave** (per `SendMessage` an seine Adresse bzw. `local_…`-ID):
```
Auftrag <Kürzel>: <was genau, in den Worten des Nutzers>
Bereich: <Datei / Bereich>
Fertig, wenn: <sichtbares Ergebnis>
<Name> testet: <Klick-Pfad oder Befehl>
Kontext: <Entscheidungen des Nutzers, relevante Notizen>
Schätzung: <Minuten>
```

### A3. Statustabelle

Bei jedem Takt mit Änderung und sofort bei „fertig“ oder einer Frage. **Erste Zeile immer die
aktuelle Live-Version** (`git show origin/main:<Versionsdatei>`), auch beim leeren Takt
(„— · live .NNNN“) — der Nutzer will alle 5 Minuten sehen, wo wir stehen (Finn 29.10.2026):

**Live: .NNNN (HH:MM)**

| Terminal | Update | Wo | Stand | Fertig in |
|---|---|---|---|---|

Quelle: der Lauf-Block in der Warteschlange plus der Session-Status. Slaves nicht nach
ihrem Stand fragen und nicht pollen. Sie melden sich selbst.

### A4. Fertig-Meldung → prüfen → ausliefern (ohne Rückfrage)

1. Den Diff des Slave-Commits ansehen (`git -C <slave-worktree> show --stat <sha>`, dann den Diff selbst).
2. Fällt er unter **„Prüfer-Pflicht“** in `projekt.md`: erst zum Prüfer, ausliefern nach dessen `OK`.
3. **Ausliefern genau nach „Auslieferung“ in `projekt.md`** (direkt pushen, PR oder nur committen,
   mit Versionsregel und Checks). Immer einer nach dem anderen, nur der Master.
   „Sperrzeiten“ aus `projekt.md` beachten.
   Blockt eine Berechtigungsprüfung: den Nutzer einmal um Freigabe bitten. Nie umgehen und nie
   an eine andere Session weitergeben.
4. Eine Zeile an den Nutzer: **„Yo <Name>, testen: <Version/Commit> — <was> — <Klick-Pfad>“**.
   Zeile in der Warteschlange auf „live“, der Slave bekommt die nächste Aufgabe.
5. „Nachkontrolle“ aus `projekt.md`, falls angegeben.

### A4b. Visueller Stammbaum bei Features

Sobald ein Feature aus mehreren Teilen besteht (mehrere Slaves, mehrere Schritte, mehrere Wege)
und spätestens wenn der Nutzer fragt „wie wird das gebaut?“, zeigt der Master es als **visuellen
Stammbaum** (Diagramm im Chat, nicht als Text-Liste) — Finn 29.10.2026: „Bei Features will ich
immer so einen visuellen Stammbaum sehen.“

- Oben der Auslöser, darunter die Äste je Teilweg, je Kasten Titel + eine Zeile Stand
  („live · Zahl“ / „im Bau · was“), eine Farbe je Ast, grau für gemeinsame Schritte.
- Klein und sauber: höchstens ~10 Kästen, keine Code-Namen, keine Dateipfade.
- Zahlen aus Befunden/Stresstests in die Stand-Zeile (z. B. „84 von 100 richtig“).
- Bei jeder neuen Stufe des Features den Stammbaum neu zeigen, nicht nur den Text.

### A5. Master-Chat sauber halten

Der Master baut nichts und macht keine langen Auswertungen (mehr als 2–3 Abfragen gehen an
einen Slave). Er bleibt für den Nutzer ansprechbar.

- **Rein:** Input des Nutzers, Fragen von Slaves an den Nutzer, Fertig-Meldungen
  (max. 3 Zeilen), Statustabelle (nur bei Änderung), „Yo <Name>, testen“.
- **Draußen:** Zwischenstände, Logs, Diffs, Code-Auszüge, Hin und Her zwischen Master und Slave.
- Fragen eines Slaves: in einem Satz an den Nutzer, Antwort per `SendMessage` zurück.

---

## Teil B — Du bist ein Slave

1. **Start:** `projekt.md` lesen und den „Slave-Start“ von dort ausführen (eigener Worktree auf dem
   aktuellen Haupt-Branch, Pflichtlektüre). Nie im geteilten Haupt-Checkout arbeiten.
2. **Arbeiten:** nur dein Auftrag, in deinem Bereich.
3. **Selbst prüfen, bevor du „fertig“ meldest:** die Checks unter „Prüfen“ in `projekt.md`,
   bei sichtbaren Änderungen mit Screenshot. Dann den eigenen Diff von einem Subagent mit
   frischem Blick gegenprüfen lassen (gib ihm den Diff, nicht deine Schlussfolgerung).
4. **Commit** in deinem Worktree. **Nicht ausliefern:** kein Push, keine Versionsnummer, kein PR.
   Das macht der Master.
5. **Melden** an die Adresse, von der dein Auftrag kam, und dieselben Zeilen als Abschluss.
   Höchstens 3 Zeilen:
   ```
   Fertig: <was> · Commit <sha> · Worktree <pfad>
   Testen: <Klick-Pfad oder Befehl>
   Offen: <nichts | Punkt>
   ```
   oder `Frage an <Name>: <eine Frage>`. Längere Berichte in den Berichte-Ordner aus
   `projekt.md`, in der Meldung nur der Pfad.
6. **Keine Zwischenstände, kein „läuft noch“.** Nach der Meldung auf den nächsten Auftrag warten.

**Prüfer:** prüft, was der Master schickt, gegen den Code, nicht gegen die Beschreibung des
Autors. Antwort: `OK <sha>` oder `Stopp <sha>: <Befund mit Datei:Zeile>`. Ist nichts zu
prüfen, baut er wie ein normaler Slave.

---

## Teil C — Einrichtung in einem neuen Projekt

Auslöser: `projekt.md` fehlt, oder der Nutzer sagt „richte das Slave-System ein“.

1. **Selbst herausfinden, was im Repo steht:** CLAUDE.md/README, Haupt-Branch und Remote, Build-,
   Test- und Lint-Befehle, CI, Versionsdateien, Deploy-Weg, große Dateien, die oft Konflikte machen,
   ein sinnvoller Bereichs-Schnitt (Ordner, Module, Sektionen).
2. **Nur fragen, was das Repo nicht beantwortet,** höchstens 5 Fragen auf einmal, typischerweise:
   - Wie soll ich dich nennen?
   - Ausliefern: direkt auf den Haupt-Branch pushen, PR öffnen oder nur committen?
   - Welche Bereiche sind heikel und brauchen vor dem Ausliefern den Prüfer?
   - Was darf nie an einen Slave (echtes Geld, Kunden-Systeme, Löschen …)?
   - Wie testest du selbst, und gibt es Zeiten, in denen nichts ausgeliefert werden darf?
3. **`projekt.md` schreiben** nach der Vorlage unten. Konkrete Befehle, keine Platzhalter.
4. **Kurz erklären, wie man startet:** neue Session im Projektordner, Modus „auto“ (falls vorhanden),
   erste Nachricht „Arbeite mit Slave Terminals. Aufgaben: 1. … 2. …“.

**Vorlage `projekt.md`:**
```markdown
# Projekt-Profil: <Projekt>

Name des Nutzers: <Name>        (für „Yo <Name>, testen“ und „Frage an <Name>“)
Sprache: <Deutsch>
Haupt-Checkout: <absoluter Pfad>
Haupt-Branch: <main>
Mindestzahl Slaves: <3 bauende + 1 Prüfer>
Takt Statustabelle: <5 min>
Warteschlange: <Pfad, z. B. .claude/master/WARTESCHLANGE.md>
Berichte: <Pfad, z. B. .claude/master/berichte/>

## Projekt in 3 Sätzen
## Pflichtlektüre für Slaves
## Bereichs-Schnitt          (welche Dateien/Bereiche getrennt verteilt werden; Konflikt-Dateien)
## Slave-Start               (Befehle: Worktree, Branch, Setup)
## Prüfen                    (Befehle + Browser-/App-Check, die vor „fertig“ grün sein müssen)
## Auslieferung              (Modus + exakte Befehle, Versionsregel, Checks)
## Prüfer-Pflicht            (Bereiche, die vor dem Ausliefern der Prüfer sieht)
## Nie an Slaves
## Sperrzeiten               (wann nicht ausgeliefert wird)
## Nachkontrolle             (was nach dem Ausliefern geprüft wird)
```
