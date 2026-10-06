-- Auto-Planer: die vier Kernwerte je Firma als EINE Quelle (Finn 06.10.2026: „pro Firma müssen nur vier Werte stimmen —
-- Max-Drawdown (Total), TP-Ziel Phase 1, TP-Ziel Phase 2, Kaufpreis; alles andere wird daraus gerechnet").
-- Gelesen von app.py ap_kw_param (Kontowert/Probelauf), ap_konto_rechnen (Ziel + statischer Boden, Phasen-Felder nur noch
-- Rückfall) und dem Vorrat (T2). Felder je firmen[]-Eintrag:
--   kauf_eur   Zahl (gilt für die kleinste Größe, skaliert) oder {"größe": €}
--   dd_usd     Max-Drawdown in $ (Futures)  ODER  dd_pct in % der Kontogröße (CFD)
--   boden      'statisch' | 'nachziehend'
--   ziel_pct   {"challenge"|"phase1"|"phase2": %} — keine Phase 'funded'
--   daily_usd + soft  weicher Tagesstopp (Apex Daily Loss = Soft Breach)
--   tp_max     Etappe bei nachziehendem Boden (Topstep 4.500; Tradeify steht in phasen.challenge.tp_max = 3.600)
--   wert_groessen  Größen nur für den Kontowert (FundedNext/FundingPips 50k), der Planer plant weiter nur groessen
--   planen:false  nur Kernwerte, der Nachtlauf lässt die Firma aus (Topstep, FTMO)
-- Kaufpreise: Durchschnitt laut Finn (Tradeify 215, Topstep 237, Apex 150), CFD Median der Käufe seit 08/2026 bis Finn ändert.
-- FundingPips (Finn 06.10.2026, verbindlich): 2-Step 100k Standard = Ziel P1 8 %, P2 5 %, Max Loss 10 % statisch (Boden 90.000)
-- — vorher 10 %/8 %/12 %. Planer-Phasen angeglichen; die 50-%-Regel aus Finns Diktat bleibt als Anteil vom Ziel: tp_max P1 4.000,
-- P2 2.500, TP-Spannen auf diese Deckel gekappt (P1 3.500–4.000, P2 2.000–2.500).
-- Wiederholbar: vorhandene Einträge werden ergänzt/überschrieben, Topstep/FTMO nie doppelt angehängt.
update auto_plan_regeln set regeln = jsonb_set(regeln, '{firmen}', (
  select coalesce(jsonb_agg(case
      when f->'namen' ? 'tradeify'    then f || '{"kauf_eur":215,"dd_usd":4500,"boden":"nachziehend","ziel_pct":{"challenge":6}}'
      when f->'namen' ? 'apextrader'  then f || '{"kauf_eur":150,"dd_usd":4000,"boden":"statisch","daily_usd":2000,"soft":true,"ziel_pct":{"challenge":6}}'
      when f->'namen' ? 'fundednext'  then f || '{"kauf_eur":{"50000":261,"100000":500},"dd_pct":10,"boden":"statisch","ziel_pct":{"phase1":8,"phase2":5},"wert_groessen":[50000,100000]}'
      when f->'namen' ? 'fundingpips' then jsonb_set(jsonb_set(
             f || '{"kauf_eur":{"50000":240,"100000":464},"dd_pct":10,"boden":"statisch","ziel_pct":{"phase1":8,"phase2":5},"wert_groessen":[50000,100000]}',
             '{phasen,phase1}', coalesce(f->'phasen'->'phase1', '{}') || '{"ziel_pct":8,"boden_pct":10,"tp_max":4000,"tp":[3500,4000]}'),
             '{phasen,phase2}', coalesce(f->'phasen'->'phase2', '{}') || '{"ziel_pct":5,"boden_pct":10,"tp_max":2500,"tp":[2000,2500]}')
      when f->'namen' ? 'the5ers'     then f || '{"kauf_eur":{"100000":146,"200000":226},"dd_pct":10,"boden":"statisch","ziel_pct":{"phase1":8,"phase2":5}}'
      else f end order by ord) filter (where not (f->'namen' ?| array['topstep','ftmo'])), '[]'::jsonb)
  from jsonb_array_elements(regeln->'firmen') with ordinality as x(f, ord)
) || '[{"namen":["topstep"],"planen":false,"route":"tvv2","kauf_eur":237,"dd_usd":4500,"boden":"nachziehend","tp_max":4500,"ziel_pct":{"challenge":6},"groessen":[150000]},
       {"namen":["ftmo"],"planen":false,"route":"mt5v2","kauf_eur":446,"dd_pct":10,"boden":"statisch","ziel_pct":{"phase1":10,"phase2":5},"groessen":[100000,200000]}]'::jsonb),
  updated_at = now()
where id = 1;
