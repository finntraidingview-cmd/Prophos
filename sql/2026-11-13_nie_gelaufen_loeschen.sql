-- Zwei Pläne vom 12.11., die nie gelaufen sind, löschen (Finn 13.11.2026 ~03:10 Dubai: „Kannst du alle Trades hier abhaken, die sind noch von gestern und haben
-- kein P&L“ → Rückfrage löschen statt 0 abhaken → „Ja, löschen“). Wie NG1/NG2 (bewiesen nicht gelaufen → Plan weg), damit kein 0-$-Tag als Handelstag zählt.
-- a5204eb4 Simon FundingPips 100k 21196932 → Phase 2: Panel klickte nicht („Copier liefert keine frischen Daten — Order würde UNGEHEDGET bleiben“), kein Fill.
-- 13b6397d Marc Topstep 150k …80376187 → Challenge: Futures-Waage sperrte bis „aufgegeben“; Finn hat in TopstepX geprüft: kein Trade am 12.11.
-- Guard: nie gestartet, kein P&L, nichts gesendet. polar_lauf hängt per ON DELETE CASCADE dran (für diese Pläne leer).
delete from public.trade_plans
 where id::text in (select id::text from public.trade_plans where (id::text like 'a5204eb4%' or id::text like '13b6397d%'))
   and started_at is null and master_pl is null and orbit_gesendet_at is null and planned_for = '2026-11-12';
