-- Thanksgiving 26.11.2026 (Finn ~03:10 Dubai): „Heute Trades alle in der Nacht machen, weil um 12 Uhr New York der Markt schon schließt …
-- alle Topstep-Trades, die geplant sind, 3 Uhr Dubai bis 10 Uhr Dubai.“ NUR HEUTE.
-- Teil 1: die fünf Topstep-Pläne nach 10:00 Dubai in freie Lücken davor (gestreut, ≥ 25 min je ID, ≥ 10 min zu jedem anderen Topstep-Start).
-- Teil 2: Topstep-Kette für heute auf dasselbe Fenster (zeiten.tz = Europe/Berlin, 10:00 Dubai = 07:00 Berlin), sonst plant der Bot den
--         zweiten Trade erst ab 11:00 Berlin (t2_ab) — also in den Feiertagsmarkt.
-- RÜCKWEG (vor dem Nachtlauf 27.11. 01:30 Dubai ausführen): Teil 3 ganz unten.

-- Teil 1 — Startzeiten (UTC; Dubai = UTC+4)
with neu(id, nach) as (values
  ('680521fe-d3e2-48b7-95cd-a86746cecc81'::uuid, timestamptz '2026-11-25 23:47:23+00'),   -- Marc …48456381 sell: 10:46 → 03:47 Dubai
  ('4258d516-7e72-4af8-83e9-08ecd49305b2'::uuid, timestamptz '2026-11-26 00:24:41+00'),   -- Marc …80376187 sell: 10:53 → 04:24
  ('b93d65d9-3c96-42ce-af7f-faa422444db5'::uuid, timestamptz '2026-11-26 03:14:52+00'),   -- …702233-24036316 WD buy: 12:11 → 07:14
  ('2b5eef99-e22a-49eb-8bb4-e9da1a5a1388'::uuid, timestamptz '2026-11-26 04:07:34+00'),   -- …702233-17698204 buy: 12:43 → 08:07
  ('e9fd3f29-da07-423b-8add-5ed58a6f7b60'::uuid, timestamptz '2026-11-26 04:36:17+00')    -- Marc …20719220 sell: 12:15 → 08:36
), alt as (
  select p.id, p.user_id, p.master_firm, p.richtung, p.start_um von, n.nach from trade_plans p join neu n on n.id = p.id where p.status = 'planned'
), upd as (
  update trade_plans p set start_um = a.nach, updated_at = now() from alt a where p.id = a.id and p.status = 'planned' returning p.id
)
insert into auto_plan_umplanung (um, plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
select now(), a.id, a.user_id, a.master_firm, a.richtung, a.richtung, a.von, a.nach, 'Thanksgiving 26.11.2026: alle Topstep-Starts bis 10:00 Dubai (Finn)', 'hand'
from alt a join upd u on u.id = a.id;

-- Teil 2 — Topstep-Kette nur heute: T1 und T2 bis 07:00 Berlin, T2 ab sofort statt ab 11:00
update auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'topstep'
                               then jsonb_set(f, '{kette}', (f->'kette') || '{"t1_bis":"07:00","t2_ab":"00:00","t2_bis":"07:00"}'::jsonb)
                               else f end order by ord)
           from jsonb_array_elements(r.regeln->'firmen') with ordinality x(f, ord))),
       updated_at = now()
 where r.id = 1;

-- Teil 3 — RÜCKWEG (27.11.): alte Werte t1_bis 11:00 · t2_ab 11:00 · t2_bis 19:30
-- update auto_plan_regeln r
--    set regeln = jsonb_set(r.regeln, '{firmen}', (
--          select jsonb_agg(case when f->'namen' ? 'topstep'
--                                then jsonb_set(f, '{kette}', (f->'kette') || '{"t1_bis":"11:00","t2_ab":"11:00","t2_bis":"19:30"}'::jsonb)
--                                else f end order by ord)
--            from jsonb_array_elements(r.regeln->'firmen') with ordinality x(f, ord))),
--        updated_at = now()
--  where r.id = 1;
