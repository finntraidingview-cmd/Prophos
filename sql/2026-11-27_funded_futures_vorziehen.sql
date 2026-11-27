-- Funded-Planer Futures 27.11.2026 (Finn ~06:50 Dubai, Screenshot Funded Planer: „alle innerhalb der nächsten 1 h hier starten“, danach
-- „habe alles bestätigt“ — auto_bestaetigt_at 06:51 Dubai von Finn selbst). Nur die Startzeit wird vorgezogen, Plan-Werte unverändert.
--   0d0cd57f Mike  Lucid 150k …0004  SELL 3 NQ   12:48 → 07:11:30 Dubai
--   b738aa7f Jacob Apex 100k …0003   SELL 7 MNQ  12:01 → 07:26:40 Dubai
--   495043e8 Chris Lucid 150k …0002  BUY 3 NQ    bleibt 07:42 (liegt schon in der Stunde; Chris' anderer Lucid-Start 07:17)
-- NICHT vorgezogen: Marc Apex …0002 (13:28) und …0005 (16:32) — PC von Marc (pc-7ftp5l) ist seit 26.11. 20:30 Dubai aus, dazu wären SELL und BUY
--   bei derselben ID × Firma gleichzeitig offen (Gegenrichtung hart).
-- VERSCHOBEN statt verfallen: c828432b Pascal Lucid 150k …0003 BUY 3 NQ, 06:53 → 13:15:20 Dubai — PC von Pascal (pc-3wghru) ist seit 22.11. aus.
-- Guard: nur planned, nichts gestartet/gesendet.

update public.trade_plans p
set start_um = v.neu, start_um_gestartet_at = null
from (values
  ('0d0cd57f'::text, timestamptz '2026-11-27 07:11:30+04'),
  ('b738aa7f'::text, timestamptz '2026-11-27 07:26:40+04'),
  ('c828432b'::text, timestamptz '2026-11-27 13:15:20+04')
) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.planned_for = date '2026-11-27'
  and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null and p.start_claim_art is null
returning left(p.id::text,8) id, p.master_firm, to_char(p.start_um at time zone 'Asia/Dubai', 'HH24:MI:SS') start_dubai;
