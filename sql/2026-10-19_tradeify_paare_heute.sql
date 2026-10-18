-- sql/2026-10-19_tradeify_paare_heute.sql — Paare Long/Short je zwei IDs, 2–10 min (Finn 19.10.2026 ~02:50 Dubai)
-- Moritz Tradeify buy 06:02:00 → 05:22:43 Dubai (Anker 05:16:00)
update trade_plans set start_um = '2026-10-19 01:22:42+00' where id = '0b745c9c-cf44-49fe-b7bf-24df87bc3d14' and status = 'planned' and start_um_gestartet_at is null and hand_werte_at is null;
-- Aurel Tradeify buy 07:35:00 → 05:34:43 Dubai (Anker 05:25:00)
update trade_plans set start_um = '2026-10-19 01:34:42+00' where id = 'd186fbbd-0073-4e38-b220-0d506de0084e' and status = 'planned' and start_um_gestartet_at is null and hand_werte_at is null;
-- Ina Tradeify buy 09:08:00 → 06:43:37 Dubai (Anker 06:34:00)
update trade_plans set start_um = '2026-10-19 02:43:37+00' where id = '2269bb01-f797-4981-80d0-18ad9c52731c' and status = 'planned' and start_um_gestartet_at is null and hand_werte_at is null;
-- Mike Tradeify buy 10:51:00 → 07:19:42 Dubai (Anker 07:16:00)
update trade_plans set start_um = '2026-10-19 03:19:41+00' where id = '9bcbdace-0f3d-45d7-b7d9-3e8679e8c9e7' and status = 'planned' and start_um_gestartet_at is null and hand_werte_at is null;
-- Mike Tradeify buy 12:33:00 → 07:48:19 Dubai (Anker 07:42:00)
update trade_plans set start_um = '2026-10-19 03:48:18+00' where id = '8dcc4cae-98bd-40b8-bca7-71ca04db05ac' and status = 'planned' and start_um_gestartet_at is null and hand_werte_at is null;
-- Marc Tradeify buy 14:50:00 → 11:08:08 Dubai (Anker 11:04:00)
update trade_plans set start_um = '2026-10-19 07:08:08+00' where id = '62c7880f-2a2d-4c63-8eb0-4f98b14a2a34' and status = 'planned' and start_um_gestartet_at is null and hand_werte_at is null;
-- Marc Tradeify buy 17:11:00 → 12:45:13 Dubai (Anker 12:43:00)
update trade_plans set start_um = '2026-10-19 08:45:13+00' where id = '9e7df883-94a8-479d-a2da-336edea4a09c' and status = 'planned' and start_um_gestartet_at is null and hand_werte_at is null;
-- Finn + Pascal Tradeify buy 17:12:00 → 14:08:48 Dubai (Anker 14:01:00)
update trade_plans set start_um = '2026-10-19 10:08:48+00' where id = '7f6c5626-9d25-4526-b5c6-93a439516b69' and status = 'planned' and start_um_gestartet_at is null and hand_werte_at is null;
-- Mike Tradeify buy 18:50:00 → 15:12:21 Dubai (Anker 15:08:00)
update trade_plans set start_um = '2026-10-19 11:12:21+00' where id = 'c27bef98-cd92-4f31-adc9-66e5f8a828ca' and status = 'planned' and start_um_gestartet_at is null and hand_werte_at is null;
-- 9 Paare, ohne Partner: []
-- Protokoll im Delta-Monitor („Umplanungen"), quelle hand = Finns Wort im Chat
insert into auto_plan_umplanung (um, plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
select now(), tp.id, tp.user_id, tp.master_firm, tp.richtung, tp.richtung, null, tp.start_um,
  '[Paar] Tradeify Long/Short je zwei IDs innerhalb 2–10 min (Finn 19.10.2026 ~02:50 Dubai) — Partner vorgezogen', 'hand'
from trade_plans tp where tp.id in ('0b745c9c-cf44-49fe-b7bf-24df87bc3d14','d186fbbd-0073-4e38-b220-0d506de0084e','2269bb01-f797-4981-80d0-18ad9c52731c',
 '9bcbdace-0f3d-45d7-b7d9-3e8679e8c9e7','8dcc4cae-98bd-40b8-bca7-71ca04db05ac','62c7880f-2a2d-4c63-8eb0-4f98b14a2a34','9e7df883-94a8-479d-a2da-336edea4a09c',
 '7f6c5626-9d25-4526-b5c6-93a439516b69','c27bef98-cd92-4f31-adc9-66e5f8a828ca');
