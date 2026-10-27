-- SUPPORT-CHAT „Lotse“ (Finn 27.10.2026: „Alle Leute, die Prophos nutzen, sollen mich nicht alle 10 Minuten fragen müssen. Ein Chat-Support
-- kommt unten rechts, da wo die Münze ist … beschränkter Zugriff auf die Datenbank, kennt sich in der Navigation aus“; Nachtrag: „wie eine
-- eigene KI, Screenshots hochladen ist ganz wichtig“). Konzept im Notizordner des Masters, freigegeben 27.10.2026.
--
-- Alle vier Tabellen: RLS an, KEINE Policy → nur das Backend (Service-Key) liest und schreibt. Der Browser spricht nur mit /support/*.
-- Idempotent.

-- Wer darf den Chat nutzen. Keine Zeile = AUS. Zum Start nur Finns Login (Zeile per Hand, s. unten).
create table if not exists public.support_zugang (
  user_id     uuid primary key,
  an          boolean not null default false,
  tageslimit  integer not null default 40,          -- Fragen je deutschem Tag (ab 03:00 Dubai, wie die Tagesgrenze)
  -- 'eigene' = nur die eigene ID; 'alle' = wie im Admin (Standard-Sicht Hermann Technologies bzw. gewählter Gruppen-Chip) — wirkt nur
  -- für Logins, die im Admin unbeschränkt sind (Finn, Pascal; Freigabe 27.10.2026). Verwalter sehen ihre Gruppe nur mit 'alle',
  -- sonst nur sich (Finn 27.10.2026: „jede ID darf nur zu ihrer eigenen ID fragen").
  sicht       text not null default 'eigene' check (sicht in ('eigene', 'alle')),
  notiz       text,
  updated_at  timestamptz not null default now()
);

-- Eine Unterhaltung je Thema. geschlossen = ihre Bilder sind abgelaufen → nur noch lesen, neue Unterhaltung starten
-- (der Verlauf wird nur angehängt, nie umgeschrieben — sonst bricht der Cache und die Denk-Blöcke der API).
create table if not exists public.support_unterhaltung (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null,
  titel       text,
  geschlossen boolean not null default false,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index if not exists support_unterhaltung_user_idx on public.support_unterhaltung (user_id, updated_at desc);

-- Die Nachrichten genau so, wie sie an die Claude-API gehen (inhalt = Content-Blöcke inkl. Tool-Aufrufe/-Ergebnisse als JSON-TEXT,
-- nicht jsonb: jsonb sortiert die Schlüssel um, der Verlauf muss aber Zeichen für Zeichen gleich zurück an die API — sonst bricht der
-- Cache). Bilder stehen NICHT im inhalt, sondern als Pfad im Bucket support-bilder (bilder[]); im inhalt nur ein Platzhalter-Block.
-- aktionen = die Bestätigen-Vorschläge dieser Antwort (Anzeige beim Wieder-Öffnen), text = was das Panel als Blase zeigt.
create table if not exists public.support_nachricht (
  id              bigserial primary key,
  unterhaltung_id uuid not null references public.support_unterhaltung(id) on delete cascade,
  rolle           text not null check (rolle in ('user', 'assistant')),
  inhalt          text not null,
  text            text,
  bilder          text[] not null default '{}',
  aktionen        jsonb,
  sichtbar        boolean not null default true,     -- false = Tool-Ergebnis/Kontext, im Panel nicht als Blase
  at              timestamptz not null default now()
);
create index if not exists support_nachricht_unterhaltung_idx on public.support_nachricht (unterhaltung_id, id);

-- Protokoll jeder Frage und Aktion (Kosten, Missbrauch). Frage/Antwort gekürzt, lange Ziffernfolgen maskiert, von Bildern nur die Maße.
create table if not exists public.support_log (
  id                  bigserial primary key,
  at                  timestamptz not null default now(),
  user_id             uuid,
  unterhaltung_id     uuid,
  art                 text not null,               -- frage | aktion_ok | aktion_fehler | limit | fehler
  frage               text,
  antwort             text,
  tools               jsonb,
  bilder              text,
  modell              text,
  tok_ein             integer,
  tok_aus             integer,
  tok_cache_lesen     integer,
  tok_cache_schreiben integer
);
create index if not exists support_log_user_at_idx on public.support_log (user_id, at desc);

alter table public.support_zugang       enable row level security;
alter table public.support_unterhaltung enable row level security;
alter table public.support_nachricht    enable row level security;
alter table public.support_log          enable row level security;

-- Bilder: privater Bucket, nur Service-Key. Ablauf 7 Tage räumt das Backend ab (support_aufraeumen in app.py).
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('support-bilder', 'support-bilder', false, 3145728, array['image/jpeg', 'image/png', 'image/webp', 'image/gif'])
on conflict (id) do nothing;

-- Freischalten je ID (per Hand, mit der echten user_id — keine IDs im öffentlichen Repo):
-- insert into public.support_zugang (user_id, an) values ('<user-id>', true)
--   on conflict (user_id) do update set an = excluded.an, updated_at = now();
-- Master-Login (Finn / Pascal) mit Sicht wie im Admin:
-- insert into public.support_zugang (user_id, an, sicht) values ('<user-id>', true, 'alle')
--   on conflict (user_id) do update set an = excluded.an, sicht = excluded.sicht, updated_at = now();
-- Abschalten: update public.support_zugang set an = false, updated_at = now() where user_id = '<user-id>';

-- Kontrolle / Kosten:
-- select user_id, date_trunc('day', at) tag, count(*) filter (where art = 'frage') fragen, sum(tok_ein) ein, sum(tok_aus) aus,
--        sum(tok_cache_lesen) cache from public.support_log group by 1, 2 order by 2 desc, 3 desc;
