-- Polar-Test ab91b218 (Lauf 7b57a23e, 21.10.2026 17:06 Dubai, Ina Apex 150k …0002 gegen Moritz The5%ers 200k …6641, Master −9,54 $, Slave +0,22 $)
-- abhaken: Finn hakte im Radar ab und bekam einen Fehler — der Plan gehört Ina, und Railway läuft noch auf .1684 (Störung, Builds pausiert),
-- dort kennt /admin/wd-plaene erledigt die Route polar noch nicht (seit .1691 im Code, nicht ausgerollt). P&L wie abgerechnet, keine Buchung.
update trade_plans
   set status = 'completed', completed_at = now()
 where id::text like 'ab91b218%' and route = 'polar' and status = 'review';
