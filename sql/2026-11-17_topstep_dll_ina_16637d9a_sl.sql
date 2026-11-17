-- NUR AUF FINNS WORT — nicht Teil der Pflicht-SQL sql/2026-11-17_topstep_dll_funded_wd.sql (Prüfer-MUSS 17.11.2026).
-- TS-DLL (17.11.2026, Slave 14): ein schon geplanter, noch NICHT gestarteter Topstep-WD-Plan (16637d9a, Start 17.11. 09:16 UTC, „gewürfelt: ohne SL“) bekäme nach
-- der neuen Regel (Soft Breach wie Lucid, DL2) den Pflicht-SL 100 $ vor dem Tageslimit: erster Trade des CME-Tags 17.11. (Beginn 23:00 UTC am 16.11.) →
-- Tagesstart = Plan-Balance → SL = 3.000 − 100 = 2.900 $ (Express-MLL ≤ 0 liegt bei ~18.300 $ Balance weit dahinter).
-- Ohne diese Datei schützt den Trade trotzdem das Hedge-Level am Tageslimit (hedgeTopstepDll beim Open). Läuft erst nach dem Start → die Guards machen nichts
-- (0 Zeilen). Nur solange NICHT geclaimt/gestartet/gesendet, ohne SL, keine Start-Sperre des Tabs, kein anderer Plan des Kontos heute gestartet.
-- Laufende/abgeschlossene Pläne und Broker-Orders werden NICHT angefasst.
update public.trade_plans p
   set master_sl = 2900,
       mt5_baseline = jsonb_set(p.mt5_baseline, '{wd_sl}', (p.mt5_baseline->'wd_sl') || jsonb_build_object(
         'ohne', false, 'usd', 2900, 'pflicht_dll', true, 'quelle', 'ts_dll_sql', 'puffer', 2900,
         'liq_balance', round((p.mt5_baseline->'wd_sl'->>'balance')::numeric - 2900, 2),
         'liq_quelle', 'Tageslimit 3.000 $ ab Tagesstart (Plan-Balance) + 100 $ — TS-DLL nachgetragen',
         'grund', 'ohne SL gewürfelt — Daily Loss: SL 2900 $ = 3.000 $ bis zum Tageslimit − 100 $ (TS-DLL 17.11.2026, nachgetragen)'))
 where p.id::text like '16637d9a%'
   and p.status = 'planned' and p.master_sl is null
   and p.start_um_gestartet_at is null and p.started_at is null and p.orbit_gesendet_at is null
   and (p.mt5_baseline->>'sl_lauf_at') is null
   and (p.mt5_baseline->'wd_sl'->>'ohne') = 'true'
   and (p.mt5_baseline->'wd_sl'->>'balance')::numeric > 3100
   and not exists (select 1 from public.trade_plans q where q.master_account_id = p.master_account_id and q.id <> p.id
                    and q.started_at >= '2026-11-16 23:00:00+00');

-- Kontrolle (nur lesen):
-- select left(id::text, 8), status, master_sl, mt5_baseline->'wd_sl' from public.trade_plans where id::text like '16637d9a%';
