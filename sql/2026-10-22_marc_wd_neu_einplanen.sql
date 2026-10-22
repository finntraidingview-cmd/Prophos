-- MARC: WINNING DAY APEX 150k …0001 NEU EINPLANEN (22.10.2026 ~09:10 Dubai, Finn: „bei Marc einmal noch die Uhrzeit ein bisschen nach
-- hinten verstellen, weil der Puffer jetzt passt")
-- Anlass: Plan 842453ce (Farmer, Start 05:20 Dubai) wartete 79 Prüfungen lang im Slave-Vorcheck auf Fusion-Marge (frei 4.066 € · nötig
-- ≈ 8.407 € für 32 Lot BUY) und lief um 06:20 als „verpasst_slave" aus (Claim gesetzt, nie gesendet). Finn hat die Marge aufgestockt.
-- Neu: Start 09:24:37 Dubai (vor Chris 09:44 — Fusion noch ohne andere WD-Hedges), Claim und Vorcheck leer, wie „Neu einplanen" per DB
-- (prophos-neu-starten-nach-fensterschluss). Tageszeile Marc: Status/Startzeit nachgezogen, damit der Farmer-Abgleich ihn wieder führt.
-- Angewendet 22.10.2026 direkt gegen die DB.
update public.trade_plans
   set start_um = '2026-10-22 05:24:37+00',
       start_um_gestartet_at = null,
       orbit_gesendet_at = null,
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) - 'vorcheck'
 where id = '842453ce-b91c-46d9-aa0b-c901927c9f53'
   and status = 'planned'
   and started_at is null;

update public.wd_tagesplan
   set status = 'geplant',
       start_um = '2026-10-22 05:24:37+00',
       konten = (select jsonb_agg(case when k->>'plan_id' = '842453ce-b91c-46d9-aa0b-c901927c9f53'
                                       then (k - 'vorcheck') || jsonb_build_object('status', 'planned', 'start_um', '2026-10-22T05:24:37.000Z', 'um', null, 'gesendet', false)
                                       else k end)
                   from jsonb_array_elements(konten) k),
       updated_at = now()
 where tag = '2026-10-22'
   and user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1';
