-- ============================================================================
-- Prophos: BANKKONTEN je ID (BK1, 24.11.2026)
--
-- Finn 24.11.2026: „Da mittlerweile viel Geld bei Kunden auf Bankkonten … liegt, will ich — so was Ähnliches wie Meta-Wallets — auch
-- deren Bankkonto-Balance checken: indem ich dort immer manuell Transaktionen hinzufügen kann und von jeder ID auch die IBAN sehe …
-- Das alles unter Admin, neuer Reiter Finanzen, Finanzen unterteilt in Meta Wallet und Bankkonto. Bei Bankkonto das Ganze immer
-- manuell eintragen.“
--
--   bank_konten    je ID beliebig viele Konten (Zweck: Account-Kauf = Konto, auf das HT das Geld schickt; Vergütung = Kundenkonto
--                  für die Monatszahlung; Sonstiges). Saldo = start_saldo + Σ bank_buchungen.betrag.
--   bank_buchungen Hand-Buchungen (+ Eingang / − Ausgang). quelle 'sheet' = einmaliger Import aus den Sheets „Finanzen <Name>“
--                  (Master-Entscheid 24.11.2026: danach führt Prophos, die Sheets bleiben unangetastet als Archiv).
--
-- IBANs sind sensibel: gelesen und geschrieben wird NUR über app.py (bank_app.py, /admin/bank*, Service-Key, Gate wie Kapital:
-- Finn + Pascal alle HT-IDs, ein Verwalter nur seine Gruppe). RLS an, KEINE Policy für anon/authenticated, Rechte entzogen.
-- Keine echten Kontodaten in dieser Datei (Repo öffentlich) — Startdaten spielt der Master aus einer Datei außerhalb des Repos ein.
-- Kartendaten gehören nie hierher. Idempotent.
-- ============================================================================

create table if not exists public.bank_konten (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null references auth.users(id) on delete cascade,   -- die ID (Kunde), zu der das Konto gehört
  zweck         text not null default 'Account-Kauf' check (zweck in ('Account-Kauf','Vergütung','Sonstiges')),
  bank          text,
  inhaber       text,
  iban          text,
  bic           text,
  waehrung      text not null default 'EUR' check (waehrung in ('EUR','USD')),
  start_saldo   numeric not null default 0,
  start_am      date,
  notiz         text,
  aktiv         boolean not null default true,
  angelegt_von  text,
  created_at    timestamptz not null default now()
);
create index if not exists bank_konten_user_idx on public.bank_konten (user_id);

create table if not exists public.bank_buchungen (
  id            uuid primary key default gen_random_uuid(),
  konto_id      uuid not null references public.bank_konten(id) on delete cascade,
  datum         date not null default current_date,
  betrag        numeric not null check (betrag <> 0),
  text          text,
  art           text not null default 'Sonstiges'
                check (art in ('Einzahlung HT','Account-Kauf','Payout','Gebühr','Vergütung','Sonstiges')),
  quelle        text not null default 'hand' check (quelle in ('hand','sheet')),
  angelegt_von  text,
  created_at    timestamptz not null default now()
);
create index if not exists bank_buchungen_konto_idx on public.bank_buchungen (konto_id, datum, created_at);

-- RLS an, keine Policy für Logins: nur der Service-Key (app.py) kommt heran
alter table public.bank_konten    enable row level security;
alter table public.bank_buchungen enable row level security;
revoke all on public.bank_konten    from anon, authenticated;
revoke all on public.bank_buchungen from anon, authenticated;
grant all on public.bank_konten    to service_role;
grant all on public.bank_buchungen to service_role;

-- Backup-Agent liest wie bei allen Tabellen mit (lokales Backup auf dem Mac, prophos-backup-agent)
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'backup_reader') then
    execute 'grant select on public.bank_konten to backup_reader';
    execute 'grant select on public.bank_buchungen to backup_reader';
    execute 'drop policy if exists backup_reader_select on public.bank_konten';
    execute 'create policy backup_reader_select on public.bank_konten for select to backup_reader using (true)';
    execute 'drop policy if exists backup_reader_select on public.bank_buchungen';
    execute 'create policy backup_reader_select on public.bank_buchungen for select to backup_reader using (true)';
  end if;
end $$;

-- ── Leere Vorlage für die Startdaten (NICHT hier ausfüllen — echte Werte nur in einer Datei außerhalb des Repos) ──
-- insert into public.bank_konten (user_id, zweck, bank, inhaber, iban, bic, waehrung, angelegt_von)
--   values ('<uuid der ID>', 'Account-Kauf', '<Bank>', '<Inhaber>', '<IBAN>', '<BIC>', 'EUR', 'import');
-- insert into public.bank_buchungen (konto_id, datum, betrag, text, art, quelle, angelegt_von)
--   values ('<konto-uuid>', 'JJJJ-MM-TT', <±betrag>, '<Text aus dem Sheet>', 'Sonstiges', 'sheet', 'import');
