-- Goat Funded Trader 27.11.2026 ~15:05 Dubai (Finn: „Kannst du gucken, ob du fixen kannst?“). Ursache der drei Fehlstarts „Copier nicht scharf — warte auf
-- Snapshot des Master-Terminals“ am PC Finn+Pascal (pc-2zc2we): panel.py _inject_ea_into_profile schreibt das Lese-EA ins erste Chart des Profils
-- (Default/chart01.chr = „EURUSD“). GFT kennt nur Symbole mit Endung („EURUSD.x“) → Journal „ProphosHedgeReader (EURUSD,H1) … failed (symbol
-- synchronization timeout)“, EA entfernt, nie ein Snapshot. GT3 (25.11.) hat nur den [StartUp]-Weg auf startup_symbol umgestellt, nicht die Profil-Injektion.
-- Behoben am PC per Lotse (Terminals zu, chart01.chr symbol=EURUSD → EURUSD.x, Sicherung .goat-bak, Terminals neu gestartet): alle drei liefern seit
-- 15:03 Dubai Snapshots (Balance 100.000). Der Code-Fix in panel.py steht noch aus — neue GFT-Konten laufen sonst in denselben Fehler.
-- Nichts gesendet (started_at / orbit_gesendet_at leer). Nachholen:
--   70882092 Finn+Pascal Goat Funded …3686 SELL → 15:14:30 Dubai
--   3102b221 Finn+Pascal Goat Funded …3687 SELL → 15:22:50 Dubai
--   b389fcc1 Finn+Pascal Goat Funded …3752 BUY  → 16:24:10 Dubai  (Gegenrichtung gleiche ID × Firma: 61 min nach …3687)
-- Guard: nur planned, nichts gestartet/gesendet.

update public.trade_plans p
set start_um = v.neu,
    start_um_gestartet_at = null,
    start_claim_art = null,
    mt5_baseline = case when p.mt5_baseline ? 'start_fehler'
                        then p.mt5_baseline || jsonb_build_object('start_fehler',
                               (p.mt5_baseline->'start_fehler') || jsonb_build_object('status','neu',
                                 'behoben','nachgeholt per SQL 27.11.2026 (GFT: Lese-EA-Chart auf EURUSD.x gestellt, Snapshot fließt)'))
                        else p.mt5_baseline end
from (values
  ('70882092'::text, timestamptz '2026-11-27 15:14:30+04'),
  ('3102b221'::text, timestamptz '2026-11-27 15:22:50+04'),
  ('b389fcc1'::text, timestamptz '2026-11-27 16:24:10+04')
) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.planned_for = date '2026-11-27'
  and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null
returning left(p.id::text,8) id, p.master_firm, to_char(p.start_um at time zone 'Asia/Dubai', 'HH24:MI:SS') start_dubai;
