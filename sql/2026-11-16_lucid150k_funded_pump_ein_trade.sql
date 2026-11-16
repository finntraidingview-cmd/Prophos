-- Lucid 150k im Funded-Planer Futures einschalten, Pump immer in EINEM Trade (Finn 16.11.2026: „am Anfang erst mal nur alles an einem Tag
-- hochpumpen … mit dem Pump in einem Trade“, erstes Konto: Simon 150k LFF15098351860001 → Funded, angelegt 16:38).
-- Vorher: je_groesse.150000.an = false, pump2_pct = 30 (30 % Zwei-Trade-Weg). Jetzt: an = true, pump2_pct = 0. Alle übrigen Werte
-- (Ziel 13–19k, ein_sl 2.600–2.700, 3 NQ, Daily 2.700, Hedge 750 € je 4.500 $) bleiben. Idempotent.
update public.funded_plan_regeln r
set firmen = (
  select jsonb_agg(case when f->>'name' = 'Lucid Trading'
                        then jsonb_set(jsonb_set(f, '{je_groesse,150000,an}', 'true'::jsonb), '{je_groesse,150000,pump2_pct}', '0'::jsonb)
                        else f end order by i)
  from jsonb_array_elements(r.firmen) with ordinality e(f, i)),
    updated_at = now()
where r.id = 1;
