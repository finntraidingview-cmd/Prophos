-- FT2 (Finn 11.11.2026 21:05 über den Master): „Wenn die ihr Ziel erreicht haben, ist da genau das Gleiche wieder: Winning Days, genau die gleiche Logik wie
-- immer. Winning Days sollten auch schon auf dem Weg gezählt werden … Wir brauchen 5 Winning Days, je Winning Day 200+. Aber beim Winning-Day-Farm aufpassen,
-- dass wir auch wieder dieses Daily Loss mit haben, was ein Hard Breach ist. Bei Winning Days: TP so 220 bis 240, SL 750 bis 850, wir kaufen 2 bis 3 MNQ, 50 % / 50 %.“
-- Code (Commit FT2): Farmer-Schlüssel „ftmofutures“ (app.py fdp_wd_schluessel / prophos.html tpVorplanFirmaKey), Gewinntag 200 $ (WD_GOOD_DAY_MIN / zielWdMin,
-- zählt schon in der Funded-Phase ab Anlage des Kontos), 5 WD = Futures-Standard (zielKonfig/wd_auto_staende). Hier nur die Einstellungen:
--   1) Farmer: TP 220–240 $ und Kontrakte 2–3 (wdKontrakteFuer: gleichverteilt, fest je Konto × Tag im Würfel) — vorplan.regeln.fu/kt.ftmofutures
--   2) SL 750–850 $ fest je WD-Trade (sl_wuerfel.firmen.ftmofutures, app.py wd_sl_fest): gekappt am Abstand zum Daily Loss − 50 $, unter 100 $ kein Plan
--   3) Daily Loss FTMO Futures 50k = 1.000 $ ab Tagesstart (liq_regeln) — derselbe Wert wie im Funded-Planer (funded_plan_regeln ftmofutures daily_usd 1.000,
--      Eingang 03.11.2026); firm_rules.json hat keinen FTMO-Futures-Eintrag. Damit rechnet der SL-Puffer (hf_wd_master_verlust) ab Tagesstart bis zur Tagesgrenze.
-- Idempotent. Kontrakte gelten auf dem Farmer-Instrument (vorplan.instr, heute MNQ).
-- REIHENFOLGE (Prüfer FT2): ERST Code ausliefern + Bump + alle Tabs neu geladen, DANN diese Datei, dann die Prüf-Abfragen unten. Ein alter Tab, der nach dem
-- Einspielen speichert, würde fu/kt.ftmofutures (wdHedgeSpeichern mit altem TP_VP_FIRMEN) bzw. sl_wuerfel.firmen (alter wdSlwSpeichern) still verwerfen.

-- 1) Farmer-Werte (nur die zwei Schlüssel; die Einstellungs-Seite liest/schreibt fu/kt je Firma aus TP_VP_FIRMEN, ftmofutures ist dort jetzt dabei)
update public.wd_farmer_regeln
   set vorplan = jsonb_set(coalesce(vorplan, '{}'::jsonb), '{regeln}',
                           coalesce(vorplan->'regeln', '{}'::jsonb)
                             || jsonb_build_object('fu', coalesce(vorplan->'regeln'->'fu', '{}'::jsonb) || '{"ftmofutures": [220, 240]}'::jsonb,
                                                   'kt', coalesce(vorplan->'regeln'->'kt', '{}'::jsonb) || '{"ftmofutures": [2, 3]}'::jsonb),
                           true),
       updated_at = now()
 where id = 1;

-- 2) Fester SL je Firma — gilt unabhängig vom Zufalls-SL (app.py _wd_sl_fest_lesen). Ist sl_wuerfel noch leer, wird {an: false, firmen} angelegt
--    (Würfel bleibt AUS — ohne „an“ hieße die Zeile sonst „gemeint = an“ und schaltete den Würfel mit Standard-Stufen ein, Prüfer 2 KANN 10)
update public.wd_farmer_regeln
   set sl_wuerfel = case when sl_wuerfel is not null and jsonb_typeof(sl_wuerfel) = 'object'
                         then sl_wuerfel || jsonb_build_object('firmen', coalesce(sl_wuerfel->'firmen', '{}'::jsonb) || '{"ftmofutures": {"usd": [750, 850]}}'::jsonb)
                         else '{"an": false, "firmen": {"ftmofutures": {"usd": [750, 850]}}}'::jsonb end,
       updated_at = now()
 where id = 1;

