-- ============================================================================
-- Prophos: Kaufplan — welche Accounts sollen künftig auf welcher ID gekauft
-- werden (31.08.2026, Finns Wunsch: „bau ein feature wo ich als admin so acc
-- planen kann die in zukunft bei der jeweiligen id gekauft werden sollen —
-- weil aktuell mach ich das immer in google sheets etc").
--
-- ABGRENZUNG zum bestehenden Acc-Käufe-Tab (26.08.2026): der schaut ZURÜCK und
-- liest aus `accounts` (jede Zeile mit purchase_cost > 0). Diese Tabelle schaut
-- NACH VORN und hat bewusst keine Verbindung zu `accounts` — ein geplanter Kauf
-- ist noch kein Account, hat keine Login-Daten, keine Firma-Zuordnung im System
-- und darf in keiner Kapital-/Risiko-Auswertung mitzählen. Erst beim Umschalten
-- auf 'gekauft' entsteht die Brücke (account_id, optional).
--
-- RECHTE — bewusst NICHT das geteilte Kasse-Muster (2026-08-11_kasse.sql):
--   Die Kasse teilen sich alle eingeloggten User absichtlich. Der Kaufplan
--   dagegen enthält, was Finn für FREMDE IDs plant und was es kosten soll —
--   das gehört keinem der Teilnehmer auf den Tisch, auch nicht per API-Aufruf
--   am UI-Gate vorbei. Deshalb: RLS an, aber GAR KEINE Policies. Damit kommt
--   kein Client an die Tabelle; gelesen und geschrieben wird ausschließlich
--   über app.py mit dem Service-Key, hinter dem ADMIN_EMAILS-Gate
--   (_admin_auth, dasselbe Muster wie 2026-08-28_rechnungen.sql).
--
-- Im Supabase SQL Editor einfügen und auf „Run" klicken. Idempotent.
-- ============================================================================

create table if not exists public.acc_plan (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid not null,                 -- die ID/Person, auf der gekauft wird
  firma         text not null default '',      -- Apex, Tradeify, Topstep …
  bezeichnung   text not null default '',      -- „Funded", „neuer 100k", „next 100k"
  anzahl        integer not null default 1 check (anzahl >= 1),
  -- Preis PRO STÜCK in USD. Warum USD: der Acc-Käufe-Tab rechnet seit dem
  -- 26.08. in USD, weil Accounts in USD gekauft werden — zwei Währungen in
  -- zwei Ansichten derselben Sache wären eine stille Fehlerquelle.
  kosten        numeric not null default 0 check (kosten >= 0),
  zahlweg       text not null default '',      -- „Revolut", „Karte", … (Finns Notiz führt das mit)
  notiz         text not null default '',
  status        text not null default 'geplant'
                check (status in ('geplant', 'gekauft', 'verworfen')),
  gekauft_am    timestamptz,                   -- gesetzt beim Umschalten auf 'gekauft'
  account_id    uuid,                          -- optionale Brücke zum echten Account
  created_by    text not null default '',      -- E-Mail des Admins
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

-- Die eine Abfrage, die die Ansicht macht: offene Posten je Person, neueste zuerst.
create index if not exists acc_plan_user_idx
  on public.acc_plan (user_id, status, created_at desc);

alter table public.acc_plan enable row level security;

-- Bewusst KEINE Policy. RLS ohne Policy = für jeden Client dicht; der
-- Service-Key von app.py geht daran vorbei. Falls hier je eine Policy
-- entsteht, gehört vorher die Frage beantwortet, wer den Plan sehen darf.
drop policy if exists "acc_plan_select_own" on public.acc_plan;
