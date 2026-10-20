-- NEUER PC SIMON (Finn 21.10.2026 02:20 Dubai: „neuer PC, Simon gehört zu Hermann Technologies")
-- ID simon.tihar95 = 5409e926-09bc-4789-9c99-f8584d87a89a, PC pc-pmqd8g (Railway tab-stand 16:29 UTC, Befund S2).
-- Zwei Listen, beide nötig (Lehre Marco 20.10.2026: puls_augen_cdp allein reicht nicht — der Topstep-Weg liest nur
-- puls_topstep_pcs und fällt sonst auf UIA ins Haupt-Chrome zurück). Dazu der PC-Name für Admin → PC-Tabs.
-- Idempotent. Eingespielt vom Master 21.10.2026 ~02:40 Dubai.

update public.wd_farmer_regeln
   set puls_augen_cdp = array_append(puls_augen_cdp, 'pc-pmqd8g'), updated_at = now()
 where id = 1 and not ('pc-pmqd8g' = any(coalesce(puls_augen_cdp, '{}')));

update public.wd_farmer_regeln
   set puls_topstep_pcs = array_append(puls_topstep_pcs, 'pc-pmqd8g'), updated_at = now()
 where id = 1 and not ('pc-pmqd8g' = any(coalesce(puls_topstep_pcs, '{}')));

insert into public.pc_namen (pc_id, name, updated_at) values ('pc-pmqd8g', 'Simon', now())
on conflict (pc_id) do update set name = excluded.name, updated_at = now();

-- Kontrolle:
-- select puls_augen_cdp, puls_topstep_pcs from public.wd_farmer_regeln where id = 1;
-- select * from public.pc_namen where pc_id = 'pc-pmqd8g';
