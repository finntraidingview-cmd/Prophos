-- PU3 Hand-Notiz je Payout-Anfrage (Finn 18.11.2026, Admin → Kasse → Payouts → „Payouts unterwegs“, Spalte Notiz: „bitte hier auch Notiz hinzufügen“).
-- Eigene Spalte statt notes: notes trägt den automatischen Text („Aus Admin angefragt · vorher: …“ aus payout_anfrage_notiz bzw. die Notiz aus Finanzen),
-- der beim „Erhalten“ in die transactions-Notiz wandert — den darf die Hand-Notiz nicht überschreiben. liegt_bei gehört dem Payout-Mail-Matcher.
-- admin_notiz liest und schreibt nur die Admin-Karte (GET /admin/overview, PATCH /admin/payout-notiz, Service-Key wie Approved/Erhalten) — keine RLS-Änderung.
-- Reihenfolge egal: ohne die Spalte zeigt die Karte keinen „+ Notiz“-Knopf, die Route antwortet 409 „Spalte fehlt“.
-- Nur Spalte, keine Daten. Idempotent.
alter table public.pending_payouts add column if not exists admin_notiz text;

-- Kontrolle
-- select status, count(*), count(admin_notiz) from public.pending_payouts group by 1;
