-- Echo-Hedge AN (Finn 29.10.2026 abends: „ab jetzt jeden Echo-V2-Trade einfach mit Echo ersetzen, wie bei Emin"). eh_tick stellt jeden
-- bestätigten HT-CFD-Challenge-Plan (Echo V2) ab 20 min vor dem Start auf Echo mit Fusion-Gegenhedge um (q = Kontowert/Polster/0,89);
-- laufende bleiben. Alle HT-IDs mit Echo-V2-Trades der letzten 14 Tage haben ein echo_hedge_account (geprüft). Rückfall ohne Hedge (⚪) bei
-- < 0,01 Lot / keine Fusion-Lesung / Marge. Rücknahme: echo_hedge.an = false.
update public.auto_plan_regeln set regeln = jsonb_set(regeln, '{echo_hedge,an}', 'true'::jsonb), updated_at = now() where id = 1;