-- 3) Daily Loss FTMO Futures 50k (Winning Days) — Max DD wie am Konto (eod_trailing, accounts.max_drawdown)
insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, maxdd_art, notiz, quelle, updated_at)
select 'FTMO Futures', 'winning_days', 50000, 'tagesstart', 1000, 'eod_trailing',
       'FTMO Futures 50k Winning Days: Daily Loss 1.000 $ ab Tagesstart = HARD BREACH (Konto weg). WD-SL (fester SL 750–850 $) wird darauf gekappt, darunter kein Plan.',
       'Finn 11.11.2026 21:05 (FT2) · Wert wie funded_plan_regeln ftmofutures daily_usd (Eingang 03.11.2026)', now()
 where not exists (select 1 from public.liq_regeln where lower(firma) = 'ftmo futures' and kontotyp = 'winning_days' and groesse = 50000);

-- 4) DB-RIEGEL (Prüfer FT2 MUSS 1–5): ein FTMO-Futures-Winning-Day startet NIE ohne Master-SL — egal über welchen Weg er angelegt wurde (Mac/Railway,
--    PC-Tab-Rückfall, alter Tab, PATCH). Angelegt werden darf er (der Tab-Rückfall legt ohne SL an, SL1 würfelt den festen SL ≥ 120 s vor dem Start nach);
--    der Claim/Start (start_um_gestartet_at bzw. orbit_gesendet_at wird gesetzt) wird abgelehnt, solange master_sl leer/0 ist.
--    NICHT beim Übergang planned → open (Prüfer S2, STOPP 11.11.2026): den schreibt der Tab erst NACH dem Fill — eine Exception dort ließe das ganze open-Update
--    (started_at, Ticket, Baseline) scheitern → offene Position ohne Plan-Status, keine Ende-Erkennung, kein Hedge-Abbau. Hand-/Fern-Starts über Orbit V2 setzen
--    keinen Claim; die harte Sperre vor dem Klick macht der PC-Tab (wdSlFestPflicht in tpOrbitStartenKern).
--    Verbrauchs-Claims (start_claim_art 'verbrauch') gehen durch. Firma: master_firm, sonst accounts.firm.
--    Gilt nur, solange sl_wuerfel.firmen.ftmofutures eingerichtet ist (aus = wie bisher). Firma wie app.py fdp_wd_schluessel: „ftmo“ + „futur“.
--    Reihenfolge (Prüfer S2 KANN): erst die billigen Feld-Prüfungen, die Unterabfragen (accounts, wd_farmer_regeln) nur, wenn ein Claim gerade gesetzt wird —
--    der Trigger läuft vor JEDEM trade_plans-UPDATE.
create or replace function public.trade_plans_wd_sl_pflicht() returns trigger language plpgsql as $$
begin
  if (new.winning_day is true or coalesce(new.notes, '') like '%Winning-Day-Farmer%')
     and coalesce(new.master_sl, 0) <= 0                                                    -- auch 0: der Tab sendet bei SL ≤ 0 ohne SL (Prüfer 2 KANN 5)
     and coalesce(new.start_claim_art, '') <> 'verbrauch'                                   -- Verbrauch (verpasst, Archiv, „passt heute nicht“) sendet nichts
     and ((old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
          or (old.orbit_gesendet_at is null and new.orbit_gesendet_at is not null)) then
    if lower(coalesce(nullif(new.master_firm, ''), (select a.firm from public.accounts a where a.id = new.master_account_id), '')) like '%ftmo%futur%'
       and exists (select 1 from public.wd_farmer_regeln w where w.id = 1 and jsonb_typeof(w.sl_wuerfel) = 'object' and (w.sl_wuerfel->'firmen') ? 'ftmofutures') then
      raise exception 'WD-SL-Pflicht: FTMO-Futures-Winning-Day ohne Master-SL startet nicht (Daily Loss = Hard Breach) — SL setzen oder Plan löschen'
        using errcode = 'P0001';
    end if;
  end if;
  return new;
end $$;
drop trigger if exists trade_plans_wd_sl_pflicht on public.trade_plans;
create trigger trade_plans_wd_sl_pflicht before update on public.trade_plans
  for each row execute function public.trade_plans_wd_sl_pflicht();

-- Prüfen:
-- select vorplan->'regeln'->'fu'->'ftmofutures', vorplan->'regeln'->'kt'->'ftmofutures', sl_wuerfel->'firmen' from public.wd_farmer_regeln where id = 1;
-- select * from public.liq_regeln where firma = 'FTMO Futures';
-- select tgname from pg_trigger where tgname = 'trade_plans_wd_sl_pflicht';
