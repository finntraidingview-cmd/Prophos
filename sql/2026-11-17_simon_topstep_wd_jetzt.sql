-- Simons Topstep-WDs 17.11.2026 jetzt starten (Finn ~06:56 Dubai: „Ich habe es weggeklickt … Bei Simon bitte jetzt beide direkt neu starten.“).
-- Ursache der Fehlstarts: TopstepX-Werbe-Popup „Give 50% Off – Friendsgiving“ unten rechts → Vorprüfung „Dialog offen ('')“, nichts platziert
-- (4be65fa2 06:48, vorher 5cd9f337 Time-Sync-Dialog). Finn hat das Popup geschlossen.
--   4be65fa2 Express …2392 SELL 3 MNQ → 07:04:20 Dubai
--   5cd9f337 Express …6316 SELL 3 MNQ → 07:10:40 Dubai (Farmer-Block war 12:49 — Finn will jetzt)
-- Abstände: Simons Apex-Challenge 06:59, FundingPips 07:46; beide SELL Topstep (keine Gegenrichtung).
-- wd_tagesplan: start_um UND g_versatz_min (relativ zum Blockstart 12:49) mitziehen — sonst setzt wdAbgleich Gruppe 1 / Versatz 0 auf 12:49
-- zurück (so geschehen 06:29 mit 5cd9f337). Guard: nichts gestartet/gesendet.

update public.trade_plans p
set start_um = v.neu, start_um_gestartet_at = null,
    mt5_baseline = coalesce(p.mt5_baseline,'{}'::jsonb) || jsonb_build_object('start_fehler',
                     coalesce(p.mt5_baseline->'start_fehler','{}'::jsonb) || jsonb_build_object('status','neu',
                       'behoben','nachgeholt per SQL 17.11.2026 (TopstepX-Werbe-Popup, Finn: jetzt starten)'))
from (values ('4be65fa2'::text, timestamptz '2026-11-17 07:04:20+04'),
             ('5cd9f337'::text, timestamptz '2026-11-17 07:10:40+04')) as v(kurz, neu)
where left(p.id::text, 8) = v.kurz and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null;

update public.wd_tagesplan w
set konten = (select jsonb_agg(case when v.kurz is not null
                                    then e.k || jsonb_build_object('start_um', v.neu, 'status', 'planned', 'um', null, 'g_versatz_min', v.vers)
                                    else e.k end order by e.i)
              from jsonb_array_elements(w.konten) with ordinality e(k, i)
              left join (values ('4be65fa2', '2026-11-17T03:04:20.000Z', -344.6667),
                                ('5cd9f337', '2026-11-17T03:10:40.000Z', -338.3333)) v(kurz, neu, vers) on v.kurz = left(e.k->>'plan_id',8)),
    updated_at = now()
where w.tag = date '2026-11-17' and w.user_id = '5409e926-09bc-4789-9c99-f8584d87a89a';

-- Nachtrag ~06:57 (Finn: „habe beides weggeklickt“ — Popup auch bei Mike zu): Mike 38201ff1 Express …1691 BUY 3 MNQ → 07:17:30 Dubai
-- (Mikes The5%ers 07:11, Apex 08:32; ohne Gruppe → start_um in der Tageszeile genügt).
update public.trade_plans p
set start_um = timestamptz '2026-11-17 07:17:30+04', start_um_gestartet_at = null,
    mt5_baseline = coalesce(p.mt5_baseline,'{}'::jsonb) || jsonb_build_object('start_fehler',
                     coalesce(p.mt5_baseline->'start_fehler','{}'::jsonb) || jsonb_build_object('status','neu',
                       'behoben','nachgeholt per SQL 17.11.2026 (TopstepX-Werbe-Popup weggeklickt, Finn)'))
where p.id::text like '38201ff1%' and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null;
update public.wd_tagesplan w
set konten = (select jsonb_agg(case when left(e.k->>'plan_id',8) = '38201ff1'
                                    then e.k || jsonb_build_object('start_um', '2026-11-17T03:17:30.000Z', 'status', 'planned', 'um', null)
                                    else e.k end order by e.i)
              from jsonb_array_elements(w.konten) with ordinality e(k, i)), updated_at = now()
where w.tag = date '2026-11-17' and w.user_id = '32b854d1-866f-4e7e-ba0b-9bf63df2d993';
