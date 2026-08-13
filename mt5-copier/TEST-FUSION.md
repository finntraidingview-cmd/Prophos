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
