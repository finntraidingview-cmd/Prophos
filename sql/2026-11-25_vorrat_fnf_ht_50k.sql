-- Finn 25.11.2026: Hermann Technologies kauft bei FundedNext Futures ab jetzt nur noch 50k (wie Emin, vorrat_ziele_gruppe). Kaufliste/Kaufplan-Vorschlag
-- in 50k-Einheiten. Laufende 150k-Konten bleiben im Challenge-Planer (groessen 50000+150000 unverändert). Ziel-Spanne 10–15k bleibt. Idempotent.
update public.vorrat_ziele set kauf_einheit = '50k', kauf_groesse = 50000, updated_at = now()
 where firma = 'FundedNext Futures' and kauf_groesse = 150000;
