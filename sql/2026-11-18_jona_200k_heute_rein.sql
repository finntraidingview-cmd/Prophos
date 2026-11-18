-- Finn 18.11.2026 ~04:10 Dubai zu Jonas The5%ers 200k 26847792 (98bb2efa, External ID gerade korrigiert): „kannst du dann gleich neuplanen, dass er
-- heute gehandelt wird“. Das Konto hatte durch die falsche External ID die Boden-Sperre („geblowt?“) und keinen Plan. Würfel-Ausnahme nur für dieses
-- Konto heute (wie Marc …7821 am 17.11.) → der Funded-CFD-Takt plant es heute sicher ein. Idempotent.
insert into public.planer_wuerfel_ausnahme (user_id, firma, konto_id, tag, angelegt_von)
select a.user_id, null, a.id, date '2026-11-18', 'Master SQL (Finn 18.11.2026: Jona 200k …7792 heute planen)'
from public.accounts a
where a.id::text like '98bb2efa%'
  and not exists (select 1 from public.planer_wuerfel_ausnahme x where x.konto_id = a.id and x.tag = date '2026-11-18');
