-- 2026-09-30: liq_regeln, zweite Fassung nach Finns Antworten (über den Master). Setzt auf sql/2026-09-30_liq-regeln.sql auf.
--   • Tradeify Funded: „Bei Tradeify Funded ist es 4,5k." → fest 4.500 $, KEIN Lock mehr (erste Fassung: trailing bis Start + 100).
--   • Tradeify Winning Days: „Sobald die zu Winning Days verschoben werden, ist die Liquidation bei 150.100." → neue art 'boden'.
--   • Apex Winning Days bleibt über die generische Zeile (alle, winning_days, wie funded) → Apex-Funded-Stufen (Fall Moritz …0008).
--   • FundedNext: „ist CFD, da gebe ich immer einen Stop Loss ein, relativ egal. FundedNext Futures: gerade kein Funded, egal."
--     → keine Regel, nur Notiz (die Spanne nimmt bei CFD den echten SL).
--   • Apex Evaluation 2.000 $: weiter offen, Zeile unverändert.
--
-- art (vollständig, ersetzt die Liste in der ersten Datei):
--   fest          Liquidation = Balance beim Trade-Start − betrag_usd
--   trailing_lock wie fest, aber nie über (groesse + lock_ueber_start_usd): Liq = min(Start − betrag, Größe + Lock)
--   stufen        Daily Loss je Stufe: Stufe = letzte mit ab_balance ≤ Tagesstart-Balance, Liq = Tagesstart-Balance − daily_loss_usd
--   tagesstart    Daily Loss: Liq = Balance zu Tagesbeginn (CME-Handelstag) − betrag_usd
--   boden   (NEU) fester Boden: Liq-Balance = (groesse der Zeile, sonst Kontogröße des Kontos) + lock_ueber_start_usd
--                 (Tradeify Winning Days: 150.000 + 100 = 150.100), unabhängig von der Balance beim Start
--   null          noch offen (siehe notiz)
-- Nachschlagen wie bisher: spezifischste Zeile gewinnt — Tradeify/winning_days schlägt (alle)/winning_days „wie funded".
--
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.

-- 1) art 'boden' zulassen
alter table public.liq_regeln drop constraint if exists liq_regeln_art_check;
alter table public.liq_regeln add constraint liq_regeln_art_check
  check (art is null or art in ('fest', 'trailing_lock', 'stufen', 'tagesstart', 'boden'));

-- 2) Tradeify Funded: fest 4.500 $, kein Lock
update public.liq_regeln
   set art = 'fest', betrag_usd = 4500, lock_ueber_start_usd = null,
       notiz = 'Finn (Antwort 30.09.2026): „Bei Tradeify Funded ist es 4,5k." → fest 4.500 $ ab Balance beim Trade-Start, KEIN Lock '
            || '(ersetzt „trailt bis Start + 100 $" aus der ersten Fassung). Der Boden 150.100 gilt erst, wenn das Konto zu Winning Days '
            || 'verschoben ist (eigene Zeile Tradeify/winning_days).',
       quelle = 'Finn 30.09.2026 (Antwort über den Master)'
 where lower(firma) = 'tradeify' and kontotyp = 'funded' and groesse is null;

-- 3) Tradeify Winning Days: Boden Kontogröße + 100 $
insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, lock_ueber_start_usd, notiz, quelle)
select 'Tradeify', 'winning_days', null::numeric, 'boden', null::numeric, 100::numeric,
       'Finn (Antwort 30.09.2026): „Sobald die zu Winning Days verschoben werden, ist die Liquidation bei 150.100." → Liq-Balance = '
    || 'Kontogröße + 100 $ (150k: 150.100), fest. Schlägt die generische Zeile (alle, winning_days, wie funded). Deckt sich mit der '
    || 'heutigen WD-Rechnung in app.py (_lt_liq_balance) und dem Fusion-Hedge-Level.',
       'Finn 30.09.2026 (Antwort über den Master)'
where not exists (select 1 from public.liq_regeln r
                  where lower(r.firma) = 'tradeify' and r.kontotyp = 'winning_days' and r.groesse is null);

-- 4) FundedNext: keine Regel, nur Notiz
update public.liq_regeln
   set art = null, betrag_usd = null, lock_ueber_start_usd = null, stufen = null,
       notiz = 'Finn (Antwort 30.09.2026): „ist CFD, da gebe ich immer einen Stop Loss ein, relativ egal. FundedNext Futures: gerade kein '
            || 'Funded, egal." → keine Regel: CFD hat immer einen echten SL, die Spanne nutzt den SL; FundedNext Futures noch ohne Funded.',
       quelle = 'Finn 30.09.2026 (Antwort über den Master)'
 where lower(firma) = 'fundednext' and kontotyp is null and groesse is null;

-- Prüfen:
-- select id, firma, kontotyp, groesse, art, betrag_usd, lock_ueber_start_usd, wie_kontotyp, left(notiz, 70)
--   from public.liq_regeln order by firma nulls last, kontotyp nulls first;
