-- WD2 (16.11.2026, Finn: „ja, und falls welche für heute auch noch geplant sind, auch direkt anpassen, dass die richtig gemacht werden“).
-- Die Tradeify-WD-TP-Spanne im Farmer stand vom 12.11. ~20:12 bis 16.11. 16:16 Dubai auf 225–244 $ statt 266–280 $ (Befund WD1).
-- Seit 16:16 gilt wieder 266–280 — was davor gewürfelt wurde, trägt aber noch die kleine Spanne:
--   (A) noch NICHT gestartete Tradeify-WD-Pläne (heute/morgen), deren TP noch genau dem Würfel entspricht,
--   (B) wd_tagesplan-Einträge für heute/morgen ohne Plan, die noch mit 225–244 gewürfelt sind.
-- Neuer TP je Konto zufällig 266–280 $ (ganze Dollar, wie tpVorplanZeile). Kontrakte, Zeiten, Richtung, SL (wd_sl) bleiben.
-- Hedge wie der Farmer selbst (prophos.html wdFarmHedgeKern → tpMultiplierAusRisiko): Multiplikator = Staffel-€ × Master-Punktwert /
-- (Fusion-Punktwert × Risiko), hedge_eur = Lots × Fusion-Punktwert × TP-Punkte. Zwei Fälle (Prüfer S2, Stopp zu 1f7bcf43):
--   Risiko = TP (Farmer-Regel ohne Handwert, master_risk = master_tp ±0,5): Risiko geht mit → multiplier_neu = multiplier_alt × risk_alt / TP_neu,
--     master_risk = TP_neu, hedge_eur ∝ Lots × TP (Fusion-Verlust am TP bleibt beim Staffel-Betrag).
--   Eigenes Risiko (SL-Vorgabe / max_risiko_trade, z. B. d41d37c3 risk 229 bei TP 225): master_risk, multiplier, hedge_faktor bleiben
--     (Lots gleich), nur hedge_eur = hedge_eur_alt × TP_neu / TP_alt. Alte Werte als Notiz in
-- mt5_baseline.tp_neu_wd2. Gestartete/laufende/geclaimte Pläne werden NIE angefasst. Idempotent: alles läuft nur über die alte
-- Spanne (gewürfelter TP 225–244, ohne Würfel tpVon 225 / tpBis 244); danach steht 266–280 und ein zweiter Lauf ändert nichts.
-- Auswahl über den GEWÜRFELTEN TP, nicht über tpVon: die PC-Tabs schreiben tpVon/tpBis schon aus der neuen Einstellung (266/280),
-- der Würfel und der Plan behalten aber 225 (gesehen 16:21 Dubai an Plan d41d37c3).

-- ── VORSCHAU (vor dem Einspielen ansehen) ──────────────────────────────────────────────────────────────────────────────────────
-- select 'Plan' art, w.tag, p.master_name konto, p.master_tp tp_alt, left(p.id::text,8) plan_id, p.master_contracts kt, p.multiplier, p.master_risk, p.hedge_eur
-- from trade_plans p
-- join wd_tagesplan w on w.user_id = p.user_id and w.tag between (now() at time zone 'Asia/Dubai')::date and (now() at time zone 'Asia/Dubai')::date + 1
-- join lateral jsonb_array_elements(w.konten) k on k->>'plan_id' = p.id::text
-- where p.winning_day and p.master_firm = 'Tradeify' and p.notes = 'Winning-Day-Farmer' and p.status = 'planned'
--   and p.started_at is null and p.start_um_gestartet_at is null and p.orbit_gesendet_at is null and p.start_claim_art is null
--   and p.master_tp between 225 and 244 and (k->'wuerfel'->>'tp')::numeric between 225 and 244
--   and k->'wuerfel'->>'quelle' = 'wuerfel' and abs((k->'wuerfel'->>'tp')::numeric - p.master_tp) <= 0.5
-- union all
-- select 'Tageszeile', w.tag, k->>'name', (k->'wuerfel'->>'tp')::numeric, null, (k->'wuerfel'->>'kt')::numeric, null, null, null
-- from wd_tagesplan w, jsonb_array_elements(w.konten) k
-- where w.tag between (now() at time zone 'Asia/Dubai')::date and (now() at time zone 'Asia/Dubai')::date + 1
--   and k->>'firm' = 'Tradeify' and coalesce(k->>'plan_id', '') = '' and (case when jsonb_typeof(k->'wuerfel') = 'object' then (k->'wuerfel'->>'tp')::numeric between 225 and 244 else k->>'tpVon' = '225' and k->>'tpBis' = '244' end)
-- order by 1, 2, 3;

