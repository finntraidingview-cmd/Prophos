-- 2026-09-30: liq_regeln, dritte Fassung — Apex Evaluation bestätigt (Finn, Antwort über den Master). Setzt auf
-- sql/2026-09-30_liq-regeln.sql und -2.sql auf. Die Regel selbst bleibt (art 'tagesstart', 2.000 $); nur die Notiz verliert das
-- „Offen: …" und trägt Finns Bestätigung, quelle wird die Antwort. Sonst ändert sich nichts.
--
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent (setzt nur Text, derselbe Lauf zweimal ergibt denselben Stand).

update public.liq_regeln
   set notiz = 'Finn (Antwort 30.09.2026): „Apex Evaluation ist Daily Loss 2.000 $ ab Tagesbeginn. Wenn du 500 verlierst, bleibt der '
            || 'Rest. Macht keinen Unterschied, ich mache pro Konto und Tag immer nur einen Trade, entweder komplettes SL oder komplettes '
            || 'TP." → Daily Loss 2.000 $ ab Balance zu Tagesbeginn (CME-Handelstag). Größe nicht genannt (gilt für alle Apex-Evaluations).',
       quelle = 'Finn 30.09.2026 (Antwort über den Master)'
 where lower(firma) = 'apex trader' and kontotyp = 'challenge' and groesse is null
   and art = 'tagesstart' and betrag_usd = 2000;

-- Prüfen:
-- select id, firma, kontotyp, art, betrag_usd, left(notiz, 90), quelle from public.liq_regeln
--  where lower(firma) = 'apex trader' and kontotyp = 'challenge';
