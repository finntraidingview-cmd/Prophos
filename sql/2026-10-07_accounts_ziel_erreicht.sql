-- Ziel-Wache (07.10.2026, Finn: „Benachrichtigung, wenn irgendwo ein Account sein Ziel erreicht hat … dass der getaggt wird").
-- app.py zw_tick setzt die Spalten alle 5 min (Railway), Prophos zeigt den Tag „🎯 Ziel erreicht" und startet keinen Trade.
-- Nur Zusatzspalten, alle leer — nichts Bestehendes ändert sich.
alter table public.accounts add column if not exists ziel_erreicht_at timestamptz;
alter table public.accounts add column if not exists ziel_erreicht_bal numeric;
alter table public.accounts add column if not exists ziel_usd numeric;
