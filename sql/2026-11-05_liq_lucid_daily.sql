-- LQ1 (05.11.2026, Finn 21:35 Dubai zu Lucid 150k Flex Eval: „Der Max Drawdown ist 4k, aber wir haben hier ein Daily von 2,7k“): Radar-Liq-Linie,
-- Radar-Demo und „Konto weg“-Schätzung nahmen für Lucid-Challenges ohne Hedge (Orbit V2, z. B. Simon c1ed32a3 / Pascal 9dd4573b) nur die
-- Lucid-Zeile id 12 (EOD-Trailing, Betrag = accounts.max_drawdown 4.500) → Level ~109 Pkt × 2 NQ ≈ 4.370 $ unter dem Einstieg. Der Daily Loss
-- (accounts.max_daily_drawdown: 150k 2.700, 50k 1.200) greift aber zuerst. Orbit Prio 2 mit Hedge rechnet ihn schon (ah_abstand/ah_dll_balance,
-- Notiz „Hedge zu am Daily Loss 48.800“ bei 50k) — die Liq-Regel kannte ihn nicht.
-- Jetzt je Größe eine Challenge-Zeile art 'tagesstart' (Daily Loss ab Tagesstart). liq_regel_felder nimmt die ENGERE von Regel und Konto-Boden,
-- also min(Daily, Max Loss). liq_regel_waehlen nimmt nur EINE Zeile (die spezifischste) — deshalb tragen die neuen Zeilen maxdd_art 'eod_trailing'
-- wie id 12 mit, sonst fiele der EOD-Trailing-Boden weg. Nachgerechnet (Lader von tools/selftest_liq_regeln.py): 150k Start 150.000 → Liq 147.300
-- (vorher 145.500), 50k → 48.800 (vorher 48.000); unter dem EOD-Hoch (152.000, Balance 149.000) gilt weiter der Boden 147.500.
-- Wirkung NUR auf Anzeige/Schätzung (Radar-Spanne, Chart, Demo, „Konto weg“, hf_wd_master_verlust nur für WD — WD hat eigene Zeile id 14, unberührt).
-- Fusion-Hedge-Level und Orbit-Prio-2-Lots unverändert. art 'tagesstart' heißt im Radar „Tageslimit, Konto lebt“ (liq_regel_soft) — ist der Lucid-
-- Daily-Loss ein HARTER Breach (Konto weg), statt 'tagesstart' art 'fest' nehmen (gleicher Betrag ab Trade-Start; bei einem Trade je Tag gleich).
-- Idempotent (where not exists). Nicht eingespielt — Master/Finn.

insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, maxdd_art, notiz, quelle)
select 'Lucid Trading', 'challenge', 150000, 'tagesstart', 2700, 'eod_trailing',
       'Lucid 150k Flex Eval: Daily Loss 2.700 $ ab Tagesstart greift vor dem Max Loss 4.500 EOD (Boden wie id 12 mitgetragen).',
       'Finn 05.11.2026 21:35 Dubai (über den Master, LQ1)'
where not exists (select 1 from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'challenge' and groesse = 150000);

insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, maxdd_art, notiz, quelle)
select 'Lucid Trading', 'challenge', 50000, 'tagesstart', 1200, 'eod_trailing',
       'Lucid 50k Flex Eval: Daily Loss 1.200 $ ab Tagesstart (accounts.max_daily_drawdown) greift vor dem Max Loss 2.000 EOD.',
       'Finn 05.11.2026 21:35 Dubai (über den Master, LQ1)'
where not exists (select 1 from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'challenge' and groesse = 50000);

-- Optional, nur auf Finns Wort (Lucid Funded 150k hat am Konto ebenfalls max_daily_drawdown 2.700, 1 Konto):
-- insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, maxdd_art, notiz, quelle)
-- select 'Lucid Trading', 'funded', 150000, 'tagesstart', 2700, 'eod_trailing', 'Lucid 150k Funded: Daily Loss 2.700 $ ab Tagesstart.', 'Finn …'
-- where not exists (select 1 from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'funded' and groesse = 150000);

-- Kontrolle:
-- select id, firma, kontotyp, groesse, art, betrag_usd, maxdd_art from public.liq_regeln where firma = 'Lucid Trading' order by id;

-- RÜCKBAU:
-- delete from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'challenge' and groesse in (50000, 150000);
