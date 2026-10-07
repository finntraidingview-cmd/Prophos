-- Auto-Planer-Haken je Konto (Finn 08.10.2026: „unter Accounts eine grobe Übersicht, welche Accounts gerade im Auto-Planer drin
-- sind — so einen Haken: Auto-Planer"). true = darf eingeplant werden (Standard, wie bisher), false = der Nachtlauf und das
-- Nachplanen lassen das Konto aus (Grund im Lauf: „vom Auto-Planer ausgenommen"). Alles andere (Typ, Firma, Balance, Ziel)
-- entscheidet weiter der Planer selbst.
alter table public.accounts add column if not exists auto_planer boolean not null default true;
comment on column public.accounts.auto_planer is 'Auto-Planer-Haken (08.10.2026): false = Konto wird nie automatisch eingeplant';
