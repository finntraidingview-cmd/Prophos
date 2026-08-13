# MT5-Hedge-Copier — eigenständige Testversion

Ersetzt langfristig Duplikum auf der **MT5/CFD-Seite**. Läuft komplett lokal auf dem PC der
jeweiligen Person. **Das laufende Duplikum-Setup wird nicht angefasst** und kann während der
gesamten Testphase normal weiterlaufen.

## Architektur

    PROP-Terminal                gemeinsamer Ordner          LIVE-Terminal
    ProphosHedgeReader.mq5   →   prophos_master.csv     →    copier.py
    (nur lesend)                 (Positions-Snapshot)        (setzt den Hedge)

**Warum die Master-Seite ein EA ist und nicht Python:** Der `path=`-Parameter von
`mt5.initialize()` greift laut mehreren dokumentierten Fällen nicht zuverlässig — man kann
an der *falschen* Terminal-Installation landen (Fehler `-10003`). Ein Python-Prozess, der
versehentlich am Prop-Terminal hängt und dort Orders sendet, ist das schlimmste denkbare
Szenario. Deshalb: Python hängt an **genau einem** Terminal (dem Live-Konto), die
Master-Seite ist ein reines Lese-EA. Zusätzlich prüft `copier.py` nach dem Verbinden hart,
ob wirklich das erwartete Konto dranhängt — bei Abweichung Abbruch, ohne eine einzige Order.

**Deklaratives Modell statt Event-Copier:** Das EA veröffentlicht den *kompletten*
Positionsstand (mit Sequenznummer und Footer, atomar per `FileMove` geschrieben).
`copier.py` berechnet daraus pro Master-Position ein **Soll-Volumen** und bringt den Hedge
darauf. Teil-Schließungen, verpasste Events, Teilfüllungen und Neustart-Recovery sind damit
derselbe Codepfad statt vier Sonderfälle — und driftfrei, weil nicht mit Prozenten vom Rest
gerechnet wird.

## Sicherheitsgarantien (im Code verifiziert)
- **Kein Broker-Login:** `initialize()` nutzt den im Terminal bereits eingeloggten Account.
  `mt5.login()` wird **nie** aufgerufen — das würde ein Terminal auf ein anderes Konto
  umschalten, mitten in deinem laufenden Trade.
- **Auf dem Prop-Konto ist keine Order möglich:** Das EA enthält keine einzige
  Handelsfunktion (nur `PositionGet*`, `File*`, `AccountInfo*`). Zusätzlich kann
  „Algo Trading" im Prop-Terminal **aus** bleiben — EAs laufen und dürfen Dateien
  schreiben, aber das Terminal blockt jede Order. Doppelt abgesichert.
- **Konto-Verifikation:** `hedge_expected_login` und `master_expected_login` in der Config.
  Hängt das Programm am falschen Konto oder weicht der Terminal-Pfad ab → Abbruch.
- **Hedging-Modus erzwungen:** Auf einem Netting-Konto bricht es ab (dort gibt es nur eine
  Position pro Symbol, die Zuordnung Master↔Hedge wäre kaputt).
- **Zuordnung:** Master-Seite über `POSITION_IDENTIFIER` (stabiler als das Ticket),
  Hedge-Seite über **Magic** als Primärfilter (broker-stabil) plus Kommentar-Token
  `PH-<identifier>`. Broker können Kommentare ergänzen, deshalb wird nur der Präfix gesucht.
- **Exposure-Umrechnung:** Lots werden über die Kontraktgrößen beider Broker gerechnet
  (`master_lots × master_contract_size × multiplier / hedge_contract_size`), nicht 1:1 —
  derselbe Index hat bei verschiedenen Brokern Kontraktgrößen 1, 10 oder 100.
- **Kein SL/TP auf dem Hedge** (ein eigener Stop würde die Absicherung vorzeitig auflösen).
- **`max_lots_per_hedge`** bricht ab, statt eine absurde Größe zu senden.

