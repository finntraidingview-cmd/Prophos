-- Apex-Challenges wieder an, für ALLE IDs (Finn 23.11.2026 ~02:45 Dubai: „apex wieder aktivieren" → „alle Challenges",
-- „bei den Fundeds bisher nur Marc"). Anlass: Chris' 10 neue Apex-Challenges (…0022–…0031, angelegt 18.11.) standen
-- seit der Pause vom 20.11. still (sql/2026-11-20_apex_pause.sql).
-- NUR Schritt 1 des Rückwegs: Challenge-Planer plant Apex wieder (Tagesdeckel max_konten_tag 2–3 je ID bleibt).
-- BEWUSST NICHT: Funded-Planer Apex bleibt an=false, wd_farm der 8 Konten in apex_pause_20261120_wd bleibt aus —
-- Fundeds laufen weiter nur bei Marc über sein Striking-Gate (addon_firma + striking_regeln).
-- Gesicherte Pläne aus apex_pause_20261120_plaene nicht zurückspielen, der Planer plant neu.
-- Idempotent: entfernt nur den Schlüssel „planen" an der Apex-Firma.

update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'apex' then f - 'planen' else f end order by o)
           from jsonb_array_elements(regeln->'firmen') with ordinality as t(f, o))),
       updated_at = now()
 where id = 1
   and exists (select 1 from jsonb_array_elements(regeln->'firmen') f where f->'namen' ? 'apex' and f ? 'planen');

-- Rückweg (wieder pausieren): Schritt 1 aus sql/2026-11-20_apex_pause.sql.
