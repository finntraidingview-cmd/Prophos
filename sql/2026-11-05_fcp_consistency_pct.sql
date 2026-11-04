-- FUNDED-CFD-PLANER: CONSISTENCY ALS PARAMETER (E1b, Finn 05.11.2026: „bei The5ers Consistency einfach 50 % je Zyklus eintippen, dann wird das automatisch
-- angewandt — die Logik soll nicht da stehen, nur der Parameter"). Neu je Firma: firmen[].consistency_pct (1–99 %, 0 = aus).
-- Der Planer rechnet nach WEG A (Finn 05.11.2026 ~04:20 Dubai: „Weg A, das Ziel bleibt", app.py fcp_cons_rechnen): Z = gewürfeltes Ziel der Größe,
-- G = Balance − Kontogröße, B = größter Gewinn-Tag im Payout-Zyklus · Endziel F = max(Z, B ÷ p × 1,02) · Deckel je Trade c = p × F × 0,95 ·
-- Rest R = F − G gleich verteilt auf n = ceil(R ÷ c) Trades (TP ≥ 50 $, ≤ c) · fertig, wenn G ≥ max(Z, B ÷ p) · Zyklus nicht lesbar → TP = max(50, min(c, Rest)).
--
-- Diese Datei schreibt The5%ers ausdrücklich 50 % in die Regel. Ohne den Wert nimmt der Code bei The5%ers ebenfalls 50 % (tp_modus consistency50
-- bzw. Code-Standard als Rückfall) — das Einspielen ändert also nichts an den Plänen, es macht den Wert nur in den Einstellungen änderbar.
-- tp_modus bleibt stehen, damit ein älterer Code-Stand weiter dasselbe rechnet. Andere Firmen bleiben unverändert (ohne Wert = keine Consistency).
-- Idempotent: setzt den Wert nur, wenn die Firma noch keinen consistency_pct-Schlüssel hat; Reihenfolge der Firmen bleibt.
update public.funded_cfd_plan_regeln r
set firmen = (
      select jsonb_agg(case when e.f->>'name' = 'The5%ers' and not (e.f ? 'consistency_pct')
                            then e.f || '{"consistency_pct": 50}'::jsonb else e.f end order by e.ord)
      from jsonb_array_elements(r.firmen) with ordinality as e(f, ord)),
    updated_at = now()
where r.id = 1
  and exists (select 1 from jsonb_array_elements(r.firmen) x(f) where x.f->>'name' = 'The5%ers' and not (x.f ? 'consistency_pct'));

-- Prüfen: select f->>'name', f->'consistency_pct', f->'tp_modus' from public.funded_cfd_plan_regeln, jsonb_array_elements(firmen) f where id = 1;
-- erwartet: The5%ers · 50 · "consistency50", alle anderen · null
