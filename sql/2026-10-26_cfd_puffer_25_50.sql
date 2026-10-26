-- CFD-PUFFER AUF 25–50 $ (26.10.2026, Finn: „Wenn wir genau nachjustieren, sodass er beim TP immer nur auf das Take-Profit-Goal kommt
-- oder vielleicht +50 $, maximal +100 $, dann können wir auch den Puffer runterschrauben.“). Hintergrund: Die Echo-Justage (.1747,
-- order_bot._sltp_nachziehen) setzt bei Ziel-Trades den TP nach dem Fill exakt ab dem echten Entry inkl. Kommission — der Puffer, den
-- der Planer auf den Rest bis zum Ziel legt, muss Fill-Schlupf nicht mehr auffangen. Ein TP-Treffer landet damit bei Ziel + 25–50 $.
-- Nur CFD-Firmen (Route mt5v2): phasen.phase1/phase2.puffer und bei FundingPips zusätzlich flex.je_groesse.*.phasen.*.puffer.
-- Futures (tvv2/tsv2) unberührt. Eingespielt vom Master 26.10.2026 (Finn: „Ja, Puffer bei allen CFD-Firmen auf 25–50 $ senken.“). Alter Stand: Blue Guardian 100/100, FundedNext 100/100, Tradeify CFD 75–100, FTMO P1 75 / P2 50,
-- FundingPips 50–75 (Flex 75–100), The5ers 55–75. Wiederholbar.

with firmen as (
  select x.o,
         case when x.f->>'route' = 'mt5v2' and x.f ? 'phasen'
              then jsonb_set(x.f, '{phasen}', (select jsonb_object_agg(ph, pv || '{"puffer": [25, 50]}'::jsonb)
                                                 from jsonb_each(x.f->'phasen') as w(ph, pv)))
              else x.f end as f1
    from public.auto_plan_regeln r, jsonb_array_elements(r.regeln->'firmen') with ordinality as x(f, o)
   where r.id = 1),
firmen2 as (
  select o,
         case when f1->>'route' = 'mt5v2' and jsonb_typeof(f1->'flex'->'je_groesse') = 'object'
              then jsonb_set(f1, '{flex,je_groesse}', (
                     select jsonb_object_agg(g, case when v ? 'phasen'
                              then jsonb_set(v, '{phasen}', (select jsonb_object_agg(ph, pv || '{"puffer": [25, 50]}'::jsonb)
                                                               from jsonb_each(v->'phasen') as z(ph, pv)))
                              else v end)
                       from jsonb_each(f1->'flex'->'je_groesse') as y(g, v)))
              else f1 end as f2
    from firmen)
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (select jsonb_agg(f2 order by o) from firmen2)),
       updated_at = now()
 where id = 1;

-- Prüfen:
-- select f->'namen'->>0, f->'phasen'->'phase1'->'puffer', f->'phasen'->'phase2'->'puffer',
--        (select jsonb_object_agg(g, v->'phasen'->'phase1'->'puffer') from jsonb_each(coalesce(f->'flex'->'je_groesse','{}')) y(g,v))
--   from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->>'route' = 'mt5v2';
-- Rückbau: Werte aus dem Kopf je Firma per jsonb_set zurücksetzen.
