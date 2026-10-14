-- SCHLUSS FÜR HEUTE (14.10.2026 ~19:15 Dubai, Finn: „schluss für heute keine neuen trades mehr starten" — nach 28 Blows an einem
-- Trendtag: der Ausgleich wog nur laufende Trades, Longs starben in Minuten und wurden den Vormittag über nachgefüllt).
-- Zwei Handgriffe, beide ohne Löschen, laufende Trades bleiben unberührt (Endlesung/Auto-Close sind keine neuen Orders):
--   1. auto_plan_regeln.aktiv = false — Nachplan-Takt und Ausgleichs-Bot legen nichts Neues an.
--      ACHTUNG: damit läuft auch der Nachtlauf 01:30 Dubai nicht; vor dem nächsten Handelstag wieder auf true.
--   1b. regeln.ausgleich.aktiv = false — das ist der Schalter „Bot an" in der Kachel Heute (Ausgleichs-Bot, eigener Wert neben
--      auto_plan_regeln.aktiv; der Bot liest nur regeln.ausgleich). Nachtrag 15:25 UTC, Finn: Kachel zeigte noch „Bot an".
--   2. Alle geplanten, noch nicht gestarteten Pläne (Auto UND Hand, alle IDs) auf unbestätigt, Marke mt5_baseline.puls_pause —
--      PC-Tab und DB-Claim-Guard starten unbestätigte Pläne nie; „bestätigen" lässt sie seit .1551 nicht wieder scharf.
-- Angewendet 14.10.2026 15:16 UTC direkt gegen die DB (Bot aus, 5 Pläne neu markiert, 7 unbestätigt gesamt, 0 scharf).
update public.auto_plan_regeln set aktiv = false, updated_at = now() where id = 1;
update public.auto_plan_regeln set regeln = jsonb_set(regeln, '{ausgleich,aktiv}', 'false'::jsonb), updated_at = now() where id = 1;
update public.trade_plans
   set auto_bestaetigt_at = null,
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('puls_pause', jsonb_build_object(
         'at', to_char(now() at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
         'grund', 'Schluss für heute — keine neuen Trades (Finn 14.10.2026 19:15 Dubai nach 28 Blows)',
         'bestaetigt_war', auto_bestaetigt_at is not null))
 where status = 'planned' and start_um_gestartet_at is null
   and not (mt5_baseline ? 'puls_pause');

-- RÜCKWEG (wenn Finn freigibt — Bot wieder an, die heute markierten Pläne sind dann vorbei, der Nachtlauf/Nachplan-Takt plant neu;
-- Mike/Moritz bleiben wie in 2026-10-14_puls_pause_mike_moritz.sql raus, bis Finn sie freigibt):
-- update public.auto_plan_regeln set aktiv = true, regeln = jsonb_set(regeln, '{ausgleich,aktiv}', 'true'::jsonb), updated_at = now() where id = 1;
-- update public.trade_plans set mt5_baseline = mt5_baseline - 'puls_pause'
--  where status = 'planned' and mt5_baseline->'puls_pause'->>'grund' like 'Schluss für heute%';
