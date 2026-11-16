-- LF1 (Master 16.11.2026, Finn): Lucid Flex 50k Funded als Profil im Funded-Planer Futures (funded_plan_regeln id 1, Firma „Lucid Trading“).
-- Gilt für alle Unternehmen (Standard), genutzt vor allem von Emins Unternehmen. Idempotent: mehrfach ausführbar, ändert nur Lucid.
--
-- Firmenregeln Lucid Flex 50k Funded: Max Loss Limit 2.000 $ (EOD trailing, Lock Größe + 100), DLL 1.200 $, keine Consistency im Funded,
-- max 4 Mini / 40 Micro, Payout nach 5 Gewinntagen je ≥ 150 $ (WD_GOOD_DAY_MIN im Code), Scaling-Plan ja.
-- Finns Vorgaben: Ziel-Gewinn 6.000–8.000 $ je Zyklus (fest je Konto × Zyklus gewürfelt, fdp_pump_tag_wurf), EIN Pump-Trade aufs Ziel
-- (Pump-Modell pump2 mit pump2_pct 0 = nie Trade 1 + Trade 2), 1–2 NQ, SL 1.000–1.100 $ (immer mit SL: sl_kein_pct 0; unter DLL 1.200 − 100 Puffer),
-- Liq/Lock wie 150k (EOD trailing, lock_usd 100 der Firma), danach Winning Days. Hedge 300 € je 2.000 $ Risiko (Finn 16.11.2026) —
-- den Endwert setzt der Master (Funded Planer → Futures → Einstellungen → Lucid · 50k · Hedge).
-- Schalter je Größe (je_groesse.<Größe>.an, neu mit LF1): Firma an, 150k aus (Profil bleibt erhalten), 50k an.
-- Ohne diese Zeilen ändert der Code nichts: Profile ohne „an“ je Größe folgen allein dem Schalter der Firma.

update public.funded_plan_regeln r
set firmen = (
  select jsonb_agg(
    case when f->>'name' = 'Lucid Trading' then
      jsonb_set(
        jsonb_set(f || '{"an": true}'::jsonb, '{je_groesse,150000,an}', 'false'::jsonb, true),
        '{je_groesse,50000}',
        coalesce(f->'je_groesse'->'50000', '{}'::jsonb) || '{
          "an": true,
          "dd": 2000,
          "daily_usd": 1200,
          "ziel_gewinn": [6000, 8000],
          "ziel_toleranz_pct": 10,
          "pump2_pct": 0,
          "ein_kontrakte": {"1": 0.5, "2": 0.5},
          "ein_sl": [1000, 1100],
          "sl_kein_pct": 0,
          "sl_hinter_liq": false,
          "t1_von": "03:00",
          "t1_bis": "16:00",
          "hedge_eur": 300,
          "hedge_auf_usd": 2000
        }'::jsonb,
        true)
    else f end
    order by ord)
  from jsonb_array_elements(r.firmen) with ordinality as x(f, ord)
),
updated_at = now()
where r.id = 1
  and exists (select 1 from jsonb_array_elements(r.firmen) f where f->>'name' = 'Lucid Trading');

-- Liquidation/Daily Loss für Radar und Hedge (liq_regeln): Lucid 50k Funded und Winning Days = DLL 1.200 $ ab Tagesstart (wie id 17/18 für 150k mit 2.700).
-- id ist eine Identity-Spalte (GENERATED ALWAYS) → nicht mitgeben (Master 16.11.2026: erster Lauf brach mit 428C9 ab)
insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, maxdd_art, maxdd_lock_ueber_groesse_usd, notiz, quelle)
select 'Lucid Trading', t.kontotyp, 50000, 'tagesstart', 1200, 'eod_trailing', 100,
       'LF1 16.11.2026: Lucid Flex 50k ' || t.text || ' — Daily Loss 1.200 $ ab Tagesstart (Tagespause, Konto lebt); Blow nur am Max Loss 2.000 EOD, Lock Größe + 100 (wie id 12).',
       'Finn 16.11.2026 (über den Master, LF1)'
from (values ('funded', 'Funded'), ('winning_days', 'Winning Days')) as t(kontotyp, text)
where not exists (select 1 from public.liq_regeln l where l.firma = 'Lucid Trading' and l.kontotyp = t.kontotyp and l.groesse = 50000);
