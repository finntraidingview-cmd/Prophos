-- TAGESGRENZE IM AUTO-PLANER (26.10.2026, Finn über Master, Teil A „Nachziehen am Fill bei Tagesgrenze/Ziel"). Anlass FundingPips 100k …6924
-- am 23.10.2026: SL 2.948 $ bei Daily Loss 3 % der Tagesstart-Equity (96.463 → 2.894 $), echter Verlust 2.990 $ → Daily gerissen. Der Planer
-- kappte den SL nur am Boden, eine Tagesgrenze kannte er nicht. app.py ap_tagesgrenze/ap_konto_rechnen liest jetzt je Firma bzw. Größe:
--   daily_pct + daily_basis ('tagesstart' = % der Balance zum Planen, Standard | 'groesse' = % der Kontogröße), sonst daily_usd fest;
--   soft = true (Apex) = weicher Tagesstopp → keine Grenze. SL ≤ Grenze − 100 $ (AP_TAGES_PUFFER), ohne „+50 dahinter".
-- Neue Spalte trade_plans.tages_grenze_usd = Tagesgrenze-Rest dieses Trades in $ OHNE Puffer (Vertrag Teil B/C: Echo/Orbit ziehen den SL am Fill
-- nach, wenn er die Grenze reißen würde), null = keine Prüfung. Solange die Spalte fehlt, legt der Planer Pläne ohne das Feld an (app.py).
-- Nur Werte, die belegt sind (Dashboard bzw. firm_rules.json) — offene Firmen stehen unten, Finn ergänzt sie.
-- NICHT eingespielt (Master 26.10.2026). Wiederholbar.

-- 1) Spalte am Plan
alter table public.trade_plans add column if not exists tages_grenze_usd numeric;
comment on column public.trade_plans.tages_grenze_usd is
  'Tagesgrenze-Rest dieses Trades in $ ohne Puffer (Auto-Planer ap_tagesgrenze, 26.10.2026) — null = keine Prüfung';

-- 2) Kernwerte je Firma
--    FundingPips Standard: 3 % der Tagesstart-Equity (Dashboard Jacob …6924 am 23.10.2026: 2.893,90 = 3 % von 96.463,40).
--      firm_rules.json nennt für „2-Step Standard" 5 % — das Dashboard gilt.
--      Flex (flex.je_groesse 50k/100k): Wert offen → daily_pct ausdrücklich null, sonst erbten Flex-Konten die 3 % des Standards.
--    FundedNext Stellar 2-Step: 5 % der Startgröße (firm_rules.json „Daily Loss Limit: 5% des Initial Balance").
--    FTMO 2-Step: 5 % der Startgröße (firm_rules.json „2-Step: 5% des Initial…"); daily_usd 5.000 bleibt für den Kontowert stehen,
--      daily_pct geht in ap_tagesgrenze vor (200k = 10.000 statt 5.000).
--    Unverändert, schon da und so übernommen: Tradeify CFD daily_usd 3.000, Lucid 2.700, FTMO Futures 1.000; Apex soft (keine Grenze).
update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{firmen}', (
         select jsonb_agg(
                  case
                    when f->'namen' ? 'fundingpips' then f || '{"daily_pct": 3, "daily_basis": "tagesstart"}'::jsonb
                    when f->'namen' ? 'fundednext' then f || '{"daily_pct": 5, "daily_basis": "groesse"}'::jsonb
                    when f->'namen' ? 'ftmo'       then f || '{"daily_pct": 5, "daily_basis": "groesse"}'::jsonb
                    else f
                  end
                  order by o)
           from jsonb_array_elements(r.regeln->'firmen') with ordinality as x(f, o))),
       updated_at = now()
 where r.id = 1;

-- FundingPips Flex: daily_pct null je vorhandener Flex-Größe (Wert offen, keine Prüfung statt der Standard-3 %)
update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{firmen}', (
         select jsonb_agg(
                  case
                    when f->'namen' ? 'fundingpips' and jsonb_typeof(f->'flex'->'je_groesse') = 'object' then
                      jsonb_set(f, '{flex,je_groesse}', (
                        select coalesce(jsonb_object_agg(g, v || '{"daily_pct": null}'::jsonb), '{}'::jsonb)
                          from jsonb_each(f->'flex'->'je_groesse') as y(g, v)))
                    else f
                  end
                  order by o)
           from jsonb_array_elements(r.regeln->'firmen') with ordinality as x(f, o))),
       updated_at = now()
 where r.id = 1;

-- Prüfen:
-- select f->'namen'->>0 firma, f->>'daily_pct' pct, f->>'daily_basis' basis, f->>'daily_usd' fest, f->>'soft' soft,
--        (select jsonb_object_agg(g, v->'daily_pct') from jsonb_each(coalesce(f->'flex'->'je_groesse','{}')) y(g, v)) flex_pct
--   from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1;
-- select column_name from information_schema.columns where table_name = 'trade_plans' and column_name = 'tages_grenze_usd';

-- OFFEN (Finn trägt ein, Muster: f || '{"daily_pct": <n>, "daily_basis": "tagesstart"|"groesse"}'):
--   The5ers 100k/200k (Programm mit 10 % Boden: High Stakes 5 % hart? Basis?), Blue Guardian 100k (nicht in firm_rules.json),
--   FundingPips Flex 50k/100k, FundedNext Futures, Tradeify CFD (3.000 hart?), Lucid 2.700 / FTMO Futures 1.000 (hart? sonst soft: true).

-- Rückbau:
-- update public.auto_plan_regeln r set regeln = jsonb_set(r.regeln, '{firmen}', (
--   select jsonb_agg(case when f->'namen' ?| array['fundingpips','fundednext','ftmo'] then
--            case when jsonb_typeof(f->'flex'->'je_groesse') = 'object' then
--              jsonb_set(f - 'daily_pct' - 'daily_basis', '{flex,je_groesse}', (select coalesce(jsonb_object_agg(g, v - 'daily_pct'), '{}'::jsonb)
--                from jsonb_each(f->'flex'->'je_groesse') y(g, v)))
--            else f - 'daily_pct' - 'daily_basis' end
--          else f end order by o)
--   from jsonb_array_elements(r.regeln->'firmen') with ordinality as x(f, o))), updated_at = now() where r.id = 1;
-- alter table public.trade_plans drop column if exists tages_grenze_usd;
