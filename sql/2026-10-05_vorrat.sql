-- VORRAT (05.10.2026, Finn: „je ID und Prop-Firma festlegen, ob die ID dort freigeschaltet oder gesperrt ist … ein Vorrats-Ziel an
-- Funded-Konten … wo jede ID bei jeder Firma im Funnel steht und was bis zum Ziel fehlt"). Stufe 1: Sperr-Matrix + Ziele je Firma
-- für die Seite „Vorrat". Drei NEUE Tabellen, nichts Bestehendes wird verändert (auftrag_plan bleibt, wie es ist).
--
-- Alle drei liest und schreibt NUR das Backend (/admin/vorrat, Service-Key, an RLS vorbei) — dort greifen Login-Prüfung und
-- „nur eigene" (admin_zugang) wie bei /admin/prop-baum. RLS an, keine Policy: ein Browser kommt mit dem Anon-/User-Token nicht dran.
-- firma = Schreibweise nach _firm_norm (app.py): „Apex Trader", „The5%ers", „FundedNext" (CFD) ≠ „FundedNext Futures".

-- 1) Sperr-Matrix: eine Zeile je ID × Firma, sobald jemand die Zelle umgeschaltet hat. Keine Zeile = Standard aus
-- vorrat_einstellung.standard_status. Die eine Wahrheit, ob eine ID bei einer Firma kaufen/handeln soll.
-- status: frei · pausiert (Finn 06.10.2026: freigeschaltet, aber gerade nichts kaufen) · gesperrt.
create table if not exists public.vorrat_matrix (
  user_id       uuid not null references auth.users(id) on delete cascade,
  firma         text not null,
  status        text not null check (status in ('frei', 'pausiert', 'gesperrt')),
  geaendert_von uuid references auth.users(id) on delete set null,
  geaendert_at  timestamptz not null default now(),
  primary key (user_id, firma)
);

-- 2) Ziele je Firma — gelten für JEDE freigeschaltete ID einzeln (Finn: keine eigenen Werte je ID). Nur Firmen mit Zeile stehen
-- auf der Seite (Finn 06.10.2026: FundedNext Futures, Lucid, Blue Guardian, MyFundedFutures, Fusion Markets bleiben ganz weg,
-- bis er sie freigibt — dann eine Zeile hier). Ziel ändern = UPDATE auf die Zeile, kein Code.
--   art plus_ueber_start  Summe „Plus über der Startgröße" der Konten in typen (164.000 bei 150k → +14.000; Topstep Express ab 0)
--   art groessen_summe    Summe der Kontogrößen der Konten in typen
--   art stueck            Stückzahl; groessen = [{"groesse": 100000, "stueck": 1}, …], groesse null = jede Größe
--   typen                 Kontotypen, die als sicherer Bestand zählen (Futures: nur winning_days — funded vor dem Big Trade ist Funnel;
--                         CFD: funded_cfd und der Altbestand, der noch funded heißt). Waiting for Payout zählt mit (Finn 05.10.2026).
--   von / bis             Spanne in USD: unter von fehlt Vorrat, aufgefüllt wird bis bis (bei stueck leer)
--   kauf_einheit          was nachgekauft wird, als Text (Finn 05.10.2026) — die Nachkauf-Liste selbst kommt mit Stufe 2
--   reihe                 Reihenfolge der Firmen auf der Seite
create table if not exists public.vorrat_ziele (
  firma        text primary key,
  art          text not null check (art in ('plus_ueber_start', 'groessen_summe', 'stueck')),
  typen        text[] not null,
  von          numeric,
  bis          numeric,
  groessen     jsonb,
  kauf_einheit text,
  reihe        smallint not null default 100,
  updated_at   timestamptz not null default now(),
  check ((art = 'stueck' and groessen is not null)
      or (art <> 'stueck' and von is not null and bis is not null and bis >= von))
);

-- 3) Schalter, eine Zeile (id = 1). standard_status = Zustand einer Zelle ohne Matrix-Zeile (Finn entscheidet noch: alles frei
-- oder alles gesperrt — bis dahin frei, dann steht die ganze Übersicht sofort da).
create table if not exists public.vorrat_einstellung (
  id              smallint primary key default 1 check (id = 1),
  standard_status text not null default 'frei' check (standard_status in ('frei', 'gesperrt')),
  updated_at      timestamptz not null default now()
);

alter table public.vorrat_matrix enable row level security;
alter table public.vorrat_ziele enable row level security;
alter table public.vorrat_einstellung enable row level security;

insert into public.vorrat_einstellung (id) values (1) on conflict (id) do nothing;

-- Finns Liste vom 05.10.2026 (Ziele und Kauf-Einheiten). on conflict do nothing: ein zweiter Lauf überschreibt spätere Änderungen
-- nicht. Topstep ohne Kauf-Einheit (nicht genannt), Apex nur „150k" (das Produkt hat Finn diktiert, aber unklar — nicht raten).
insert into public.vorrat_ziele (firma, art, typen, von, bis, groessen, kauf_einheit, reihe) values
  ('Tradeify',    'plus_ueber_start', '{winning_days}',      20000,  30000, null, '150k Select', 1),
  ('Topstep',     'plus_ueber_start', '{winning_days}',      20000,  30000, null, null, 2),
  ('Apex Trader', 'stueck',           '{winning_days}',      null,   null,  '[{"groesse": null, "stueck": 1}]'::jsonb, '150k', 3),
  ('FTMO',        'groessen_summe',   '{funded_cfd,funded}', 100000, 200000, null, '100k oder 200k', 4),
  ('FundedNext',  'groessen_summe',   '{funded_cfd,funded}', 200000, 300000, null, '100k 2-Step Standard (selten 50k)', 5),
  ('FundingPips', 'groessen_summe',   '{funded_cfd,funded}', 150000, 250000, null, '100k 2-Step Standard', 6),
  ('The5%ers',    'stueck',           '{funded_cfd,funded}', null,   null,
   '[{"groesse": 100000, "stueck": 1}, {"groesse": 200000, "stueck": 1}]'::jsonb, '100k Summer Plan, 200k Summer Plan', 7)
on conflict (firma) do nothing;
