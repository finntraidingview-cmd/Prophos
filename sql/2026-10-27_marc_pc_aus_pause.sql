-- MARC: PC AUS AM 27.10.2026 (Finn 27.10.2026 ~02:35 Dubai: „Marks PC ist aus … den morgen aus dem Trade Planner herauspacken").
-- „Mark" = ID Marc (user 6c206a34…, PC pc-7ftp5l). Ohne PC laufen seine Starts nur in „keine Antwort vom PC".
-- Muster wie sql/2026-10-15_puls_pause_finn_pascal_jacob.sql (starke Form, coalesce gegen mt5_baseline NULL):
--   1. Marc aus auto_plan_regeln.user_ids — Nachtlauf, Nachplan-Takt und Ausgleich legen nichts Neues an
--      (Marc ist kein Admin-Login, verliert also keinen Admin-Reiter).
--   2. alle geplanten, nicht gestarteten Pläne (7 Auto + 1 WD-Hand-Plan Apex PA 11:37 UTC) stillgelegt: unbestätigt,
--      start_um 01.01.2027, Marke mt5_baseline.puls_pause mit start_um_war/bestaetigt_war.
--   3. WD-Tagesplan 27.10. (1 Konto) abgewählt, sonst setzt der Tab ihn auf „geplant" zurück.
-- Eingespielt vom Master 27.10.2026 ~02:40 Dubai.

update public.auto_plan_regeln
   set user_ids = array_remove(user_ids, '6c206a34-c4a7-4352-8097-bb17366bcea1'::uuid), updated_at = now()
 where id = 1;

update public.trade_plans
   set auto_bestaetigt_at = null,
       start_um = '2027-01-01 00:00:00+00',
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('puls_pause', jsonb_build_object(
           'at', '2026-10-27T00:00:00Z',
           'grund', 'Marcs PC aus am 27.10.2026 — aus dem Planer genommen (Finn)',
           'start_um_war', start_um,
           'bestaetigt_war', (auto_bestaetigt_at is not null),
           'stillgelegt_at', now()))
 where user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1'
   and status = 'planned' and start_um_gestartet_at is null and start_um is not null
   and not coalesce(mt5_baseline ? 'puls_pause', false);

update public.wd_tagesplan
   set konten = (select jsonb_agg(k || '{"aktiv": false, "hinweis": "PC aus 27.10.2026 — aus dem Planer genommen", "puls_pause": true}'::jsonb) from jsonb_array_elements(konten) k),
       status = 'leer', start_um = null, updated_at = now()
 where user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1' and tag = '2026-10-27' and status <> 'laeuft';

-- RÜCKWEG (sobald der PC wieder an ist) — Marc zurück in den Planer; die alten Startzeiten sind dann meist vorbei,
-- deshalb die stillgelegten Pläne löschen statt zurückholen, der Nachplan-Takt plant neu:
-- update public.auto_plan_regeln set user_ids = array_append(user_ids, '6c206a34-c4a7-4352-8097-bb17366bcea1'::uuid), updated_at = now()
--  where id = 1 and not ('6c206a34-c4a7-4352-8097-bb17366bcea1'::uuid = any(user_ids));
-- delete from public.trade_plans where user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1' and status = 'planned'
--    and auto_plan and mt5_baseline->'puls_pause'->>'at' = '2026-10-27T00:00:00Z';
-- Der WD-Hand-Plan (auto_plan = false) und der Tagesplan bleiben stillgelegt — Finn entscheidet, ob er neu angelegt wird.

-- RÜCKWEG GEFAHREN 27.10.2026 ~14:25 Dubai (Finn: „Mark wieder zum Trade-Planer hinzugefügt, heute läuft der PC wieder"):
-- Marc stand schon wieder in user_ids (Finn per Admin); die 7 stillgelegten Auto-Pläne gelöscht (sonst sieht der Planer die Konten
-- als „Plan liegt noch" und plant nicht neu). WD-Hand-Plan dd3d1a9a + Tagesplan 27.10. bleiben stillgelegt (Finn entscheidet).
