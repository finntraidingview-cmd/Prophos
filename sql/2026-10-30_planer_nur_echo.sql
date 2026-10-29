-- Trade-Planer wieder an, aber NUR CFD-Challenges (Echo mit Hedge) — Futures-Firmen vorerst nicht planen (Finn 30.10.2026 ~02:15
-- Dubai: „eins nach dem anderen wieder online … wir beginnen nur mit den Challenges, nur Sachen mit Echo … noch keine Futures").
-- Mechanik: regeln.firmen[].planen = false (app.py: „planen:false = nur Kernwerte, nicht planen") für tradeify, apex, fundednextfutures,
-- lucid, topstep, ftmofutures. CFD-Firmen (fundednext, fundingpips, the5ers, ftmo, blueguardian, tradeifycfd) planen weiter.
-- auto_bestaetigen bleibt false → alles nur Vorschlag, Finn bestätigt im Planer → Challenge. aktiv = true → Nachtlauf holt den Tag nach.
-- VORHER-Stand planen: tradeify null, apex null, fundednextfutures null, lucid true, topstep true, ftmofutures true.
-- Rückweg Futures: dieselben Einträge wieder auf diesen Vorher-Stand (null = Schlüssel entfernen).
update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ?| array['tradeify','apex','apextrader','fundednextfutures','lucid','lucidtrading','topstep','ftmofutures']
                                    and not (f->'namen' ? 'tradeifycfd')
                               then f || '{"planen": false}'::jsonb else f end order by ord)
           from jsonb_array_elements(r.regeln->'firmen') with ordinality as t(f, ord))),
       aktiv = true, updated_at = now()
 where r.id = 1;
