-- Thanksgiving 26.11.2026, Finn 17:05 Dubai: „bitte keine mehr starten“ — alle IDs, alle Wege. Eingespielt 17:05:16 (38 Pläne) und 17:08 (9 Pläne,
-- die geclaimt ohne Start hingen). Muster wie die Puls-Pausen (memory prophos-puls-pause-lehren), aber start_um = NULL statt 2027: ohne Startzeit
-- feuert kein PC-Tab (suKandidaten verlangt p.startUm), unbestätigt bereitet eh_tick keinen Echo-Hedge vor. Laufende Trades unberührt.
-- Marke mt5_baseline.puls_pause {start_um_war, bestaetigt_war, bestaetigt_at_war, claim_war}.

update public.trade_plans
   set auto_bestaetigt_at = null, start_um = null, updated_at = now(),
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('puls_pause', jsonb_build_object(
         'at', now(), 'grund', 'Thanksgiving 26.11.2026 — Finn 17:05 Dubai: heute keine Trades mehr starten',
         'start_um_war', start_um, 'bestaetigt_war', (auto_bestaetigt_at is not null), 'bestaetigt_at_war', auto_bestaetigt_at,
         'claim_war', start_um_gestartet_at))
 where status = 'planned' and start_um is not null and started_at is null
   and start_um < now() + interval '30 hours'
   and not coalesce(mt5_baseline ? 'puls_pause', false);

-- WD-Tagesplan: der eine noch geplante Eintrag (Pascal, Lucid …0002) — sonst setzt der Tab den Plan aus dem Tagesplan zurück
update public.wd_tagesplan t
   set konten = (select jsonb_agg(case when k->>'status' = 'planned'
                                       then k || jsonb_build_object('aktiv', false, 'puls_pause', jsonb_build_object('at', now(), 'grund', 'Thanksgiving 26.11.2026 — keine Starts mehr', 'aktiv_war', k->'aktiv'))
                                       else k end) from jsonb_array_elements(t.konten) k),
       status = 'leer', start_um = null, updated_at = now()
 where t.tag = '2026-11-26' and t.status = 'geplant';

-- RÜCKWEG: nicht nötig, wenn die Pläne einfach verfallen sollen (planned_for 26.11., der Nachtlauf plant neu). Sollen sie doch noch laufen:
-- update public.trade_plans
--    set start_um = now() + interval '10 minutes' + (row_number() over ()) * interval '3 minutes',   -- als CTE ausschreiben, gestaffelt
--        auto_bestaetigt_at = case when (mt5_baseline->'puls_pause'->>'bestaetigt_war')::boolean then now() end,
--        start_um_gestartet_at = null,                                                               -- Claim leeren (Falle Mike 92936a05)
--        mt5_baseline = mt5_baseline - 'puls_pause'
--  where status = 'planned' and mt5_baseline->'puls_pause'->>'grund' like 'Thanksgiving 26.11.2026%';
