-- Nicht-Starts 27.11.2026 früh nachholen (Finn ~06:50 Dubai: „Ja, nachplanen“). Nichts wurde gesendet (started_at/orbit_gesendet_at leer).
-- Ursachen: PC von Marc (pc-7ftp5l) meldet seit 26.11. 20:30 Dubai nichts, PC von Pascal (pc-3wghru) seit 22.11., am PC Finn+Pascal (pc-2zc2we)
-- liefert das Goat-Funded-Master-Terminal keinen Snapshot („Copier nicht scharf“). Die neuen Zeiten liegen bewusst am Mittag Dubai (ab 09:30 dt),
-- damit die PCs vorher wieder laufen können — bleiben sie aus, verfallen die Pläne erneut.
--   b389fcc1 Finn+Pascal Goat Funded …3752  BUY  (mt5)  → 12:34:20 Dubai
--   3102b221 Finn+Pascal Goat Funded …3687  SELL (mt5)  → 13:41:50 Dubai  (Gegenrichtung gleiche ID × Firma: 67 min nach …3752)
--   58b7ea4d Marc        FundedNext  …7821  BUY  (mt5)  → 12:47:40 Dubai  (Marc FundedNext SELL …4623 um 11:13 → 94 min)
--   b79c059d Marc        FTMO        …5199  SELL (mt5)  → 13:08:30 Dubai
--   8cae8cd3 Marc        Topstep     …8044  BUY  (tsv2) → 13:29:10 Dubai
--   8f3ce0cd Pascal      Tradeify CFD …3884 BUY  (mt5)  → 12:56:50 Dubai  (Pascal Tradeify CFD SELL …3370 um 11:44 → 72 min)
-- Wie aktion „nachholen“: start_um neu, start_um_gestartet_at null, Claim zurück, start_fehler.status 'neu'. Guard: nur planned, nichts gestartet/gesendet.

update public.trade_plans p
set start_um = v.neu,
    start_um_gestartet_at = null,
    start_claim_art = null,
    mt5_baseline = case when p.mt5_baseline ? 'start_fehler'
                        then p.mt5_baseline || jsonb_build_object('start_fehler',
                               (p.mt5_baseline->'start_fehler') || jsonb_build_object('status','neu',
                                 'behoben','nachgeholt per SQL 27.11.2026 (PC aus bzw. Goat-Terminal ohne Snapshot, Finn: nachplanen)'))
                        else p.mt5_baseline end
from (values
  ('b389fcc1'::text, timestamptz '2026-11-27 12:34:20+04'),
  ('3102b221'::text, timestamptz '2026-11-27 13:41:50+04'),
  ('58b7ea4d'::text, timestamptz '2026-11-27 12:47:40+04'),
  ('b79c059d'::text, timestamptz '2026-11-27 13:08:30+04'),
  ('8cae8cd3'::text, timestamptz '2026-11-27 13:29:10+04'),
  ('8f3ce0cd'::text, timestamptz '2026-11-27 12:56:50+04')
) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.planned_for = date '2026-11-27'
  and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null
returning left(p.id::text,8) id, p.master_firm, to_char(p.start_um at time zone 'Asia/Dubai', 'HH24:MI:SS') start_dubai;
