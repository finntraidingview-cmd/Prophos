# MT5-Hedge-Copier — eigenständige Testversion

Ersetzt langfristig Duplikum auf der **MT5/CFD-Seite**. Läuft komplett lokal auf dem PC der
jeweiligen Person. **Das laufende Duplikum-Setup wird nicht angefasst** und kann während der
gesamten Testphase normal weiterlaufen.

## Architektur

    MASTER-Terminal 1 ── prophos_master.csv  ──┐
    MASTER-Terminal 2 ── prophos_master2.csv ──┼──►  copier.py  ──►  HEDGE-Terminal
    MASTER-Terminal N ── prophos_masterN.csv ──┘   (EIN Prozess)     (ein Live-Konto)

**Seit 13.08.2026 bedient EIN `copier.py`-Prozess ALLE Master dieses PCs.** Jede
`config*.json` im Ordner ist ein Master. Warum nicht ein Prozess pro Master: Die
Recherche fand keinen einzigen belastbaren Beleg, dass zwei Python-Prozesse stabil
am selben MT5-Terminal hängen können (dokumentierte Ausfälle: `-10003`/`-10004`
IPC-Fehler; Projekte, die es stabil haben, serialisieren alle Aufrufe durch einen
Prozess). Und das Code-Audit fand 8 kritische Kollisionen zwischen parallelen
Copier-Prozessen — ein einzelner Prozess kann sich nicht selbst in die Quere kommen.

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
6. `start-copier.bat` doppelklicken.

## Immer echt — aber nur im Trade-Fenster
Der Copier sendet **echte Orders** (die frühere Modus-Treppe `dryrun`/`demo`/`live`
ist am **25.08.2026** auf Finns Ansage komplett ausgebaut; ein `mode`-Feld in alten
Configs wird still ignoriert). **Neue Hedges eröffnet er aber nur im Trade-Fenster**
(gleicher Tag, nach der Geisterposition auf dem Live-Konto): zwischen „Trade starten"
in Prophos (Panel-Plan `geplant`, max. 6 h gültig) und dem Trade-Ende (`beendet`).
Außerhalb des Fensters wird **nie** eröffnet — egal was Snapshot oder Master zeigen
(Log: `🔒 kein offenes Trade-Fenster`). **Closes laufen immer**, eigene Hedges
abbauen ist nie falsch. Ebenfalls immer: ein von Hand geschlossener Hedge bleibt zu
(`✋ Hand-Close wird respektiert`), und eine eingefrorene Snapshot-Datei ist keine
Order-Basis. Was bleibt: **vor dem Start Duplikum für die Master-Paare abschalten** —
sonst spiegeln zwei Systeme parallel und der Hedge ist doppelt.

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
- **„Algo Trading nicht aktiv"** → im **Hedge**-Terminal einschalten (im Master nicht nötig).
- **`hedge_portable`** muss `false` sein, wenn MT5 normal (nicht portable) installiert wurde.

## Panel — Frontend im Browser (statt Textdatei)
Eigenständiges Mini-Frontend für die Copier auf **diesem** PC. Prophos wird nicht angefasst.

    python panel.py        (oder start-panel.bat)  →  http://127.0.0.1:8770

Was es kann:
- **Multiplikator und Symbol-Mapping im Browser setzen** — Änderungen landen in der
  `config.json` und der Copier übernimmt sie **live in ~2 s**, ohne Neustart.
- **Mehrere Master gleichzeitig:** jede `config*.json` im Ordner ist ein Master —
  `config.json`, `config-master2.json`, `config-ftmo.json` … Jede bekommt eine eigene Karte.
  **EIN** `start-copier.bat` startet **einen** Prozess, der alle bedient; der Status je
  Master landet automatisch in der passenden `status*.json`. Erlaubte Namen:
  `config.json` oder `config-<name>.json` (Buchstaben/Zahlen) — Explorer-Kopien wie
  „config - Kopie.json" werden bewusst ignoriert und beim Panel-Start als ignoriert gelistet.
- **Live-Anzeige pro Master:** Master-/Hedge-Kontonummer, Anzahl Master-Positionen, offene
  Hedges, „läuft/gestoppt" (Statusdatei-Alter) und die letzten Log-Zeilen.
