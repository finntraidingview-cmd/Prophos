-- ============================================================================
-- Prophos: Wallet-Transfers im Archiv + Kommentar pro Transaktion (18.09.2026)
--
-- Finn 18.09.2026: „Ich will erstmal alles in die Datenbank … ich kann jeder
-- Transaktion so einen Kommentar draufklicken und sagen, was es war. Wir ziehen
-- oft Geld von der Wallet runter auf die Bank, weil wir Kunden-Payouts über die
-- Bank schicken … gern auch schon mit voreingestellten Jobs."
--
-- WARUM EIN ARCHIV UND NICHT NUR EINE KOMMENTAR-TABELLE: der Meta-Wallet-Tab
-- liest Transfers live von den Chains, und dieses Fenster ist kurz — BNB kennt
-- keyless nur die letzten ~Stunden, TronGrid gibt 10 Zeilen, Blockscout ~25.
-- Ohne Archiv wäre ein kommentierter Transfer am nächsten Tag aus dem Feed
-- verschwunden und der Kommentar mit ihm. Deshalb: jede einmal gesehene Zeile
-- wandert nach wallet_tx, der Feed zeigt Chain-Zeilen UND Archiv-Zeilen.
--
-- tx_key ist der stabile Schlüssel einer Transfer-ZEILE (nicht der Tx-Hash: eine
-- Solana-Tx kann mehrere Token-Bewegungen enthalten, und dieselbe Tx taucht bei
-- Sender UND Empfänger auf, wenn beide Wallets in Prophos stehen):
--   chain | hash-oder-ts-Minute | wallet-id | rein/raus | symbol | betrag(6)
-- Genau so baut ihn das Frontend (walTxKey) — beim Schreiben wie beim Lesen.
--
-- Das Frontend schreibt Archiv-Zeilen mit ignoreDuplicates: ein Lade-Lauf legt
-- nur NEUE Zeilen an und fasst einen bestehenden Kommentar nie an.
--
-- Wie id_wallets/wallet_labels bewusst NICHT nach user_id getrennt: der
-- Admin-Bereich verwaltet die Wallets aller Personen.
-- Im Supabase SQL Editor einfügen und auf "Run" klicken. Idempotent.
-- ============================================================================

-- ── Die Transfers selbst ────────────────────────────────────────────────────
create table if not exists public.wallet_tx (
  id           uuid primary key default gen_random_uuid(),
  tx_key       text not null unique,
  wallet_id    uuid references public.id_wallets(id) on delete set null,
  -- Kopien aus der Wallet-Zeile: eine gelöschte Wallet darf die Historie samt
  -- Kommentaren nicht mitnehmen (deshalb oben auch set null statt cascade).
  chain        text not null,
  address      text,
  person_name  text,
  hash         text,
  ts           timestamptz,           -- Blockzeit; null bei Zeilen jenseits der Archiv-Grenze
  dir          text not null check (dir in ('rein','raus')),
  amount       numeric not null,
  sym          text not null default '',
  other        text,                  -- Gegenseite (Adresse), wie von der Chain gelesen
  -- ── Der eigentliche Wunsch: was war das? ──
  kategorie    text,                  -- Vorlage aus wallet_tx_kategorien (freier Text erlaubt)
  kommentar    text,
  komm_von     text,                  -- E-Mail dessen, der zuletzt kommentiert hat
  komm_at      timestamptz,
  seen_at      timestamptz not null default now(),   -- wann Prophos die Zeile zuerst gesehen hat
  created_at   timestamptz not null default now()
);

create index if not exists wallet_tx_ts_idx        on public.wallet_tx (ts desc nulls last);
create index if not exists wallet_tx_wallet_idx    on public.wallet_tx (wallet_id, ts desc nulls last);
create index if not exists wallet_tx_kategorie_idx on public.wallet_tx (kategorie) where kategorie is not null;

alter table public.wallet_tx enable row level security;

drop policy if exists "wallet_tx read"   on public.wallet_tx;
drop policy if exists "wallet_tx insert" on public.wallet_tx;
drop policy if exists "wallet_tx update" on public.wallet_tx;
drop policy if exists "wallet_tx delete" on public.wallet_tx;

create policy "wallet_tx read"   on public.wallet_tx for select to authenticated using (true);
create policy "wallet_tx insert" on public.wallet_tx for insert to authenticated with check (true);
create policy "wallet_tx update" on public.wallet_tx for update to authenticated using (true) with check (true);
create policy "wallet_tx delete" on public.wallet_tx for delete to authenticated using (true);

-- ── Die voreingestellten „Jobs" ─────────────────────────────────────────────
-- Vorlagen, damit der Normalfall ein Klick ist statt getippter Text. Eigene
-- kommen im Modal dazu (source = 'manuell'); farbe ist ein Design-Token-Name
-- aus dem bestehenden System (violet/good/danger/sub), kein neues Muster.
create table if not exists public.wallet_tx_kategorien (
  id          uuid primary key default gen_random_uuid(),
  name        text not null unique,
  farbe       text not null default 'violet' check (farbe in ('violet','good','danger','sub')),
  sort        integer not null default 100,
  aktiv       boolean not null default true,
  source      text not null default 'seed',   -- 'seed' | 'manuell'
  created_at  timestamptz not null default now()
);

alter table public.wallet_tx_kategorien enable row level security;

drop policy if exists "wallet_tx_kat read"   on public.wallet_tx_kategorien;
drop policy if exists "wallet_tx_kat insert" on public.wallet_tx_kategorien;
drop policy if exists "wallet_tx_kat update" on public.wallet_tx_kategorien;
drop policy if exists "wallet_tx_kat delete" on public.wallet_tx_kategorien;

create policy "wallet_tx_kat read"   on public.wallet_tx_kategorien for select to authenticated using (true);
create policy "wallet_tx_kat insert" on public.wallet_tx_kategorien for insert to authenticated with check (true);
create policy "wallet_tx_kat update" on public.wallet_tx_kategorien for update to authenticated using (true) with check (true);
create policy "wallet_tx_kat delete" on public.wallet_tx_kategorien for delete to authenticated using (true);

-- Startwerte: die Fälle, die im Feed heute schon vorkommen (Account-Käufe und
-- Payouts über CoinPayments, interne Umbuchungen) plus Finns Bank-Weg.
insert into public.wallet_tx_kategorien (name, farbe, sort, source) values
  ('Kunden-Payout → Bank',   'danger', 10, 'seed'),
  ('Auszahlung an Person',   'danger', 20, 'seed'),
  ('Account-Kauf',           'danger', 30, 'seed'),
  ('Gebühren / Gas',         'sub',    40, 'seed'),
  ('Payout Prop-Firm',       'good',   50, 'seed'),
  ('Einzahlung',             'good',   60, 'seed'),
  ('Umbuchung intern',       'violet', 70, 'seed'),
  ('Privat',                 'sub',    80, 'seed'),
  ('Sonstiges',              'sub',    90, 'seed')
on conflict (name) do nothing;
