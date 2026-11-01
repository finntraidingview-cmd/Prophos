-- TSX-MENGE (Finn 02.11.2026): Topstep-Challenge-Planer würfelt die Kontrakte je Trade gewichtet: 20 % 1 NQ, 70 % 2 NQ, 10 % 3 NQ.
-- Finn schrieb „10 % 1 NQ“, der Eingang liest 3 NQ (sonst wäre es nie 3 NQ und die Summe stimmt nur so); die Korrektur wäre eine Zahl in diesen Gewichten.
-- Vorher: Spanne [2, 2.6667] gerundet, also 2 NQ oder 3 NQ. TP und SL in $ bleiben, die Punkte ergeben sich aus $ ÷ (Menge × 20).
-- Gelesen von app.py _ap_spanne: kette.menge_gewichte (Trade 1), kette.t2_menge_gewichte (Trade 2), phasen.challenge.menge_gewichte
-- (Rückfall ohne Kette). Die Spannen bleiben als Rückfall stehen. puffer_je_menge bekommt 1 NQ (Vorschlag [10, 15] $, Finn kann anpassen).
-- Nur der Topstep-Eintrag. Wiederholbar: vorhandene Werte gewinnen, eine spätere Anpassung wird beim erneuten Einspielen nicht überschrieben.
update auto_plan_regeln r set regeln = jsonb_set(r.regeln, '{firmen}', (
  select jsonb_agg(case when f->'namen' ? 'topstep' then
      jsonb_set(jsonb_set(jsonb_set(f,
        '{kette}', '{"menge_gewichte": {"1": 20, "2": 70, "3": 10}, "t2_menge_gewichte": {"1": 20, "2": 70, "3": 10}}'::jsonb || coalesce(f->'kette', '{}'::jsonb)),
        '{phasen,challenge}', '{"menge_gewichte": {"1": 20, "2": 70, "3": 10}}'::jsonb || coalesce(f->'phasen'->'challenge', '{}'::jsonb)),
        '{phasen,challenge,puffer_je_menge}', '{"1": [10, 15]}'::jsonb || coalesce(f->'phasen'->'challenge'->'puffer_je_menge', '{}'::jsonb))
    else f end order by ord)
  from jsonb_array_elements(r.regeln->'firmen') with ordinality as x(f, ord)
))
where r.id = 1 and r.regeln->'firmen' @> '[{"namen": ["topstep"]}]';

-- Kontrolle: select f->'kette'->'menge_gewichte', f->'kette'->'t2_menge_gewichte', f->'phasen'->'challenge'->'menge_gewichte',
--   f->'phasen'->'challenge'->'puffer_je_menge' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->'namen' ? 'topstep';
