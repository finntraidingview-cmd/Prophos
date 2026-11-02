-- Apex-Challenges wieder planen, mit Fusion-Gegenhedge auf dem WD-Weg (Finn 02.11.2026 04:05: „ja bau und push"; Konstrukt
-- berichte/2026-11-02_apex-hedge-konstrukt.md). Gegenstück zu sql/2026-10-30_planer_nur_echo.sql: dort wurde Apex am 30.10. auf planen:false
-- gesetzt, seitdem keine Pläne und der fertige Weg (ah_tick, hedge_art 'apex', Freigabe-Block) hatte nichts zu tun.
-- Mechanik: Schlüssel planen am Apex-Eintrag entfernen = Vorher-Stand laut planer_nur_echo.sql (null). Andere Firmen, aktiv und
-- auto_bestaetigen bleiben unberührt: alles bleibt Vorschlag, Finn bestätigt. Kernwerte (groessen, je_groesse, kauf_eur) unverändert.
-- Wiederholbar. Rückweg: f || '{"planen": false}' am selben Eintrag.
update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'apextrader' then f - 'planen' else f end order by ord)
           from jsonb_array_elements(r.regeln->'firmen') with ordinality as t(f, ord))),
       updated_at = now()
 where r.id = 1
   and exists (select 1 from jsonb_array_elements(r.regeln->'firmen') f where f->'namen' ? 'apextrader' and f ? 'planen');

-- Kontrolle: apextrader planen = null, alle anderen wie vorher; apex_hedge.an = true.
-- select f->'namen'->>0 firma, f->'planen' planen from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1;
-- select regeln->'apex_hedge' from auto_plan_regeln where id = 1;
