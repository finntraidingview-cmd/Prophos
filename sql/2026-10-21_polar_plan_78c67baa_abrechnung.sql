-- Polar-Plan 78c67baa (Ina gegen Moritz, Lauf 3cc4d9b7, 21.10.2026 04:50–04:54 Dubai) blieb nach dem Lauf auf planned mit
-- start_um_gestartet_at: das „open" nach dem Master-Fill kam nicht in der DB an, _abrechnen schreibt nur auf open/review → Plan
-- unverändert, „Polar starten" meldete „schon gestartet" (Finn: „ich kann irgendwie nicht starten"). Railway-Log 00:54:15 UTC:
-- „3cc4d9b7 abgerechnet: Master -40.04 · Slave 0.49 · Verzug 6593 ms". Hier einmalig nachgetragen wie _abrechnen (review + beide P&L).
update trade_plans
   set status = 'review',
       started_at = to_timestamp(1792543889.493),
       ended_at = to_timestamp(1792544048.480),
       master_pl = -40.04,
       slave_pl = 0.49
 where id::text like '78c67baa%'
   and route = 'polar'
   and status = 'planned';
