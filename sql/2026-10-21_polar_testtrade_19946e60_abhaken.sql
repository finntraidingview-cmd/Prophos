-- Polar-Testtrade 19946e60 (Lauf 582c58c0 „Slave zuerst", 21.10.2026 05:57 Dubai, Ina Apex 150k …0002 gegen Moritz The5%ers 200k …6641)
-- abhaken (Finn 21.10.2026: „einfach archivieren, das war nur der Testtrade von Polar"). Im Radar war „Abhaken" gesperrt: der Plan gehört
-- Ina, und wdlAbhakenSperre / app.py WD_ERLEDIGT_ROUTEN kennen route 'polar' für fremde Pläne nicht. P&L bleibt wie abgerechnet
-- (Master −2,02 $, Slave −0,11 $), keine Buchung, keine Konto-Änderung.
update trade_plans
   set status = 'completed', completed_at = now()
 where id = '19946e60-3276-466c-b12a-a441b8fff259'
   and route = 'polar' and status = 'review';
