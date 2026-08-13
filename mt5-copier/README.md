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
   Die zweite Installation im *portable* Modus starten (Verknüpfung mit `/portable`).
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

## Noch offen (bewusst)
- Keine Pending Orders, kein SL/TP-Spiegeln (bei einem Hedge nicht gewollt).
- Noch keine Prophos-Anbindung: Multiplikator und Mapping stehen in der `config.json`.
  Läuft das Ganze stabil, kann Prophos die Werte dorthin schreiben — genau wie es sie heute
  an Duplikum pusht.
- Kein Watchdog/Autostart, solange getestet wird. Für den Dauerbetrieb kommt ein
  Reattach-Watchdog dazu (`-10002`/`-10003` nach Terminal-Neustart).
- Ein Snapshot-Timeout ist noch nicht scharf: Wenn das EA ausfällt, merkt der Executor es
  aktuell nur daran, dass die Datei nicht mehr aktualisiert wird. Vor Live-Betrieb ergänzen.
