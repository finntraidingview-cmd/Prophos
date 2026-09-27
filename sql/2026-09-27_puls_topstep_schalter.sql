-- 2026-09-27: Schalter „Puls für Topstep" zentral für alle PCs (Auftrag Koordination B16 / F23). Werte: 'aus' (Topstep V2
-- von Hand wie bisher), 'lesen' (Starten fährt nur /api/tsx-lesen: Konto, Balance, Position — keine Order; Standard),
-- 'scharf' (Order über /api/tsx-konto — kommt erst mit Etappe 2 im Bot). Liegt an der vorhandenen Regel-Zeile des
-- Farmers (wd_farmer_regeln, id = 1): lesen alle Eingeloggten, schreiben wie scharf/aktiv. Das Frontend liest mit
-- Rückfall 'lesen', solange die Spalte fehlt.
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.
alter table public.wd_farmer_regeln add column if not exists puls_topstep text not null default 'lesen';
alter table public.wd_farmer_regeln drop constraint if exists wd_farmer_regeln_puls_topstep_check;
alter table public.wd_farmer_regeln add constraint wd_farmer_regeln_puls_topstep_check
  check (puls_topstep in ('aus', 'lesen', 'scharf'));
