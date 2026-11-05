-- Emins FNF Futures 50k …3807, Plan 82a25d69 (Orbit Prio 2, Start 09:17 Dubai) ANHALTEN, bis PB1 live ist (Befund S2 NK1 05.11.2026 06:10 Dubai:
-- Vorschau rechnet Boden 48.500 statt 49.498, weil der +1.000-Trade vom 04.11. über Route tvplus im Liq-Verlauf fehlt → Hedge 205 € statt ≈123 €).
-- Ohne start_um startet kein PC-Tab den Plan. Ursprüngliche Startzeit in mt5_baseline.halten.start gemerkt; nach PB1 wieder setzen:
--   update trade_plans set start_um = (mt5_baseline->'halten'->>'start')::timestamptz, mt5_baseline = mt5_baseline - 'halten' where id = '82a25d69-cce5-4c3b-89e9-adcc7c31c457' and status = 'planned';
update public.trade_plans
   set mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('halten', jsonb_build_object('at', now(), 'start', start_um,
                        'grund', 'Master 05.11.: Boden-Rechnung Orbit Prio 2 falsch (PB1) — gehalten bis Fix')),
       start_um = null, start_um_gestartet_at = null, start_claim_art = null
 where id = '82a25d69-cce5-4c3b-89e9-adcc7c31c457' and status = 'planned' and started_at is null;
