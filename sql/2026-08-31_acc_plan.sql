-- ============================================================================
-- Prophos: Kaufplan — ZIELZUSTAND je ID (31.08.2026, Finns Wunsch)
--
-- Erste Fassung war ein Einkaufszettel („kauf 2 Accounts"). Finns Klarstellung
-- am selben Tag hat das Modell gedreht:
--   „Es ist nicht so ein Plan, wo ich sage: ich möchte drei Accounts kaufen.
--    Das wäre das ZIEL, was ich an Accounts dort geparkt haben würde …
--    also: da bitte so lange weitermachen, bis die Anzahl erreicht ist.
--    Ich weiß ja nicht, wenn ich zwei Accounts kaufe, ob ich beide blowe."
--
-- Daraus folgen zwei Entwurfs-Entscheidungen:
--   1. Eine Zeile ist ein ZIEL („auf Pascals ID: 1× Funded 150k bei Tradeify"),
--      kein Posten. Wie viele Käufe nötig sind, steht nirgends — das weiß
--      vorher niemand, weil Accounts blowen können.
--   2. KEIN Abhaken (Finn ausdrücklich: „dass wir die auch nicht so abhaken
--      können wie bei Google Keep"). Der Ist-Stand wird bei jedem Laden aus
--      den echten `accounts` berechnet: gleiche Person, gleiche Firma,
--      account_type = Zielzustand, Größe aus dem Account-NAMEN, nicht
--      archiviert. Ein Haken wäre eine zweite Wahrheit neben den Accounts —
--      und die beiden würden auseinanderlaufen.
--
-- Warum die Größe aus dem Namen: `accounts.account_size` ist bei 3 von 432
-- Zeilen gefüllt, der Name trägt sie bei 382 („150k Tradeify FTDFY…").
--
-- gewinn_ziel ist bewusst NUR eine Notiz und geht in KEINE Berechnung ein:
-- bei Tradeify- und Apex-Funded-Accounts steht in Prophos `balance = 0.00`,
-- ein automatisches „mit X im Plus" wäre also eine erfundene Zahl. Sobald die
-- Salden dieser Firmen echt in Prophos landen, kann daraus eine Bedingung
-- werden — vorher nicht.
--
-- RECHTE — bewusst NICHT das geteilte Kasse-Muster (2026-08-11_kasse.sql):
--   Die Kasse teilen sich alle eingeloggten User absichtlich. Hier steht, was
--   für FREMDE IDs geplant ist — das gehört keinem Teilnehmer auf den Tisch,
--   auch nicht per API-Aufruf am UI-Gate vorbei. Deshalb: RLS an, aber GAR
--   KEINE Policy. Gelesen und geschrieben wird nur über app.py mit dem
--   Service-Key hinter dem ADMIN_EMAILS-Gate (_admin_auth, wie 2026-08-28_rechnungen.sql).
--
-- Im Supabase SQL Editor einfügen und auf „Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.acc_plan (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null,                 -- die ID/Person, auf der gekauft wird
  firma         text not null default '',      -- Tradeify, Apex, Topstep …
  ziel_typ      text not null default 'funded' -- welcher Zustand gemeint ist
                check (ziel_typ in ('challenge', 'phase1', 'phase2', 'funded', 'live')),
  ziel_groesse  numeric,                       -- z.B. 150000; leer = Größe egal
  ziel_anzahl   integer not null default 1 check (ziel_anzahl >= 1),
  gewinn_ziel   numeric,                       -- reine Notiz, siehe Kopf
  notiz         text not null default '',
  aktiv         boolean not null default true, -- Daueraufträge lassen sich stilllegen
  created_by    text not null default '',
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create index if not exists acc_plan_user_idx
  on public.acc_plan (user_id, aktiv, created_at desc);

alter table public.acc_plan enable row level security;

-- Bewusst KEINE Policy. RLS ohne Policy = für jeden Client dicht; der
-- Service-Key von app.py geht daran vorbei. Falls hier je eine Policy
-- entsteht, gehört vorher die Frage beantwortet, wer den Plan sehen darf.
drop policy if exists "acc_plan_select_own" on public.acc_plan;
