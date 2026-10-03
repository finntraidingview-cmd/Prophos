-- Blue Guardian als CFD-Firma (Finn 04.10.2026: 2 × 100k 2-Step Standard gekauft).
-- Eine Zeile je Nutzer wie bei den anderen Firmen, sonst fällt firmToPreset() für
-- den Namen ins Futures-Preset (MNQ, Kontrakte) zurück.
-- ppl 1.0 ist VORLÄUFIG: der Punktwert je Lot steht nirgends öffentlich, Finn liest
-- ihn gleich aus der MT5-Specification ab → dann per UPDATE korrigieren.
-- Idempotent: legt nur an, wo der Nutzer noch keine Blue-Guardian-Zeile hat.
insert into firm_specs (user_id, name, symbol, unit, ppl, currency)
select u.user_id, 'Blue Guardian', 'NAS100', 'Lots', 1.0, '$'
from (select distinct user_id from firm_specs) u
where not exists (
  select 1 from firm_specs f where f.user_id = u.user_id and f.name = 'Blue Guardian'
);
