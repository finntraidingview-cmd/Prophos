-- WD-Farmer wieder an (Finn 30.10.2026 ~02:10 Dubai: „Ja, WD-Farmer an“ — Anlass: Emins WD-Konto bekam keinen Plan).
-- Trade-Planer (auto_plan_regeln.aktiv) bleibt pausiert bis Finns eigene Freigabe.
update public.wd_farmer_regeln set aktiv = true, updated_at = now() where id = 1;
