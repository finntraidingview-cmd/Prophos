-- Werte von Hand (08.10.2026, Finn/Master: TP, SL und Größe eines geplanten Trades per Mini-Popup ändern).
-- app.py POST /admin/auto-plan/plan aktion „werte" setzt die Spalte; so ein Plan zählt für den Ausgleichs-Bot als fest
-- („Werte von Hand geändert" — nie drehen/verschieben) und wird vom Nachtlauf nicht ersetzt. Bestätigen und Start unberührt.
-- Nur eine Zusatzspalte, leer — nichts Bestehendes ändert sich.
alter table public.trade_plans add column if not exists hand_werte_at timestamptz;
comment on column public.trade_plans.hand_werte_at is
  'Zeitpunkt der letzten Hand-Änderung von TP/SL/Größe (aktion werte) — Bot und Nachtlauf lassen den Plan dann stehen';
