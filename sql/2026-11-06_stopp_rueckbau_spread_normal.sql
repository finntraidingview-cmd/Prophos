-- RÜCKBAU STOPP (Finn 06.11.2026 ~04:07 Dubai: „der Fusion-Market-Spread ist wieder normal. Du kannst wieder alle Pläne ganz normal
-- reinbringen und alle verpassten Pläne einfach ranhängen, damit die noch gemacht werden"). Gegenstück zu 2026-11-06_stopp_alle_starts_spread.sql
-- und 2026-11-06_alle_starts_plus_1h_spread.sql.
-- start_vor_stopp = Zeit NACH der +1-h-Verschiebung → „ganz normal“ = start_vor_stopp − 60 min (ursprünglicher Plan).
-- Ist die ursprüngliche Zeit schon vorbei (verpasst), wird der Plan hinten angehängt: ab jetzt +5 min, je verpasstem Plan 4 min Abstand
-- in alter Reihenfolge + 0–60 s Streuung (Jitter-Regel). WD-Tagesplan zieht −60 min mit, sonst setzt der Farmer zurück.
-- Danach Planer + WD-Farmer wieder an.
begin;

with z as (
  select id, (mt5_baseline->>'start_vor_stopp')::timestamptz - interval '60 minutes' as ur
    from public.trade_plans
   where status = 'planned' and start_um is null and mt5_baseline ? 'start_vor_stopp'
), v as (
  select id, row_number() over (order by ur) as n from z where ur <= now() + interval '5 minutes'
)
update public.trade_plans p
   set start_um = case when v.id is null then z.ur
                       else now() + interval '5 minutes' + (v.n - 1) * interval '4 minutes' + make_interval(secs => floor(random() * 60)) end,
       mt5_baseline = p.mt5_baseline - 'start_vor_stopp', updated_at = now()
  from z left join v on v.id = z.id
 where p.id = z.id;

update public.wd_tagesplan
   set start_um = greatest(start_um - interval '60 minutes', now() + interval '5 minutes'), updated_at = now()
 where tag = '2026-11-06' and status = 'geplant' and gestartet_at is null and start_um is not null;

update public.auto_plan_regeln       set aktiv = true, updated_at = now() where id = 1;
update public.funded_cfd_plan_regeln set aktiv = true, updated_at = now() where id = 1;
update public.funded_plan_regeln     set aktiv = true, updated_at = now() where id = 1;
update public.wd_farmer_regeln       set aktiv = true, updated_at = now() where id = 1;

commit;