## Einrichtung auf dem PC
1. Windows + Python 3.10+, dann `pip install MetaTrader5` (Paket ist Windows-only).
2. **Zwei** MT5-Installationen in **verschiedenen Ordnern** — offiziell: „Two copies of the
   platform cannot run from the same directory."
   - `C:\MT5-Master` → das Prop-Konto (das, in dem du per Parsec tradest).
   - `C:\MT5-Hedge` → **für den Test ein DEMO-Konto** deines Live-Brokers.
   Normal installieren (nicht portable) — zwei verschiedene Zielordner reichen, MT5 legt
   dann automatisch getrennte Datenordner an. In der Config entsprechend
   `"hedge_portable": false`. Im MT5-Installer dafür auf **„Einstellungen"** klicken und den
   Zielordner setzen; **nicht** nach `C:\Program Files` installieren.
3. **EA installieren:** `ProphosHedgeReader.mq5` im Master-Terminal über MetaEditor
   kompilieren (F7), dann auf einen beliebigen Chart ziehen. Im Journal muss stehen:
   `ProphosHedgeReader gestartet — Konto … (nur lesend)`.
4. Im **Hedge**-Terminal „Algo Trading" aktivieren (Extras → Optionen → Expert Advisors).
   Im Master-Terminal **nicht** nötig — dort wird nur gelesen.
5. `config.example.json` → `config.json`, ausfüllen. Besonders wichtig:
   `hedge_expected_login` (Konto, auf dem gehedged werden darf) und
   `master_expected_login` (Prop-Konto — hängt das Programm dort, bricht es ab).
6. `start-copier.bat` doppelklicken. `mode` bleibt zunächst `dryrun`.

## Die drei Stufen — in dieser Reihenfolge
### Stufe 1 · `dryrun` — Schattenbetrieb, null Risiko
Keine einzige Order, nur Protokoll. Duplikum läuft normal weiter, du tradest wie gewohnt:

    [reader] Snapshot verbunden — Master-Konto 123456 …
    DRYRUN — wuerde senden: HEDGE OPEN SELL 1.0 NAS100 (Master-Pos 987654)

**Das ist der eigentliche Test:** Vergleiche die Zeile mit dem, was Duplikum tatsächlich
gemacht hat. Stimmen Richtung, Lots und Symbol, rechnet der Copier korrekt. Auch Schließen
und Teil-Schließen durchspielen.

### Stufe 2 · `demo` — echte Orders, nur auf Demo
Hedge-Terminal auf ein Demo-Konto einloggen. Das Programm **verweigert** den Versand, wenn
dort ein Echtgeld-Konto hängt. Jetzt Öffnen, Teil-Schließen und Schließen real durchlaufen.

### Stufe 3 · `live` — scharf
Erst wenn Stufe 2 mehrfach sauber war. **Vorher für dieses Master-Paar Duplikum
abschalten** — sonst spiegeln zwei Systeme parallel und der Hedge ist doppelt.

## Live getestet (13.08.2026, zwei Fusion-Demo-Konten)
- `✅ HEDGE OPEN SELL 2.0 NAS100 · deal=355572440` — Gegenposition wurde real platziert.
- `✅ HEDGE CLOSE 2.0 NAS100 · deal=355572637` — Hedge folgte dem Master-Close.
- `⚠ Sicherheitsgrenze: 5.0 > max_lots_per_hedge 2.0 — uebersprungen` — Notbremse hat gehalten.
- `⛔ ABBRUCH: 'Algo Trading' ist im Live-Terminal nicht aktiv` — Startprüfung greift.
- Logik-Selbsttest: `python3 selftest.py` → **15/15** (läuft ohne MetaTrader, auch auf macOS).
Noch nicht am Broker getestet: Teil-Schließung und Neustart-Recovery (im Selbsttest grün).

