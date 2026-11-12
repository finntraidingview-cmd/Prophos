-- Marc Topstep 150k …80376187 (Challenge, Kette 1/2, Buy, Plan 13b6397d) neu einplanen (Finn 12.11.2026 ~23:37 Dubai: „Da wurde kein Trade heute gemacht,
-- auf ganz Marc Topstep liegt heute kein Trade“). 12:36 Dubai geclaimt, Tab nach dem Claim neu geladen → kein Ergebnis (puls_still, unklar). Finn hat in
-- TopstepX nachgesehen: keine Order, keine Position → Neustart ohne Doppel-Order. CME-Handelstag 12.11. läuft bis 17:00 CT (03:00 Dubai).
-- Weg wie Memory „Nachplanen per Supabase“: Claim zurück, start_fehler.status 'neu', start_um gestreut in 4–8 min. Andere Pläne der ID: keine offenen/geplanten.
-- Guard: planned, nie gestartet, nichts gesendet.

update public.trade_plans
   set start_um = now() + make_interval(secs => 240 + floor(random() * 240)::int),
       start_um_gestartet_at = null, start_claim_art = null,
       mt5_baseline = jsonb_set(mt5_baseline, '{start_fehler,status}', '"neu"', false),
       updated_at = now()
 where id::text like '13b6397d%' and master_firm = 'Topstep'
   and status = 'planned' and started_at is null and orbit_gesendet_at is null;
