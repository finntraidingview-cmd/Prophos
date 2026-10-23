-- 23.10.2026 Finn: Tradeify CFD ins Muster-Portfolio — „Ziel 2× Accounts je 100k Funded, also 200k Accounts und Funds".
-- Wie Blue Guardian (sql/2026-10-17_muster_testfirmen_lucid_mffu_blueguardian.sql): Summe der Kontogrößen in Funded (CFD), Nachkauf 100k.
-- Testfirma: erst nur die ID mit dem ersten Konto, alle anderen IDs gesperrt — freischalten über das Schloss am Tacho.
-- Firmenname = _firm_norm in app.py. ERST NACH dem Push des Umbaus „Tradeify CFD ≠ Tradeify" einspielen (vorher normte _firm_norm
-- „Tradeify CFD" auf „Tradeify", die Rechnung hätte das Konto bei den Futures gezählt).
insert into vorrat_ziele (firma, art, typen, von, bis, groessen, kauf_einheit, reihe, kauf_groesse, updated_at)
select 'Tradeify CFD', 'groessen_summe', array['funded_cfd','funded'], 200000, 200000, null, '100k', 11, 100000, now()
where not exists (select 1 from vorrat_ziele where firma = 'Tradeify CFD');

insert into vorrat_matrix (user_id, firma, status, geaendert_at)
select u.id, 'Tradeify CFD', 'gesperrt', now()
  from auth.users u
 where u.id <> '48f272b4-913e-4598-a06a-1dcc3d5679fb'
on conflict (user_id, firma) do update set status = 'gesperrt', geaendert_at = now();
delete from vorrat_matrix where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and firma = 'Tradeify CFD';
-- Prüfen: select firma, art, von, bis, reihe from vorrat_ziele where firma = 'Tradeify CFD';
--         select status, count(*) from vorrat_matrix where firma = 'Tradeify CFD' group by 1;
