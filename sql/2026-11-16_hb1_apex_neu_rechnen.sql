-- HB1-Nachtrag (Master 16.11.2026): Chris Apex 100k …0006 und …0005 — die zwei Pläne vom 15.11. 21:33 UTC wurden noch mit der alten Hedge-Basis
-- (Pfad-Simulation: 519,68 € bzw. 579,55 €, ~17 bzw. 13,7 Fusion-Lots) angelegt und sind auto-bestätigt (start_um gesetzt). fdp_vorschlag_basis_neu rechnet
-- nur unbestätigte Vorschläge nach — darum genau das, was POST /admin/funded-plan/zurueck macht (app.py _fdp_eingriff „zurueck“ + fdp_eingriff_filter):
-- auto_bestaetigt_at und start_um leer, sonst nichts. Der Funded-Planer rechnet sie im nächsten Lauf mit HB1 nach (Satz eines frischen Kontos × Abstand:
-- …0006 ≈ 158 €, …0005 ≈ 218 €, je ~5,2 Lot), die vorgeschlagene Zeit bleibt in mt5_baseline.funded_plan.start_um. Finn bestätigt sie danach selbst
-- („Selbst bestätigen“ ist seit 16.11. 03:52 aus).
-- ERST NACH dem HB1-Push (558d8b46) einspielen — sonst rechnet der alte Planer sie mit der alten Basis nach.
-- Nur diese zwei Plan-IDs, nur mit demselben Guard wie die Route: status planned, Funded-Planer-Plan (funded_plan da, art leer), nie geclaimt/gestartet.
-- …0007 (7cac75c1, echte Kosten 313 € > Satz × Abstand, bleibt wie er ist) wird NICHT angefasst. Idempotent (zweiter Lauf: 0 Zeilen).
--   b05e910b-599e-4130-8d4f-77d82e99d7d2 · 100k PAAPEX6687940000006 → Funded · start_um 16.11. 05:11 UTC · slave_risk 519,68 €
--   684f6528-f34a-4801-8612-cd22177a730e · 100k PAAPEX6687940000005 → Funded · start_um 16.11. 15:11 UTC · slave_risk 579,55 €

update public.trade_plans
   set auto_bestaetigt_at = null, start_um = null
 where id in ('b05e910b-599e-4130-8d4f-77d82e99d7d2', '684f6528-f34a-4801-8612-cd22177a730e')
   and status = 'planned'
   and mt5_baseline->'funded_plan' is not null
   and mt5_baseline->'funded_plan'->>'art' is null
   and start_um_gestartet_at is null
   and started_at is null
returning id, master_name, status, start_um, auto_bestaetigt_at, mt5_baseline->'funded_plan'->>'start_um' as vorschlag_zeit;

-- Kontrolle danach (nächster Planer-Lauf, ≤ 5 min): slave_risk ≈ 158 € (…0006) bzw. ≈ 218 € (…0005), Notiz-Ende „Hedge-Basis … = theoretische Kosten (frisches Konto)“
-- select id, master_name, auto_bestaetigt_at, start_um, slave_risk, multiplier, mt5_baseline->'funded_plan'->>'offen_eur' basis, right(notes, 90)
--   from public.trade_plans where id in ('b05e910b-599e-4130-8d4f-77d82e99d7d2', '684f6528-f34a-4801-8612-cd22177a730e');
