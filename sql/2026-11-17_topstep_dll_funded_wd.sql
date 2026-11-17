-- TS-DLL (17.11.2026, Slave 14) — Topstep Daily Loss Limit 3.000 $ auch bei Funded/Express und Winning Days, Soft Breach wie Lucid
-- Anlass: Finn 17.11.2026 ~07:05 Dubai: „Bei Funded ist auch ein 3K Daily Loss Limit. Bitte einbauen, auch bei den bestehenden Trades: Radar, Fusion (Hedge),
-- Stop Loss, Take Profit, alles anpassen … Auch bei Topstep ist das Daily Loss Limit 3K.“ (TopstepX „150K DLL Express (…6316)“: „DLL: $0.00 … $3,000.00“)
-- 07:07: „Ist Soft Breach wie bei Lucid, nur eben 3k.“ → 1:1 wie Lucid id 17/18 (tagesstart, Tagespause, Topstep schließt den Master, Konto lebt; kein Hard
-- Breach wie FTMO Futures id 19). 07:13 auf die Frage „auch Konten OHNE ‚DLL‘ in der SKU (Mike …1691 „EXPRESS-V2-682437-57131691“)?“: „Ja, für alle.“
-- Risiko-Hinweis (Slave 14, festgehalten auf Master-Wunsch): hätte ein Konto in Wahrheit KEIN DLL, schlösse der Fusion-Hedge / Radar bei −3.000 $ ab Tagesstart,
-- während der Master weiterläuft. Laut Finn (07:13) haben alle Topstep-Funded/Express/WD-Konten real ein 3K-DLL — der Fall tritt also nicht ein.
--
-- WIRKUNG (zusammen mit dem Code im selben Commit):
--   Radar        app.py liq_regel_felder: WD (id 6 „wie funded“) bzw. funded → diese Zeile → „Daily Loss 3.000 $ ab Tagesstart“, soft (liq_regel_soft); Boden = MLL
--   Fusion/Airbag prophos.html hedgeTopstepDll: Funded/WD nehmen die eigene Zeile ohne SKU-Bedingung (vorher nur DLL-SKUs über id 8) → näheres von MLL + 100 und
--                Tagesstart − 3.000 + 100 (liq_art daily_loss)
--   WD-SL-Würfel app.py wd_sl_fuer_plan (Express-Zweig): Puffer bis zum NÄHEREN von MLL + 100 und Tagesstart − 3.000 + 100; „ohne SL“ gewürfelt und DLL näher →
--                Pflicht-SL 100 $ vor dem DLL (DL2 wie Lucid). DL2b (wd_sl_dll_firma → True): ein Topstep-WD-Plan ohne SL entsteht nicht mehr (wie Lucid).
--                Ohne MLL-Lesung: Express-MLL liegt nie über 0 → liegt Tagesstart − 3.000 + 100 über 100, gilt das DLL auch ohne Lesung (sonst sperrte DL2b das Konto,
--                bevor Puls die erste MLL lesen kann). Liegt die MLL näher (z. B. Mike …1691 bei BAL 2.026) und ist „ohne SL“ gewürfelt → an dem Tag kein Plan.
--   Radar-Fail-closed: Tagesstart mehr als 3.000 über der Start-Balance → Regel verworfen, nur MLL (wie TX4).
-- REIHENFOLGE: erst diese SQL, dann den Code pushen (DLL-SKUs nähmen mit dem Code allein den DLL-Puffer über id 8, aber noch ohne Pflicht-SL).
--   Funded-Planer funded_plan_regeln Topstep daily_usd 3.000 (wie Lucid 2.700, LP1) — Topstep steht dort auf „an“: false → erst beim Einschalten.
-- UNVERÄNDERT: id 8 (Challenge, nur DLL-SKU im Hedge), MLL/Boden (Express → liq_konto_boden „Boden = MLL aus TopstepX“, Lock bei 0; maxdd_* dieser Zeilen NULL =
--   wie bisher ohne eigene Zeile bzw. id 6), keine groesse (alle Topstep-Funded/WD sind 150k, viele ohne starting_balance — mit groesse 150000 griffe die Zeile dort nicht).

