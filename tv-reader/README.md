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
  viermal pro Sekunde die Positionstabelle (hängt an den stabilen
  `data-label`-Attributen der ka-table, nicht an gehashten CSS-Klassen) und POSTet
  sie an den Empfänger. Seit 0.4.0 aus einem Web Worker getaktet und mit
  Blind-Erkennung — siehe „Der verdeckte Tab" weiter unten.
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
   `echoplus_live`, damit die **Orbit-View** ihn von jedem Gerät zeigt.

## Der verdeckte Tab (01.09.2026) — warum „0 Positionen" ein Beweis braucht

Finns Fund beim Zwei-Konten-Test: Order in TradingView platziert, sauber
gespiegelt — und sobald er den **Tab von TradingView auf Prophos wechselte**,
ging der Hedge im Sekundentakt zu und wieder auf.

Die Ursache lag in einer einzigen Zeile: der Reader las die Tabellenzellen mit
`td.innerText`. `innerText` ist der **gerenderte** Text — er braucht ein
aktuelles Layout. Chrome hält Rendering und Layout eines verdeckten Tabs an,
also kamen die Zellen **leer** zurück, obwohl die Zeilen weiter im DOM standen.
Der Reader meldete daraufhin „0 Positionen" — mit **frischem Zeitstempel**.

Und das ist der einzige Fall, in dem die Frische-Doktrin der ganzen Kette
versagt: der Verbinder friert nicht ein, weil die Daten ja frisch *sind*, das
CSV meldet ehrlich „flat", und der Copier macht den Hedge zu. Beim nächsten
Tick war die Zelle wieder lesbar → Hedge wieder auf. Das Flattern.

Drei Riegel, alle in dieser Reihenfolge:

1. **`textContent` statt `innerText`** (Userscript 0.4.0) — hängt an keinem
   Layout und liest im verdeckten Tab genauso wie im sichtbaren.
2. **Blind-Flag.** Der Reader unterscheidet jetzt „Tabelle gesehen, wirklich
   flach" von „Tabelle nicht lesbar". Nur der erste Fall ist eine Aussage; im
   zweiten sendet er `blind:true`, der Empfänger friert den Stand ein, und der
   Verbinder schreibt nicht → der Copier hält die Hedges. *Stale != flat*,
   jetzt auch für den Lesevorgang selbst.
3. **Struktur-Riegel im Empfänger.** Eine Nachricht ohne Feld `positionen`
   (Liste) wird abgelehnt statt als „flat" gelesen.

