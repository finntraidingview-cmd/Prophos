-- Ina Topstep 150k …92558936 (Express, WD, 3 × MNQ Sell, Plan 0ad96857) neu einplanen (Finn 12.11.2026 ~20:15 Dubai: „bei Ina auch mal bitte neu“).
-- 13:11 Dubai geclaimt, Tab nach dem Claim neu geladen → kein Ergebnis (puls_still, unklar). Finns TopstepX-Screenshot 20:12 Dubai: „No Positions“,
-- „No Active Position“, BAL 20.524,08 (= letzte Lesung 11.11.), RP&L 0 → um 13:11 ging keine Order raus, Neustart ohne Doppel-Order.
-- Weg wie Memory „Nachplanen per Supabase“: Claim zurück, start_fehler.status 'neu', start_um gestreut in 4–8 min. Andere Starts der ID in den nächsten
-- 2 h: keine (Tradeify 18:22 Sell fertig, gleiche Richtung). Guard: planned, nie gestartet, nichts gesendet.

update public.trade_plans
   set start_um = now() + make_interval(secs => 240 + floor(random() * 240)::int),
       start_um_gestartet_at = null, start_claim_art = null,
       mt5_baseline = jsonb_set(mt5_baseline, '{start_fehler,status}', '"neu"', false),
       updated_at = now()
 where id::text like '0ad96857%' and master_firm = 'Topstep'
   and status = 'planned' and started_at is null and orbit_gesendet_at is null;
