-- Polar-Plan 1a956ec6 (Ina gegen Moritz) zum erneuten Test freigeben (21.10.2026 ~05:17 Dubai, Finn: „dass ich nicht immer die Pläne
-- neu machen muss … zurück auf Geplant und neu starten, aber es steht immer ‚schon gestartet'"). Startmarke des letzten Laufs lösen,
-- nur solange der Plan geplant ist und kein Lauf dieses Plans aktiv ist. Dauerhafter Fix (Frontend + /polar/freigeben) folgt.
update trade_plans set start_um = null, start_um_gestartet_at = null
 where id::text like '1a956ec6%' and route = 'polar' and status = 'planned'
   and not exists (select 1 from polar_lauf l where l.plan_id = trade_plans.id and l.status not in ('abbruch','fehler','fertig'));
