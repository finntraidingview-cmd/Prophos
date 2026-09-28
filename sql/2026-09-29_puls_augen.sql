-- 2026-09-29: Puls „Augen“ über das Chrome DevTools Protocol (CDP), Etappe E0 (Finns Go, Master-Koordination).
-- (1) Schalter je PC: wd_farmer_regeln.puls_augen_cdp = Liste der pc_ids, deren Puls zusätzlich ein eigenes Puls-Chrome
--     (eigenes --user-data-dir, Port 9333 nur 127.0.0.1) hält und darin mitliest. Alle anderen PCs: 'uia' wie bisher.
--     Der Puls fragt über GET https://web-production-bec81.up.railway.app/puls-regel/<pc_id> (Service-Key, Rückfall 'uia').
-- (2) Ergebnisse: Tabelle puls_augen, eine Zeile je PC und Art ('stand' | 'inventar'), immer der letzte Lesestand. Schreiben
--     nur die Railway-Route POST /puls-augen/<pc_id> mit dem Service-Key; RLS an, KEINE Policy für anon/authenticated
--     (Lesen nur Admin über den Service-Weg / SQL-Editor).
-- E0 ändert am Verhalten nichts: kein Klick, keine Order — nur Lesen in die Spur und in diese Tabelle.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.

alter table public.wd_farmer_regeln add column if not exists puls_augen_cdp text[] not null default '{}';

create table if not exists public.puls_augen (
  pc_id  text not null check (pc_id ~ '^pc-[a-z0-9]{4,12}$'),
  art    text not null check (art in ('stand', 'inventar')),
  daten  jsonb not null,
  at     timestamptz not null default now(),
  primary key (pc_id, art)
);
alter table public.puls_augen enable row level security;

-- Startwert — ERST nach dem einmaligen Menschen-Login im Puls-Chrome an Moritz' PC (TradingView + Tradovate, „Remember me“ an),
-- und nur, wenn auf seinen Konten kein Trade läuft. Bis dahin auskommentiert lassen:
-- update public.wd_farmer_regeln set puls_augen_cdp = array['pc-usq1i6'], updated_at = now() where id = 1;

-- Lesen (Admin):
-- select pc_id, art, at, daten->'geo' geo, daten->'ticket' ticket from public.puls_augen order by at desc;
