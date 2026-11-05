-- SIMON TOPSTEP HEUTE NUR SHORT (Finn 05.11.2026 ~05:30 Dubai: „bei Simon bitte Topstep heute nur short“).
-- Einziger offener Topstep-Plan von Simon: 72c7bafb (150K …78201817, Kette 1/2, Start 06:59 Dubai) stand auf buy → sell.
-- TP/SL sind $-Beträge (2.002 / 1.749), keine Kurse — Richtungswechsel ändert sonst nichts. hand_werte_at schützt vor Überschreiben durch Nachplanen.
-- Nur solange planned und nicht gestartet. Idempotent.
update public.trade_plans
   set richtung = 'sell', hand_werte_at = now(),
       notes = coalesce(notes, '') || ' · Finn 05.11.: heute nur Short'
 where id = '72c7bafb-c43f-4907-99a6-6104726d15af' and status = 'planned' and started_at is null and richtung <> 'sell';
