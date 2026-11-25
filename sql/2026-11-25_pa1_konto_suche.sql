-- PA1 (Finn 25.11.2026: „Wenn ich bei Futures gekauft habe, drücke ich nur auf ‚Gekauft'. Dann soll der Knopf grün werden und dort die Zeit
-- stehen, wann überprüft wird.") — Klick „Gekauft" (Kaufliste, S6/KP2) → POST /konto-suche legt einen Auftrag art 'gekauft' an (fällig gestreut
-- in 1 min–5 h), der PC-Tab der ID lässt Puls die Konto-Liste der Firma lesen (bestehender Weg tvkTick → modus_tvkontenliste, nur lesen),
-- Railway zieht alle bekannten External IDs ALLER IDs ab und legt höchstens „anzahl" neue Konten mit der Vorlage an.
-- NICHT eingespielt (Slave 5) — der Master spielt ein. Ohne diese Datei antwortet POST /konto-suche mit „SQL fehlt" und ändert nichts.
-- Idempotent: mehrfach ausführbar.

begin;

-- 1) Auftrag: neue Art 'gekauft', neuer Stand 'pruefen' (Ende ohne volle Anlage: „von Hand" bzw. 🟠 — zählt NICHT als offen, der eindeutige
--    Index je ID × Firma bleibt wie er ist)
alter table public.tv_konten_auftrag drop constraint if exists tv_konten_auftrag_art_check;
alter table public.tv_konten_auftrag add constraint tv_konten_auftrag_art_check check (art in ('mail', 'taeglich', 'gekauft'));
alter table public.tv_konten_auftrag drop constraint if exists tv_konten_auftrag_status_check;
alter table public.tv_konten_auftrag add constraint tv_konten_auftrag_status_check check (status in ('offen', 'laeuft', 'erledigt', 'fehler', 'pruefen'));

alter table public.tv_konten_auftrag add column if not exists anzahl      integer check (anzahl is null or anzahl between 1 and 20);  -- gekauft (Stück)
alter table public.tv_konten_auftrag add column if not exists vorlage_id  uuid;                                       -- bulk_vorlagen.id
alter table public.tv_konten_auftrag add column if not exists posten      jsonb;                                      -- PA1b: [{vorlage_id, anzahl, at}] — mehrere Klicks = EINE Prüfung
alter table public.tv_konten_auftrag add column if not exists angelegt   jsonb not null default '[]'::jsonb;        -- [{id, ext, name}]
alter table public.tv_konten_auftrag add column if not exists frist_bis   timestamptz;                                -- Klick + 24 h, danach 🟠
alter table public.tv_konten_auftrag add column if not exists erstellt_von uuid;                                      -- Login, der „Gekauft" drückte

-- 2) Riegel gegen Doppel-Anlage: je Firma × normierter External ID höchstens EIN von PA1 angelegtes Konto — auch bei zwei gleichzeitigen
-- Läufen (zwei PC-Tabs, Wiederholung nach Zeitüberschreitung). Kein Index auf accounts selbst: dort gibt es heute schon Dubletten
-- (Fusion-Live-Konten je ID, alte FundedNext-/Tradeify-Doppel), ein eindeutiger Index ließe sich nicht anlegen.
create table if not exists public.konto_suche_riegel (
  firma       text not null,
  ext_norm    text not null check (ext_norm ~ '^[A-Z0-9]{6,40}$'),
  user_id     uuid not null,
  auftrag_id  uuid,
  account_id  uuid,
  created_at  timestamptz not null default now(),
  primary key (firma, ext_norm)
);
alter table public.konto_suche_riegel enable row level security;      -- keine Policy: nur Service-Key (Railway)
revoke all on public.konto_suche_riegel from anon, authenticated;

commit;

-- Prüfung:
--   select pg_get_constraintdef(oid) from pg_constraint where conrelid = 'public.tv_konten_auftrag'::regclass and contype = 'c';
--   select column_name from information_schema.columns where table_name = 'tv_konten_auftrag' and column_name in ('anzahl','vorlage_id','posten','angelegt','frist_bis','erstellt_von');
--   select count(*) from public.konto_suche_riegel;
-- Zurück (nur wenn keine Zeile art 'gekauft'/status 'pruefen' mehr existiert):
--   drop table public.konto_suche_riegel;
--   alter table public.tv_konten_auftrag drop column anzahl, drop column vorlage_id, drop column posten, drop column angelegt, drop column frist_bis, drop column erstellt_von;
--   (Checks wie in sql/2026-10-29_tv_konten.sql)
