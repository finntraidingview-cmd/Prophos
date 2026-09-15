-- 2026-09-15 — Payout-Termin pro Account (Finn: "bei CFD-Accounts direkt ein
-- Feld, an welchem Datum ich den Payout anfragen kann"). CFD-Firmen zahlen in
-- Zeitfenstern (alle 14 Tage / monatlich ab Funded-Datum) — das Datum trägt
-- Finn beim Anlegen bzw. unter „Account bearbeiten" ein. Das Frontend zeigt es
-- auf der Account-Karte („Payout ab …" / „anfragbar seit …"), der Admin-Tab
-- Finanzen listet alle Termine über alle Personen als Kalender. Beim Payout-
-- Anfragen (Finanzen → Payout anfragen bzw. direkt gebucht) wird das Datum
-- geleert — der Termin ist verbraucht, den nächsten setzt Finn neu.
alter table public.accounts
  add column if not exists payout_ready_at date;   -- ab wann der nächste Payout angefragt werden kann (null = kein Termin)
