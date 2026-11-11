-- DL2 SCHNELLWEG (11.11.2026, Finn 21:12 „Direkt bitte fixen“): Daily Loss am Fusion-Hedge der Lucid-Winning-Days — NUR SQL, wirkt mit dem LIVE-Code.
-- Warum es ohne Deploy greift: prophos.html hedgeLiqDll (live) liest die liq_regeln-Zeile der Kontoart winning_days; mit art 'tagesstart' schließt der
-- Hedge 5 NQ-Punkte vor Tagesstart − Daily Loss (das engere von Boden Größe + 100 und DLL-Level). app.py liest dieselbe Zeile (Radar, WD-Planer):
-- tagesstart = Tagespause, Konto lebt; der harte Boden bleibt über maxdd_art eod_trailing + Lock Größe + 100 (wie Lucid funded id 17, LH1).
-- Die neue Zeile ist spezifischer (Größe 150000) als id 14 (Lucid/winning_days/alle Größen, art boden) und gewinnt nur für 150k.
--
-- NICHT im Schnellweg (eine liq_regeln-Zeile gilt für ALLE Konten einer Firma × Kontoart × Größe):
--   Tradeify  — Select Daily (DLL 1.750 bei 150K) und Select Flex (KEIN DLL) sind nicht unterscheidbar (alle Kennungen FTDFYSLX…). Eine Firmen-Zeile
--               schlösse den Hedge bei Flex-Konten 1.750 $ zu früh → Master ungehedgt. Braucht das Konto-Feld accounts.dll_usd (DL2-Code + SQL dl2_konto_dll).
--   Topstep   — der Hedge-Level-Zweig für tsv2 nimmt die TopstepX-MLL und fragt das Tageslimit gar nicht (Code nötig).
--   FTMO Futures — Zeile winning_days tagesstart 1.000 bringt S3 mit FT2.
-- Prüfen vor dem Einspielen (Finn): Lucid-Kennungen beginnen mit „LFF“ — falls das „Lucid Flex Funded“ ohne Tageslimit heißt, NICHT einspielen.
-- Heute ein Lucid-WD-Konto (150k, Balance 157.369): Tagesstart − 2.700 ≈ 154.669 > Boden 150.100 — der Hedge schließt dort statt am Boden.
-- Idempotent (legt die Zeile nur an, wenn es Lucid/winning_days/150000 noch nicht gibt). Einspielen nur durch den Master (execute_sql).

-- id ist GENERATED ALWAYS AS IDENTITY → nicht mitgeben
insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, lock_ueber_start_usd, stufen, wie_kontotyp, maxdd_art, maxdd_lock_ueber_groesse_usd, maxdd_usd, notiz, quelle, updated_at)
select 'Lucid Trading', 'winning_days', 150000, 'tagesstart', 2700, null, null, null, 'eod_trailing', 100, null,
       'DL2 11.11.2026: Lucid 150k Winning Days = dasselbe Funded-Konto → Daily Loss 2.700 $ ab Tagesstart (Tagespause, Lucid schließt den Master), harter Boden Größe + 100 (eod_trailing). Fusion-Hedge schließt vor dem DLL-Level (hedgeLiqDll).',
       'Finn 11.11.2026 (id 17: „bei Lucid halt Daily Drawdown … von 2,7k“; DL2 21:12 „Direkt bitte fixen“)', now()
where not exists (select 1 from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'winning_days' and groesse = 150000);

-- Kontrolle: select id, firma, kontotyp, groesse, art, betrag_usd, maxdd_art, maxdd_lock_ueber_groesse_usd from public.liq_regeln where firma = 'Lucid Trading' order by id;
-- Rückbau:   delete from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'winning_days' and groesse = 150000;
