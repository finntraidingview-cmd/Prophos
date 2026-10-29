-- Funded-Planer Apex: Kontrakte 2 NQ zu 90 %, 3 NQ zu 10 % (Finn 29.10.2026 06:20 Dubai: „mach 90 % immer 2 und nur zu 10 % 3" —
-- vorher 150k 2 NQ 75 % / 3 NQ 25 %, 100k 2 NQ 50 % / 3 NQ 50 %). Gilt für beide Größen. Nur funded_plan_regeln.firmen[Apex].je_groesse.*.kontrakte,
-- alles andere bleibt. Wirkt ab dem nächsten Planungslauf; schon vorgeschlagene Pläne behalten ihre Kontraktzahl.
-- Rücknahme: dieselbe Abfrage mit '{"2":0.75,"3":0.25}' (150000) und '{"2":0.5,"3":0.5}' (100000).

update public.funded_plan_regeln r
set firmen = (
      select jsonb_agg(
               case when f->>'name' = 'Apex Trader' then
                 jsonb_set(jsonb_set(f, '{je_groesse,150000,kontrakte}', '{"2":0.9,"3":0.1}'::jsonb),
                           '{je_groesse,100000,kontrakte}', '{"2":0.9,"3":0.1}'::jsonb)
               else f end order by i)
      from jsonb_array_elements(r.firmen) with ordinality t(f, i)
    ),
    updated_at = now()
where r.id = 1;
