-- MARC: WINNING DAY APEX 150k …0001 NEU EINPLANEN AUF 17:20 DUBAI (22.10.2026 ~16:50 Dubai, Finn: „ok top dann plane den Trade jetzt neu
-- für 17:20 Uhr")
-- Anlass: Plan 842453ce stand seit 13:14 Dubai im Auto-Start „Angehalten" (Vorcheck slave_nicht_bereit: Fusion-Marge für 32,00 Lot). Die
-- Lots sind korrigiert (sql/2026-10-22_marc_wd_hedge_lots_mnq.sql, 3,20 Lot, Code-Fix .1712), die Tageszeile stand auf „verpasst".
-- Neu: Start 17:20:00 Dubai = 13:20 UTC, Claim und Vorcheck leer — wie sql/2026-10-22_marc_wd_neu_einplanen.sql heute Morgen.
-- Angewendet 22.10.2026 direkt gegen die DB.
update public.trade_plans
   set start_um = '2026-10-22 13:20:00+00',
       start_um_gestartet_at = null,
       orbit_gesendet_at = null,
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) - 'vorcheck'
 where id = '842453ce-b91c-46d9-aa0b-c901927c9f53'
   and status = 'planned'
   and started_at is null;

update public.wd_tagesplan
   set status = 'geplant',
       start_um = '2026-10-22 13:20:00+00',
       konten = (select jsonb_agg(case when k->>'plan_id' = '842453ce-b91c-46d9-aa0b-c901927c9f53'
                                       then (k - 'vorcheck') || jsonb_build_object('status', 'planned', 'start_um', '2026-10-22T13:20:00.000Z', 'um', null, 'gesendet', false)
                                       else k end)
                   from jsonb_array_elements(konten) k),
       updated_at = now()
 where tag = '2026-10-22'
   and user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1';
