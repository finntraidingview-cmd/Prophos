-- Polar-Plan e8f7e81a (Ina gegen Moritz) trug nach dem abgebrochenen Lauf 2a854cb4 (03:46 Dubai) noch start_um + start_um_gestartet_at —
-- die Karte zeigte 15 min „⏰ gestartet" statt „Starten" (Finn 21.10.2026: „da ist kein Start-Knopf"). Seit .1670 löst polar_app das nach
-- jedem Abbruch selbst; hier einmalig für diesen Plan, nur solange er noch geplant ist.
update trade_plans
   set start_um = null, start_um_gestartet_at = null
 where id = 'e8f7e81a-814d-4474-b3c7-949934c4fa63'
   and route = 'polar'
   and status = 'planned';
