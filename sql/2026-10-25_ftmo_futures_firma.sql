-- FTMO Futures als neue Futures-Firma für ALLE Prophos-Logins (Finn 25.10.2026, zur Vorlage „FTMO Futures 50k Pro").
-- Eigener Name statt „FTMO", damit die Konten nicht unter der CFD-Firma (NAS100, Lots) laufen.
-- Wie FundedNext Futures / MyFundedFutures (sql/2026-09-21_firmen_…): Zeile je User aus SEINER Tradeify-Zeile
-- kopiert (MNQ, Kontrakte, $2/Pkt, Duplikum-Symbol = aktueller NQ-Frontkontrakt), sonst dieselben Werte als Vorgabe.
-- Nur für User mit bestehenden firm_specs-Zeilen — eine einzelne Zeile würde den Erst-Login-Seed verhindern.
-- Planer-Behandlung (tpFirmIstFutures, prophos_firma_key) bewusst NOCH NICHT — macht Finn danach.
-- Mehrfach ausführbar: on conflict do nothing.

insert into firm_specs (user_id, name, symbol, unit, ppl, currency, dup_symbol)
select u.user_id,
       'FTMO Futures',
       coalesce(t.symbol, 'MNQ'),
       coalesce(t.unit, 'Kontrakte'),
       coalesce(t.ppl, 2.00),
       coalesce(t.currency, '$'),
       coalesce(t.dup_symbol, 'NQZ6')
from (select distinct user_id from firm_specs) u
left join lateral (
  select symbol, unit, ppl, currency, dup_symbol
  from firm_specs f
  where f.user_id = u.user_id and lower(f.name) = 'tradeify'
  limit 1
) t on true
on conflict (user_id, name) do nothing;
