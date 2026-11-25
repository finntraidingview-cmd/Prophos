-- Finn 25.11.2026: Blue Guardian kaufen wir nur noch als Nano. Schablone „Blue Guardian 100k Standard Phase 1“ aus (aktiv false) → Kaufliste/Kaufplan
-- und Bulk-Fenster nehmen „Blue Guardian 100k Nano Phase 1“ (145 €). Bestehende Standard-Konten unberührt. Rückweg: aktiv true. Idempotent.
update public.bulk_vorlagen set aktiv = false where id = '637fda5b-1ccb-4b3a-9901-d580d71f580a' and firm = 'Blue Guardian' and aktiv;
