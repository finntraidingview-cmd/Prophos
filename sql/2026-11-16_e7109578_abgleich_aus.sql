-- Finn+Pascal FundedNext Futures 150k …38896, WD BUY 2 MNQ (e7109578): Fusion-Hedge wurde 18:52 fälschlich geschlossen (FH2: kurz leere
-- Positionsliste 488579 → level_mt5-Close). Danach wollte der Abgleich („Hedge zu + Master offen → Master schließen“, prophos.html ~63789)
-- den Master immer wieder schließen; Finn musste abbrechen. Finn 16.11.2026 ~19:40: „lass den einfach laufen, den vergessen wir.“
-- abKandidat nimmt tvv2/tsv2 nur mit hedge.ticket → Ticket nach ticket_alt verschieben, Status/P&L bleiben. Nur dieser Plan.
update public.trade_plans p
set mt5_baseline = jsonb_set(p.mt5_baseline, '{hedge}', ((p.mt5_baseline->'hedge') - 'ticket') || jsonb_build_object('ticket_alt', p.mt5_baseline->'hedge'->'ticket',
      'abgleich_aus', 'Finn 16.11.2026 ~19:40: WD ohne Hedge einfach laufen lassen, Abgleich soll den Master nicht schließen (Hedge fälschlich zu, FH2)'))
where p.id::text like 'e7109578%' and p.status = 'open' and p.mt5_baseline->'hedge'->>'status' = 'geschlossen' and p.mt5_baseline->'hedge' ? 'ticket';
