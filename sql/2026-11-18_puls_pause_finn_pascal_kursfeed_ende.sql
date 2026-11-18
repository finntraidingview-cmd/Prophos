-- RÜCKWEG zu 2026-11-18_puls_pause_finn_pascal_kursfeed.sql — erst einspielen, wenn Finn sagt: Moritz' PC liefert wieder Kurse UND auf
-- pc-2zc2we ist der Tampermonkey-Modus „Puls-Chrome (Orbit V3)“ wieder AN (Tab neu geladen).
-- Stand beim Pausieren (18.11. ~04:45 Dubai): 3 Pläne geparkt — f271ed46 WD 10:08, 7b872500 WD 10:09, 3f58115d Echo 18:46 (Dubai);
-- 99 Konten Auto-Planer-Haken aus (Liste in user_settings 'puls_pause_2026_11_18').
-- Startzeit: alte Zeit, wenn sie noch ≥ 10 min in der Zukunft liegt; sonst gestaffelt jetzt + 10 / 13 / 16 … min (je Plan +3 min).
-- Claim (start_um_gestartet_at) ist bei geparkten Plänen leer (Guard beim Pausieren) — trotzdem hier nochmals null (Falle Mike 92936a05).

begin;

update public.accounts a set auto_planer = true, updated_at = now()
where a.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and a.auto_planer = false
  and a.id::text in (select jsonb_array_elements_text(value->'konten_auto_planer') from public.user_settings
                      where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and key = 'puls_pause_2026_11_18');

with z as (
  select p.id, (p.mt5_baseline->'puls_pause'->>'start_um_war')::timestamptz war,
         row_number() over (order by (p.mt5_baseline->'puls_pause'->>'start_um_war')::timestamptz) n
  from public.trade_plans p
  where p.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and p.status = 'planned'
    and p.mt5_baseline->'puls_pause'->>'at' = '2026-11-18T00:45:00Z')
update public.trade_plans p
   set start_um = case when z.war >= now() + interval '10 minutes' then z.war else now() + interval '10 minutes' + (z.n - 1) * interval '3 minutes' end,
       start_um_gestartet_at = null,
       auto_bestaetigt_at = case when (p.mt5_baseline->'puls_pause'->>'bestaetigt_war')::boolean then now() else null end,
       mt5_baseline = (p.mt5_baseline - 'puls_pause') || jsonb_build_object('puls_pause_ende', jsonb_build_object('at', now(),
                        'grund', 'Finn: Moritz-PC liefert wieder, Puls-Modus auf pc-2zc2we wieder an'))
  from z where p.id = z.id;

update public.wd_tagesplan w
   set konten = (select jsonb_agg(case when coalesce((e.k->>'puls_pause')::boolean, false)
                                       then (e.k - 'puls_pause') || jsonb_build_object('aktiv', true, 'hinweis', '',
                                              'start_um', (select to_char(tp.start_um at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS".000Z"')
                                                           from public.trade_plans tp where tp.id::text = e.k->>'plan_id'),
                                              'status', 'planned', 'um', null)
                                       else e.k end order by e.i)
                 from jsonb_array_elements(w.konten) with ordinality e(k, i)),
       status = 'geplant',
       start_um = (select min(tp.start_um) from public.trade_plans tp, jsonb_array_elements(w.konten) k2
                    where tp.id::text = k2->>'plan_id' and tp.status = 'planned'),
       updated_at = now()
 where w.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and w.tag = current_date and w.status = 'leer';

delete from public.user_settings where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and key = 'puls_pause_2026_11_18';

commit;
