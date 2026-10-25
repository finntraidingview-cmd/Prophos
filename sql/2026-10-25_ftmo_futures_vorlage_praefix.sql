-- Vorlage „FTMO Futures 50k Pro" automatisch für Kennungen „FTMO…" (Finn 25.10.2026, Dashboard-Kennung „FTMO397898"): Bulk-Hinzufügen
-- wählt die Vorlage über muster_praefix (bulkVorlageFuer, längster Präfix gewinnt). FTMO-CFD-Logins sind reine Zahlen — kein Konflikt.
update bulk_vorlagen set muster_praefix = 'FTMO', updated_at = now()
where name = 'FTMO Futures 50k Pro' and muster_praefix is distinct from 'FTMO';
