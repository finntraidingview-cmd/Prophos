-- Auto-Planer-Regeln für die neuen Schablonen (Finn 25.10.2026, Werte im Chat):
--  • FundedNext Futures 50k Flex: eigener Block je_groesse["50000"] in der bestehenden Regel „fundednextfutures" (150k bleibt unverändert).
--    1 NQ, TP 900–980 $, KEIN SL (Verlust = Liq bei 1.500 $ EOD = Konto weg), Tageshöchstwert 1.000 $ (Consistency 40 % von 2.500),
--    Ziel 5 % = 2.500 $. Letzter Trade = Rest bis Ziel (~550–700 $) macht der Planer selbst. Kauf 74 €. kauf_eur wird dafür zum Dict
--    je Größe — eine Zahl gälte für die KLEINSTE Größe und würde skaliert (150k stünde dann bei 3 × 74 €).
--  • FTMO Futures 50k Pro: neue Regel „ftmofutures" (vorher keine — die CFD-Regel „ftmo" greift nicht, ap_regel_finden vergleicht exakt).
--    1 NQ, TP 1.475–1.500 $ (Consistency 50 % von 3.000 = Tageshöchstwert 1.500), SL 700–800 $ (Daily Loss 1.000 HART), DD 3.000 $ EOD
--    trailing mit Lock bei der Startbalance, Ziel 6 % = 3.000 $, Weg TradingView (tvv2) + NQ wie FundedNext Futures, Kauf ~120 € (139 $/Monat).
-- Firmenschlüssel FTMO Futures: sql/2026-10-25_ftmo_futures_firma_key.sql (vorher einspielen). Idempotent.

-- 1) FundedNext Futures: 50k dazu
update auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(case
        when x->'namen' ? 'fundednextfutures' and not ((x->'groessen') @> '[50000]'::jsonb) then
          x || jsonb_build_object(
            'groessen', '[50000, 150000]'::jsonb,
            'kauf_eur', '{"50000": 74, "150000": 258}'::jsonb,
            'je_groesse', coalesce(x->'je_groesse', '{}'::jsonb) || '{
              "50000": {"dd_usd": 1500, "ziel_pct": {"challenge": 5},
                "phasen": {"challenge": {"sl": null, "tp": [900, 980], "menge": [1, 1], "menge_schritt": 1, "dd_usd": 1500,
                                         "tp_max": 1000, "ziel_pct": 5, "puffer_je_menge": {"1": [15, 25]}}}}}'::jsonb)
        else x end order by o)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality t(x, o))),
    updated_at = now()
where r.id = 1
  and exists (select 1 from jsonb_array_elements(r.regeln->'firmen') x where x->'namen' ? 'fundednextfutures'
                                                                        and not ((x->'groessen') @> '[50000]'::jsonb));

-- 2) FTMO Futures: neue Regel
update auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (r.regeln->'firmen') || jsonb_build_array('{
      "namen": ["ftmofutures"], "route": "tvv2", "symbol": "NQ", "planen": true,
      "boden": "nachziehend", "dd_usd": 3000, "lock_bei_start": true, "daily_usd": 1000,
      "groessen": [50000], "kauf_eur": 120, "ziel_pct": {"challenge": 6},
      "phasen": {"challenge": {"sl": [700, 800], "tp": [1475, 1500], "menge": [1, 1], "menge_schritt": 1, "dd_usd": 3000,
                               "tp_max": 1500, "ziel_pct": 6, "puffer_je_menge": {"1": [15, 25]}}}}'::jsonb)),
    updated_at = now()
where r.id = 1
  and not exists (select 1 from jsonb_array_elements(r.regeln->'firmen') x where x->'namen' ? 'ftmofutures');

-- Prüfen: select x from auto_plan_regeln r, jsonb_array_elements(r.regeln->'firmen') x
--          where x->'namen' ?| array['fundednextfutures','ftmofutures'];
