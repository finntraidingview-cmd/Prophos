-- Alle wartenden Starts +1 h (Finn 06.11.2026 ~03:35 Dubai: „Alle Pläne, die noch aktiv sind, nicht starten, mal 1 Stunde nach hinten verschieben.
-- Gerade ist auf Fusion Market der Spread ein bisschen scam, weil das Volumen so hoch ist. Ich melde mich, wenn der Spread wieder normal ist").
-- Wie der UI-Weg „Startzeit ändern": start_um + 60 min, Abstände untereinander bleiben gleich (Gegenrichtung/Firmen-Abstand unverändert).
-- Nur status planned, nie gestartet, NICHT geclaimt (ein geclaimter Plan ist mitten im Start — Claim nicht anfassen, sonst Doppelstart).
-- WD-Farmer-Pläne: wd_tagesplan des Tages mitziehen, sonst setzt der Farmer die Startzeiten zurück (Vorfall Jacob 05.11.2026).
-- Alle Gruppen (HT + Emin): der Spread trifft jeden Fusion-Hedge. Rückweg = dieselbe Datei mit −60 min bzw. neu planen.
begin;

update public.trade_plans
   set start_um = start_um + interval '60 minutes'
 where status = 'planned' and started_at is null and start_um is not null
   and start_um_gestartet_at is null
   and start_um >= now() and start_um < now() + interval '24 hours'
   and coalesce(notes, '') not like '%[+1h Spread 06.11.]%';

update public.wd_tagesplan
   set start_um = start_um + interval '60 minutes', updated_at = now()
 where tag = '2026-11-06' and status = 'geplant' and gestartet_at is null
   and start_um is not null and start_um >= now();

commit;
