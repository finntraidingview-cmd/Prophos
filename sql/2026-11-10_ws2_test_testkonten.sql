-- WS2-Test 10.11.2026 (Finn über Master, OK „mit Zufalls-Schluss“): 7 Testkonten, test_n 3; heute feste Anzahl 4/3/2 auf den drei teilbaren Plänen. Haupt an Platz 1, Lots/SL/Start/Hedge unverändert. Einmalig ausgeführt per execute_sql.
-- 1) Einstellung
update auto_plan_regeln set regeln = jsonb_set(jsonb_set(jsonb_set(regeln, '{tagesteilung,an}', 'true'),
  '{tagesteilung,nur_konten}', '["1d91cb16-cf23-4fae-86f4-9fda275b7c7e","05558b29-f2d4-4b0b-9864-9e617bd6acba","99762298-08d4-438d-8b2b-d361342f8a30","ec85d450-99d7-4d2a-9d37-676700c93249","45e81ee9-91c6-4875-9767-9ddd4c38054f","a4517dac-00b9-4f09-9bc9-edffe053495e","a9712512-61a5-4bba-aace-815fad5be70b"]'),
  '{tagesteilung,test_n}', '3')
where id = 1 returning regeln->'tagesteilung';

-- 2) Pläne → Trade 1 einer Kette (nur planned, ohne Claim, nicht gestartet)
with neu(pid, n, anteile, tp, ziel, menge, ppl, schritt, txt) as (values
  ('a1a11968', 4, '[0.76,0.08,0.08,0.08]'::jsonb, 8507, 11193, 53, 1.0, 1, 'Tag 1/4 · Haupt 76 % (Test WS2, Tag: Haupt 76 % · 8 % · 8 % · 8 %, Ziel +11.193 $) · '),
  ('05bf9e57', 3, '[0.8,0.1,0.1]'::jsonb, 4614, 5768, 34, 1.0, 1, 'Tag 1/3 · Haupt 80 % (Test WS2, Tag: Haupt 80 % · 10 % · 10 %, Ziel +5.768 $) · '),
  ('893cccfc', 2, '[0.8,0.2]'::jsonb, 5278, 6597, 3, 10.0, 0.1, 'Tag 1/2 · Haupt 80 % (Test WS2, Tag: Haupt 80 % · 20 %, Ziel +6.597 $) · ')
)
update trade_plans p set master_tp = neu.tp,
  mt5_baseline = jsonb_set(coalesce(p.mt5_baseline, '{}'::jsonb), '{kette}', jsonb_build_object('nr', 1, 'von', neu.n, 'rolle', 'haupt',
     'plan', jsonb_build_object('n', neu.n, 'haupt_an', 1, 'anteile', neu.anteile), 'tagesziel', neu.ziel, 'haupt_menge', neu.menge,
     'ppl', neu.ppl, 'menge_schritt', neu.schritt, 'test', 'WS2-Test 10.11.2026')),
  notes = 'Auto-Planer · ' || neu.txt || regexp_replace(p.notes, '^Auto-Planer · ', '')
from neu
where left(p.id::text, 8) = neu.pid and p.status = 'planned' and p.start_um_gestartet_at is null and p.started_at is null
  and p.master_tp = neu.ziel and p.master_contracts = neu.menge and not (p.mt5_baseline ? 'kette')
returning left(p.id::text, 8), p.master_tp, p.start_um, p.mt5_baseline->'kette';
