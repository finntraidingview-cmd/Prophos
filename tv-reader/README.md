# Prophos TV-Reader

Liest die **offenen Positionen aus TradingView direkt im Browser** (DOM) und schickt
sie an einen lokalen Empfänger. Kein NinjaTrader, kein zweiter Tradovate-Login,
**keine zusätzliche Session** — der Reader liest nur mit, was TradingView ohnehin
anzeigt. Damit bleibt das saubere Ein-Session-Bild erhalten (der Grund für den
ganzen Umstieg weg von Duplikium).

Bewiesen am 28.08.2026 live gegen TradingView Paper-Trading: Position öffnen →
Reader sieht sie in < 1 s, schließen → sofort weg.

## Bausteine
- `tv-reader.user.js` — Tampermonkey-Userscript, läuft auf tradingview.com, liest
  jede Sekunde die Positionstabelle (hängt an den stabilen `data-label`-Attributen
  der ka-table, nicht an gehashten CSS-Klassen) und POSTet sie an den Empfänger.
- `reader-server.py` — lokaler Empfänger (nur Python-Standardbibliothek). Nimmt die
  Daten an, hält den Stand, schreibt `positions.json` (atomar) und zeigt eine
  Live-Zeile im Terminal.

## Setup (einmalig)
1. **Tampermonkey** in Chrome installieren (kostenlose Extension), dann in
   `chrome://extensions` → Tampermonkey → Details → **„Nutzerscripts zulassen"**
   aktivieren (Entwicklermodus an) — ohne das läuft kein Userscript
   (Stolperstein vom Mac-Test 28.08.2026).
2. Tampermonkey-Dashboard → **Utilities → Import** (oder **+ → Code einfügen**) →
   Inhalt von `tv-reader.user.js` einfügen → **speichern**.
3. Empfänger starten:
   ```
   python3 reader-server.py
   ```
   Auf dem Windows-PC: einfach `start-reader.bat` doppelklicken.
4. **Prophos-Tab offen lassen** (auf dem PC wie gehabt `localhost:5000`): der Tab
   ist die Brücke in die Cloud — er pusht den Reader-Stand alle 5s nach
   `echoplus_live`, damit die **Echo-+-View** ihn von jedem Gerät zeigt.

## Ein/Aus — die Echo-+-View in Prophos
Prophos hat einen eigenen Navigations-Punkt **Echo +**: eine Karte pro Gerät,
darauf live die Positionen, die der Reader sieht, plus ein **Pausieren/
Einschalten**-Knopf — der funktioniert von überall (Handy, Mac), nicht nur am PC:
- Der Knopf schreibt den Wunsch (`soll_an`) in die Cloud; der Prophos-Tab des
  Reader-Geräts setzt ihn beim lokalen `reader-server` durch (`POST /schalter`)
  und meldet den Ist-Zustand zurück. Am Gerät selbst greift er sofort.
- **Pausiert** heißt: der Stand **friert ein** (stale ≠ flat — ein pausierter
  Reader meldet NIE „keine Positionen", sonst würde ein Copier-Konsument die
  Hedges schließen). `positions.json` trägt `"an": false`; jeder Konsument
  MUSS das prüfen: `an=false` → nicht syncen. Persistiert als
  `reader_aus.flag`, überlebt also einen Server-Neustart.
- Der Tampermonkey-Badge zeigt Pausiert grau an (`⏸ Reader pausiert`); das
  Script liest lokal weiter mit, damit Wiedereinschalten sofort greift.

## Test
1. TradingView öffnen, das **Positionen-Panel unten sichtbar** halten (das DOM ist
   nur da, wenn das Panel gerendert ist — siehe Einschränkung).
2. Unten rechts im Chart erscheint ein grüner Badge: `● Reader · N Pos · Copier ok`.
   Orange = Empfänger nicht erreichbar (läuft `reader-server.py`?).
3. Im Terminal des Empfängers tickt die Live-Zeile mit deinen Positionen.
4. Position öffnen/schließen → Badge **und** Terminal aktualisieren binnen 1 s.
5. Gegenprobe im Browser: `http://127.0.0.1:8790/positions` zeigt den JSON-Stand.

## Einschränkung (bewusst, siehe Fahrplan)
- Der DOM zeigt nur das **in TradingView aktive Konto**. Bei mehreren Konten mit
  parallelen Positionen greift später das preis-basierte Register + der Airbag-SL
  (broker-seitig auf Fusion, konto-unabhängig). Für den Start: ein Konto / eine
  Order zur Zeit reicht.
- Panel muss gerendert sein. Ist es zu, liest der Reader 0 — der Airbag deckt den
  Blindmoment broker-seitig ab.
- ToS: das Auslesen des eigenen Kontos ist ein TradingView-AGB-Grauzonenpunkt; das
  Restrisiko ist bewusst getragen (rein lesend, isolierter content-script-Kontext,
  keine Netzwerk-Requests an TradingView → praktisch nicht detektierbar).

## Nächster Schritt
Der Empfänger hält den Stand unter `GET http://127.0.0.1:8790/positions` und in
`positions.json`. Der bestehende MT5-Copier (`mt5-copier/copier.py`) liest das und
setzt/synchronisiert den Fusion-Hedge; SL/TP kommen aus dem Trade-Plan, Airbag-SL
broker-seitig wie gehabt.
