-- Tradeify-Final-Hedge ohne 11-%-Aufschlag: netto_faktor 0,89 → 1,0, der Hedge deckt genau den Kontowert (Finn 29.10.2026: „wir nehmen
-- keinen 11%-Aufschlag, wenn einfach der Kontowert dieser 670 € … das gegenhält"). Marc …7231: 758 € → 675 € am Blow, Pass 344 € → 306 €.
-- Echo- und Apex-Hedge bleiben bei 0,89.
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{tradeify_final_hedge,netto_faktor}', '1.0'::jsonb), updated_at = now()
 where id = 1;