Dazu läuft der Takt seit 0.4.0 aus einem **Web Worker**: `setInterval` im
Seiten-Kontext drosselt Chrome im verdeckten Tab auf 1 Lauf/Sekunde und nach
fünf Minuten auf 1 Lauf/**Minute** — mit dem 10-s-Frischefenster des Verbinders
stünde Orbit dann 50 von 60 Sekunden eingefroren, nur weil jemand woanders
hinschaut. Worker-Timer unterliegen dieser Drosselung nicht. Verbietet die
TradingView-CSP den Worker, fällt es auf `setInterval` zurück — langsamer, aber
durch die drei Riegel oben weiterhin sicher.

**Am Badge ablesbar:** `● Reader · n Pos · Copier ok` = liest.
`⚠ Reader blind: … — Stand eingefroren, Hedge bleibt stehen` = sieht nichts und
behauptet auch nichts.

## Ein/Aus — die Orbit-View in Prophos
Prophos hat einen eigenen Navigations-Punkt **Orbit** (bis 28.08.2026 „Echo +" —
umgetauft, weil zu leicht mit Echo zu verwechseln): eine Karte pro Gerät,
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

## Bedienfeld — die Augen für den Puls (0.3.0, 30.08.2026)
Seit Userscript-Version **0.3.0** meldet der Reader neben den Positionen auch das
**Bedienfeld**: wo Konto-Umschalter, Symbol-Suche, Order-Ticket und die
Kaufen/Verkaufen-Knöpfe gerade auf dem Bildschirm liegen (Rechtecke in
CSS-Pixeln, plus `innerWidth`/`innerHeight`/`devicePixelRatio` zur Kalibrierung).

Arbeitsteilung, bewusst so geschnitten:
- **Userscript = Augen.** Findet die Steuerelemente, misst sie, klickt **nie**.
- **Puls (`order_bot.py tvorder`) = Hände und Kopf.** Entscheidet (passt das
  Konto? das Symbol?) und klickt mit **echter Maus** (`_klick_absolut`).

Warum der Umweg: ein `element.click()` aus dem Userscript trüge `isTrusted=false`.
Die Puls-Doktrin (15.08.2026) ist „muss wie ein Handklick aussehen" — auf der
MT5-Seite wegen der Expert-Markierung, hier aus demselben Reflex.

Routen am `reader-server`:
- `POST /bedienfeld` — Userscript schickt den Stand (alle 500 ms).
- `GET /bedienfeld` — Puls holt ihn ab; `alter_s` sagt, wie alt er ist. Puls
  wartet nach jedem Klick auf einen Stand, der **jünger** ist als sein Klick —
  Beweis statt Vermutung, dieselbe Regel wie beim MT5-Puls.
- `POST /dump-an` — schaltet für 60 s den **Kandidaten-Dump** scharf (alle
  sichtbaren Knöpfe/Felder mit `data-name`, `aria-label`, Text und Rechteck).
  Der Puls ruft das bei jedem Fehlversuch selbst auf. Das ist das Gegenstück zu
  `order_bot.py inspect` beim MT5-Weg: **Dump an Claude schicken, daraus wird
  die Zuordnung gehärtet.** Anschauen: `http://127.0.0.1:8790/bedienfeld`.

Findet der Puls ein Steuerelement **nicht eindeutig**, bricht er ab, statt einen
von mehreren Kandidaten zu erwischen — auf einer Trading-Seite ist ein
danebengegangener Klick kein harmloser Fehlversuch.

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

## Spiegel-Weg: TradingView → Fusion-Hedge (der Verbinder, 28.08.2026)
`tv_verbinder.py` schließt die Kette auf dem Windows-PC: er liest alle 0,5 s den
Reader-Stand (Port 8790) und schreibt per `tv_snapshot.py` das PROPHOS1-CSV in
den Common-Files-Ordner — **der Copier braucht null Änderungen**, der TV-Reader
ist für ihn ein weiterer Master mit eigener Instanz-Config.

Einrichtung auf dem PC (einmalig, zusätzlich zum Reader-Setup oben):
1. `verbinder.config.example.json` → `verbinder.config.json` kopieren,
   `master_login` ausfüllen (z.B. Tradovate-Kontonummer).
2. In `C:\mt5-copier`: `config.tvplus.vorlage.json` → `config-tvplus.json`
   kopieren, `master_expected_login` (= derselbe Wert) und die Hedge-Zeilen wie
   in den anderen Configs des PCs ausfüllen. `immer_scharf: true` ist der Kern:
   manuelle TradingView-Trades werden ohne Prophos-Trade-Fenster gehedgt.
3. `start-verbinder.bat` doppelklicken (Reihenfolge egal), Copier neu starten.
4. **Erster Test mit 1 MNQ** (= 2 NAS100-Lots bei multiplier 1.0), nicht mit NQ.

Sicherheits-Doktrin des Verbinders (stale ≠ flat):
- Reader **pausiert** / **Daten älter 10 s** / **Server weg** → es wird NICHT
  geschrieben, das CSV friert ein → der Copier meldet „Snapshot unverändert"
  und **hält die Hedges**. Kein Zustand des Readers schließt je einen Hedge.
- **SL/TP werden genullt** (`sltp_uebernehmen: false` lassen): TradingView
  liefert Futures-Preise, der Fusion-CFD hat eine andere Preisskala — Level
  1:1 übernommen wären falsche Notfall-Level. Leer statt falsch, bis die
  Umrechnung gebaut ist.

## 24/7-Kurs-Feed NQ + MNQ (0.7.0, 24.09.2026) — Betriebs-Checkliste

Finn: „Ich muss das zu 100 % sicher haben: die MNQ- und NQ-Live-Daten in Prophos, mit einem
Script, das die ganze Zeit liest, auf einem PC, der 24/7 an ist — genau von dem NQ und MNQ, wo
auch die Order platziert ist." Der Feed speist den Markt-Chart, die Demo-Orders und die
Anzeige der Gegenhedge-Level (die Schließ-Level selbst liegen im Fusion-Terminal).

**Woher der Kurs kommt (0.8.0).** Das Userscript hört TradingViews **eigene WebSocket-Verbindung**
passiv mit — kein eigener Socket, keine eigene Anfrage, es liest nur, was ohnehin ankommt: Kurse
(`qsd`: letzter Preis, Bid, Ask, Zeit des letzten Trades) für jedes Symbol in Chart **und Watchlist**,
und die Minutenkerzen der Chart-Serie (`timescale_update` = Erstladung mit Historie, `du` = laufend).
WebSocket-Nachrichten werden im verdeckten Tab **nicht** gedrosselt — dieser Weg liefert auch,
wenn Prophos vorn liegt. Voraussetzungen: Chart auf **1 Minute**, Symbol NQ (NQ1! oder Front-Month),
**MNQ1! in der Watchlist** (dann kommen NQ und MNQ parallel). Steht der Chart auf einer anderen
Auflösung, gibt es keine Minutenkerzen — Prophos zeigt „Chart-Auflösung x statt 1". **Kerzen gibt
es nur für Symbole, die als Chart-Pane im Layout liegen** — die Watchlist liefert per `qsd` nur den
Kurs, keine Bars. Für NQ-Kerzen braucht es also ein NQ-Pane (zwei Panes: NQ1! und MNQ1!, siehe
Einrichtung unten); liegt NQ nur in der Watchlist, füllt sich `tv_kurs_1m` nur für MNQ (Moritz' PC,
25.09.2026). Zeigt der
Feed `delayed_streaming_600`, ist das TradingView-CME-Abo auf dem PC nicht aktiv: alle Kurse sind
dann 10 Minuten alt mit frischem Zeitstempel — der Markt-Kopf warnt.

Rückfälle bleiben eingebaut: die Sell/Buy-Knöpfe der Legende je Chart-Pane (0.7.0, nur im sichtbaren
Tab zuverlässig) und der Tab-Titel (0.6.0).

**Die Live-Zeile im Reader-Fenster lesen (reader-server 0.8.2+).** Rechts steht `Kerzen NQ n/MNQ n ·
du/min x · Serien y (z geraten) · unbek u · fremd … · Aufl ok · Script 0.8.x · Reader 0.8.x`.
`du/min 0` = keine Chart-Frames (kein Chart im Tab oder Socket nicht mitgehört → F5).
`Serien 0` + `unbek > 0` = Chart-Serie nicht zuordenbar und kein Rückfall (F5). `fremd ESZ2026` =
ein Pane zeigt ein Symbol, das weder NQ noch MNQ ist — kein Fehler, nur keine Bars dafür.
`(unaufgel. n)` = Send gehört, Symbol-Klartext noch nicht angekommen (heilt sich beim nächsten
symbol_resolved, sonst F5). `Aufl-WARNUNG` = Chart nicht auf 1 min. `Script ?` = noch kein POST,
`kein feed` = Script < 0.8.0. Nach F5 im TV-Tab schickt TradingView die Erstladung (Hunderte Bars)
— die Brücke im Prophos-Tab holt sie einmal je Tab-Sitzung über `GET /kerzen`; war ihr letzter
Versuch „leer", wiederholt sie erst nach einer Stunde → nach dem TV-F5 auch den Prophos-PC-Tab neu
laden, dann springt `tv_kurs_1m` sofort auf Hunderte Zeilen.

**Woher der Kurs im Rückfall kommt (0.7.0).** Je Chart-Pane liest das Userscript die Sell/Buy-Knöpfe in der
Legende (`data-name="sell-order-button"` / `"buy-order-button"`) — sie tragen Bid und Ask.
Der Kurs im Payload ist die Mitte. Welches Symbol das Pane zeigt, steht in der Legende
daneben (Symbol oder Beschreibung, beides wird erkannt). Rückfall ist der Tab-Titel (nur
das aktive Chart). Zwei Panes = beide Symbole gleichzeitig.

**Einmal einrichten (am 24/7-PC, eingeloggtes TradingView mit Tradovate verbunden):**
1. Layout „Prophos-Feed": Chart-Layout mit **zwei Panes** (Layout-Knopf oben rechts → 2 Charts
   übereinander), oben **NQ1!**, unten **MNQ1!**, Layout speichern. In den Legenden müssen
   die Sell/Buy-Knöpfe stehen (Chart-Einstellungen → Trading → „Kaufen/Verkaufen-Buttons").
   Legende darf Symbol ODER Beschreibung zeigen.
2. Tampermonkey-Script auf **0.7.0** (Dashboard → Updates suchen, oder von `@updateURL`),
   danach TradingView **F5**. Badge muss grün sein.
3. `start-reader.bat` läuft (Reader-Empfänger, Port 8790) — als Autostart eintragen
   (Verknüpfung in `shell:startup`).
4. Prophos-PC-Tab (`localhost:5000`) offen lassen — er ist die Brücke: `tv_kurse` (je Symbol
   eine Zeile `<pc>:NQ` / `<pc>:MNQ`) und `tv_kurs_1m` (Minutenkerzen) alle 5 s.
5. Browser-Autostart mit der Layout-URL (Chrome-Verknüpfung mit der URL des gespeicherten
   Layouts in `shell:startup`), TradingView-Fenster **sichtbar** lassen (nicht minimiert —
   ein verdecktes Fenster tickt gedrosselt, das Script meldet dann `sichtbar:false` und
   schreibt keine Kerzen).
6. PC nie schlafen lassen: `powercfg /change standby-timeout-ac 0` und
   `powercfg /change monitor-timeout-ac 0` (Admin-Eingabeaufforderung); Windows-Update auf
   Nutzungszeit stellen.

**Woran man sieht, dass der Feed steht:**
- Prophos → Markt: Kopfzeile zeigt „live · vor x s · pc-…" — steht dort „kein Live-Kurs" oder
  ein Alter über 30 s, liefert der PC nicht.
- SQL: `select id, symbol, preis, reader_ts, updated_at from tv_kurse` — `reader_ts` darf
  nicht älter als ~10 s sein.
- Badge im TradingView-Tab: grün „Reader · … · Copier ok"; grau = pausiert, orange = blind/offline.

**Selbstheilung:** kein neuer Kurs > 45 s → `stale:true` je Symbol im Payload (Prophos zeigt
den Kurs gedämpft). Neu laden tut sich das Script nur, wenn **gar kein WebSocket-Frame** mehr
ankommt (auch kein Herzschlag) **und** 90 s kein Titel-/Legenden-Wert sich geändert hat —
höchstens alle 10 Minuten; der Grund steht danach im Payload (`reload_grund`) und im
Reader-Fenster. Am Wochenende und in der CME-Pause läuft der Herzschlag weiter: stale, aber
kein Reload. Im Bedienfeld (`feed`) stehen Frames/Minute je Quelle, `letzter_frame_ms`
(irgendein Frame) getrennt von `letzter_ws_ms` (Kurs-/Bar-Frame) — so unterscheidet man
„Markt zu" (Herzschlag ja, Kurs nein) von „Socket tot" (nichts).

**Weg 2 — Chrome so einstellen, dass der Tab nie verworfen wird (10 Minuten, einmalig):**
1. TradingView in ein **eigenes Chrome-Fenster** legen (Tab dort aktiv), Fenster **nie
   minimieren** — klein an den Rand schieben reicht.
2. Chrome-Verknüpfung mit Flags starten (gelten nur, wenn Chrome damit als **erste** Instanz
   startet — alle Chrome-Fenster vorher schließen):
   `--disable-backgrounding-occluded-windows --disable-background-timer-throttling --disable-renderer-backgrounding`
3. `chrome://settings/performance`: Memory Saver **aus** oder `tradingview.com` unter „Diese
   Websites immer aktiv lassen"; Energiesparmodus aus.
4. Windows: Ruhezustand/Standby aus (Bildschirm sperren ist ok, Chrome läuft weiter);
   PC-Neustart = Chrome per Autostart mit derselben Verknüpfung.
Mit 1–3 bleibt der Tab `visible`, also liefern auch Legende und Titel; der Socket-Weg braucht
das nicht, profitiert aber von 3–4 (kein Verwerfen des Tabs).

**Live-Beweis:** `select wurzel, count(*), min(minute), max(minute) from tv_kurs_1m group by 1`
zeigt Bars; `tv_kurse` hat NQ **und** MNQ mit Alter < 20 s, **während der TV-Tab verdeckt ist**
(Prophos-Tab davor). Dann Screenshot der Markt-View mit Kerzen.

**Was Finn am PC einmal prüfen muss (vom Mac nicht beweisbar):** (1) tickt die Legende auch,
wenn das TradingView-Fenster hinter Prophos liegt (Kopfzeile in Markt beobachten, während
Prophos vorn ist) — wenn nein: TradingView in ein eigenes, nebeneinander liegendes Fenster;
(2) erkennt das Script beide Panes (Markt-Kopf zeigt NQ und MNQ; SQL: zwei `tv_kurse`-Zeilen
für den PC); (3) Reload-Selbstheilung: Chart einfrieren lassen (Netz kurz trennen) → nach
90 s lädt die Seite neu, `reload_grund` steht im Reader-Fenster.
