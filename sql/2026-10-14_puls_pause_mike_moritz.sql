-- PULS-PAUSE MIKE + MORITZ (14.10.2026 ~16:45 Dubai, Finn: „Moritz und Mike mache ich gerade den Polar-Trade manuell. Deswegen sollen
-- da jetzt keine Orders von Puls kommen" — bis auf Weiteres, auch keine manuellen Starts). Es gibt keinen Schalter je ID, deshalb
-- zwei Handgriffe, beide ohne Löschen:
--   1. Mike und Moritz aus auto_plan_regeln.user_ids — der Auto-Planer (Nachtlauf, Nachplan-Takt, Ausgleichs-Bot) legt nichts Neues an.
--   2. Ihre geplanten, noch nicht geclaimten Auto-Pläne auf „unbestätigt" (auto_bestaetigt_at = null): PC-Tab (suKandidaten) und
--      DB-Claim-Guard (SU_CLAIM_GUARD) starten unbestätigte Pläne nie; Startzeiten bleiben stehen. Marke mt5_baseline.puls_pause.
-- Laufende Trades (Moritz …1667 SELL, Mikes Winning Day …1691) bleiben unberührt — Endlesung/Auto-Close sind keine neuen Orders.
-- Angewendet 14.10.2026 12:45 UTC direkt gegen die DB (4 Pläne Mike, 3 Pläne Moritz).
update public.auto_plan_regeln
   set user_ids = array_remove(array_remove(user_ids, '32b854d1-866f-4e7e-ba0b-9bf63df2d993'), 'aff98e60-e9a0-4821-9d1d-31634571a2f4'),
       updated_at = now()
 where id = 1;
update public.trade_plans
   set auto_bestaetigt_at = null,
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || '{"puls_pause":{"at":"2026-10-14T12:45:00Z","grund":"Finn macht den Polar-Trade manuell (Mike/Moritz) — keine Puls-Orders bis Freigabe","bestaetigt_war":true}}'::jsonb
 where user_id in ('32b854d1-866f-4e7e-ba0b-9bf63df2d993', 'aff98e60-e9a0-4821-9d1d-31634571a2f4')
   and status = 'planned' and start_um_gestartet_at is null and auto_plan = true;

-- RÜCKWEG (sobald Finn freigibt): IDs wieder in den Planer, markierte Pläne wieder bestätigen (Startzeiten sind dann vermutlich vorbei —
-- der Nachplan-Takt plant neu).
-- update public.auto_plan_regeln set user_ids = user_ids || array['32b854d1-866f-4e7e-ba0b-9bf63df2d993','aff98e60-e9a0-4821-9d1d-31634571a2f4'], updated_at = now() where id = 1;
-- update public.trade_plans set auto_bestaetigt_at = now(), mt5_baseline = mt5_baseline - 'puls_pause'
--  where status = 'planned' and (mt5_baseline->'puls_pause'->>'bestaetigt_war')::boolean;
