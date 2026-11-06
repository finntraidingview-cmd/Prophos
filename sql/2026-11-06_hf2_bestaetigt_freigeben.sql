-- HF2 (Finn 06.11.2026: „dass man einfach nur einmal auf ‚Bestätigen' drücken muss … nicht noch mit diesem Hedge-Freigabe … einfach einmal
-- ‚Bestätigen', fertig"): seit HF2 setzt jedes Bestätigen (einzeln, „✓ alle", Auto-Bestätigen, alle Gruppen) bei Hedge-Plänen
-- (mt5_baseline.hedge_art 'apex' = Orbit Prio 2, 'tradeify_final' = Tradeify-/Lucid-Final) hedge_freigabe_at gleich mit. Diese Datei gibt
-- die Altfälle frei, die HEUTE (Dubai-Tag) schon bestätigt wurden, aber noch keine Freigabe haben — genau der Block „Hedge-Freigabe offen".
-- Guard wie POST /admin/auto-plan/hedge-freigabe: planned, ungeclaimt, ohne Freigabe. start_um bleibt unverändert (ein überfälliger Start
-- wird hier NICHT verschoben — dafür im Admin einzeln ✓, das zieht ihn auf jetzt + 3–6 min). Idempotent.
-- Stand beim Schreiben (06.11.2026 ~04:50 Dubai): 0 Zeilen betroffen.
update public.trade_plans
   set hedge_freigabe_at = now(),
       hedge_freigabe_von = 'hf2_sql'
 where status = 'planned'
   and start_um_gestartet_at is null
   and hedge_freigabe_at is null
   and auto_bestaetigt_at is not null
   and auto_bestaetigt_at >= (date_trunc('day', now() at time zone 'Asia/Dubai') at time zone 'Asia/Dubai')
   and coalesce(mt5_baseline->>'hedge_art', '') in ('apex', 'tradeify_final')
returning id, master_name, master_firm, start_um, auto_bestaetigt_at;
