-- FT1 (Finn 11.11.2026 20:53 über den Master): „FTMO Futures bitte Ziel zu 4000–4500 und Lots 50 % 1 NQ und 50 % 2 NQ.“
-- Funded-Planer Futures, Firma ftmofutures, Größe 50k — nur diese zwei Felder, alles andere am Eintrag bleibt.
--   ziel_gewinn [4.750, 5.000] → [4.000, 4.500]  (fdp_ziel_gewinn: je Konto fest aus der Konto-ID gewürfelt, ab Zyklus 2 je Zyklus neu)
--   kontrakte   {"1": 1}       → {"1": 0.5, "2": 0.5}  (fdp_kontrakte im Rest-Modus: beim Anlegen des Plans gewürfelt, danach fest am Plan)
-- TP und SL bleiben in $ (Rest bis Ziel bzw. SL [750, 850]); die Punkte folgen aus den Kontrakten (NQ 20 $/Pkt), der Fusion-Hedge rechnet aus $ und
-- bleibt in € gleich (Selbsttest tools/selftest_ft1_ftmo_futures.py). Gleiche Felder, die der Reiter Funded-Planer → Einstellungen liest und feldweise
-- speichert (POST /admin/funded-plan/regeln, _FDP_GR_FELDER / _FDP_GR_KT) — e4Speichern (wd_farmer_regeln) berührt diese Tabelle nicht.
-- Idempotent: setzt die Werte, egal wie oft eingespielt; fehlt der Eintrag, ändert sich nichts.

update public.funded_plan_regeln r
   set firmen = (
         select jsonb_agg(case when f->'namen' ? 'ftmofutures' and f->'je_groesse' ? '50000'
                               then jsonb_set(jsonb_set(f, '{je_groesse,50000,ziel_gewinn}', '[4000, 4500]'::jsonb),
                                              '{je_groesse,50000,kontrakte}', '{"1": 0.5, "2": 0.5}'::jsonb)
                               else f end order by o)
           from jsonb_array_elements(r.firmen) with ordinality as e(f, o)),
       updated_at = now()
 where r.id = 1 and jsonb_typeof(r.firmen) = 'array';

-- Prüfen:
-- select f->'je_groesse'->'50000' from public.funded_plan_regeln, jsonb_array_elements(firmen) f where f->'namen' ? 'ftmofutures';
--   → {"dd": 3000, "sl": [750, 850], "daily_usd": 1000, "hedge_eur": 450, "kontrakte": {"1": 0.5, "2": 0.5}, "kosten_eur": 120, "ziel_gewinn": [4000, 4500]}
