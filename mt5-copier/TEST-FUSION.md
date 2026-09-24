# Erster Test mit zwei Fusion-Demo-Konten

Ziel: beweisen, dass der Copier richtig rechnet und richtig ausführt — mit Spielgeld, ohne
Prop-Konto, ohne dass Duplikum berührt wird.

**Warum dieses Setup gut ist:** Beide Konten liegen beim selben Broker → identische
Symbolnamen und Kontraktgrößen. Damit testest du nur die Copier-Logik, ohne dass
Symbol-Mapping oder Kontraktgrößen dazwischenfunken. Und es ist kein Prop-Konto beteiligt.

    Demo-Konto A (Master)          gemeinsamer Ordner        Demo-Konto B (Hedge)
    MT5 #1 + Lese-EA          →    prophos_master.csv   →    MT5 #2 + copier.py
    (hier machst du Trades)                                  (hier erscheint der Hedge)

## Schon erledigt (nichts zu tun)
Die Rechenlogik ist geprüft: `python3 selftest.py` → **15/15 Tests bestanden**, u.a.
Richtung gedreht, Teil-Schließung, Aufstocken, Kontraktgrößen-Umrechnung, Lot-Rundung,
Sicherheitsgrenze, Doppel-Hedge-Schutz. Der Test läuft ohne MetaTrader, auch auf dem Mac.

## Schritt 1 — Windows-PC vorbereiten
1. Python von python.org installieren, Häkchen **„Add python.exe to PATH"**.
2. Ordner `mt5-copier` auf den PC kopieren (oder Repo per ZIP von GitHub).
3. Im Ordner `cmd` öffnen, dann: `pip install MetaTrader5`