begin;

-- (A) Pläne + ihr Tageszeilen-Eintrag in EINER Anweisung (derselbe neue TP an beiden Stellen)
with kand as (
  select p.id, p.user_id, w.tag, p.master_tp tp_alt, p.master_contracts kt,
         coalesce(nullif(p.master_risk, 0), p.master_tp) risk_alt, p.multiplier mult_alt, p.hedge_eur eur_alt,
         (266 + floor(random() * 15))::numeric tp_neu
  from trade_plans p
  join wd_tagesplan w on w.user_id = p.user_id
   and w.tag between (now() at time zone 'Asia/Dubai')::date and (now() at time zone 'Asia/Dubai')::date + 1
  join lateral jsonb_array_elements(w.konten) k on k->>'plan_id' = p.id::text
  where p.winning_day and p.master_firm = 'Tradeify' and p.notes = 'Winning-Day-Farmer' and p.status = 'planned'
    and p.started_at is null and p.start_um_gestartet_at is null and p.orbit_gesendet_at is null and p.start_claim_art is null
    and p.master_tp between 225 and 244 and (k->'wuerfel'->>'tp')::numeric between 225 and 244
    and k->'wuerfel'->>'quelle' = 'wuerfel' and abs((k->'wuerfel'->>'tp')::numeric - p.master_tp) <= 0.5
  for update of p
),
rech as (
  select kand.*,
         abs(risk_alt - tp_alt) <= 0.5 as risk_ist_tp,
         case when mult_alt > 0 and abs(risk_alt - tp_alt) <= 0.5 then round(mult_alt * risk_alt / tp_neu, 4) end mult_neu
  from kand
),
upd as (
  update trade_plans p set
    master_tp    = r.tp_neu,
    master_risk  = case when r.risk_ist_tp then r.tp_neu else p.master_risk end,   -- eigenes Risiko (SL-Vorgabe/max_risiko_trade) bleibt
    multiplier   = coalesce(r.mult_neu, p.multiplier),
    hedge_faktor = case when r.mult_neu is not null then round(r.mult_neu, 3) else p.hedge_faktor end,
    hedge_eur    = case when r.mult_neu is not null and r.eur_alt > 0 and round(r.kt * r.mult_alt, 2) > 0
                        then round(r.eur_alt * round(r.kt * r.mult_neu, 2) * r.tp_neu / (round(r.kt * r.mult_alt, 2) * r.tp_alt), 2)
                        when not r.risk_ist_tp and r.eur_alt > 0
                        then round(r.eur_alt * r.tp_neu / r.tp_alt, 2)   -- Lots gleich, nur der Fusion-Betrag am TP wächst mit
                        else p.hedge_eur end,
    mt5_baseline = coalesce(p.mt5_baseline, '{}'::jsonb) || jsonb_build_object('tp_neu_wd2', jsonb_build_object(
                     'at', now(), 'tp_alt', r.tp_alt, 'tp_neu', r.tp_neu, 'risk_alt', r.risk_alt, 'risk_ist_tp', r.risk_ist_tp, 'mult_alt', r.mult_alt,
                     'hedge_eur_alt', r.eur_alt, 'grund', 'WD2 16.11.2026: Tradeify-TP-Spanne 225–244 → 266–280 (Finn)'))
  from rech r
  where p.id = r.id and p.status = 'planned' and p.started_at is null and p.start_um_gestartet_at is null and p.orbit_gesendet_at is null
  returning p.id, p.user_id, r.tag, r.tp_neu
)
update wd_tagesplan w set konten = (
  select jsonb_agg(case when u.id is not null
                        then e.k || jsonb_build_object('tpVon', 266, 'tpBis', 280,
                               'wuerfel', coalesce(e.k->'wuerfel', '{}'::jsonb) || jsonb_build_object('tp', u.tp_neu, 'wd2_tp_alt', e.k->'wuerfel'->'tp'))
                             || case when e.k ? 'tp' then jsonb_build_object('tp', u.tp_neu) else '{}'::jsonb end
                        else e.k end order by e.i)
  from jsonb_array_elements(w.konten) with ordinality e(k, i)
  left join upd u on u.id::text = e.k->>'plan_id' and u.user_id = w.user_id and u.tag = w.tag)
