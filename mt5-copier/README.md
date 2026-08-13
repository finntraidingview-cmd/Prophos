# MT5-Hedge-Copier — eigenständige Testversion

Ersetzt langfristig Duplikum auf der **MT5/CFD-Seite**. Läuft komplett lokal auf dem PC der
jeweiligen Person: liest die Positionen des Prop-Masters aus dem dort laufenden Terminal und
setzt die Gegenposition (Reverse-Hedge) im zweiten Terminal mit dem Live-Konto.

## Das laufende System wird nicht angefasst
- Eigener Ordner, eigenes Programm, eigene `config.json`. **`app.py`, `prophos.html`,
  Duplikum und die Supabase-Tabellen bleiben unberührt** — nichts davon wird gelesen oder
  geschrieben.
- **Kein Broker-Login:** Das Programm hängt sich an die *laufenden* Terminals und benutzt
  den dort schon eingeloggten Account. Es braucht keine Zugangsdaten, erzeugt keine zweite
  Session und keinen zweiten Geräte-Fingerprint.
- **Auf dem Prop-Konto wird nichts platziert.** Der Reader-Prozess enthält keinen
  Order-Code — strukturell ausgeschlossen, nicht nur per Schalter.
- Duplikum kann während der ganzen Testphase **weiterlaufen wie bisher**.

## Voraussetzungen auf dem PC
1. Windows + Python 3.10+ (`pip install MetaTrader5`) — das Paket ist Windows-only.
2. **Zwei** MT5-Installationen, damit beide Konten gleichzeitig offen sein können
   (z.B. `C:\MT5-Master` und `C:\MT5-Hedge`; zweite Installation im *portable* Modus).
   - Master-Terminal: das Prop-Konto (das, in dem du per Parsec tradest).
   - Hedge-Terminal: **für den Test ein DEMO-Konto** deines Live-Brokers.
3. Im **Hedge**-Terminal muss „Algo Trading" erlaubt sein (Extras → Optionen → Expert
   Advisors). Im Master-Terminal ist das nicht nötig — dort wird nur gelesen.
4. `config.example.json` → `config.json` kopieren, Pfade/Multiplikator/Symbol-Mapping
   eintragen. `mode` bleibt zunächst `dryrun`.

## Die drei Stufen — in dieser Reihenfolge
### Stufe 1 · `mode: "dryrun"` — Schattenbetrieb, null Risiko
Es wird **keine einzige Order** gesendet, nur protokolliert. Starte den Copier, während
Duplikum normal weiterläuft, und trade wie gewohnt. Im Fenster erscheint dann z.B.:

    [reader] 🆕 Master-Position: BUY 1.0 US100.cash #123456
    [writer] DRYRUN — wuerde senden: HEDGE OPEN SELL 1.0 NAS100 (Master #123456 1.0 US100.cash)

**Das ist der eigentliche Test:** Vergleiche diese Zeile mit dem, was Duplikum tatsächlich
gemacht hat. Stimmen Richtung, Lots und Symbol überein, rechnet der Copier korrekt.
Auch Schließen und Teil-Schließen hier durchspielen.

### Stufe 2 · `mode: "demo"` — echte Orders, aber nur auf Demo
Hedge-Terminal auf ein **Demo-Konto** einloggen. Das Programm **verweigert** den Versand,
wenn dort ein Echtgeld-Konto eingeloggt ist (Prüfung über `account_info().trade_mode`).
Jetzt sollten Öffnen, Teil-Schließen und Schließen real durchlaufen — auf Spielgeld.

### Stufe 3 · `mode: "live"` — scharf
Erst wenn Stufe 2 mehrfach sauber war. **Vorher für dieses Master-Paar Duplikum
abschalten** — sonst spiegeln zwei Systeme parallel und der Hedge ist doppelt.

## Was schon eingebaut ist
- **Reverse-Logik:** Master BUY → Hedge SELL und umgekehrt.
- **Teil-Schließungen:** schrumpft das Master-Volumen, wird anteilig geschlossen.
- **Idempotenz nach Neustart:** bestehende Hedges werden am Kommentar `PH-<Master-Ticket>`
  wiedererkannt → keine Doppel-Hedges, wenn der Copier neu startet.
- **Keine Übernahme von Alt-Positionen:** was beim Start schon offen war, wird nicht
  nachträglich gehedged (`adopt_existing_master_positions` schaltet es ein).
- **Lot-Rundung** auf `volume_step` des Hedge-Symbols, Klemmung auf min/max.
- **Sicherheitsgrenze** `max_lots_per_hedge` — bricht ab, statt eine absurde Größe zu senden.
- **Symbol-Mapping** aus der Config; fehlt ein Mapping, wird übersprungen statt geraten.

## Offen / noch nicht drin (bewusst)
- Kein SL/TP-Spiegeln (bei einem Hedge in der Regel nicht gewollt).
- Keine Pending Orders (nur Marktpositionen).
- Noch keine Prophos-Anbindung: Multiplikator und Mapping stehen in der `config.json`.
  Sobald die Stufen sauber laufen, kann Prophos die Werte dorthin schreiben — genau wie es
  sie heute an Duplikum pusht.
- Kein Watchdog/Autostart — bewusst manuell, solange getestet wird.
