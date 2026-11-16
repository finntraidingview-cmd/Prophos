-- TW4-Ausnahme (Finn 16.11.2026 ~03:30 Dubai: „mach Simon mal rein für heute"): Simons Lucid-Challenges heute ohne Firmen-/Konto-Würfel.
-- Alle anderen Planer-Regeln bleiben (Waage, Tagesdeckel, Liq, Grenzen je ID/Firma). Morgen wieder normal gewürfelt.
insert into public.planer_wuerfel_ausnahme (user_id, firma, tag, angelegt_von)
values ('5409e926-09bc-4789-9c99-f8584d87a89a', 'Lucid Trading', '2026-11-16', 'Master SQL (Finn 16.11.2026)')
on conflict do nothing;
