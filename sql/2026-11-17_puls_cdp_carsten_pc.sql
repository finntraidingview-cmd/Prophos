-- Neuer Kunde Carsten (carstenschweiz…, ID 7fc987c0, Gruppe Hermann Technologies seit 16.11.2026), eigener neuer PC pc-8uf5j1
-- (pc_id.json gesetzt 16.11.2026 16:51, von Finn 17.11.2026 ~04:28 Dubai per PowerShell abgelesen). Finn hat Puls-Chrome, TV-Reader 0.9.11 und
-- Userscript 0.10.9 eingerichtet. Beide Listen nötig (Lehre Marco 20.10. / Artur 17.11.: sonst UIA-Weg im normalen Chrome) + PC-Name. Idempotent.

update public.wd_farmer_regeln
   set puls_augen_cdp = coalesce(puls_augen_cdp, '{}') || array(select pc from unnest(array['pc-8uf5j1']) pc
                                                              where not (pc = any(coalesce(puls_augen_cdp, '{}')))),
       puls_topstep_pcs = coalesce(puls_topstep_pcs, '{}') || array(select pc from unnest(array['pc-8uf5j1']) pc
                                                                  where not (pc = any(coalesce(puls_topstep_pcs, '{}')))),
       updated_at = now()
 where id = 1;

insert into public.pc_namen (pc_id, name, updated_at) values ('pc-8uf5j1', 'Carsten', now())
on conflict (pc_id) do update set name = excluded.name, updated_at = now();

-- Kontrolle: select 'pc-8uf5j1' = any(puls_augen_cdp), 'pc-8uf5j1' = any(puls_topstep_pcs) from public.wd_farmer_regeln where id = 1;
