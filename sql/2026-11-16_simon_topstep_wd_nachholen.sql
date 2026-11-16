-- Simons Topstep-WD von heute nachholen (Finn 16.11.2026 ~15:15 Dubai: „Simon TopstepX Problem wurde gelöst … wie immer, weil sich
-- Topstep so geändert hat und ich mich nur anmelden musste. Bei Simon Topstep alle Winning Days für heute neu planen, damit die gleich starten.“)
-- Vorfall: Plan b9ef909d (150k EXPRESS …24036316 → Funded, WD BUY 3 MNQ, tsv2) um 08:45 geclaimt, danach still (puls_still 08:55,
-- „in TopstepX prüfen, ob eine Order liegt“) — TopstepX war im Puls-Chrome abgemeldet. Laut Finn ist nichts offen.
-- Einziger nicht gestarteter Topstep-Plan der ID heute. Neue Startzeit 15:28 Dubai: ≥ 5 min zu Simons anderen Starts (Apex 15:20,
-- The5%ers 16:03/16:09), keine Gegenrichtung bei Topstep heute. Wie aktion „nachholen“: Claim zurück, start_fehler.status 'neu'.
-- Guard: nur, wenn noch nichts gestartet/gesendet ist. Idempotent (zweiter Lauf trifft nur noch einen Plan auf 'neu' mit gleicher Zeit).

update public.trade_plans p
set start_um = v.neu,
    start_um_gestartet_at = null,
    mt5_baseline = case when p.mt5_baseline ? 'start_fehler'
                        then jsonb_set(jsonb_set(p.mt5_baseline, '{start_fehler,status}', '"neu"'),
                                       '{start_fehler,behoben}', to_jsonb('nachgeholt per SQL 16.11.2026 (TopstepX neu angemeldet)'::text))
                        else p.mt5_baseline end
from (values
  ('b9ef909d-2f2a-4699-b9a7-f6526ca4669d'::uuid, timestamptz '2026-11-16 15:28:40+04')   -- Simon Express WD …6316 buy 3 MNQ
) as v(id, neu)
where p.id = v.id and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null
returning p.id, to_char(p.start_um at time zone 'Asia/Dubai', 'HH24:MI:SS') start_dubai;
