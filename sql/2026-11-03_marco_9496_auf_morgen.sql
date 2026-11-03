-- MARCO THE5%ERS 200k …9496 AUF MORGEN (Finn 03.11.2026 ~22:30 Dubai: „Einfach auf morgen verschieben.")
-- Ursache (Slave 5, nur lesend): Plan 2e876ab9 (Echo mt5, BUY, bestätigt) wurde 13:27 UTC (17:27 Dubai) geclaimt, aber das MT5-Terminal des Kontos lief
-- auf dem PC von Marco (pc-t8wg97) nicht (CSV zuletzt 16:37 Dubai, kein terminal64) → keine Order-Antwort, Master-Konto nicht lesbar, start_fehler
-- „m5still" unklar. Das Terminal startete der Lotse 13:55 UTC neu (eingeloggt, Reader am Chart, Balance 193.017,18 $, keine Position) — es liegt nichts am Konto.
-- Warum eine Datei: Der Nachtlauf (ap_tagesreset, 01:30 Dubai) würde diesen Plan NICHT neu planen, sondern als „Start-Fehler unklar" nach Überprüfen
-- schieben (wie abc02a19 am 02.11.); danach plant ap_planen das Konto nicht („letzter Trade noch nicht erledigt"). Mit planned_for = morgen lässt der
-- Tagesreset ihn stehen, und der Planer zählt ihn als bestehenden Plan (bestätigt = kein Vorschlag, wird nicht ersetzt) → kein Doppel-Plan.
-- Was die Datei tut: derselbe Plan (Richtung, TP/SL, Echo-Hedge-Vorschau, Bestätigung bleiben) auf morgen 17:27 Dubai + 0–10 min gestreut, Claim und
-- Start-Fehler weg, status bleibt planned. Balance unverändert (193.017,18) → die Balance-Wache lässt ihn stehen.
-- Wiederholbar: greift nur, solange der Plan noch auf den 03.11. lautet und nie gesendet/gestartet ist.

update public.trade_plans
   set planned_for = '2026-11-04',
       start_um = timestamptz '2026-11-04 13:27:00+00' + make_interval(secs => floor(random() * 600)),
       start_um_gestartet_at = null,
       start_claim_art = null,
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) - 'start_fehler' - 'puls_spur' - 'start_sperre'
 where id = '2e876ab9-2f0e-4b71-b63f-45e2afa3e404'
   and status = 'planned' and started_at is null and orbit_gesendet_at is null
   and planned_for = '2026-11-03';

-- Kontrolle
select id, status, planned_for, start_um at time zone 'Asia/Dubai' as start_dubai, start_um_gestartet_at, auto_bestaetigt_at,
       mt5_baseline ? 'start_fehler' as noch_fehler
  from public.trade_plans where id = '2e876ab9-2f0e-4b71-b63f-45e2afa3e404';
