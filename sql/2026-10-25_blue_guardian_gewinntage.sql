-- Blue Guardian: Gewinntage statt Trading Days (Finn 25.10.2026)
-- Blue Guardian zählt je Phase nur Tage mit ≥ 0,5 % geschlossenem Gewinn (100k = 500 $), 3 Stück. Bei uns zählte jeder Tag mit
-- gestartetem Trade (trading_days) — …601805 (Phase 2) stand bei uns auf 3/3, bei Blue Guardian auf 1/3 (zwei Mini-Tage ohne 500 $).
-- Planer (app.py ap_konto_rechnen regel.gewinntage): solange ≥ 2 Gewinntage fehlen nur Gewinntag-Trades TP 1.000–1.100 $, SL/Lots wie
-- die Regel; erst bei höchstens einem fehlenden Tag die Big Trades. ERST NACH dem Railway-Deploy des Backends einspielen — das alte
-- Backend kennt winning_days mit goal_min_profit nicht und würde …602629 sonst normal mit Etappe planen.

-- 1) Gewinntag-TP in der Firmenregel blueguardian
update auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}',
       (select jsonb_agg(case when f->'namen' ? 'blueguardian' then f || '{"gewinntage": {"tp": [1000, 1100]}}'::jsonb else f end order by i)
          from jsonb_array_elements(regeln->'firmen') with ordinality t(f, i)))
 where id = 1;

-- 2) …602629 (Phase 2, Finn + Pascal, im Minus): Gewinntage 3 × ≥ 500 $, zählt ab Anlegetag 22.10.2026 — bisher 0/3
update accounts
   set goal_kind = 'winning_days', goal_target = 3, goal_min_profit = 500, goal_manual = false,
       goal_since = '2026-10-22', goal_done_offset = 0
 where id = '62d25eae-e069-4cef-8673-fd25c328cdda';

-- 3) …601805 (Phase 2, bestanden, 1/3 bei Blue Guardian): bleibt in Review, Finn holt die zwei Tage Mo/Di von Hand → nicht mehr einplanen
update accounts set auto_planer = false where id = 'f742b593-caae-4d09-8190-220b125a510b';

-- Prüfen
select external_id, account_type, auto_planer, goal_kind, goal_target, goal_min_profit, goal_since, goal_done_offset
  from accounts where id in ('62d25eae-e069-4cef-8673-fd25c328cdda', 'f742b593-caae-4d09-8190-220b125a510b');
select f->'gewinntage' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->'namen' ? 'blueguardian';
