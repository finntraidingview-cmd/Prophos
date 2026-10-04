-- Blue Guardian: echter Punktwert aus der MT5-Specification (Finn 04.10.2026):
-- NAS100 „US Tech 100 Index CFD", Kontraktgröße 10, Kalkulation CFD, Profitwährung USD
-- → 1 Lot = 10 $ je Punkt (ersetzt den vorläufigen Wert 1,0 aus 2026-10-04_blue_guardian_firma.sql).
-- Server laut Login: BlueGuardian-Server.
update firm_specs
set ppl = 10.0, symbol = 'NAS100', server = 'BlueGuardian-Server'
where name = 'Blue Guardian';