## Schritt 2 — zwei MT5-Installationen
Ein Terminal kann nur ein Konto halten, deshalb zwei getrennte Ordner:
- `C:\MT5-Master` → **Demo-Konto A** einloggen (das wird „der Master").
- `C:\MT5-Hedge`  → **Demo-Konto B** einloggen (dort erscheint der Hedge).
Die zweite Installation über eine Verknüpfung mit dem Zusatz `/portable` starten.
Im **Hedge**-Terminal „Algo Trading" aktivieren (Extras → Optionen → Expert Advisors).
Im Master-Terminal nicht nötig — dort wird nur gelesen.

## Schritt 3 — Lese-EA auf Konto A
1. Im **Master**-Terminal: F4 (MetaEditor) → `ProphosHedgeReader.mq5` öffnen → F7 (kompilieren).
2. Zurück im Terminal: EA aus dem Navigator auf einen beliebigen Chart ziehen.
3. Im Reiter **Experten** muss stehen: `ProphosHedgeReader gestartet — Konto … (nur lesend)`.

## Schritt 4 — Config
`config.fusion-test.json` → nach `config.json` kopieren und **vier Werte** eintragen:
- `hedge_terminal_path` → Pfad zur `terminal64.exe` von `C:\MT5-Hedge`
- `hedge_expected_login` → Kontonummer B
- `master_expected_login` → Kontonummer A
- `symbol_map` → das Symbol ergänzen, mit dem du testen willst (falls nicht dabei)

Alles andere ist schon passend: `mode: "demo"`, `multiplier: 1.0` (Hedge hat dieselbe
Lotgröße wie der Master — am leichtesten zu prüfen), `max_lots_per_hedge: 2.0`.

## Schritt 5 — starten und testen
`start-copier.bat` doppelklicken. Im Fenster muss stehen:

    Verbunden mit Terminal: C:\MT5-Hedge\terminal64.exe
    Konto <B> @ FusionMarkets-Demo · DEMO/CONTEST
    ✓ Snapshot verbunden — Master-Konto <A> …

Bricht es hier ab, ist eine der vier Config-Zeilen falsch — die Meldung sagt welche.

Dann der eigentliche Test, in dieser Reihenfolge:

| # | Was du auf Konto A machst | Was auf Konto B passieren muss |
|---|---|---|
| 1 | BUY 0.10 NAS100 öffnen | SELL 0.10 NAS100 erscheint |
| 2 | Position auf 0.06 teil-schließen | Hedge geht auf 0.06 runter |
| 3 | auf 0.20 aufstocken | Hedge geht auf 0.20 hoch |
| 4 | Position komplett schließen | Hedge verschwindet |
| 5 | SELL 0.10 NAS100 öffnen | BUY 0.10 NAS100 erscheint (Richtung gedreht) |
| 6 | Copier-Fenster schließen, neu starten, dann Master schließen | Hedge wird trotzdem korrekt geschlossen (Recovery) |

Läuft das durch, ist der Copier funktional bewiesen. **Erst danach** wird über ein echtes
Prop-Konto und echtes Geld geredet — und dann für dieses Paar Duplikum abgeschaltet.

## Wenn etwas nicht klappt
Die Meldung im Fenster kopieren und schicken. Häufige Fälle:
- `initialize() fehlgeschlagen` → Hedge-Terminal läuft nicht oder Pfad falsch.
- `Terminal-Pfad weicht ab` → bekanntes MT5-Verhalten; das Hedge-Terminal muss laufen,
  am besten als **einziges** starten, dann den Copier.
- `NICHT im Hedging-Modus` → das Demo-Konto ist ein Netting-Konto; bei Fusion ein
  Hedging-Demo-Konto anlegen.
- `Algo Trading ist nicht aktiv` → im Hedge-Terminal einschalten.
- `Warte auf Snapshot` bleibt stehen → das EA läuft nicht auf einem Chart im Master-Terminal.

## Erster echter Winning-Days-Farm-Hedge — Checkliste (Stand 25.09.2026)

Reihenfolge einhalten, jeder Punkt ist ein Beweis, kein Klick ins Blaue.

**Vorbedingung 0:** Fusion 488579 braucht **Marge** — heute 0 €. Ohne Guthaben lehnt der Broker die
Gegen-Order ab (`abgelehnt`, retcode „not enough money"); erst einzahlen, dann starten.

**Voraussetzungen am PC**
1. Copier läuft mit Version ≥ `.512` (notfall_faktor + Grund-Durchreichung; Copier-Fenster: Kopfzeile,
   oder Prophos → Echo → Instanz-Chip).
2. Fusion-Terminal (`C:\MT5-Hedge`) offen, **Algo-Handel AN** (Knopf oben grün), Symbol **NAS100** in der
   Marktübersicht sichtbar.
3. Prophos-PC-Tab mit Build ≥ `.516` (Feed-Wächter, Puffer in Ticks; Versions-Leiste unten), eingeloggt in
   die ID, deren Konto gehedgt wird.
4. Kein Echo-Not-Aus (Pause) aktiv — ein Solo-Open wird sonst mit `pausiert` abgelehnt.
5. **Kurs-Feed läuft:** der Markt-Kopf in Prophos zeigt NQ/MNQ „live · vor x s" (Reader-PC mit Userscript
   ≥ 0.8.0, siehe `tv-reader/README.md`). Ohne Feed schließt nur das Netz im Terminal — kein Wächter.

**Kleinster Plan**
6. Trade-Plan → Weg **Winning Days Farm** → Funded-Futures-Konto wählen → 1 MNQ, kleiner TP (z. B. 30 $),
   **Risiko Master ($)** = Stop-Distanz, z. B. 30 $, **Risiko Slave (€)** z. B. 10 € — die Multiplikator-Box
   zeigt die Fusion-Lots (Kontrakte × Multiplikator) → Speichern.
7. „Starten" (PC oder Mac). Puls platziert in TradingView; in der Sekunde des bestätigten Buy-Klicks geht
   die Gegen-Order auf Fusion raus.

**Was in MetaTrader zu sehen sein muss**
8. Position auf NAS100, Kommentar `PXsolo`, Magic 790001, Richtung = Gegenseite des Masters, Lots wie in
   der Multiplikator-Box.
9. **SL UND TP gesetzt:** SL = Fill ± TP-Distanz × 1,10 (Notfall, Finn: „110 % vom Master-Take-Profit"),
   TP = Fill ∓ (SL-Distanz + Puffer) — Reserve HINTER dem Master-SL. Fehlt eines, steht in Prophos
   `sl_fehler`/`tp_fehler` mit dem Retcode.

**Was in Prophos zu sehen sein muss**
10. Karte: Chip „FUSION SELL 0,xx Lot · ±x,xx € · schließt bei NQ 31.002 · Notfall 20.143 / 19.870" —
    „schließt bei" = Master-TP ± 8 Ticks (Kurs-Feed), „Notfall" = die beiden Terminal-Level; Live-P&L aus
    dem Copier-Status, auch am Mac über `mt5_live`. Unter dem Markt-Chart steht der Plan mit Entry/TP/SL-
    Linien und Δ TP.
11. **Normalweg:** der Wächter im PC-Tab schließt über den NQ-Feed (Grund `tp_feed` bei Master-TP + 8 Ticks,
    `sl_feed` bei Master-SL). **Netz:** erreicht der Kurs vorher ein Terminal-Level, schließt der Broker; der
    Copier erkennt es selbst (`hedge_solo_zu`, Grund `level_tp`/`level_sl` = Notfall gefüllt) und der
    PC-Tab bucht es auf die Karte.

**Abbrechen**
12. Knopf **„Hedge zu"** auf der Karte (nur am PC, der den Hedge hält) → Grund `hand`.
13. Oder von Hand im Terminal schließen → der Copier bucht es mit Grund `hand`. Nie den Copier beenden,
    solange die Position offen ist — der Close-Auftrag braucht ihn.

Gelingt 8–11, ist der Weg bewiesen. Beim ersten Fehlschlag: Copier-Fenster-Meldung + Chip-Tooltip kopieren
und schicken.
