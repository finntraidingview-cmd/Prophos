-- PC von Hans (pc-czv8js) und PC von Julian (pc-6qnjpu): Puls-Chrome (CDP, %LOCALAPPDATA%\Prophos\puls-chrome) am 26.11.2026
-- von Finn eingerichtet (Abzeichen „Orbit V3 · Puls-Chrome“ steht unten rechts in TradingView). Puls ging trotzdem weiter ins
-- normale Chrome (puls_diagnose: gemerktes Fenster „Prophos - Google Chrome“, nie ein Eintrag in puls_augen), weil beide PCs in
-- keiner Puls-Liste standen → wie Artur 17.11.2026 (sql/2026-11-17_puls_cdp_artur_pc.sql) beide Listen setzen
-- (puls_augen_cdp für TradingView, puls_topstep_pcs für den Topstep-Weg, sonst UIA-Rückfall ins Haupt-Chrome). Idempotent.
update public.wd_farmer_regeln
   set puls_augen_cdp = array_append(array_append(puls_augen_cdp, 'pc-czv8js'), 'pc-6qnjpu'), updated_at = now()
 where id = 1
   and not ('pc-czv8js' = any(coalesce(puls_augen_cdp, '{}')))
   and not ('pc-6qnjpu' = any(coalesce(puls_augen_cdp, '{}')));

update public.wd_farmer_regeln
   set puls_topstep_pcs = array_append(array_append(puls_topstep_pcs, 'pc-czv8js'), 'pc-6qnjpu'), updated_at = now()
 where id = 1
   and not ('pc-czv8js' = any(coalesce(puls_topstep_pcs, '{}')))
   and not ('pc-6qnjpu' = any(coalesce(puls_topstep_pcs, '{}')));