- **„Terminal starten":** startet die `master_terminal_path`-Exe der Karte. Es werden KEINE
  Zugangsdaten gespeichert — MT5 merkt sich den Login pro Installationsordner selbst
  (einmal manuell einloggen, „Zugangsdaten speichern" ✓). Der Pfad ist über die API bewusst
  NICHT setzbar, nur direkt in der JSON.
- **Konflikt-Banner:** doppelte `magic` oder `snapshot_file` zwischen den Configs werden rot
  angezeigt, bevor der Copier beim Start deswegen abbricht.

Sicherheit (getestet):
- Bindet **nur an 127.0.0.1** — aus dem Netz nicht erreichbar.
- **Whitelist:** das Panel darf ausschließlich `multiplier` und `symbol_map` schreiben.
  Terminal-Pfade und die erwarteten Kontonummern (`hedge_expected_login` /
  `master_expected_login`) sind tabu — das sind die Sicherheitsanker des Copiers.
  Verifiziert: ein Push mit fremden Kontonummern und Pfad ließ diese Felder unverändert.
- Werte-Prüfung: negative/nicht-numerische Multiplikatoren werden abgelehnt, statt in
  die Config zu wandern.
- Nur Python-Standardbibliothek — kein `pip install`, keine Cloud, keine Schlüssel auf dem PC.

## Account hinzufügen — automatisch (Panel-Knopf)
Im Panel gibt es die Karte **„＋ Account hinzufügen"**: Name (kurz, nur Buchstaben/Zahlen),
Kontonummer, Passwort, Server → „Fertig". Danach läuft alles von selbst (Fortschritt live
in der Karte):

1. **Prüfen & Kennwerte vergeben** — magic, comment_prefix und snapshot_file werden
   fortlaufend vergeben und KÖNNEN nicht mehr kollidieren.
2. **Klonen** — die Vorlage (`master_terminal_path` aus `config.json`) wird nach
   `C:\MT5-<name>` kopiert; `Config/`, `logs/`, `Bases/` werden vorsorglich entfernt.
3. **Erststart + Login** — Start per offizieller MT5-Startdatei (`/config`) mit
   `KeepPrivate=1`; der Login wird im Terminal-Journal **verifiziert** („authorized"),
   erst dann geht es weiter. **Die Startdatei mit dem Passwort wird garantiert gelöscht**
   (auch im Fehlerfall) — dauerhaft speichert die Zugangsdaten nur MT5 selbst,
   verschlüsselt, wie beim manuellen Login.
4. **EA + Preset** — die kompilierte `ProphosHedgeReader.ex5` aus dem Vorlage-Terminal
   wird in den Datenordner des Klons gelegt (gefunden über `origin.txt`, nie über den
   Hash geraten), dazu ein Preset mit dem eindeutigen Snapshot-Namen.
5. **Neustart mit `[StartUp]`** — das EA landet automatisch auf einem EURUSD-Chart und
   bleibt dort dauerhaft (Chart-Persistenz). Bewiesen wird der Schritt über die
   Snapshot-Datei selbst; die Start-ini wird danach gelöscht (ein zweiter Start damit
   würde das EA auf einen ZWEITEN Chart duplizieren).
6. **Config anlegen** — `config-<name>.json`; der laufende Copier
   nimmt sie binnen 5 s in die Flotte, die Karte erscheint im Panel.

Voraussetzungen: Vorlage-Terminal ist eingerichtet (EA einmal kompiliert),
`master_terminal_path` steht in der `config.json`, der Account existiert beim Broker.
Achtung: die neue Instanz kopiert ab dem ersten Master-Trade **sofort echt**.

## Zweiter Master auf dasselbe Hedge-Konto (Schritt für Schritt)
1. **Terminal-Ordner kopieren** statt neu installieren: `xcopy "C:\MT5-Master" "C:\MT5-Master2" /E /I /H`,
   dann `C:\MT5-Master2\terminal64.exe` starten, **einmal** mit dem neuen Konto einloggen
   („Zugangsdaten speichern" ✓). Ab dann gilt: dieser Ordner = dieses Konto.
2. **EA aufziehen** (Datei → Datenordner öffnen → `MQL5\Experts`, kompilieren, auf einen Chart)
   und dabei den Input **`InpFileName` ändern**, z.B. `prophos_master2.csv`.
3. **`config-master2.json`** anlegen (Kopie der config.json) und diese Felder ändern:

   | Feld | muss pro Master EINDEUTIG sein | Beispiel Master 2 |
   |---|---|---|
   | `snapshot_file` | ja — identisch mit `InpFileName` im EA | `prophos_master2.csv` |
   | `magic` | ja — daran erkennt der Copier SEINE Hedges | `770002` |
   | `comment_prefix` | empfohlen | `P2` |
   | `master_expected_login` | ja (ab 2 Mastern Pflicht, sonst Abbruch) | die neue Kontonummer |
   | `master_terminal_path` | ja (für den Terminal-Start-Knopf) | `C:\\MT5-Master2\\terminal64.exe` |

   `hedge_terminal_path` und `hedge_expected_login` bleiben in ALLEN Configs identisch —
   bei Abweichung bricht der Copier ab.
4. Der laufende Copier erkennt die neue Datei binnen 5 s, startet sich selbst neu und prüft
   dabei die ganze Flotte durch. Doppelte `magic`/`snapshot_file` → Abbruch mit klarer Meldung
   (das war der gefährlichste Audit-Fund: zwei Copier mit gleicher magic schließen sich
   gegenseitig die Hedges).

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
