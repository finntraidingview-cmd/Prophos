-- WINNING-DAYS-FARMER: ZEITFENSTER STATT OPENING (08.10.2026, Finn: „Bisher öffnen sie zum Opening und pumpen dann den ganzen Tag in
-- eine Richtung … nur die Uhrzeiten anpassen: von Dubai-Zeit 5 Uhr morgens bis zum US-Markt-Opening bzw. 18 Uhr Dubai-Zeit … die
-- Zeitspanne von–bis selbst eingeben"). Das Frontend (wdWuerfeln/wdZeitenVerteilen, ab 2026-09-22.1352) verteilt die Blöcke je ID
-- zufällig und gleichmäßig über [start_hhmm, bis_hhmm] Dubai (nur Firmen-Abstand 1 min hinter dem letzten Konto eines Blocks)
-- statt ab start_hhmm im 20–55-min-Takt.
--   bis_hhmm   neu, Standard '18:00' — „Spätestens · Dubai" in Admin → Winning Days → Einstellungen → Ablauf → Zeiten
--   start_hhmm '02:00' → '05:00' (Standard der Spalte ebenso)
-- Ohne dieses SQL rechnet der Code mit 18:00 als Spätestens, „Spätestens" ist dann gesperrt; „Start ab" bleibt änderbar.
-- Wiederholbar. Rückbau: alter table … drop column bis_hhmm; start_hhmm wieder '02:00'.
alter table public.wd_farmer_regeln add column if not exists bis_hhmm text not null default '18:00'
  check (bis_hhmm ~ '^\d{1,2}:\d{2}$');
alter table public.wd_farmer_regeln alter column start_hhmm set default '05:00';
update public.wd_farmer_regeln set start_hhmm = '05:00', bis_hhmm = '18:00', updated_at = now() where id = 1;
-- Prüfen: select start_hhmm, bis_hhmm, tz from public.wd_farmer_regeln where id = 1;
