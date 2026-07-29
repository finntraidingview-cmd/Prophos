# Topstep-Mirror-Agent (lokal pro PC)

Verlagert den Topstep-Mirror vom zentralen Railway-Server (Amsterdam) auf den PC der
jeweiligen Person. Die TopstepX-API-Verbindung kommt dann aus **der eigenen PC-IP** —
dieselbe IP wie die manuelle TopstepX-Order — statt aus Amsterdam. Damit gibt es keine
gemeinsame Amsterdam-IP mehr über mehrere Accounts.

**Berührt nichts Bestehendes.** `app.py` (Railway) und `prophos.html` bleiben unverändert;
der alte Mirror läuft weiter, bis du bewusst umschaltest. Dieser Agent ist ein separates
Programm.

## Architektur
- Steuerung **autonom über Supabase** (Tabelle `mirror_control`, siehe `sql/2026-07-29_mirror_control.sql`).
  Prophos schreibt den Auftrag rein (`active=true` + Parameter); der Agent liest seine
  Zeilen (per `agent_id`) und führt den Mirror lokal aus. Kein offener Browser/Tab nötig.
- **Secrets bleiben lokal**: TopstepX-Username/-API-Key und MetaApi-Token stehen NUR in
  `config.json` auf dem PC — nie in Supabase, nie in git.
- Mirror-Kernlogik ist 1:1 aus `app.py` portiert (Polling, `tsx_to_mt`), inkl. der dort
  dokumentierten Bugfixes (Zombie-Schutz per Session-Identität, Backoff, Token-Refresh).
  Eigene Auth über `loginKey` (Username + API-Key), damit der Agent selbstständig einloggt.

## Einrichtung pro PC (Windows, 24/7)
1. Python 3.10+ installieren.
2. Diesen Ordner auf den PC kopieren. `pip install -r requirements.txt`.
3. `config.example.json` → `config.json` kopieren und ausfüllen:
   - `agent_id`: eindeutig pro PC (z.B. `moritz-pc`).
   - `supabase_key`: am besten ein Key mit RLS, der nur die Zeilen dieses Nutzers sieht.
   - `accounts`: pro `pair_id` die drei Secrets. Der `pair_id`-Schlüssel muss exakt dem
     `pair_id` in der Supabase-Zeile entsprechen.
4. SQL `sql/2026-07-29_mirror_control.sql` einmalig im Supabase-SQL-Editor ausführen.
5. Start: `python agent.py`. Als Dauerdienst: Windows-Aufgabenplanung (bei Anmeldung,
   „neu starten bei Fehler") oder NSSM als Service. **Watchdog/Neustart ist Pflicht** —
   ein toter Agent = kein Hedge für diese Person.

## Steuerung (bis das Prophos-Frontend angebunden ist — Stufe 2)
Zeile in `mirror_control` anlegen/aktualisieren (Supabase Table Editor oder SQL):
`agent_id`, `pair_id`, `active=true`, `tsx_account_id`, `ma_account_id`, `multiplier`,
`base_instrument`, `symbol_map`. Der Agent startet innerhalb weniger Sekunden.
`active=false` stoppt ihn. Status/Log/Positions schreibt der Agent in dieselbe Zeile zurück.

## GESTUFTER TESTPLAN — vor echtem Geld zwingend
Es ist Live-Trading-Code, nicht in dieser Umgebung getestet. Bug = echter Geldverlust.
1. **Trockenlauf:** Agent starten, `mirror_control`-Zeile inaktiv → nur Steuer-Loop-Logs.
2. **Auth:** Zeile aktiv, aber KEIN Trade → prüfen, dass loginKey + `searchOpen` sauber
   durchlaufen (Log „🚀 Mirror gestartet", Heartbeats), keine 401/Fehler.
3. **Sim/Demo-Hedge:** MetaApi-Token eines DEMO-Kontos in `config.json`. Auf dem
   TopstepX-Eval/Sim-Account eine kleine Position öffnen/schließen → prüfen, dass Lots,
   Symbol-Mapping, Richtung und das Schließen exakt stimmen (mit dem alten Railway-Mirror
   vergleichen).
4. **Erst danach** echtes Hedge-Konto, klein anfangen, mitschauen.

## Was noch offen ist (Stufe 2, separat)
- Prophos-Frontend so anbinden, dass „Trade starten" die `mirror_control`-Zeile schreibt
  statt `TS_BACKEND/mirror/start` (Railway) zu rufen. Erst umschalten, wenn Stufe 1 pro
  Person sauber getestet ist. Bis dahin laufen alt (Railway) und neu (Agent) parallel —
  aber **nie beide gleichzeitig für dasselbe Konto** (doppelte Hedges).
