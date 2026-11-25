-- PC von Aaron (pc-doasoo, Mini-Backend-Laptop seit 25.11.2026): Puls-Chrome ist eingerichtet, Puls ging aber weiter ins normale
-- Chrome (Finn 26.11.2026: „öffnet bei Aaron immer im falschen Chrome“; puls_diagnose: gemerktes Fenster „Prophos - Google Chrome“,
-- nie ein Eintrag in puls_augen), weil der PC in keiner Puls-Liste stand → wie Hans/Julian am selben Tag
-- (sql/2026-11-26_puls_cdp_hans_julian_pc.sql) beide Listen setzen. Idempotent.
update public.wd_farmer_regeln
   set puls_augen_cdp = array_append(puls_augen_cdp, 'pc-doasoo'), updated_at = now()
 where id = 1 and not ('pc-doasoo' = any(coalesce(puls_augen_cdp, '{}')));

update public.wd_farmer_regeln
   set puls_topstep_pcs = array_append(puls_topstep_pcs, 'pc-doasoo'), updated_at = now()
 where id = 1 and not ('pc-doasoo' = any(coalesce(puls_topstep_pcs, '{}')));
