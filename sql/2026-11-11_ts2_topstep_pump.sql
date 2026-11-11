-- TS2 Topstep im Funded-Planer Futures 1:1 wie Tradeify (Finn 11.11.2026 20:35 Dubai: „Topstep kommt genau wie bei Tradeify, ganz genau alles gleich“).
-- Übernimmt die Pump-Einstellung (tp_modus pump2, symbol, lock_usd, je_groesse — Ziel 13–19k, 70/30, SL-Würfel, T2-Fenster, Hedge 850 € je 4.500 $) von der
-- Firma Tradeify, so wie sie beim Einspielen live steht, in die Firma Topstep. Name/namen bleiben Topstep, an bleibt FALSE — einschalten nur Finn in der Karte
-- Funded-Planer → Futures → Einstellungen (Master TS2: „Finn schaltet die Firma selbst an, wenn alles passt“).
-- Planer-Weg: Topstep plant als Nova (tsv2, Puls in TopstepX), Express 0-basiert absolut gerechnet, Liq aus der TopstepX-MLL + 100 $ (app.py TS2, fdp_route/
-- fdp_express_*). lock_usd wirkt bei Topstep Express nicht (Liq kommt fest aus der MLL, die bei 0 lockt).
-- ERST NACH dem app.py-Push einspielen (vorher plante ein alter Planer Topstep als tvv2, falls jemand die Firma anschaltet).
-- Idempotent: setzt nur, solange Topstep noch kein tp_modus hat — spätere Änderungen von Finn an Topstep bleiben stehen.
update funded_plan_regeln r set firmen = (
  select jsonb_agg(case when f->'namen' ? 'topstep' and not (f ? 'tp_modus')
      then (select t - 'name' - 'namen' - 'an' from jsonb_array_elements(r.firmen) t where t->'namen' ? 'tradeify' and t->>'tp_modus' = 'pump2' limit 1)
           || jsonb_build_object('name', f->'name', 'namen', f->'namen', 'an', false)
      else f end order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
), updated_at = now()
where r.id = 1
  and exists (select 1 from jsonb_array_elements(r.firmen) f where f->'namen' ? 'topstep' and not (f ? 'tp_modus'))
  and exists (select 1 from jsonb_array_elements(r.firmen) t where t->'namen' ? 'tradeify' and t->>'tp_modus' = 'pump2');

-- Kontrolle: Topstep = Tradeify bis auf name/namen/an
-- select f->>'name' name, f->>'an' an, f->>'tp_modus' modus, f->'je_groesse'->'150000'->>'hedge_eur' hedge, f->'je_groesse'->'150000'->'ziel_gewinn' ziel
-- from funded_plan_regeln, jsonb_array_elements(firmen) f where f->'namen' ?| array['topstep','tradeify'];
