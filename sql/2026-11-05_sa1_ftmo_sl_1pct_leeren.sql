-- SA1 #6 (05.11.2026, Prüfer-Hinweis O1/E1e aus berichte/2026-11-05_NK1.md (c); Finn: „1 % gibt es nur bei FundedNext"). NICHT EINGESPIELT (Master).
-- funded_cfd_plan_regeln (id 1) hat bei FTMO je Größe einen sl_1pct-Wert (100k [670, 780], 200k [1500, 1700]), den die UI nicht zeigt (Feld nur bei
-- FundedNext). Seit SA1 #6 nimmt der Planer sl_1pct ohnehin nur bei FundedNext (app.py fcp_sl_1pct_firma) — diese Datei räumt die unsichtbaren Werte weg,
-- damit DB und Anzeige übereinstimmen. Nur FTMO, nur der Schlüssel sl_1pct; alle anderen Felder und Firmen bleiben Zeichen für Zeichen.
-- Live 05.11.2026: kein FTMO-Funded-CFD-Konto mit max_risiko_trade oder „1% RULE" im Namen (nur FTMO phase1, die plant dieser Planer nicht).

begin;
update public.funded_cfd_plan_regeln r
   set firmen = (
     select jsonb_agg(
              case when f->'namen'->>0 = 'ftmo' and jsonb_typeof(f->'je_groesse') = 'object'
                   then jsonb_set(f, '{je_groesse}',
                                  (select jsonb_object_agg(g.key, case when jsonb_typeof(g.value) = 'object' then g.value - 'sl_1pct' else g.value end)
                                     from jsonb_each(f->'je_groesse') g))
                   else f end
              order by i)
       from jsonb_array_elements(r.firmen) with ordinality as e(f, i))
 where r.id = 1;
-- Prüfung: FTMO ohne sl_1pct, FundedNext unverändert (50k [300,400], 100k [670,780], 200k [1500,1700])
-- select f->>'name', g.key, g.value->'sl_1pct' from funded_cfd_plan_regeln r, jsonb_array_elements(r.firmen) f, jsonb_each(f->'je_groesse') g
--  where r.id = 1 and f->'namen'->>0 in ('ftmo', 'fundednext');
commit;

-- RÜCKBAU (Werte vom 05.11.2026):
-- update public.funded_cfd_plan_regeln r set firmen = (select jsonb_agg(case when f->'namen'->>0 = 'ftmo'
--     then jsonb_set(jsonb_set(f, '{je_groesse,100000,sl_1pct}', '[670, 780]'), '{je_groesse,200000,sl_1pct}', '[1500, 1700]') else f end order by i)
--   from jsonb_array_elements(r.firmen) with ordinality as e(f, i)) where r.id = 1;
