-- Trade-Planer komplett pausiert (Finn 29.10.2026 ~23:55 Dubai: „Machen wir morgen um 2 Uhr noch keine Trades, das wird zu viel
-- schiefgehen. Pause den kompletten Trade-Planer, bis ich den wieder freigebe."). auto_plan_regeln.aktiv = false stoppt Nachtlauf,
-- Nachplanen, Balance-Auto und Auto-Bestätigen (app.py ap_nachtlauf/ap_nachplan_tick/_ap_bal_auto/_ap_auto_best).
-- Wieder an NUR auf Finns Wort: update public.auto_plan_regeln set aktiv = true, updated_at = now() where id = 1;
update public.auto_plan_regeln set aktiv = false, updated_at = now() where id = 1;

-- Winning-Day-Farmer ebenfalls pausiert (gleiche Anweisung „morgen noch keine Trades"): aktiv = false, damit um 00:10 Dubai nicht
-- gewürfelt wird und ab 04:00 keine WD-Trades starten. scharf bleibt unverändert. Laufende Trades/Hedges bleiben unberührt.
-- Wieder an NUR auf Finns Wort: update public.wd_farmer_regeln set aktiv = true, updated_at = now() where id = 1;
update public.wd_farmer_regeln set aktiv = false, updated_at = now() where id = 1;
