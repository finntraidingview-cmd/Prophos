-- 17.10.2026 Finn: Testfirmen ins Muster-Portfolio — erst nur die ID „Finn + Pascal" testet sie, alle anderen IDs gesperrt
-- („wenn es ein Approved wird, gebe ich es frei"). Freischalten danach wie gewohnt über das Schloss am Tacho.
--   Lucid Trading   — 10.000–15.000 Plus über Start in Winning Days (Ziel stand schon, sql/2026-10-17_vorrat_lucid_wd_10_15k.sql)
--   MyFundedFutures — 10.000–15.000 Plus über Start in Winning Days, Nachkauf 150k (Bulk-Vorlage „MyFundedFutures 150k Eval Pro")
--   Blue Guardian   — 100k–200k Summe der Kontogrößen in Funded (CFD), wie FTMO
-- Firmennamen = _firm_norm in app.py (sonst findet die Rechnung die Konten nicht).
insert into vorrat_ziele (firma, art, typen, von, bis, groessen, kauf_einheit, reihe, kauf_groesse, updated_at)
select 'MyFundedFutures', 'plus_ueber_start', array['winning_days'], 10000, 15000, null, '150k Eval Pro', 9, 150000, now()
where not exists (select 1 from vorrat_ziele where firma = 'MyFundedFutures');
insert into vorrat_ziele (firma, art, typen, von, bis, groessen, kauf_einheit, reihe, kauf_groesse, updated_at)
select 'Blue Guardian', 'groessen_summe', array['funded_cfd','funded'], 100000, 200000, null, '100k', 10, 100000, now()
where not exists (select 1 from vorrat_ziele where firma = 'Blue Guardian');

-- Sperre: jede ID außer „Finn + Pascal" (48f272b4…) gesperrt; dort frei (keine Zeile = frei)
insert into vorrat_matrix (user_id, firma, status, geaendert_at)
select u.id, f.firma, 'gesperrt', now()
  from auth.users u
 cross join (values ('Lucid Trading'), ('MyFundedFutures'), ('Blue Guardian')) f(firma)
 where u.id <> '48f272b4-913e-4598-a06a-1dcc3d5679fb'
on conflict (user_id, firma) do update set status = 'gesperrt', geaendert_at = now();
delete from vorrat_matrix
 where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and firma in ('Lucid Trading', 'MyFundedFutures', 'Blue Guardian');
-- Prüfen: select firma, status, count(*) from vorrat_matrix where firma in ('Lucid Trading','MyFundedFutures','Blue Guardian') group by 1,2;
