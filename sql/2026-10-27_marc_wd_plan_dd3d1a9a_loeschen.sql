-- MARC: GEPLANTEN WINNING-DAY-FARMER-PLAN dd3d1a9a ENTFERNEN (27.10.2026, Finn unter Marcs Login: „Wenn ich hier den Trade löschen will —
-- warum geht das nicht?" — er will den Trade weg haben). Der 🗑 der Karte sperrte geplante Farmer-Pläne (seit 28.09.2026), der Ausweg
-- „nur heute raus" war hier eine Sackgasse, weil das Konto im Tagesplan schon aktiv=false stand (puls_pause aus
-- sql/2026-10-27_marc_pc_aus_pause.sql). Code-Fix .1755 (077fb193): 🗑 trägt jetzt erst den Tagesplan aus und löscht dann.
-- Hier dasselbe einmal per SQL, in derselben Reihenfolge und nur für diesen einen, nie gestarteten Plan: Tagesplan-Eintrag austragen
-- (plan_id/status/start_um null, aktiv false, Hinweis — wie tpWdTagesplanAustragen), dann den Plan löschen.
-- Plan (zur Nachvollziehbarkeit): Apex 150k Funded (Konto a4973d33-0c64-4127-8f00-93f633608a05), Winning Day, Orbit V2 (tvv2) mit Fusion-Hedge
-- 175,44 €, SELL 3 MNQ, TP 387 $, notes 'Winning-Day-Farmer', status planned, nie gestartet.
-- Rückbau: keiner nötig — der Farmer legt für das Konto wieder einen Plan an, sobald es im Tagesplan wieder aktiv ist („heute wieder rein").

begin;

update public.wd_tagesplan w
   set konten = (select jsonb_agg(case when k->>'plan_id' = 'dd3d1a9a-1e1d-4c84-9bd7-5ecaf6c57632'
                                       then k || jsonb_build_object('plan_id', null, 'status', null, 'start_um', null, 'aktiv', false,
                                                                    'hinweis', 'Plan von Hand gelöscht')
                                       else k end order by o)
                   from jsonb_array_elements(w.konten) with ordinality as x(k, o)),
       status = case when exists (select 1 from jsonb_array_elements(w.konten) k
                                   where k->>'plan_id' is distinct from 'dd3d1a9a-1e1d-4c84-9bd7-5ecaf6c57632'
                                     and coalesce((k->>'aktiv')::boolean, true)) then w.status else 'leer' end,
       updated_at = now()
 where w.user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1'
   and w.status <> 'laeuft'
   and w.konten @> '[{"plan_id": "dd3d1a9a-1e1d-4c84-9bd7-5ecaf6c57632"}]';

delete from public.trade_plans
 where id = 'dd3d1a9a-1e1d-4c84-9bd7-5ecaf6c57632'
   and user_id = '6c206a34-c4a7-4352-8097-bb17366bcea1'
   and status = 'planned'
   and start_um_gestartet_at is null
   and started_at is null;

commit;

-- Prüfen:
-- select count(*) from trade_plans where id = 'dd3d1a9a-1e1d-4c84-9bd7-5ecaf6c57632';                       -- 0
-- select count(*) from wd_tagesplan, jsonb_array_elements(konten) k
--  where k->>'plan_id' = 'dd3d1a9a-1e1d-4c84-9bd7-5ecaf6c57632';                                            -- 0
