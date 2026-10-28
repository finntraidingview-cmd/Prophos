-- Funded-Planer Apex: 100k nie mehr 1 NQ, sondern 2 oder 3 NQ je 50 % (28.10.2026, Finn: „Kein einziger Trade bei Funded soll wieder ein NQ
-- sein. Ein NQ ist zu wenig. Immer zwei bis drei, auch bei 100K"). 150k bleibt 2 NQ 75 % / 3 NQ 25 %. Apex-Stufe 1 (100k) erlaubt 3 Minis.
-- Dazu die zwei schon bestätigten, ungestarteten 100k-Pläne mit 1 NQ: Kontrakte hoch. Hedge-€, Multiplikator (Lots je Kontrakt), master_risk
-- und slave_risk hängen nicht an der Kontraktzahl (fdp_hedge: lots ∝ Kontrakte, hedge_eur = offen × TP ÷ (Balance − Liq)) und bleiben.

-- 1) Regel: firmen[Apex].je_groesse."100000".kontrakte
update funded_plan_regeln r
set firmen = (
  select jsonb_agg(case when f->>'name' = 'Apex Trader'
                        then jsonb_set(f, '{je_groesse,100000,kontrakte}', '{"2": 0.5, "3": 0.5}'::jsonb)
                        else f end order by i)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, i)),
    updated_at = now()
where r.id = 1
returning firmen -> 0 -> 'je_groesse' -> '100000' -> 'kontrakte' as apex_100k;

-- 2) offene Funded-Pläne mit 1 NQ (bestätigt, ungestartet): Chris …0006 → 3 NQ, Marc …0004 → 2 NQ (gewürfelt)
update trade_plans t set master_contracts = v.kt
from (values ('8e56c8c0-77dd-429e-8596-73b9b8ab3bce'::uuid, 3), ('744eb925-89e8-441c-8fab-fcb841ea4f72'::uuid, 2)) v(id, kt)
where t.id = v.id and t.status = 'planned' and t.started_at is null and t.start_um_gestartet_at is null and t.master_contracts = 1
returning t.id, t.master_name, t.master_contracts, t.multiplier, t.hedge_eur;
