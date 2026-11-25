-- GF2 (Master 25.11.2026, Finn): Goat Funded Trader in den Challenge-Auto-Planer. Die 4 Konten von „Finn + Pascal" (48f272b4…) werden getradet:
-- 100k …3686 (18f8cab1), …3687 (ab51d273), …3752 (f49719d6), …3753 (05d2ebca), alle Phase 1, Kauf 90 €. NICHT eingespielt — der Master spielt ein.
--
-- 1) auto_plan_regeln id 1 → firmen „goatfundedtrader": planen true. route bleibt mt5v2, wie bei ALLEN HT-CFD-Challenges (FTMO, FundedNext,
--    FundingPips, Blue Guardian …). „Echo mit Hedge“ macht eh_tick (regeln.echo_hedge.an = true, auto_bestaetigen = true): Er stellt jeden
--    bestätigten Planer-Plan 20 min vor dem Start auf route mt5 + Fusion Echo Slave um. Der Multiplikator kommt aus dem Kontowert (kauf_eur 90 /
--    DD 8 % = 8.000) und ppl NAS100.x 10 (firm_specs „Goat Funded Trader“, Lots, GoatFunded-Server, gelesen 25.11.).
-- 2) GFT verlangt je Phase mindestens 3 profitable Tage mit ≥ 0,5 % (100k = 500 $). Mechanismus wie Blue Guardian (seit 25.10.2026):
--    regel.gewinntage {tp:[1000,1100]} + Konto-Ziel goal_kind winning_days / goal_target 3 / goal_min_profit 500. Solange ≥ 2 Gewinntage fehlen,
--    plant der Planer nur Gewinntag-Trades (TP 1.000–1.100 $, SL/Lots wie die Regel), erst bei 2/3 die Big Trades. Das Ziel (Phase 1 10 % =
--    10.000 $, Phase 2 5 %) kann also frühestens mit dem 3. Gewinntag fallen. Ziel erreicht bei < 3/3 → kein Mini, Grund „von Hand“.
--    Die Konten stehen heute auf trading_days 3 ohne Mindestgewinn (Bulk-Rückfall). Das zählt jeden Trade-Tag, also falsch → umstellen.
--    goal_since = 25.11. (Konten heute angelegt, 0 Pläne bisher).
-- Daily 3 % = 3.000 $ (daily_pct 3, Basis Tagesstart): ap_tagesgrenze kappt den SL auf Grenze − 100 $ minus heutigen Verlust. SL-Regel max. 2.475 $
-- bei 2–3 Lot NAS100.x (10 $/Pkt je Lot → 69–124 Pkt). Spread ~1–2 Pkt × 3 Lot ≈ 30–60 $ → ≤ ~2.535 $ < 2.900 $. Boden 8 % statisch = 92.000.

-- Sicherung
create table if not exists public.gf2_20261125_sicherung (gesichert_at timestamptz, was text, id text, daten jsonb);
alter table public.gf2_20261125_sicherung enable row level security;
revoke all on public.gf2_20261125_sicherung from anon, authenticated;

insert into public.gf2_20261125_sicherung
select now(), 'auto_plan_regeln', r.id::text, r.regeln from public.auto_plan_regeln r
where r.id = 1 and not exists (select 1 from public.gf2_20261125_sicherung s where s.was = 'auto_plan_regeln');

insert into public.gf2_20261125_sicherung
select now(), 'accounts', a.id::text, jsonb_build_object('goal_kind', a.goal_kind, 'goal_target', a.goal_target, 'goal_min_profit', a.goal_min_profit,
       'goal_since', a.goal_since, 'goal_done_offset', a.goal_done_offset)
from public.accounts a
where a.id in ('18f8cab1-eada-433c-b30e-5ba8ebe63d8a', 'ab51d273-a9b4-4bc6-afb8-a32053c4c6ee', 'f49719d6-a553-42be-90c7-69288ae85d57', '05d2ebca-080b-4013-912d-a61a80bf69f8')
  and not exists (select 1 from public.gf2_20261125_sicherung s where s.was = 'accounts' and s.id = a.id::text);

-- 1) + 2a) Regel: GFT planen true + Gewinntag-TP (Reihenfolge der firmen bleibt)
update public.auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}',
      (select jsonb_agg(case when f->'namen' ? 'goatfundedtrader'
                             then f || '{"planen": true, "gewinntage": {"tp": [1000, 1100]}}'::jsonb else f end order by i)
       from jsonb_array_elements(r.regeln->'firmen') with ordinality t(f, i))),
    updated_at = now()
where r.id = 1
  and (select count(*) from jsonb_array_elements(r.regeln->'firmen') f where f->'namen' ? 'goatfundedtrader') = 1
  and exists (select 1 from jsonb_array_elements(r.regeln->'firmen') f
              where f->'namen' ? 'goatfundedtrader' and coalesce((f->>'planen')::boolean, false) = false
                and f->>'route' = 'mt5v2' and (f->>'dd_pct')::numeric = 8 and (f->>'daily_pct')::numeric = 3)
returning (select f from jsonb_array_elements(regeln->'firmen') f where f->'namen' ? 'goatfundedtrader') gft;

-- 2b) Konten: 3 Gewinntage ≥ 500 $ je Phase
update public.accounts a
set goal_kind = 'winning_days', goal_target = 3, goal_min_profit = 500, goal_since = date '2026-11-25', goal_done_offset = 0
where a.id in ('18f8cab1-eada-433c-b30e-5ba8ebe63d8a', 'ab51d273-a9b4-4bc6-afb8-a32053c4c6ee', 'f49719d6-a553-42be-90c7-69288ae85d57', '05d2ebca-080b-4013-912d-a61a80bf69f8')
  and a.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and a.firm = 'Goat Funded Trader' and a.account_type = 'phase1'
  and a.goal_kind = 'trading_days' and a.goal_min_profit is null
  and not exists (select 1 from public.trade_plans q where q.master_account_id = a.id and q.started_at is not null)
returning left(a.id::text, 8) id, right(a.name, 24) konto, a.goal_kind, a.goal_target, a.goal_min_profit, a.goal_since;

-- Rückweg:
-- update public.auto_plan_regeln r set regeln = s.daten, updated_at = now() from public.gf2_20261125_sicherung s where s.was = 'auto_plan_regeln' and r.id = 1;
--   (setzt die GANZE Regel zurück — nur direkt danach, sonst nur den GFT-Eintrag per jsonb wie oben mit planen false / ohne gewinntage)
-- update public.accounts a set goal_kind = s.daten->>'goal_kind', goal_target = (s.daten->>'goal_target')::int, goal_min_profit = (s.daten->>'goal_min_profit')::numeric,
--   goal_since = (s.daten->>'goal_since')::date, goal_done_offset = (s.daten->>'goal_done_offset')::int
--   from public.gf2_20261125_sicherung s where s.was = 'accounts' and s.id = a.id::text;
