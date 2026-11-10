-- TW1 HANDELS-WÜRFEL (11.11.2026, Finn ~02:00/02:05 Dubai: „… 75 % aller Trades aller Accounts machen einen Trade, und die anderen 25 % nicht …
-- Es wird einfach gewürfelt … für jedes einzelne Ding diese Wahrscheinlichkeit selber einstellen, aber das Prinzip soll für alle gelten“).
-- Je Planer × Unternehmen EIN Prozentwert: so viele Konten bekommen je Tag ihren Trade; die übrigen haben Pause (heute kein Trade, morgen neu gewürfelt).
-- Gewürfelt wird in app.py je Konto × Tag fest (Hash, tw_handelt) — kein Speicher je Tag nötig.
--   planer: challenge_cfd | challenge_futures | funded_cfd | funded_futures | winning_days
--   gruppe: '' = Standard = Hermann Technologies; sonst die gruppe_id eines Unternehmens (als Text). Ohne Zeile gilt 100 % (= wie vor TW1);
--           ein Unternehmen erbt den HT-Wert NICHT (Master 11.11.2026: „Emins Unternehmen eigene Einstellung, dort Standard 100 %“).
-- Lesen/Schreiben nur über Railway (Service-Rolle, GET/POST /admin/handel-wuerfel) — RLS an, keine Policies.
-- Teil 2 setzt HT für alle fünf Planer auf 75 % (nur, wo noch kein Wert steht). Einspielen erst nach Prüfer-OK (Master).
-- Spalten: planer, gruppe, pct, updated_at, updated_von.

create table if not exists public.planer_handel_wuerfel (
  planer     text not null check (planer in ('challenge_cfd', 'challenge_futures', 'funded_cfd', 'funded_futures', 'winning_days')),
  gruppe     text not null default '',
  pct        numeric(5, 2) not null check (pct >= 0 and pct <= 100),
  updated_at timestamptz not null default now(),
  updated_von uuid,
  primary key (planer, gruppe)
);
alter table public.planer_handel_wuerfel enable row level security;
comment on table public.planer_handel_wuerfel is
  'TW1 Handels-Würfel: % der Konten, die je Tag ihren Trade bekommen (je Planer × Unternehmen, gruppe '''' = HT-Standard). Ohne Zeile 100 %.';

-- Teil 2: Hermann Technologies (Standard) — alle fünf Planer 75 %
insert into public.planer_handel_wuerfel (planer, gruppe, pct) values
  ('challenge_cfd', '', 75),
  ('challenge_futures', '', 75),
  ('funded_cfd', '', 75),
  ('funded_futures', '', 75),
  ('winning_days', '', 75)
on conflict (planer, gruppe) do nothing;   -- erneut eingespielt: in der Karte geänderte Werte bleiben stehen

-- Zurück auf das Verhalten vor TW1 (alle 100 %):  delete from public.planer_handel_wuerfel;