-- (1) liq_regeln: Topstep funded + winning_days, tagesstart 3.000 (id ist GENERATED ALWAYS → ohne id; idempotent über not exists)
insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, lock_ueber_start_usd, stufen, wie_kontotyp, notiz, quelle,
                               maxdd_art, maxdd_lock_ueber_groesse_usd, maxdd_usd, dll_schutz)
select 'Topstep', k.typ, null, 'tagesstart', 3000, null, null, null,
       'TS-DLL 17.11.2026: Topstep ' || k.txt || ' — Daily Loss 3.000 $ ab Tagesstart = Tagespause (Soft Breach wie Lucid id 17/18), Topstep schließt den Master, '
       || 'Konto lebt; Blow nur an der MLL aus TopstepX (Express 0-basiert, Lock bei 0). Gilt für ALLE SKUs, auch ohne „DLL“ (Finn 07:13 „Ja, für alle.“).',
       'Finn 17.11.2026 ~07:05/07:07/07:13 Dubai (über den Master, TS-DLL)', null, null, null, null
  from (values ('funded', 'Funded/Express'), ('winning_days', 'Winning Days')) as k(typ, txt)
 where not exists (select 1 from public.liq_regeln r where r.firma = 'Topstep' and r.kontotyp = k.typ);

-- (2) Funded-Planer (funded_plan_regeln id 1, Firma „Topstep“, 150k): daily_usd 3.000 wie Lucid — _fdp_pump_sl kappt den SL auf Daily-Rest − Puffer,
--     „ohne SL“ wird SL knapp vor dem Tageslimit, Trade 2 höchstens E1 + 3.000
update public.funded_plan_regeln f
   set firmen = (select jsonb_agg(case when e->>'name' = 'Topstep' and jsonb_typeof(e->'je_groesse'->'150000') = 'object'
                                       then jsonb_set(e, '{je_groesse,150000,daily_usd}', '3000'::jsonb, true) else e end order by ord)
                   from jsonb_array_elements(f.firmen) with ordinality as t(e, ord))
 where f.id = 1
   and exists (select 1 from jsonb_array_elements(f.firmen) e
                where e->>'name' = 'Topstep' and jsonb_typeof(e->'je_groesse'->'150000') = 'object'
                  and (e->'je_groesse'->'150000'->>'daily_usd') is distinct from '3000');

-- (3) BESTEHENDER UNGESTARTETER PLAN (Master entscheidet; nur DL2-Gleichstand mit Lucid): Ina PRO …8936, Plan 16637d9a (Start 09:16 UTC, „gewürfelt: ohne SL“) —
--     nach der neuen Regel bekäme er den Pflicht-SL 100 $ vor dem DLL. Erster Trade des CME-Tags 17.11. (Beginn 23:00 UTC am 16.11.) → Tagesstart = Start-Balance →
--     SL = 3.000 − 100 = 2.900 $ (MLL ≤ 0 liegt bei ~18.300 $ Balance weit dahinter). Nur solange NICHT geclaimt/gestartet/gesendet, ohne SL, keine Start-Sperre
--     des Tabs, und kein anderer Plan des Kontos heute gestartet. Laufende/abgeschlossene Pläne und Broker-Orders werden NICHT angefasst.
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
-- select id, firma, kontotyp, art, betrag_usd, maxdd_art, dll_schutz from public.liq_regeln where firma = 'Topstep' order by id;
-- select e->'je_groesse'->'150000'->'daily_usd' from public.funded_plan_regeln f, jsonb_array_elements(f.firmen) e where f.id = 1 and e->>'name' = 'Topstep';
-- select left(id::text, 8), status, master_sl, mt5_baseline->'wd_sl' from public.trade_plans where id::text like '16637d9a%';
