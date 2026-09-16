-- 2026-09-17 · Payout-Rechnung im Admin-Kalender (Finn: „wie viel Geld das
-- bei dem Payout ist … dass ich selber diese Summe bearbeiten kann").
-- payout_pct:      Anteil vom Gewinn in Prozent, NULL = 80 (Standard).
-- payout_override: fester Betrag in Konto-Währung, NULL = Rechnung gilt.
-- Beide reine Anzeige-Hilfe für /admin/overview + /admin/payout-calc —
-- keine Buchung, keine Finanzen-Summe hängt daran.
alter table public.accounts
  add column if not exists payout_pct numeric,
  add column if not exists payout_override numeric;
comment on column public.accounts.payout_pct is 'Payout-Anteil in %, NULL = 80';
comment on column public.accounts.payout_override is 'Fester Payout-Betrag (Konto-Währung), NULL = berechnet';
