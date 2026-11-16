-- Puls-Chrome für Jona (ljona2776, PC pc-b97zc7) und Ahmad (ahaj7167, PC pc-na1q6b), beide Emins Gruppe.
-- Finn 17.11.2026 ~03:25 Dubai: richtet auf beiden PCs gerade Puls-Chrome + Userscript ein. PC-IDs aus mt5_live (status.user_id, Herzschlag 23:24 UTC).
-- Beide Listen nötig (Lehre Marco 20.10. / Artur 17.11.2026: ohne Eintrag nimmt Puls den alten UIA-Weg im normalen Chrome; der Bot merkt die Regel
-- lokal bis zu 10 min in augen_regel.json — deshalb VOR dem ersten Test eintragen). Dazu die PC-Namen für Admin → PC-Tabs. Idempotent.

-- Je Liste nur die fehlenden PCs anhängen (ein UPDATE … FROM mit zwei Zeilen träfe die eine Regel-Zeile nur einmal)
update public.wd_farmer_regeln
   set puls_augen_cdp = coalesce(puls_augen_cdp, '{}') || array(select pc from unnest(array['pc-b97zc7', 'pc-na1q6b']) pc
                                                              where not (pc = any(coalesce(puls_augen_cdp, '{}')))),
       puls_topstep_pcs = coalesce(puls_topstep_pcs, '{}') || array(select pc from unnest(array['pc-b97zc7', 'pc-na1q6b']) pc
                                                                  where not (pc = any(coalesce(puls_topstep_pcs, '{}')))),
       updated_at = now()
 where id = 1;

insert into public.pc_namen (pc_id, name, updated_at) values ('pc-b97zc7', 'Jona', now()), ('pc-na1q6b', 'Ahmad', now())
on conflict (pc_id) do update set name = excluded.name, updated_at = now();

-- Kontrolle: select 'pc-b97zc7' = any(puls_augen_cdp), 'pc-na1q6b' = any(puls_augen_cdp), 'pc-b97zc7' = any(puls_topstep_pcs),
--            'pc-na1q6b' = any(puls_topstep_pcs) from public.wd_farmer_regeln where id = 1;
