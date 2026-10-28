-- TV-KONTEN AUS DEM KONTO-UMSCHALTER (Finn 29.10.2026 03:10: „Konten automatisch anlegen über das Konto-Dropdown in TradingView —
-- fast noch besser als Mail"). Der Puls-Chrome-Reader (Userscript ≥ 0.9.13) liest die Einträge der Tradovate-Konto-Liste, sobald sie
-- ohnehin offen ist (Puls-Kontowechsel oder Hand — nie ein eigener Klick), der reader-server schickt die Namen an Railway
-- (POST /reader/tv-konten, Schlüssel uid.pc.sig wie /reader-kurs), Railway schreibt mit dem Service-Key. Der Admin-Reiter
-- „Konten aus Mail & TV" (GET /admin/tv-konten) zeigt neue Namen als Zeile. Schnittstelle fest mit S7 (Master 29.10.2026).
-- RLS an, KEINE Policy → nur das Backend liest/schreibt. Idempotent.
create table if not exists public.tv_konten (
  user_id    uuid not null,
  name       text not null check (name ~ '^[A-Z0-9][A-Z0-9_-]{5,39}$'),   -- voller Kontoname wie in TradingView (PAAPEX6843320000001, FTDFYSLX…)
  pc_id      text,                                                      -- Puls-Chrome-PC, der ihn zuletzt gesehen hat
  quelle     text not null default 'dropdown' check (quelle in ('dropdown', 'umschalter')),
  zuerst_at  timestamptz not null default now(),                        -- nur beim Insert (Upsert schickt die Spalte nicht mit)
  zuletzt_at timestamptz not null default now(),
  primary key (user_id, name)
);
-- Nachtrag Schnittstelle S7 (Master 29.10.2026): Kasten „Neue Konten aus TradingView · noch zu bestätigen" unter Accounts der ID
alter table public.tv_konten add column if not exists ignoriert_at        timestamptz;   -- „Ignorieren" (PATCH /tv-konten/mein), null = sichtbar
alter table public.tv_konten add column if not exists angelegt_account_id uuid;          -- „Bestätigen" hat dieses Konto angelegt
create index if not exists tv_konten_zuletzt_idx on public.tv_konten (zuletzt_at desc);
alter table public.tv_konten enable row level security;
-- Prüfung: select user_id, name, pc_id, quelle, zuerst_at, zuletzt_at from tv_konten order by zuletzt_at desc limit 50;

-- AUFTRÄGE (Finn 29.10.2026 03:25: „Jedes Mal, wenn eine Konto-Mail reinkommt, wird im Zufallsintervall 5 Minuten bis 3 Stunden einmal ganz
-- kurz in den jeweiligen Trading-Account über TradingView eingeloggt und alle neuen externen IDs gelesen"). /mail/eingang legt je Kauf-Mail
-- einer TradingView/Tradovate-Firma einen Auftrag an (faellig_at gestreut), der PC-Tab der ID holt fällige Aufträge (GET /pc/tv-konten-auftrag),
-- Puls liest die Konto-Liste der Firma (ohne Konto zu wählen) und meldet sie zurück (POST /pc/tv-konten-auftrag/erledigt → tv_konten).
-- Ohne Mail: höchstens 1× täglich je ID × Firma ein Auftrag 'taeglich' (Konten ohne Kauf-Mail, Tradeify ~50 %).
create table if not exists public.tv_konten_auftrag (
  id             uuid primary key default gen_random_uuid(),
  user_id        uuid not null,
  firma          text not null,                                             -- Schreibweise wie accounts.firm ('Tradeify', 'Apex Trader', …)
  art            text not null default 'mail' check (art in ('mail', 'taeglich')),
  quelle_mail    text,                                                      -- gmail_msg_id der auslösenden Kauf-Mail
  faellig_at     timestamptz not null,
  status         text not null default 'offen' check (status in ('offen', 'laeuft', 'erledigt', 'fehler')),
  laeuft_at      timestamptz,
  erledigt_at    timestamptz,
  versuche       integer not null default 0,                                -- Fehlversuche: nach dem 1. einmal neu (30–60 min), dann „fehler"
  ergebnis       jsonb,
  created_at     timestamptz not null default now()
);
-- je ID × Firma höchstens EIN offener/laufender Auftrag: weitere Kauf-Mails derselben Firma bündeln sich in ihm
create unique index if not exists tv_konten_auftrag_offen_uq on public.tv_konten_auftrag (user_id, firma) where status in ('offen', 'laeuft');
create index if not exists tv_konten_auftrag_faellig_idx on public.tv_konten_auftrag (user_id, faellig_at) where status = 'offen';
alter table public.tv_konten_auftrag enable row level security;
-- Prüfung: select user_id, firma, art, faellig_at, status, erledigt_at, ergebnis from tv_konten_auftrag order by created_at desc limit 30;
