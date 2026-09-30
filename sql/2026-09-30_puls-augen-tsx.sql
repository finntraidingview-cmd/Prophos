-- 2026-09-30: puls_augen für TopstepX (Topstep-Paket, Plan v2, Etappe B/K0 — Master-Auftrag TSX-S-B).
-- Bisher nur art 'stand' | 'inventar' (je PC eine Zeile, Schlüssel pc_id + art, 60-KB-Deckel je Zeile in der Railway-Route).
-- TopstepX bekommt eigene Arten, damit TV-/Tradovate-Zeilen nicht überschrieben werden und jedes Inventar seinen eigenen
-- 60-KB-Deckel hat:
--   'stand_tsx'                  Lesestand im TopstepX-Tab (wie 'stand')
--   'inventar_tsx'               Inventar ohne Zustand
--   'inventar_tsx_<teil>'        Inventar je Zustand, <teil> = 1–16 Kleinbuchstaben, z. B. inventar_tsx_grund,
--                                inventar_tsx_konto (Konto-Liste offen), inventar_tsx_bracket (Bracket-Dialog offen)
-- Die Railway-Route POST /puls-augen/<pc_id> lässt genau diese Arten zu (app.py puls_augen_saeubern, gleiche Regel).
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.

alter table public.puls_augen drop constraint if exists puls_augen_art_check;
alter table public.puls_augen add constraint puls_augen_art_check
  check (art in ('stand', 'inventar', 'stand_tsx', 'inventar_tsx') or art ~ '^inventar_tsx_[a-z]{1,16}$');

-- Lesen (Admin):
-- select pc_id, art, at, daten->>'url' url, length(daten::text) groesse from public.puls_augen where art like '%tsx%' order by at desc;
