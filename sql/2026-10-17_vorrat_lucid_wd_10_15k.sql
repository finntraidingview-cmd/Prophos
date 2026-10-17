-- 17.10.2026 Finn: „zum Musterportfolio einen Lucid-Account hinzufügen mit Winning Days: $10.000 bis $15.000". Lucid zählt wie
-- Apex/Tradeify/Topstep das Plus über der Startgröße der Winning-Days-Konten. Nachkauf-Einheit 150k (Bulk-Vorlage „Lucid 150k
-- Challenge" vom selben Tag). Firmenname „Lucid Trading" = _firm_norm in app.py, sonst findet die Rechnung die Konten nicht.
insert into vorrat_ziele (firma, art, typen, von, bis, groessen, kauf_einheit, reihe, kauf_groesse, updated_at)
select 'Lucid Trading', 'plus_ueber_start', array['winning_days'], 10000, 15000, null, '150k', 8, 150000, now()
where not exists (select 1 from vorrat_ziele where firma = 'Lucid Trading');
-- Prüfen: select firma, art, typen, von, bis, kauf_einheit, kauf_groesse, reihe from vorrat_ziele where firma = 'Lucid Trading';
