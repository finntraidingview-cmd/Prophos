-- Startwache 27.11.2026 ~11:42 Dubai: PC von Marc (pc-7ftp5l) meldet seit 11:37 wieder (war seit 26.11. 20:30 still). Der PC-Tab hat die verpassten
-- Echo-Pläne beim Anlauf mit start_claim_art 'verbrauch' geclaimt (= verpasst, nichts gestartet); die beiden Topstep-Pläne hat das System selbst
-- auf 11:40 / 11:46 gelegt. Nichts gesendet (started_at / orbit_gesendet_at leer). Auftrag Finn 27.11.: verpasste Starts nachplanen, sobald der PC läuft.
--   27c15c9b Marc FundedNext   …1445 BUY  (08:27 verpasst)                         → 11:52:30 Dubai
--   f7415502 Marc FTMO         …1469 SELL (10:25 verpasst)                         → 12:01:50 Dubai
--   0eeeaa2b Marc FundedNext   …4623 BUY  (11:37 „Popup geschlossen — nichts platziert“) → 12:09:20 Dubai
--   53ccc36c Marc Tradeify CFD …9558 SELL (07:06 verpasst)                         → 13:18:40 Dubai  (Gegenrichtung: Marc Tradeify CFD BUY …2673 um 12:17 → 61 min)
-- Abstände zu Marcs übrigen Starts (11:40, 11:46, 12:17, 12:47, 13:08, 13:28, 13:29) jeweils ≥ 5 min.
-- Guard: nur planned, nichts gestartet/gesendet.

update public.trade_plans p
set start_um = v.neu,
    start_um_gestartet_at = null,
    start_claim_art = null,
    mt5_baseline = case when p.mt5_baseline ? 'start_fehler'
                        then p.mt5_baseline || jsonb_build_object('start_fehler',
                               (p.mt5_baseline->'start_fehler') || jsonb_build_object('status','neu',
                                 'behoben','nachgeholt per SQL 27.11.2026 (PC von Marc wieder da, Startwache)'))
                        else p.mt5_baseline end
from (values
  ('27c15c9b'::text, timestamptz '2026-11-27 11:52:30+04'),
  ('f7415502'::text, timestamptz '2026-11-27 12:01:50+04'),
  ('0eeeaa2b'::text, timestamptz '2026-11-27 12:09:20+04'),
  ('53ccc36c'::text, timestamptz '2026-11-27 13:18:40+04')
) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.planned_for = date '2026-11-27'
  and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null
returning left(p.id::text,8) id, p.master_firm, to_char(p.start_um at time zone 'Asia/Dubai', 'HH24:MI:SS') start_dubai;
