-- 13.10.2026 (.1490): Mikes erster Winning-Day-Test auf Topstep (EXPRESS-V2-…-57131691) wurde um 01:00:02 UTC noch mit dem
-- alten Tab-Build als Orbit V2 + Fusion-Hedge gespeichert (vor .1489). Puls lief darum in TradingView und fand kein
-- Topstep-Konto („Kein Konto-Umschalter zu sehen", 3× order_signale fehler). Plan auf Topstep V2 drehen; winning_day = true
-- hält den Hedge-Kategorien-Riegel (prophos_hedge_weg) zufrieden. Nur solange er noch 'planned' auf tvv2 steht.
update trade_plans
   set route = 'tsv2', hedge_eur = null, hedge_faktor = null, multiplier = null, slave_risk = null, winning_day = true, orbit_v3 = false
 where id = 'f356f041-c794-4fa3-807f-c1690c9a3895' and status = 'planned' and route = 'tvv2';
