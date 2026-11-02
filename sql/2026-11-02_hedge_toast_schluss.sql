-- HEDGE-SCHNELLER (Finn 02.11.2026): Schalter für den Fusion-Schluss per Exit-Fill-Meldung, eigene Spalte (Speichern der Hedge-Tabelle überschreibt vorplan ganz).
-- Standard AUS (Prüfer S9, Finn): an erst, wenn 0.10.7 gemeldet und der Mini-Test auf zwei Konten im selben Login durch ist. Der Tab liest den Schalter alle 10 s, solange ein Hedge offen ist; ohne Spalte Flach-Weg.
-- An:  update public.wd_farmer_regeln set hedge_toast_schluss = true where id = 1;
-- Aus: update public.wd_farmer_regeln set hedge_toast_schluss = false where id = 1;
alter table public.wd_farmer_regeln add column if not exists hedge_toast_schluss boolean not null default false;
