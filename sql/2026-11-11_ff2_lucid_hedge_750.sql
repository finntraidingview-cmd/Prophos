-- FF2 Lucid-Hedge-Satz (Finn 11.11.2026 ~07:12 Dubai: „bei Lucid 750, bei Tradeify 850“ — je 4.500 $ Master-Risiko wie Tradeify).
-- Setzt im Pump-Modell (tp_modus pump2) von Lucid Trading 150k hedge_eur = 750. Das Modell bleibt an = false; einschalten nur Finn in der Karte
-- Funded-Planer → Futures → Einstellungen. Idempotent (setzt immer 750, ändert sonst nichts).
update funded_plan_regeln r set firmen = (
  select jsonb_agg(case when f->'namen' ? 'lucid' and f->>'tp_modus' = 'pump2'
      then jsonb_set(f, '{je_groesse,150000,hedge_eur}', '750'::jsonb)
      else f end order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
), updated_at = now()
where r.id = 1 and exists (select 1 from jsonb_array_elements(r.firmen) f where f->'namen' ? 'lucid' and f->>'tp_modus' = 'pump2');
