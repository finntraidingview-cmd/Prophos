-- 2026-10-12 — Mindest-Handelstage bei FundedNext (Finn, Wochenplan Mo 12.10.2026: „bei FundedNext brauchen wir immer
-- Mindesthandelstage in Phase 1 und Phase 2, immer 5 Stück pro Phase … füge es für alle bestehenden Accounts bis einen
-- Tag rückwirkend nach"). Zähler = bestehendes Ziel-System (goal_kind trading_days, Stand abgeleitet aus trade_plans wie
-- bei den Winning Days, Anzeige „🏆 x/5 Trading Days" am Konto). Der Auto-Planer sieht die fehlenden Tage (ap_tage_ist)
-- und plant je Handelstag einen Mini-Trade (ap_tage_mini), der PC-Tab schließt ihn sofort nach dem Start.

-- 1) Schablone: zentrale Bulk-Vorlagen FundedNext (Phase 1 — Phase 2 entsteht über den Nachfolger-Assistenten, der
--    goal_kind/goal_target vom alten Konto übernimmt)
update bulk_vorlagen
   set goal_kind = 'trading_days', goal_target = 5
 where firm = 'FundedNext' and account_type in ('phase1', 'phase2');

-- 2) Bestand: alle FundedNext-Konten in Phase 1/2 ohne eigenes Ziel — Tage zählen ab gestern (11.10.2026)
update accounts
   set goal_kind = 'trading_days', goal_target = 5, goal_manual = false,
       goal_since = date '2026-10-11', goal_done_offset = coalesce(goal_done_offset, 0)
 where firm = 'FundedNext' and account_type in ('phase1', 'phase2') and goal_kind is null;
