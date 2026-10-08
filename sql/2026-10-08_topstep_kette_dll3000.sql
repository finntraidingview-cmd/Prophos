-- TOPSTEP-KETTE MIT DAILY LOSS LIMIT 3.000 (Finn 08.10.2026 ~21:55 Dubai: „Topstep-Konten werden ab jetzt immer mit dem Plan gekauft, der
-- ein Daily Loss Limit von 3.000 hat" — soft: Topstep schließt für den Tag, das Konto lebt). Tagesergebnis „+4.500 oder −3.000" statt
-- „+4.500 oder geblowt (−4.500)". Code app.py ab 2026-09-22.1379 (ap_kette_trade1/trade2/abhaken, ap_kette_mll).
--
-- 1) Topstep-Regel, Block kette:
--      daily_usd 3000      → Verlustgrenze = min(3.000, Tagesstart − MLL) + blow_puffer 200; Abstand zum MLL < 3.000 = „angefressen",
--                            der Planer legt dann KEINEN Kettenplan an (Grund in der Planer-Liste, Weg entscheidet Finn)
--      t1_sl [1250, 1750]  → Trade 1 SL (TP bleibt 1.950–2.650)
--    Ohne daily_usd (vor diesem SQL) rechnet der Code wie bisher: DD + 200, SL 1.950–2.650 aus der Regel.
-- 2) liq_regeln id 8 (Topstep challenge): art 'tagesstart', betrag 3.000 — der Radar zeigt am DLL „⏸ Tageslimit" (Soft-Breach wie Apex,
--    liq_regel_soft), geblowt nur am Konto-Boden = MLL (eod_trailing, DD 4.500 aus den Kernwerten, Lock 0 = 150.000).
--    Gilt für ALLE Topstep-Challenge-Konten (die Tabelle kennt keinen Plan je Konto) — Konten ohne DLL zeigen dann ebenfalls die
--    Tageslimit-Linie bei Tagesstart − 3.000.
-- Wiederholbar. Rückbau: kette - 'daily_usd', t1_sl [1950, 2650]; liq_regeln id 8 art null, betrag_usd null.
update public.auto_plan_regeln
   set regeln = jsonb_set(regeln, '{firmen}', (
         select jsonb_agg(case when f->'namen' ? 'topstep' and f ? 'kette'
                               then jsonb_set(f, '{kette}', (f->'kette') || '{"daily_usd": 3000, "t1_sl": [1250, 1750]}'::jsonb)
                               else f end order by o)
           from jsonb_array_elements(regeln->'firmen') with ordinality as e(f, o))),
       updated_at = now()
 where id = 1;

update public.liq_regeln
   set art = 'tagesstart', betrag_usd = 3000,
       notiz = 'Finn 08.10.2026: Topstep-Konten mit Daily Loss Limit 3.000 (soft — Topstep schließt für den Tag, das Konto lebt). '
            || 'Geblowt nur am MLL (Konto-Boden eod_trailing 4.500 hinter der höchsten EOD-Balance, lockt bei der Startbalance — firm_rules.json).',
       quelle = 'Finn 08.10.2026 (über den Master)'
 where id = 8 and lower(firma) = 'topstep' and kontotyp = 'challenge';

-- Prüfen:
-- select f->'kette' from auto_plan_regeln, jsonb_array_elements(regeln->'firmen') f where id = 1 and f->'namen' ? 'topstep';
-- select id, art, betrag_usd, maxdd_art, maxdd_lock_ueber_groesse_usd from liq_regeln where id = 8;
