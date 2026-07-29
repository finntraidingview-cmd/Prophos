# Windows-Einrichtung pro PC — einmal machen, danach läuft es allein

Ziel: Der Agent startet automatisch beim Hochfahren des PCs und startet sich nach einem
Absturz selbst neu. Du musst nie manuell etwas starten.

## Schritt 1 — Python installieren (einmal pro PC)
1. python.org → Downloads → Windows → Python 3.12 herunterladen.
2. Beim Installieren **„Add python.exe to PATH" ankreuzen** (wichtig, sonst findet die
   .bat-Datei Python nicht).
3. Prüfen: Eingabeaufforderung öffnen, `python --version` → muss eine Version anzeigen.

## Schritt 2 — Ordner auf den PC kopieren
Den kompletten Ordner `topstep-agent` auf den PC legen, z.B. nach `C:\topstep-agent`.

## Schritt 3 — Abhängigkeiten installieren
Eingabeaufforderung im Ordner öffnen (Ordner öffnen → in die Adressleiste `cmd` tippen →
Enter), dann:

    pip install -r requirements.txt

## Schritt 4 — config.json anlegen
`config.example.json` kopieren, umbenennen in `config.json`, mit einem Texteditor öffnen
und ausfüllen:
- `agent_id`: eindeutiger Name für DIESEN PC, z.B. `moritz-pc`
- `supabase_key`: dein Supabase-Key
- `accounts`: unter dem `pair_id` die drei Werte dieser Person (TopstepX-Username,
  ProjectX-API-Key, MetaApi-Token)

Diese Datei bleibt auf dem PC. Sie geht nie nach Supabase und nie in git.

## Schritt 5 — Testlauf per Doppelklick
`start-agent.bat` doppelklicken. Es öffnet sich ein schwarzes Fenster mit Log-Zeilen.
So sieht der Agent aus — es gibt keine Oberfläche, nur diese Zeilen.
- Läuft alles: du siehst `Topstep-Agent gestartet · agent_id=...` und danach alle paar
  Sekunden Ruhe (bzw. Mirror-Logs, sobald eine Steuerzeile aktiv ist).
- Fehler: die Zeile steht direkt im Fenster (z.B. fehlende config, falscher Key).
Fenster einfach **minimieren** — nicht schließen. Schließen = Agent aus.

## Schritt 6 — Autostart einrichten (damit du nie wieder starten musst)
Windows-Aufgabenplanung („Task Scheduler"):
1. Startmenü → „Aufgabenplanung" öffnen.
2. Rechts auf **„Aufgabe erstellen…"** (nicht „Einfache Aufgabe").
3. Reiter **Allgemein**: Name z.B. `Topstep-Agent`.
   - „Unabhängig von der Benutzeranmeldung ausführen" **nicht** wählen — der Agent soll
     im angemeldeten Benutzer laufen (einfacher, du siehst das Fenster).
   - „Mit höchsten Privilegien ausführen" ankreuzen.
4. Reiter **Trigger** → „Neu…" → „Beim Start" (oder „Bei Anmeldung"). OK.
5. Reiter **Aktionen** → „Neu…" → Programm/Skript:
   `C:\topstep-agent\start-agent.bat`
   („Starten in" auf `C:\topstep-agent` setzen.)
6. Reiter **Einstellungen**:
   - „Aufgabe neu starten, falls Fehler" ankreuzen, alle **1 Minute**, bis zu **99** Mal.
   - „Aufgabe beenden, falls länger ausgeführt als" **abwählen** (soll dauerhaft laufen).
7. OK → PC einmal neu starten → prüfen, dass das Agent-Fenster von selbst aufgeht.

Damit greifen zwei Sicherungsnetze: die `.bat` startet Python nach einem Absturz in 10
Sekunden neu, und die Aufgabenplanung startet die `.bat` nach einem Neustart des PCs.

## Kontrolle im Alltag (ohne auf den PC zu gehen)
Der Agent schreibt seinen Status in die Supabase-Tabelle `mirror_control`:
`status` (running/stopped/error), `last_heartbeat` (Zeitstempel), `log`, `positions`.
Wenn `last_heartbeat` älter als ein paar Minuten ist, während `active=true` steht, läuft
der Agent auf dem PC nicht mehr — dann per AnyDesk nachsehen.

## Wichtig
- **Nie gleichzeitig** den alten Railway-Mirror und den lokalen Agent für dasselbe Konto
  aktiv haben → sonst doppelte Hedge-Orders.
- Vor echtem Geld den gestuften Testplan aus der README abarbeiten (Demo-Konto zuerst).
