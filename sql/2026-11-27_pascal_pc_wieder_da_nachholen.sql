-- Startwache 27.11.2026 ~14:53 Dubai: PC von Pascal (pc-3wghru) lief seit dem Windows-Neustart am 22.11. ohne Prophos-Stack (Autostart-Ordner leer,
-- kein Backend/Copier/Panel/Reader, kein Puls-Chrome). Per Lotse gestartet: start-alles.bat, Puls-Chrome, Prophos-Tab (localhost:5000) — mt5_live meldet
-- seit 14:52 wieder. Der PC-Tab hat die drei verpassten Pläne mit start_claim_art 'verbrauch' geclaimt, nichts gesendet. Auftrag Finn 27.11.: nachplanen.
--   8f3ce0cd Pascal Tradeify CFD …3884 BUY  (12:56 verpasst) → 15:04:30 Dubai
--   c828432b Pascal Lucid 150k   …0003 BUY 3 NQ (13:15 verpasst) → 15:16:40 Dubai
--   ad594d07 Pascal Tradeify CFD …3370 SELL (11:44 verpasst) → 16:08:20 Dubai  (Gegenrichtung gleiche ID × Firma: 64 min nach …3884)
-- Guard: nur planned, nichts gestartet/gesendet.

update public.trade_plans p
set start_um = v.neu,
    start_um_gestartet_at = null,
    start_claim_art = null,
    mt5_baseline = case when p.mt5_baseline ? 'start_fehler'
                        then p.mt5_baseline || jsonb_build_object('start_fehler',
                               (p.mt5_baseline->'start_fehler') || jsonb_build_object('status','neu',
                                 'behoben','nachgeholt per SQL 27.11.2026 (PC von Pascal per Lotse wieder gestartet, Startwache)'))
                        else p.mt5_baseline end
from (values
  ('8f3ce0cd'::text, timestamptz '2026-11-27 15:04:30+04'),
  ('c828432b'::text, timestamptz '2026-11-27 15:16:40+04'),
  ('ad594d07'::text, timestamptz '2026-11-27 16:08:20+04')
) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.planned_for = date '2026-11-27'
  and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null
returning left(p.id::text,8) id, p.master_firm, to_char(p.start_um at time zone 'Asia/Dubai', 'HH24:MI:SS') start_dubai;
