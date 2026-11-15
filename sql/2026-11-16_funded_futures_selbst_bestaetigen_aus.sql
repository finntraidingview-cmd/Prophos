-- Funded-Planer Futures: „Selbst bestätigen" aus (Finn 16.11.2026 ~03:50 Dubai: „ich habs grad auf off gestellt" — der Schalter kam in
-- funded_plan_regeln nicht an, Wert blieb true, updated_at 03:48 vom Tradeify-Schalter). Finn will den Tradeify-Test für Simon erst ansehen,
-- dann selbst bestätigen. Folge: neue Vorschläge (auch Apex) entstehen OHNE Startzeit und warten auf Bestätigen im Funded-Planer.
update public.funded_plan_regeln set auto_bestaetigen = false, updated_at = now() where id = 1 and auto_bestaetigen is true;
