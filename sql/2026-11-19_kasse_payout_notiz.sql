-- KN1 Payout-Notiz je Konto in der Kasse (Finn 19.11.2026, Admin → Payouts · alle IDs, #kasse, Tabelle PERSON · ACCOUNT · FIRMA · STAND · BALANCE ·
-- ANFRAGBAR: „füg das ich hier auch Payouts Notizen machen kann hinzu“). Die Kasse-Zeilen sind KONTEN (noch keine Anfrage) → eigene Spalte am Konto.
-- Bewusst getrennt von:
--   * pending_payouts.admin_notiz (PU3, sql/2026-11-18_payout_notiz.sql) — gehört der einzelnen ANFRAGE und endet mit ihr,
--   * accounts.review_notiz (Radar → Bestanden/Review, sql/2026-10-30_review_notiz.sql) — andere Ansicht, anderer Zweck,
--   * accounts.notes (allgemeine Konto-Notiz aus dem Konto-Dialog, u. a. vom Kontoart-Wechsel beschrieben).
-- Lesen: GET /admin/overview (payout_ready[].payout_notiz), schreiben: PATCH /admin/kasse-notiz (Service-Key, Rechte wie PU3) — keine RLS-Änderung.
-- Kein Trigger auf accounts hört auf diese Spalte (die bestehenden sind „update of on_demand / payout_ready_at / account_type“).
-- Reihenfolge egal: ohne die Spalte liefert die Übersicht leere Notizen, das PATCH antwortet 409 „Spalte fehlt“ (Toast im Admin).
-- Nur Spalte, keine Daten. Idempotent.
alter table public.accounts add column if not exists payout_notiz text;

-- Kontrolle
-- select count(*) filter (where payout_notiz is not null) as mit_notiz, count(*) from public.accounts;
