-- PULS-PAUSE FINN + PASCAL und JACOB (15.10.2026 ~04:10 Dubai / 00:10 UTC, Finn: „keine neuen Orders bei Puls platzieren lassen,
-- weil es gerade so langsam schief läuft … bis ich das Go gebe" — beide IDs stecken in einem Big Trade, Finn hedgt per Hand).
-- Gleiches Muster wie sql/2026-10-14_puls_pause_mike_moritz.sql, gleich in der starken Form (Nachtrag dort: die Marke allein hielt
-- nicht, „alle bestätigen" setzte auto_bestaetigt_at wieder; seit .1551 verweigert das Backend „bestaetigen" bei puls_pause).
-- Betroffen: Finn + Pascal (finnh4799, 48f272b4…) und Jacob (368076fd…). Laufende Big Trades (je ein open-Plan) bleiben unberührt.
--   1. beide IDs aus auto_plan_regeln.user_ids — Nachtlauf, Nachplan-Takt und Ausgleichs-Bot legen nichts Neues an.
--   2. alle geplanten, nicht gestarteten Pläne (Auto UND Hand, inkl. Jacobs zwei Winning-Day-Farmer-Pläne) stillgelegt:
--      auto_bestaetigt_at = null, start_um = 01.01.2027, Marke mt5_baseline.puls_pause mit start_um_war/bestaetigt_war.
--      ACHTUNG beim Nachbauen: mt5_baseline ist bei frischen Plänen NULL → „not (mt5_baseline ? 'puls_pause')" ist NULL, trifft nichts.
--      Deshalb coalesce(…, false). Der erste Versuch 00:10 UTC griff genau deshalb nicht.
--   3. Jacobs Winning-Day-Tagesplan 15.10.: Konten auf aktiv=false („heute abgewählt") mit Hinweis + puls_pause=true, status leer,
--      start_um null — der Tab setzt status sonst aus den aktiven Konten auf „geplant" zurück. Plan-IDs bleiben in den Konten stehen.
-- Angewendet 15.10.2026 00:10–00:16 UTC direkt gegen die DB: 7 Pläne Finn + Pascal, 5 Pläne Jacob, 1 Tagesplan-Zeile.
update public.auto_plan_regeln
   set user_ids = array_remove(array_remove(user_ids, '48f272b4-913e-4598-a06a-1dcc3d5679fb'::uuid), '368076fd-67c1-460c-aa86-38d81ae69350'::uuid),
       updated_at = now()
 where id = 1;
update public.trade_plans
   set auto_bestaetigt_at = null,
       start_um = '2027-01-01 00:00:00+00',
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('puls_pause', jsonb_build_object(
           'at', '2026-10-15T00:10:00Z',
           'grund', 'Big Trades laufen bei Finn + Pascal und Jacob — keine weiteren Puls-Orders bis Finn freigibt',
           'start_um_war', start_um,
           'bestaetigt_war', (auto_bestaetigt_at is not null),
           'stillgelegt_at', now()))
 where user_id in ('48f272b4-913e-4598-a06a-1dcc3d5679fb','368076fd-67c1-460c-aa86-38d81ae69350')
   and status = 'planned' and start_um_gestartet_at is null and start_um is not null
   and not coalesce(mt5_baseline ? 'puls_pause', false);
update public.wd_tagesplan
   set konten = (select jsonb_agg(k || '{"aktiv": false, "hinweis": "Puls-Pause 15.10.2026 (Big Trade läuft) — bis Finn freigibt", "puls_pause": true}'::jsonb) from jsonb_array_elements(konten) k),
       status = 'leer', start_um = null, updated_at = now()
 where user_id = '368076fd-67c1-460c-aa86-38d81ae69350' and tag = '2026-10-15' and status <> 'laeuft';

-- RÜCKWEG (sobald Finn das Go gibt) — Startzeiten sind dann vermutlich vorbei, der Nachplan-Takt plant neu:
-- update public.auto_plan_regeln set user_ids = user_ids || array['48f272b4-913e-4598-a06a-1dcc3d5679fb'::uuid,'368076fd-67c1-460c-aa86-38d81ae69350'::uuid], updated_at = now() where id = 1;
-- update public.trade_plans
--    set start_um = (mt5_baseline->'puls_pause'->>'start_um_war')::timestamptz,
--        auto_bestaetigt_at = case when (mt5_baseline->'puls_pause'->>'bestaetigt_war')::boolean then now() else null end,
--        mt5_baseline = mt5_baseline - 'puls_pause'
--  where user_id in ('48f272b4-913e-4598-a06a-1dcc3d5679fb','368076fd-67c1-460c-aa86-38d81ae69350')
--    and status = 'planned' and mt5_baseline->'puls_pause'->>'at' = '2026-10-15T00:10:00Z';
-- Jacobs Tagesplan 15.10. (war: status geplant, start_um 2026-10-15 02:07 UTC, richtung sell, reihenfolge 1, beide Konten aktiv):
-- update public.wd_tagesplan
--    set konten = (select jsonb_agg((k - 'puls_pause') || '{"aktiv": true, "hinweis": ""}'::jsonb) from jsonb_array_elements(konten) k),
--        status = 'geplant', start_um = '2026-10-15 02:07:00+00', updated_at = now()
--  where user_id = '368076fd-67c1-460c-aa86-38d81ae69350' and tag = '2026-10-15' and status <> 'laeuft';

-- NACHTRAG 15.10.2026 ~04:50 Dubai (Finn: „warum sehe ich nix" — Admin-Reiter „Trade-Planer" zeigte nur AP_NUR_PLANER_TXT):
-- der Admin-Reiter gibt Nicht-ADMIN_EMAILS-Logins alle IDs NUR, wenn die ID in auto_plan_regeln.user_ids steht (ap_eingriff_sicht,
-- Option A 08.10.2026). „Finn + Pascal" aus user_ids zu nehmen hat Finn also den Admin-Planer weggenommen. Deshalb: ID zurück in
-- user_ids, und die Pause stattdessen über den Auto-Planer-Haken je Konto (accounts.auto_planer = false) — der Nachtlauf/Nachplan-Takt
-- lässt solche Konten sichtbar aus („vom Auto-Planer ausgenommen (Haken im Konto aus)"). Jacob bleibt draußen (braucht keinen Admin).
-- 12 Konten von Finn + Pascal hatten den Haken an (nicht archiviert), alle auf aus gesetzt:
update public.accounts set auto_planer = false, updated_at = now()
 where id in ('85b1b2a1-8bf1-4c09-8bb1-b3e9520b8896','6599c953-8212-4047-8280-6dcfc46e3fd0','62b824a2-b4bb-43f9-90cd-c93e995cfd49',
              '7e0b32ce-659c-49c2-98b1-77279ea3319d','a1c49326-da3e-4b38-bd1a-4373787e3d1a','453f5f37-6d6c-4b0b-996a-4a40c448d761',
              'b329a48c-63c0-4091-9222-ed3864160b75','cf9e8e34-fa49-42bf-b092-cc64084aea0a','917a57ca-045b-47d2-84dd-cdf20f24116b',
              'cf4824e5-bd33-42e2-8902-9af33a58bb65','7cd83686-1fb2-481f-8eea-4759346ccffb','103c974d-b311-4ac4-9175-93eb6faaa32a')
   and user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and auto_planer = true;
update public.auto_plan_regeln set user_ids = array_append(user_ids, '48f272b4-913e-4598-a06a-1dcc3d5679fb'::uuid), updated_at = now()
 where id = 1 and not ('48f272b4-913e-4598-a06a-1dcc3d5679fb'::uuid = any(user_ids));
-- RÜCKWEG dazu (mit der Freigabe): die 12 Konten wieder auf auto_planer = true (selbe id-Liste), user_ids-Zeile oben dann nur für Jacob.

-- FREIGABE 15.10.2026 10:54 Dubai (Finn: „big trade is durch bei beiden, wieder normale orders machen") — Rückweg gefahren:
-- Jacob zurück in user_ids; 12 Konten von Finn + Pascal wieder auto_planer = true; 12 Pläne zurück auf start_um_war + Bestätigung wie
-- vorher, Marke puls_pause → puls_pause_ende. Drei Auto-Pläne hatten ihre Startzeit schon hinter sich (F+P 01:59 und 05:57 UTC,
-- Jacob Apex 06:00 UTC) — die gestaffelt auf jetzt+10/20/30 min statt alle sofort. Jacobs Tagesplan 15.10. wieder geplant/aktiv.
update public.auto_plan_regeln set user_ids = array_append(user_ids, '368076fd-67c1-460c-aa86-38d81ae69350'::uuid), updated_at = now()
 where id = 1 and not ('368076fd-67c1-460c-aa86-38d81ae69350'::uuid = any(user_ids));
update public.accounts set auto_planer = true, updated_at = now()
 where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and auto_planer = false and id in (/* 12 ids wie oben */ '85b1b2a1-8bf1-4c09-8bb1-b3e9520b8896','6599c953-8212-4047-8280-6dcfc46e3fd0','62b824a2-b4bb-43f9-90cd-c93e995cfd49','7e0b32ce-659c-49c2-98b1-77279ea3319d','a1c49326-da3e-4b38-bd1a-4373787e3d1a','453f5f37-6d6c-4b0b-996a-4a40c448d761','b329a48c-63c0-4091-9222-ed3864160b75','cf9e8e34-fa49-42bf-b092-cc64084aea0a','917a57ca-045b-47d2-84dd-cdf20f24116b','cf4824e5-bd33-42e2-8902-9af33a58bb65','7cd83686-1fb2-481f-8eea-4759346ccffb','103c974d-b311-4ac4-9175-93eb6faaa32a');
update public.trade_plans set start_um = now() + interval '10 minutes' where id = 'c769ca35-72c6-4659-8bb4-d7b7f24b0e41' and status='planned';
update public.trade_plans set start_um = now() + interval '20 minutes' where id = 'ed3c376b-92e6-4f06-8c11-016fd2dedcb5' and status='planned';
update public.trade_plans set start_um = now() + interval '30 minutes' where id = 'ecdf5a2e-d147-4628-8d3a-8261e8c602a9' and status='planned';
update public.trade_plans
   set start_um = case when id in ('c769ca35-72c6-4659-8bb4-d7b7f24b0e41','ed3c376b-92e6-4f06-8c11-016fd2dedcb5','ecdf5a2e-d147-4628-8d3a-8261e8c602a9') then start_um else (mt5_baseline->'puls_pause'->>'start_um_war')::timestamptz end,
       auto_bestaetigt_at = case when (mt5_baseline->'puls_pause'->>'bestaetigt_war')::boolean then now() else null end,
       mt5_baseline = (mt5_baseline - 'puls_pause') || jsonb_build_object('puls_pause_ende', jsonb_build_object('at', now(), 'grund', 'Finn 10:54 Dubai: Big Trade durch, wieder normale Orders'))
 where status = 'planned' and mt5_baseline->'puls_pause'->>'at' = '2026-10-15T00:10:00Z';
update public.wd_tagesplan
   set konten = (select jsonb_agg((k - 'puls_pause') || '{"aktiv": true, "hinweis": ""}'::jsonb) from jsonb_array_elements(konten) k),
       status = 'geplant', start_um = '2026-10-15 02:07:00+00', updated_at = now()
 where user_id = '368076fd-67c1-460c-aa86-38d81ae69350' and tag = '2026-10-15' and status <> 'laeuft';
