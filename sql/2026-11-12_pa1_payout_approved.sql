-- PA1 „Approved“-Schritt bei Payouts unterwegs (Finn 12.11.2026 ~20:05 Dubai: „Oft werden Payouts aber approved, und es dauert noch 3–4 Tage, bis sie
-- wirklich geschickt werden … Bei ‚Approved‘ wird das Konto schon wieder freigeschaltet und für Winning Days gefahren. Bei ‚Erhalten‘ wird erst wirklich zu
-- Finanzen gebucht“).
-- approved_at gesetzt = die Anfrage (status pending) sperrt das Konto nicht mehr für die Planer (app.py payout_sperrt / _payout_offen_ids, PC-Tab
-- wdKontenFrisch); gebucht wird weiter erst mit „Erhalten“ (/admin/payout-erhalten). approved_von = user_id des Logins, der Approved geklickt hat.
-- Nur Spalten, keine Daten: bestehende Anfragen bleiben ohne approved_at (zeigen [Approved], sperren wie bisher).
-- Reihenfolge egal: der Code liest ohne die Spalten wie vor PA1 (jede offene Anfrage sperrt), die Approved-Route antwortet dann 409 „Spalte fehlt“.
-- Idempotent.
alter table public.pending_payouts add column if not exists approved_at timestamptz;
alter table public.pending_payouts add column if not exists approved_von text;

-- Kontrolle
-- select status, count(*), count(approved_at) from public.pending_payouts group by 1;