## Häufige Stolpersteine
- **Es passiert nichts?** Reihenfolge: **erst Copier starten, dann traden.** Was beim Start
  schon offen war, wird absichtlich nicht gehedged (`⏭`-Zeile im Log).
- **Immer noch DRYRUN im Log?** Der Copier liest die Config **nur beim Start** — nach dem
  Ändern neu starten. Kontrolle: `type config.json`, und im Startblock muss `Modus DEMO` stehen.
  Zum Umstellen zuverlässiger als Notepad:
  `powershell -Command "(Get-Content config.json) -replace 'dryrun','demo' | Set-Content config.json"`
- **„Algo Trading nicht aktiv"** → im **Hedge**-Terminal einschalten (im Master nicht nötig).
- **`hedge_portable`** muss `false` sein, wenn MT5 normal (nicht portable) installiert wurde.

## Dauerbetrieb (Autostart + Watchdog)
Zwei Sicherungsnetze, damit der Copier unbeaufsichtigt laufen kann:
1. **`start-copier.bat`** startet `copier.py` in einer Schleife — stirbt der Prozess oder
   beendet er sich wegen dauerhaftem Verbindungsverlust, kommt er nach 10 s zurueck. Beim
   Neustart laufen ALLE Startpruefungen wieder (Konto, Hedging-Modus, Algo-Trading) — das ist
   bewusst so, statt im laufenden Prozess zu reattachen und dabei Pruefungen zu ueberspringen.
2. **Windows-Aufgabenplanung** startet die .bat beim Anmelden/Hochfahren:
   Aufgabenplanung → „Aufgabe erstellen…" → Trigger „Bei Anmeldung" → Aktion
   `C:\mt5-copier\start-copier.bat` („Starten in" = `C:\mt5-copier`) → Einstellungen:
   „Aufgabe neu starten, falls Fehler" alle 1 Minute, bis 99×; „Aufgabe beenden, falls laenger
   ausgefuehrt als" **abwaehlen**.

**Verbindungsabriss (wichtig fuer unbeaufsichtigten Betrieb):** `positions_get()` liefert bei
gestoerter Terminal-Verbindung `None`. Das darf NICHT als „es gibt keine Hedges" gelten —
sonst wuerde ein kurzer Abriss aussehen wie „Hedge fehlt" und der Executor riss ihn ein
zweites Mal auf. Der Copier setzt bei `None` aus, warnt, und beendet sich nach ~20 s Ausfall
fuer einen sauberen Neustart durch die .bat.

## Noch offen (bewusst)
- Keine Pending Orders, kein SL/TP-Spiegeln (bei einem Hedge nicht gewollt).
- Noch keine Prophos-Anbindung: Multiplikator und Mapping stehen in der `config.json`.
  Läuft das Ganze stabil, kann Prophos die Werte dorthin schreiben — genau wie es sie heute
  an Duplikum pusht.
- Kein Watchdog/Autostart, solange getestet wird. Für den Dauerbetrieb kommt ein
  Reattach-Watchdog dazu (`-10002`/`-10003` nach Terminal-Neustart).
- Live noch nicht am Broker geprüft: Teil-Schließung und Neustart-Recovery (im Selbsttest grün).

## Seit dem Live-Test ergänzt (Commit 540c434)
- **Dryrun-Bremse:** im Dryrun wird ein virtueller Hedge-Bestand geführt → jede Aktion wird
  nur noch einmal geloggt statt alle 0,5 s (verifiziert: 1 Zeile statt 5 über 5 Ticks).
- **Reopen-Guard:** wird ein gesetzter Hedge nicht wiedererkannt (z.B. Broker hat den
  Kommentar verändert), wird nach 3 Versuchen gestoppt und laut gewarnt, statt endlos
  nachzulegen. Plus 3 s Cooldown zwischen Versuchen.
- **Snapshot-Timeout:** ändert sich die Snapshot-Sequenz 15 s nicht, kommt eine Warnung
  („läuft das Lese-EA noch?").
