-- ============================================================================
-- Prophos: Gegenseiten-Labels im Meta-Wallet (15.09.2026) — CoinPayments erkennen
--
-- Finn 15.09.2026: „einen Weg finden, wie man CoinPayments-Dinge validieren
-- kann … und das ist dann so eine Anzeige für Account-Käufe".
--
-- BEFUND (15.09.2026, an den echten Arbitrum-Wallets nachvollzogen): jede
-- Zahlung an eine Prop-Firm geht an eine Einzahlungsadresse, die innerhalb von
-- ~5 Minuten in EINE Sammeladresse gesweept wird — 0x2dF9b935…3028D. Dieselbe
-- Adresse zahlt Payouts aus (Jacobs 471,81 USDT auf Ethereum, 15.09. 14:03).
-- Explorer-Labels (Etherscan/Arbiscan/TronScan) sind keyless nicht erreichbar,
-- Blockscout liefert keine Tags — also Erkennung über Verhalten:
--   kind = 'coinpayments_hot'      Sammel-/Auszahlungs-Wallet (Startwert unten)
--   kind = 'coinpayments_deposit'  Einzahlungsadresse, die nachweislich an die
--                                  Sammeladresse weiterleitet (lernt das Frontend)
--   kind = 'extern'                geprüft, leitet NICHT dorthin (gemerkt, damit
--                                  dieselbe Adresse nicht bei jedem Laden erneut
--                                  einen Blockscout-Call kostet)
-- Adressen werden klein geschrieben gespeichert (EVM ist case-insensitiv).
--
-- Wie id_wallets nicht nach user_id getrennt: Admin-Bereich, alle Personen.
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.wallet_labels (
  id          uuid primary key default gen_random_uuid(),
  chain       text not null,
  address     text not null,
  kind        text not null check (kind in ('coinpayments_hot','coinpayments_deposit','extern')),
  label       text,                          -- optional, z.B. „CoinPayments · Topstep" (manuell, später)
  source      text not null default 'auto',  -- 'seed' | 'auto' | 'manuell'
  created_at  timestamptz not null default now(),
  unique (chain, address)
);

alter table public.wallet_labels enable row level security;

drop policy if exists "wallet_labels read"   on public.wallet_labels;
drop policy if exists "wallet_labels insert" on public.wallet_labels;
drop policy if exists "wallet_labels update" on public.wallet_labels;
drop policy if exists "wallet_labels delete" on public.wallet_labels;

create policy "wallet_labels read"   on public.wallet_labels for select to authenticated using (true);
create policy "wallet_labels insert" on public.wallet_labels for insert to authenticated with check (true);
create policy "wallet_labels update" on public.wallet_labels for update to authenticated using (true) with check (true);
create policy "wallet_labels delete" on public.wallet_labels for delete to authenticated using (true);

-- Startwert: die CoinPayments-Sammeladresse — auf Arbitrum (56.000 Tx, alle
-- Sweeps der geprüften Einzahlungsadressen) und Ethereum (413.000 Tx, Payout
-- an Jacob). Auf Polygon hat sie 0 Tx (15.09.2026) — dort nicht eingetragen.
insert into public.wallet_labels (chain, address, kind, label, source) values
  ('arbitrum', '0x2df9b935c44057ac240634c7536511d8aa03028d', 'coinpayments_hot', 'CoinPayments', 'seed'),
  ('ethereum', '0x2df9b935c44057ac240634c7536511d8aa03028d', 'coinpayments_hot', 'CoinPayments', 'seed')
on conflict (chain, address) do nothing;
