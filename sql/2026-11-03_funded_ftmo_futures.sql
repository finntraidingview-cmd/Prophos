-- REIHENFOLGE (S9-Stopp zu b8e6dc2b): ERST den Code pushen, DANN diese Datei einspielen — der alte Code kennt ziel_gewinn als Spanne nicht
-- (TypeError) und hielte den ganzen Funded-Planer inkl. Apex an.
-- FTMO FUTURES 50k IM FUNDED-PLANER (Finn 03.11.2026 ~02:30 Dubai über den Eingang; Code app.py fdp_konto_rechnen Modus tp_modus = 'rest').
-- Regeln: Ziel = Start + 4.750–5.000 $ (je Konto fest gewürfelt, fdp_ziel_gewinn), 1 Trade pro Tag, immer 1 NQ, SL 750–850 $ je Trade gewürfelt (höchstens
-- Daily Loss 1.000 − 100 Puffer und höchstens Abstand zur Liquidation − 50; unter 300 $ Abstand kein Trade), TP immer der Rest bis zum Ziel — kein Deckel, kein Break-even (Verlusttag →
-- nächster TP um den Verlust größer), Hedge 450 € auf 3.000 $ Max DD (0,15 € je $ Abstand zur Liquidation, Fusion wie bei Apex), Boden wie die
-- FTMO-Futures-Challenge (auto_plan_regeln ftmofutures: nachziehend, dd 3.000, lock_bei_start → lock_usd 0), daily_usd 1.000 wie dort.
-- Bestätigen von Hand wie bei Apex (funded_plan_regeln.auto_bestaetigen bleibt, wie es ist). Ziel erreicht → Winning Days wie bei Apex.
-- Firma „FTMO Futures“, Schlüssel ftmofutures — FTMO CFD (Schlüssel ftmo) ist nicht betroffen. kosten_eur 120 = Kaufpreis wie die Challenge, im Modus rest
-- nicht für den Hedge gelesen (nur Anzeige/Rückfall).
-- Wiederholbar: ersetzt nur den Eintrag ftmofutures, die anderen Firmen bleiben.
update funded_plan_regeln r set firmen = (
  select jsonb_agg(case when f->'namen' ? 'ftmofutures' then
      jsonb_build_object(
        'name', 'FTMO Futures', 'namen', jsonb_build_array('ftmofutures'), 'an', true, 'symbol', 'NQ', 'lock_usd', 0, 'tp_modus', 'rest',
        'je_groesse', jsonb_build_object('50000', jsonb_build_object(
          'ziel_gewinn', jsonb_build_array(4750, 5000), 'sl', jsonb_build_array(750, 850), 'kontrakte', jsonb_build_object('1', 1),
          'dd', 3000, 'daily_usd', 1000, 'hedge_eur', 450, 'kosten_eur', 120)))
    else f end order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
), updated_at = now()
where r.id = 1 and r.firmen @> '[{"namen": ["ftmofutures"]}]';

-- Kontrolle: select f from funded_plan_regeln, jsonb_array_elements(firmen) f where id = 1 and f->'namen' ? 'ftmofutures';
