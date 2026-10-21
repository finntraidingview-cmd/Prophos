-- Moritz Tradeify 150k …4572: Konto bestanden (TV 159.013,64 ≥ 159.000), Nachfolger im Login von Moritz angelegt (Archiv 'passed' +
-- successorId, 21.10.2026 11:31 UTC), der letzte Trade a950bc52 (+1.968,48 $, Ende 15:04 Dubai) blieb aber auf review — bei Finn stand das Konto
-- deshalb weiter unter Bestanden → Rest von Hand (Finn: „den habe ich eigentlich schon gemacht"). Abhaken wie „Nichts ändern": completed,
-- P&L bleibt; keine Buchung (Orbit V2 ohne Hedge), kein Konto-Archiv (steht schon).
update trade_plans
   set status = 'completed', completed_at = now()
 where id::text like 'a950bc52%' and status = 'review'
   and master_account_id = '057338e7-7fe8-4bc7-a4f2-caa827e3ae01';
