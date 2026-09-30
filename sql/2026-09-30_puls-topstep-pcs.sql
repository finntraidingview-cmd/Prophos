-- 2026-09-30: Schalter je PC für den Topstep-Puls (Topstep-Paket, Plan v2, Etappe B — Master-Auftrag TSX-S-B).
-- Neben dem zentralen Schalter wd_farmer_regeln.puls_topstep ('aus' | 'lesen' | 'scharf') entscheidet jetzt die Liste
-- puls_topstep_pcs, auf welchen PCs der Topstep-Puls den neuen Weg über das Puls-Chrome (CDP) fährt — erst Mike (pc-l5o8bv),
-- dann Chris.
-- Railway liefert die Zugehörigkeit über GET /puls-regel/<pc_id> als tsx: 'cdp' (PC steht in der Liste) | 'uia' (Vertrag mit
-- Terminal 3): nur PCs in der Liste fahren TopstepX über das Puls-Chrome (CDP), alle anderen bleiben auf dem alten Weg. Der Bot
-- entscheidet, das Frontend hat keinen eigenen Riegel.
-- Gesetzt wird die Liste von Hand per SQL (keine Admin-Auswahl nötig, Master-Entscheidung).
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.

alter table public.wd_farmer_regeln add column if not exists puls_topstep_pcs text[] not null default '{}';

-- Beispiel (NICHT automatisch ausführen — Master/Finn entscheiden, wann):
-- update public.wd_farmer_regeln set puls_topstep_pcs = array['pc-l5o8bv'], updated_at = now() where id = 1;

-- Lesen:
-- select puls_topstep, puls_topstep_pcs, puls_augen_cdp from public.wd_farmer_regeln where id = 1;
