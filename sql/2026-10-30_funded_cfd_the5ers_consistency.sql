-- FUNDED-CFD-PLANER: THE5ERS-CONSISTENCY (Finn 30.10.2026 ~07:40, ersetzt bei The5ers tp_erster 750 + tp_zyklen):
-- TP = min(Rest, max(Rest / 2, Gewinne)). Rest = Ziel (gewürfelt in ziel[von, bis]) − Balance; Gewinne = Summe aller Gewinn-Trades des
-- Kontos (trade_plans status completed, master_pl > 0, alle bisherigen — die 50-%-Regel wird beim Payout nicht zurückgesetzt).
-- Fail-closed: ein beendeter Trade ohne master_pl → Rest / 2. Beispiele: Moritz 100k …2352 → 1.312; Finn + Pascal 100k …5250 → 3.073.
-- app.py (fcp_tp_modus) nimmt consistency50 für The5ers auch ohne diesen Schlüssel; die Zeile macht ihn sichtbar. tp_zyklen/tp_erster
-- bleiben stehen und werden bei diesem Modus nicht benutzt. Andere Firmen unverändert. Idempotent (|| überschreibt nur tp_modus).
update public.funded_cfd_plan_regeln r
   set firmen = (select coalesce(jsonb_agg(case when f->'namen' ? 'the5ers' then f || '{"tp_modus": "consistency50"}'::jsonb else f end
                                           order by i), '[]'::jsonb)
                   from jsonb_array_elements(r.firmen) with ordinality e(f, i)),
       updated_at = now()
 where r.id = 1;
