-- LH1 (10.11.2026, Master): Lucid-MLL sitzt bei Start + 100 $ fest (150k: 150.100, 50k: 50.100) — für Eval und Funded.
-- Quelle: support.lucidtrading.com/en/articles/12945815-lucidflex-drawdown („Once the account exceeds the trail, the MLL locks at the initial balance plus $100.“),
-- 150k: MLL 4.500, Initial Trail Balance 154.600, Locked MLL 150.100. Anlass: Finn 10.11.2026, Fall Simon LFE…0003 (−2.817 $, Fusion +221 €).
-- Bisher: id 12 (allgemein) und id 15/16 (Challenge 150k/50k, Daily Loss) eod_trailing OHNE Lock → Radar/Liq-Boden zog über 150.100 hinaus nach;
-- id 14 (winning_days) hat den Lock +100 schon. Nach dem Einspielen gewinnt dieser Lock in _ah_boden_eod (app.py) vor dem Kernwerte-Lock (lock_plus_usd 100,
-- gleicher Wert). NICHT vom Slave ausgeführt — der Master spielt ein.
update public.liq_regeln
   set maxdd_lock_ueber_groesse_usd = 100,
       notiz = coalesce(notiz, '') || ' · LH1 10.11.2026: MLL-Lock bei Größe + 100 $ (150.100 / 50.100), Quelle support.lucidtrading.com 12945815.',
       updated_at = now()
 where id in (12, 15, 16)
   and firma = 'Lucid Trading'
   and maxdd_art = 'eod_trailing'
   and maxdd_lock_ueber_groesse_usd is null
returning id, firma, kontotyp, groesse, maxdd_art, maxdd_lock_ueber_groesse_usd;
