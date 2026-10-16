-- 17.10.2026 Finn: Apex 100k EOD als Vorlage + im Trade-Planer — „Kaufpreis 45 € pro Account, Take Profit Target 6.000 von
-- Phase 1, Daily Stop Loss 1,5k, All Stop Loss 3k, immer 3 NQs". Werte laut Apex Help Center (EOD Evaluations):
-- 100k Ziel 6.000 $, Max Drawdown EOD 3.000 $, Daily Loss Limit 1.500 $.
-- Idempotent. Erst die Datei, dann im Supabase SQL Editor ausführen.

-- 1) Bulk-Vorlage, gleiche Form wie „Apex 150k Challenge" (Plattform Tradovate, Präfix APEX)
insert into bulk_vorlagen (name, firm, account_type, account_size, starting_balance, purchase_cost, max_drawdown,
  max_daily_drawdown, max_loss_per_trade, max_profit_per_trade, name_template, plattform, muster_praefix, sortierung, aktiv, wd_farm)
select 'Apex 100k Challenge', 'Apex Trader', 'challenge', 100000, 100000, 45, 3000,
  1500, 1500, 6000, '100k Apex {ex}', 'Tradovate', 'APEX', 49, true, false
where not exists (select 1 from bulk_vorlagen where name = 'Apex 100k Challenge');

-- 2) Planer-Regel: 100k als zweite Größe. Kaufpreis wird zum Dict je Größe — als Zahl gälte er für die KLEINSTE Größe und
--    würde hochgerechnet (150 € auf 100k → 225 € für 150k). 150k-Werte bleiben auf Firmenebene (DD 4.000, Daily 2.000);
--    je_groesse["100000"] trägt DD 3.000, Daily 1.500 und dieselbe Challenge-Phase (Ziel 6 %, 3 NQ fix, Puffer 100 $).
update auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, array['firmen', i.idx::text],
         (r.regeln->'firmen'->i.idx::int)
           || jsonb_build_object(
                'groessen', '[100000, 150000]'::jsonb,
                'kauf_eur', '{"100000": 45, "150000": 150}'::jsonb,
                'je_groesse', coalesce(r.regeln->'firmen'->i.idx::int->'je_groesse', '{}'::jsonb) || jsonb_build_object('100000', jsonb_build_object(
                    'dd_usd', 3000, 'daily_usd', 1500,
                    'phasen', jsonb_build_object('challenge',
                        '{"sl": null, "tp": null, "menge": [3, 3], "puffer": [100, 100], "ziel_pct": 6, "menge_schritt": 1}'::jsonb)))))
  from (select (e.ord - 1) as idx
          from auto_plan_regeln a, jsonb_array_elements(a.regeln->'firmen') with ordinality e(f, ord)
         where a.id = 1 and e.f->'namen' ? 'apex') i
 where r.id = 1;

-- Prüfen:
-- select name, purchase_cost, max_drawdown, max_daily_drawdown, max_profit_per_trade from bulk_vorlagen where firm = 'Apex Trader';
-- select f->'groessen', f->'kauf_eur', f->'je_groesse' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f
--  where id = 1 and f->'namen' ? 'apex';
