-- DB-Ausfall 16.11.2026 ~15:15–15:25 Dubai (Projekt Prophos stand auf RESIZING, jede Abfrage „Database is possibly not accessible“).
-- Danach versehentlicher Downgrade der Org auf Free → Prophos auf NANO, DB bis ~15:37 nicht erreichbar; Finn hat Pro + Medium wieder gesetzt.
-- In der Lücke gescheitert (start_fehler rot, nichts gesendet):
--   Simon Apex 100k PAAPEX6892400000002 → Funded (0c0ac551, BUY, 15:20) → 15:48:40
--   Simon Topstep 150k EXPRESS …24036316 WD (b9ef909d, BUY, 15:28:40) → 15:42:10
--   Chris Lucid 150k LFE…0012 → Challenge (dade4041, SELL, 15:36) → 15:47:20 (Chris Lucid sonst nur SELL 17:05, keine Gegenrichtung)
-- Simon ≥ 5 min zu The5%ers 16:03/16:09; beide Simon-BUYs stehen gegen seinen offenen Lucid-SELL (Waage ok).
-- NICHT angefasst: geclaimt ohne Fehler-Stand (Echo lief evtl. schon): Marco Tradeify CFD 122566 (92f63828, 15:28) und
-- Mike FundingPips 50k 21270373 (34335c37, 15:30) — erst im MT5 prüfen, ob eine Position liegt.
-- Wie aktion „nachholen“: Claim zurück, start_fehler.status 'neu'. Guard: nichts gestartet/gesendet.
update public.trade_plans p
set start_um = v.neu,
    start_um_gestartet_at = null,
    mt5_baseline = case when p.mt5_baseline ? 'start_fehler'
                        then jsonb_set(jsonb_set(p.mt5_baseline, '{start_fehler,status}', '"neu"'),
                                       '{start_fehler,behoben}', to_jsonb('nachgeholt per SQL 16.11.2026 (DB-Resize-Ausfall)'::text))
                        else p.mt5_baseline end
from (values
  ('0c0ac551'::text, timestamptz '2026-11-16 15:48:40+04'),
  ('b9ef909d'::text, timestamptz '2026-11-16 15:42:10+04'),
  ('dade4041'::text, timestamptz '2026-11-16 15:47:20+04')
) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.start_um::date = date '2026-11-16'
  and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null
returning p.id, to_char(p.start_um at time zone 'Asia/Dubai', 'HH24:MI:SS') start_dubai;

-- Nachtrag ~15:39: Railway hat 0c0ac551 nach dem Ausfall selbst auf 15:41:29 nachgeholt („nachholen … durch ID 5409e926“) → Simons Topstep
-- b9ef909d auf 15:47:40 geschoben (≥ 5 min Abstand je ID).
update public.trade_plans set start_um = timestamptz '2026-11-16 15:47:40+04'
where id='b9ef909d-2f2a-4699-b9a7-f6526ca4669d' and status='planned' and started_at is null and start_um_gestartet_at is null and orbit_gesendet_at is null;

-- Nachtrag ~15:57: Finn hat im MT5 geprüft — Marco Tradeify CFD 122566 und Mike FundingPips 50k 21270373: keine Position (m5still nach Claim im Ausfall).
-- Dazu Mike Tradeify CFD 115906 (f6cf1c7d, SELL 15:02, m5still, Copier: Master flach). Neu eingeplant:
--   Marco 92f63828 SELL → 16:04:30 (Marcos Tradeify-CFD-BUY 121594 erst 17:49 → Gegenrichtung ≥ 60 min; ≥ 5 min zu 16:15/16:27)
--   Mike 34335c37 BUY → 16:03:50 · Mike f6cf1c7d SELL → 16:10:20 (≥ 5 min zueinander und zu Apex 16:26)
update public.trade_plans p
set start_um = v.neu, start_um_gestartet_at = null,
    mt5_baseline = case when p.mt5_baseline ? 'start_fehler'
                        then jsonb_set(jsonb_set(p.mt5_baseline, '{start_fehler,status}', '"neu"'),
                                       '{start_fehler,behoben}', to_jsonb('nachgeholt per SQL 16.11.2026 (DB-Ausfall, Finn: MT5 leer geprüft)'::text))
                        else p.mt5_baseline end
from (values
  ('92f63828'::text, timestamptz '2026-11-16 16:04:30+04'),
  ('34335c37'::text, timestamptz '2026-11-16 16:03:50+04'),
  ('f6cf1c7d'::text, timestamptz '2026-11-16 16:10:20+04')
) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.start_um::date = date '2026-11-16'
  and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null;

-- Nachtrag ~16:37: Ina Topstep-WD 150k PRO-V2 …8936 (be693a00, BUY 3 MNQ) war 07:32 geclaimt, aber nie gesendet („verpasst“);
-- Finn: „ja, neu einplanen“ → 16:43:20 Dubai (keine anderen Starts der ID im Fenster). Guard: nichts gesendet.
update public.trade_plans p
set start_um = timestamptz '2026-11-16 16:43:20+04', start_um_gestartet_at = null,
    mt5_baseline = coalesce(p.mt5_baseline,'{}'::jsonb) || jsonb_build_object('start_fehler', coalesce(p.mt5_baseline->'start_fehler','{}'::jsonb) || jsonb_build_object('status','neu','behoben','nachgeholt per SQL 16.11.2026 (WD 07:32 verpasst, Finn: neu einplanen)'))
where p.id::text like 'be693a00%' and p.status='planned' and p.started_at is null and p.orbit_gesendet_at is null;
