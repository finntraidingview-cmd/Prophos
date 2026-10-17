-- 17.10.2026 Finn: „Ich habe gemeint: Funded Next Futures, nicht MyFundedFutures." Korrektur zu
-- sql/2026-10-17_muster_testfirmen_lucid_mffu_blueguardian.sql: MyFundedFutures wieder raus (Ziel + Sperren), stattdessen
-- FundedNext Futures 10.000–15.000 Plus über Start in Winning Days (dort läuft schon ein WD-Konto), Nachkauf 150k
-- (Bulk-Vorlage „FundedNext Futures 150k Challenge"). Frei nur bei „Finn + Pascal" (48f272b4…), alle anderen IDs gesperrt.
delete from vorrat_matrix where firma = 'MyFundedFutures';
delete from vorrat_ziele where firma = 'MyFundedFutures';

insert into vorrat_ziele (firma, art, typen, von, bis, groessen, kauf_einheit, reihe, kauf_groesse, updated_at)
select 'FundedNext Futures', 'plus_ueber_start', array['winning_days'], 10000, 15000, null, '150k Challenge', 9, 150000, now()
where not exists (select 1 from vorrat_ziele where firma = 'FundedNext Futures');

insert into vorrat_matrix (user_id, firma, status, geaendert_at)
select u.id, 'FundedNext Futures', 'gesperrt', now()
  from auth.users u
 where u.id <> '48f272b4-913e-4598-a06a-1dcc3d5679fb'
on conflict (user_id, firma) do update set status = 'gesperrt', geaendert_at = now();
delete from vorrat_matrix where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and firma = 'FundedNext Futures';
-- Prüfen: select firma, status, count(*) from vorrat_matrix where firma in ('FundedNext Futures','MyFundedFutures') group by 1,2;
