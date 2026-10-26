-- NEUER PC PASCAL (Finn 27.10.2026 ~02:05 Dubai: erster eigener PC für Pascals ID, Puls-Chrome eingerichtet).
-- ID 728b4d23-ff5c-45f9-b6de-9b75c1f9a78a, PC pc-3wghru (puls_diagnose 22:05 UTC).
-- Befund: Konto „150k APEX…0006“ zeigte „Puls-Fenster unklar: nur ausgeschlossene Chrome-Fenster“ — das Puls-Chrome
-- (CDP, TradingView offen) war da, aber der PC stand nicht in puls_augen_cdp → Puls lief über UIA, und UIA schließt das
-- Puls-Chrome als Fremdprofil aus. Beide Listen wie bei Simon (Lehre Marco 20.10.2026), dazu der PC-Name.
-- Idempotent. Eingespielt vom Master 27.10.2026.

update public.wd_farmer_regeln
   set puls_augen_cdp = array_append(puls_augen_cdp, 'pc-3wghru'), updated_at = now()
 where id = 1 and not ('pc-3wghru' = any(coalesce(puls_augen_cdp, '{}')));

update public.wd_farmer_regeln
   set puls_topstep_pcs = array_append(puls_topstep_pcs, 'pc-3wghru'), updated_at = now()
 where id = 1 and not ('pc-3wghru' = any(coalesce(puls_topstep_pcs, '{}')));

insert into public.pc_namen (pc_id, name, updated_at) values ('pc-3wghru', 'Pascal', now())
on conflict (pc_id) do update set name = excluded.name, updated_at = now();

-- Kontrolle:
-- select puls_augen_cdp, puls_topstep_pcs from public.wd_farmer_regeln where id = 1;
-- select * from public.pc_namen where pc_id = 'pc-3wghru';
