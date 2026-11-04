-- FUNDED-CFD-PLANER: CONSISTENCY ALS PARAMETER (E1b, Finn 05.11.2026: „bei The5ers Consistency einfach 50 % je Zyklus eintippen, dann wird das automatisch
-- angewandt — die Logik soll nicht da stehen, nur der Parameter"). Neu je Firma: firmen[].consistency_pct (1–99 %, 0 = aus). Der Planer rechnet
-- generisch: neuer Tag x ≤ G · p / (100 − p) (G = Gewinne des laufenden Zyklus), Zyklus-Beginn = Start-TP (je_groesse.tp_erster, sonst 750).
-- Bei p = 50 genau das bisherige Verhalten (min(Rest, G), Start 750, Mindest-TP, fail-closed 750).
--
-- Diese Datei schreibt The5%ers ausdrücklich 50 % in die Regel (bisher: tp_modus = consistency50 bzw. Code-Standard — gleiche Wirkung).
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
