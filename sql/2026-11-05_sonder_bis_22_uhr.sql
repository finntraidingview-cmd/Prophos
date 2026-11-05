-- SONDERREGEL HEUTE (Finn 05.11.2026 ~19:40 Dubai: „bitte heute Sonderregelung neue Acc bis 22 Uhr Dubai-Zeit direkt reinplanen, es ist so viel
-- Volumen … bei allen Sachen“). Nur Hermann Technologies (auto_plan_regeln id 1) — Emins Gruppe stellt ihre Zeiten selbst ein
-- (Memory prophos-zwei-unternehmen-getrennt). Nur Einstellung, kein Code (Memory feedback-modell-ueber-einstellung).
--   Futures-Fenster 02:00–20:00 → 02:00–22:00 Dubai, start_bis 20:00 → 22:00, CFD-Ende 18:00 → 22:00 Dubai,
--   neue Konten (Nachplan-Takt) bis 16:00 → 22:00 Dubai.
-- RÜCKBAU (Teil 2) MUSS vor dem Nachtlauf 01:30 Dubai laufen — sonst plant der Nachtlauf morgen mit dem langen Fenster.

-- Teil 1: Sonderregel an
update public.auto_plan_regeln
   set zeiten = zeiten
       || jsonb_build_object('fenster', jsonb_build_array(jsonb_build_array('02:00', '22:00', 100)),
                             'start_bis', '22:00',
                             'cfd_bis', jsonb_build_object('tz', 'Asia/Dubai', 'uhr', '22:00'),
                             'neu_bis', jsonb_build_object('tz', 'Asia/Dubai', 'uhr', '22:00')),
       updated_at = now()
 where id = 1;

-- Teil 2: RÜCKBAU auf den Stand vor dem 05.11.2026 19:40 Dubai (neu_bis fällt weg = Code-Standard 16:00 Dubai)
-- update public.auto_plan_regeln
--    set zeiten = (zeiten - 'neu_bis')
--        || jsonb_build_object('fenster', jsonb_build_array(jsonb_build_array('02:00', '20:00', 100)),
--                              'start_bis', '20:00',
--                              'cfd_bis', jsonb_build_object('tz', 'Asia/Dubai', 'uhr', '18:00')),
--        updated_at = now()
--  where id = 1;
