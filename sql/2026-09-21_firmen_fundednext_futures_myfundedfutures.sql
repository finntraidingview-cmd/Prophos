-- FundedNext Futures + MyFundedFutures als Firmen für ALLE Prophos-Logins
-- (Finn 21.09.2026: „neue Propfirm bitte hinzufügen in die DB für alle
-- Accounts — FundedNext Futures … Mapping mit NQ/MNQ genau wie bei Tradeify …
-- für alle IDs" + Nachtrag „und MyFundedFuture bitte auch").
--
-- firm_specs ist pro User (unique user_id + name). Die Zeile wird je User aus
-- SEINER Tradeify-Zeile kopiert (Symbol MNQ, Kontrakte, $2/Pkt, Duplikum-Symbol
-- = aktueller NQ-Frontkontrakt) — damit ist sie garantiert identisch zu dem,
-- womit er Tradeify heute schon spiegelt. Hat ein User keine Tradeify-Zeile,
-- greifen dieselben Werte als Vorgabe (NQZ6 = Frontkontrakt seit dem
-- September-Roll).
--
-- Bewusst NUR für User, die schon firm_specs-Zeilen haben: wer noch keine hat,
-- bekommt beim ersten Login die Standardliste geseedet (DEFAULT_FIRM_SPECS im
-- Frontend, dort stehen beide Firmen ab jetzt mit drin). Eine einzelne
-- Zeile von hier würde diesen Seed verhindern — er hätte dann NUR diese Firma.
--
-- Mehrfach ausführbar: on conflict do nothing fasst bestehende Zeilen nicht an.

insert into firm_specs (user_id, name, symbol, unit, ppl, currency, dup_symbol)
select u.user_id,
       n.name,
       coalesce(t.symbol, 'MNQ'),
       coalesce(t.unit, 'Kontrakte'),
       coalesce(t.ppl, 2.00),
       coalesce(t.currency, '$'),
       coalesce(t.dup_symbol, 'NQZ6')
from (select distinct user_id from firm_specs) u
cross join (values ('FundedNext Futures'), ('MyFundedFutures')) as n(name)
left join lateral (
  select symbol, unit, ppl, currency, dup_symbol
  from firm_specs f
  where f.user_id = u.user_id and lower(f.name) = 'tradeify'
  limit 1
) t on true
on conflict (user_id, name) do nothing;
