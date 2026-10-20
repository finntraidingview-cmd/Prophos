-- Polar-Pläne von 03:18/03:20 Dubai (21.10.2026) standen auf dem UTC-Vortag (planned_for 2026-10-20) — polar_app.py legte
-- planned_for in UTC an (seit .1665 Dubai-Tag). Ohne Korrektur zeigt die Karte den falschen Tag und der Tages-Reset im
-- Nachtlauf (planned_for < Zieltag) räumt die ungestarteten Pläne ab. Nur diese zwei, nur solange noch geplant.
update trade_plans
   set planned_for = '2026-10-21'
 where route = 'polar'
   and status = 'planned'
   and planned_for = '2026-10-20'
   and id in ('f71b0ced-4e49-4401-b789-e52a7dc6d731', '23f8aee0-a0c6-4631-be66-d8c61aec5322');
