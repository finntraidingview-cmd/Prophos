-- Echo- und Apex-Hedge ebenfalls ohne 11-%-Aufschlag: netto_faktor 0,89 → 1,0, Hedge = Kontowert (Finn 29.10.2026: „Ja, überall weg",
-- nach sql/2026-10-29_tradeify_final_ohne_aufschlag.sql). Gilt für Vorschauen und Umstellungen ab dem nächsten Takt; laufende Hedges bleiben.
update public.auto_plan_regeln
   set regeln = jsonb_set(jsonb_set(regeln, '{echo_hedge,netto_faktor}', '1.0'::jsonb), '{apex_hedge,netto_faktor}', '1.0'::jsonb),
       updated_at = now()
 where id = 1;
