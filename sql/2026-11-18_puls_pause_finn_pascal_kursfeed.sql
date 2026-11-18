-- PULS-PAUSE FINN + PASCAL (18.11.2026 ~04:45 Dubai). Finn: „Dann für Finn bitte alle Orders pausieren … dann tue ich nachher wieder Orbit
-- anschalten, wenn Moritz' PC wieder läuft.“ Anlass: Moritz' PC (pc-usq1i6, Feed-Tab für tv_kurse) fällt am Standort aus; der Kursfeed läuft
-- vorübergehend über pc-2zc2we (Finn + Pascal), dort ist im Puls-Chrome der Tampermonkey-Modus „Puls-Chrome (Orbit V3)“ AUS → Puls darf in
-- diesem Chrome keine Orders platzieren (sonst Feed weg + Positionen nicht gelesen).
-- Muster wie sql/2026-10-15_puls_pause_finn_pascal_jacob.sql (starke Form, Fallen aus memory prophos-puls-pause-lehren beachtet):
--   1. Auto-Planer-Haken der Konten aus (NICHT user_ids — sonst verliert Finns Login den Admin-Reiter). Die Liste der umgestellten Konten
--      wird in user_settings key 'puls_pause_2026_11_18' gesichert → Rückweg stellt genau diese wieder an.
--   2. alle geplanten, nicht gestarteten Pläne (Auto UND Hand, inkl. WD-Farmer, Echo): unbestätigt, start_um 2027-01-01, Marke
--      mt5_baseline.puls_pause {start_um_war, bestaetigt_war}. coalesce(… ? 'puls_pause', false), weil mt5_baseline NULL sein kann.
--   3. WD-Tagesplan 18.11.: Konten aktiv=false + puls_pause, status leer, start_um null (sonst setzt der Tab „geplant“ zurück).
-- Laufende Pläne bleiben unberührt (es läuft keiner).

begin;

insert into public.user_settings (user_id, key, value, updated_at)
select '48f272b4-913e-4598-a06a-1dcc3d5679fb', 'puls_pause_2026_11_18',
       jsonb_build_object('konten_auto_planer', coalesce(jsonb_agg(a.id), '[]'::jsonb), 'at', now(), 'grund', 'Kursfeed über pc-2zc2we, Puls-Modus aus'), now()
from public.accounts a
where a.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and a.auto_planer = true
  and not exists (select 1 from public.user_settings s where s.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and s.key = 'puls_pause_2026_11_18');

update public.accounts a set auto_planer = false, updated_at = now()
where a.user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and a.auto_planer = true
  and a.id::text in (select jsonb_array_elements_text(value->'konten_auto_planer') from public.user_settings
                      where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and key = 'puls_pause_2026_11_18');

update public.trade_plans
   set auto_bestaetigt_at = null,
       start_um = '2027-01-01 00:00:00+00',
       mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('puls_pause', jsonb_build_object(
           'at', '2026-11-18T00:45:00Z',
           'grund', 'Kursfeed läuft über pc-2zc2we (Puls-Modus aus) — keine Orders bei Finn + Pascal bis Finn Orbit wieder anschaltet',
           'start_um_war', start_um,
           'bestaetigt_war', (auto_bestaetigt_at is not null),
           'stillgelegt_at', now()))
 where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb'
   and status = 'planned' and start_um_gestartet_at is null and start_um is not null and started_at is null
   and not coalesce(mt5_baseline ? 'puls_pause', false);

update public.wd_tagesplan
   set konten = (select jsonb_agg(case when coalesce((k->>'aktiv')::boolean, false)
                                       then k || '{"aktiv": false, "hinweis": "Puls-Pause 18.11.2026 (Kursfeed auf diesem PC) — bis Finn freigibt", "puls_pause": true}'::jsonb
                                       else k end) from jsonb_array_elements(konten) k),
       status = 'leer', start_um = null, updated_at = now()
 where user_id = '48f272b4-913e-4598-a06a-1dcc3d5679fb' and tag = '2026-11-18' and status <> 'laeuft';

commit;

-- RÜCKWEG (Finn: Moritz' PC läuft wieder, Puls-Modus auf pc-2zc2we wieder AN) — siehe 2026-11-18_puls_pause_finn_pascal_kursfeed_ende.sql
