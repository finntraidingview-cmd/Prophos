-- TL1 Stufe 1 (Finn 19.11.2026, Master: „Erkennung Variante A, neue Spalte accounts.echtgeld (bool) mit Häkchen auf Jacobs 3 Konten“).
-- Anlass: Jacob bei Tradeify auf Elite Live (echtes Geld). Finn: „Unter Winning Days … Tradeify Live Accounts … als eigene Tabelle für Hedging,
-- weil ich dann wahrscheinlich mit viel, viel mehr gegenhedgen werde“. Erkennung NICHT über den Namen und NICHT über starting_balance = 0
-- (DB-Befund 19.11.: 5 alte Tradeify-Funded-Konten aus dem Juli tragen auch 0; account_type 'live' gehört den 32 Fusion-Hedgekonten).
-- echtgeld = true: Konto läuft mit echtem Geld (heute nur Tradeify Elite Live). Wirkung Stufe 1: WD-Schlüssel 'tradeifylive' (eigene TP-Zeile,
-- Kontrakte, Hedge-Tabelle unter Funded Planer → Winning Days → Einstellungen), Stand für die Hedge-Stufe = Balance selbst (Start 0).
-- Farmer/Auto-Planer bleiben an diesen Konten AUS (wd_farm/auto_planer werden hier NICHT angefasst).
-- Idempotent: add column if not exists, update nur die 3 Konten per id.

alter table public.accounts add column if not exists echtgeld boolean not null default false;

comment on column public.accounts.echtgeld is
  'TL1 19.11.2026: Konto mit echtem Geld (Tradeify Elite Live). Tradeify + echtgeld → WD-Schlüssel tradeifylive (eigene Hedge-Tabelle, Stand ab 0).';

update public.accounts
   set echtgeld = true
 where user_id = '368076fd-67c1-460c-aa86-38d81ae69350'
   and firm = 'Tradeify'
   and external_id in ('2332402', '2332403', '2332404')
   and echtgeld is distinct from true;

-- Kontrolle: genau 3 Zeilen, alle Jacob, alle wd_farm = false
-- select id, name, echtgeld, wd_farm, auto_planer from public.accounts where echtgeld;
