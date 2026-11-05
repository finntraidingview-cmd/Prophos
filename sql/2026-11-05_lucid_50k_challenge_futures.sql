-- Lucid 50K Flex Eval im Challenge-Planer Futures (Finn 05.11.2026 ~09:30 Dubai, Foto Lucid-Shop 50K Flex Eval: Profit Target 3.000 $,
-- Max Loss 2.000 $ EOD, Daily Loss Limit 1.200 $, Consistency 50 %, Max Size 4 Mini / 40 Micros, 90,30 $; „Tendenziell alles gleich behandeln
-- wie sonst immer auch“ → Vorschlag „1:1 wie Lucid 150k, auf 50k umgerechnet“: „yes bau“).
-- Anlass: Emins 5 Lucid-50k-Challenges (LFE05097865230001–0005) stehen mit Auto-Planer an, bekamen aber nie einen Plan — die Lucid-Regel
-- kannte nur groessen [150000].
-- Werte 50k (eigener je_groesse-Block, ohne Skalierung, ohne Rückfall auf 150k):
--   Ziel 6 % → 53.000 $, TP 1.450–1.500 $ (tp_max 1.500 = 50 % von 3.000), SL keiner (Orbit V2 ohne Hedge, wie 150k),
--   1 NQ fest (TP 1.500 $ = 75 Pkt — liegt in der 150k-Spanne 75–112 Pkt), Max Loss 2.000 $ nachziehend EOD, Daily Loss 1.200 $, Kauf ≈ 78 €.
-- 150k unverändert (kein je_groesse-Eintrag → bisherige phasen). Idempotent: setzt groessen und je_groesse.50000 der Lucid-Zeile.

update public.auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(
               case when e.x->'namen' ? 'lucid'
                    then e.x
                         || '{"groessen": [50000, 150000]}'::jsonb
                         || jsonb_build_object('je_groesse', coalesce(nullif(e.x->'je_groesse', 'null'::jsonb), '{}'::jsonb)
                              || '{"50000": {"dd_usd": 2000, "daily_usd": 1200, "kauf_eur": 78,
                                   "phasen": {"challenge": {"sl": null, "tp": [1450, 1500], "tp_max": 1500, "menge": [1, 1], "menge_schritt": 1,
                                                            "dd_usd": 2000, "ziel_pct": 6, "puffer_je_menge": {"1": [8, 13]}}}}}'::jsonb)
                    else e.x end
               order by e.ord)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality as e(x, ord))),
    updated_at = now()
where r.id = 1;

-- Kontrolle:
-- select x->'groessen', x->'je_groesse'->'50000' from auto_plan_regeln r, jsonb_array_elements(r.regeln->'firmen') x where r.id=1 and x->'namen' ? 'lucid';

-- Nachtrag (S5 LU1, 05.11.2026): kauf_eur als Zahl gilt für die KLEINSTE Größe und skaliert (_ap_kw_kauf) — mit groessen [50000,150000]
-- wäre 150k plötzlich 666 € statt 222 € (Kontowert, Vorrat, Waage-Einsatz, auch HT-Lucid-150k). Darum je Größe: 50k 78 €, 150k 222 €.
update public.auto_plan_regeln r
set regeln = jsonb_set(r.regeln, '{firmen}', (
      select jsonb_agg(case when e.x->'namen' ? 'lucid' then e.x || '{"kauf_eur": {"50000": 78, "150000": 222}}'::jsonb else e.x end order by e.ord)
      from jsonb_array_elements(r.regeln->'firmen') with ordinality as e(x, ord))),
    updated_at = now()
where r.id = 1;
