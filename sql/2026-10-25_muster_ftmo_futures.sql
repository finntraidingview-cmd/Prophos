-- 25.10.2026 Finn: FTMO Futures ins Muster-Portfolio — „bei FTMO Futures ist einfach Ziel 5k bei Winning Days".
-- Wie Lucid / FundedNext Futures (plus_ueber_start, Typ winning_days), Ziel 5.000 $ über Start, Nachkauf 50k Pro.
-- FundedNext Futures 50k Flex: kein eigener Eintrag — zählt unter „FundedNext Futures" mit, Muster dort unverändert (Finn).
-- Testfirma wie Tradeify CFD / Blue Guardian: erst nur „Finn + Pascal" frei, alle anderen IDs gesperrt — freischalten über das Schloss
-- am Tacho. Firmenname = app.py _firm_norm („FTMO Futures" seit sql/2026-10-25_ftmo_futures_firma_key.sql + Push .1734).
insert into vorrat_ziele (firma, art, typen, von, bis, groessen, kauf_einheit, reihe, kauf_groesse, updated_at)
select 'FTMO Futures', 'plus_ueber_start', array['winning_days'], 5000, 5000, null, '50k Pro', 12, 50000, now()
where not exists (select 1 from vorrat_ziele where firma = 'FTMO Futures');

insert into vorrat_matrix (user_id, firma, status, geaendert_at)
select u.id, 'FTMO Futures', 'gesperrt', now()
  from auth.users u
 where u.id <> '48f272b4-913e-4598-a06a-1dcc3d5679fb'
on conflict (user_id, firma) do nothing;
delete from vorrat_matrix where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and firma = 'FTMO Futures';
-- Prüfen: select firma, art, von, bis, reihe from vorrat_ziele where firma = 'FTMO Futures';
--         select status, count(*) from vorrat_matrix where firma = 'FTMO Futures' group by 1;