where exists (select 1 from upd u where u.user_id = w.user_id and u.tag = w.tag);

-- (B) Tageszeilen ohne Plan (heute/morgen), noch mit der alten Spanne: Spanne + gewürfelter TP neu (Kontrakte bleiben)
update wd_tagesplan w set konten = (
  select jsonb_agg(case when e.k->>'firm' = 'Tradeify' and coalesce(e.k->>'plan_id', '') = '' and (case when jsonb_typeof(e.k->'wuerfel') = 'object' then (e.k->'wuerfel'->>'tp')::numeric between 225 and 244 else e.k->>'tpVon' = '225' and e.k->>'tpBis' = '244' end)
                        then e.k || jsonb_build_object('tpVon', 266, 'tpBis', 280)
                             || case when jsonb_typeof(e.k->'wuerfel') = 'object'
                                     then jsonb_build_object('wuerfel', (e.k->'wuerfel') || jsonb_build_object(
                                            'tp', (266 + floor(random() * 15))::int, 'wd2_tp_alt', e.k->'wuerfel'->'tp'))
                                     else '{}'::jsonb end
                        else e.k end order by e.i)
  from jsonb_array_elements(w.konten) with ordinality e(k, i))
where w.tag between (now() at time zone 'Asia/Dubai')::date and (now() at time zone 'Asia/Dubai')::date + 1
  and exists (select 1 from jsonb_array_elements(w.konten) k
              where k->>'firm' = 'Tradeify' and coalesce(k->>'plan_id', '') = '' and (case when jsonb_typeof(k->'wuerfel') = 'object' then (k->'wuerfel'->>'tp')::numeric between 225 and 244 else k->>'tpVon' = '225' and k->>'tpBis' = '244' end));

commit;

-- ── NACHKONTROLLE (muss 0 Zeilen liefern; Liste mit neuen Werten) ───────────────────────────────────────────────────────────────
-- select w.tag, k->>'name', k->>'tpVon', k->>'tpBis', k->'wuerfel'->>'tp', k->>'plan_id' from wd_tagesplan w, jsonb_array_elements(w.konten) k
-- where w.tag between (now() at time zone 'Asia/Dubai')::date and (now() at time zone 'Asia/Dubai')::date + 1 and k->>'firm' = 'Tradeify'
--   and ((k->'wuerfel'->>'tp')::numeric between 225 and 244 or k->>'tpVon' = '225');
-- select left(id::text,8), master_name, master_tp, master_risk, multiplier, hedge_faktor, hedge_eur, mt5_baseline->'tp_neu_wd2'
-- from trade_plans where mt5_baseline ? 'tp_neu_wd2' order by updated_at desc;
-- ACHTUNG: PC-Tabs schreiben wd_tagesplan (wdTick 30 s). Steht nach ~1 min wieder 225/244 in einer Zeile, hat ein Tab seinen alten Stand
-- zurückgeschrieben → Datei einfach nochmal einspielen (idempotent) bzw. im Farmer „neu würfeln“.
