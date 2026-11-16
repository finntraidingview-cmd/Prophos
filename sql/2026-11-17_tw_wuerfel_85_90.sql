-- Handels-Würfel höher (Finn 17.11.2026 ~03:25 Dubai: „die Pausentage sind ein bisschen oft … Firmenwürfel auf 90 % — zu 90 % ist er immer drin,
-- zu 10 % raus. Handelswürfel auf 85 %, damit mehr Accounts getradet werden. Für heute noch mal neu würfeln.“)
-- Vorher: firma_je_id 85 % (sql/2026-11-13_tw3_firmen_wuerfel_85.sql), alle fünf Planer 75 % (sql/2026-11-11_tageswuerfel_75.sql). Nur Hermann Technologies
-- (gruppe ''); Emins Unternehmen hat keine Zeile = 100 % und bleibt so.
-- Wirkung heute: der Wurf je Konto × Tag ist fest (sha256), nur die Schwelle steigt → wer heute schon dran war, bleibt drin; dazu kommen die Konten mit
-- Wurf 75–85 (Konto) bzw. 85–90 (Firma). „Pause-Tag“ ist bewusst kein fester Nachplan-Grund (TW_GRUND in app.py) → das Nachplanen holt sie heute dazu.
-- Railway merkt die Werte 60 s (TW_CACHE_S).

update public.planer_handel_wuerfel set pct = 90, updated_at = now()
 where planer = 'firma_je_id' and gruppe = '';

update public.planer_handel_wuerfel set pct = 85, updated_at = now()
 where planer in ('challenge_cfd', 'challenge_futures', 'funded_cfd', 'funded_futures', 'winning_days') and gruppe = '';

-- Kontrolle: select planer, gruppe, pct from public.planer_handel_wuerfel order by 1;
-- Zurück: firma_je_id 85, die fünf Planer 75.
