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
