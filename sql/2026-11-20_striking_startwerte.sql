-- SK1 Striking-Startwerte (S1, 20.11.2026) — NUR auf Finns Wort und erst NACH sql/2026-11-20_striking_apex.sql (Spalten).
-- Ersetzt die auskommentierten Zeilen in sql/2026-11-20_marc_apex_wieder_aktiv.sql um Zyklus-Beginn (Nachtrag 1) und Probation (Nachtrag 2).
-- Reihenfolge beim Freischalten (Nachtrag 3, Finn: „Jede ID einzeln prüfen. Nicht schnell schnell.“): 1) Startwerte, 2) addon_firma-Zeile der ID,
-- 3) globaler Not-Aus striking_regeln.aktiv = true. Ohne 2) plant Striking das Konto nicht, ohne 3) niemanden.

-- 1) Marc — Trader Probation seit 18.11.2026 (Apex-Dashboards 20.11.)
update public.accounts set striking_zyklus_start = 112344.96, striking_zyklus_seit = '2026-11-18', striking_payout_nr = 2, striking_probation = true
 where id = '6f7f4acd-3d1b-41f3-bf3b-c9f234889f35';   -- 100k …05, 1 Payout 2.000
update public.accounts set striking_zyklus_start = 112288.54, striking_zyklus_seit = '2026-11-18', striking_payout_nr = 1, striking_probation = true
 where id = '171fd292-de0a-4daf-93b6-8289069178eb';   -- 100k …06, 0 Payouts, +360,84 seit 18.11.
update public.accounts set striking_zyklus_start = 161441.12, striking_zyklus_seit = '2026-11-18', striking_payout_nr = 2, striking_probation = true
 where id = '2aa6f1a9-ac0f-43a5-80d9-08e1f15c3a4d';   -- 150k …02, 1 Payout 2.500, +1.466,72 seit 18.11.

-- 2) Marc freischalten (user_id = Besitzer der drei Konten oben)
-- insert into public.addon_firma (user_id, firma, addon, an)
--   select distinct user_id, 'apex', 'striking', true from public.accounts where id = '6f7f4acd-3d1b-41f3-bf3b-c9f234889f35'
--   on conflict (user_id, firma, addon) do update set an = true, updated_at = now();

-- 3) Globaler Not-Aus an (aus = false setzen)
-- update public.striking_regeln set aktiv = true, updated_at = now() where id = 1;

-- Jacob 100k …0003 — KEINE Probation, Payout 1 (2.000) am 20.11. genehmigt; erst auf Finns Wort (nur Startwerte, keine addon_firma-Zeile):
-- update public.accounts set striking_zyklus_start = 110105.82, striking_zyklus_seit = '2026-11-20', striking_payout_nr = 2, striking_probation = false
--  where id = '7e3a65a5-73e5-4286-9458-c5a4cf12a026';
