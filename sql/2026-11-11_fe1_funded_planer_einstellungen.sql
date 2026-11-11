-- FE1 (11.11.2026): Funded-Planer-Einstellungen nach Finns Durchsicht (20:45 Dubai). NUR Einstellungen, kein Code. Idempotent: setzt nur die genannten Felder,
-- alles andere bleibt. Einspielen nur durch den Master (execute_sql, DML). Ist-Stand vor dem Einspielen (gelesen 11.11.2026):
--   funded_plan_regeln id 1 (Futures):    aktiv true, auto_bestaetigen true, zeiten {vorlauf_min 15, max_je_id_tag 3, abstand_id_min 90, firma_abstand_min 15}, konst {}
--   funded_cfd_plan_regeln id 1 (CFD):    aktiv true, auto_bestaetigen true, zeiten {vorlauf_min 15, abstand_id_min 10, firma_abstand_min 15}, parameter {}
-- Zeiten/Abstände/Grenzen gelten für alle Unternehmen gemeinsam (UNT4: nur Firmen-Felder sind je Unternehmen) — Zeile id 1 reicht.

-- 1) Aktiv + Auto-Bestätigen (Finn: „Funded CFD Planer aktiv + Auto-Bestätigen an, Funded Futures Planer aktiv + Auto-Bestätigen an“):
--    steht schon so — kein Update nötig. Kontrolle:
--    select id, aktiv, auto_bestaetigen from public.funded_plan_regeln where id = 1;      -- true, true
--    select id, aktiv, auto_bestaetigen from public.funded_cfd_plan_regeln where id = 1;  -- true, true

-- 2) Abstand gleiche ID im Funded Futures Planer 90 → 5 min (Finn: „Topstep Long, direkt danach Tradeify Short — gleiche ID, 5 Minuten“).
--    Unberührt: firma_abstand_min (15), Gegenrichtungs-Riegel je ID × Firma (DB-Trigger), Zwei-Orbit-Regel (puls_heim_regel.big_max_je_id 2, je Firma 1,
--    Zweitstart nur bei > 2.500 $ vor TP und Liq, 18:28–18:35 Dubai kein weiterer Start). Erlaubt laut POST /admin/funded-plan/regeln: 1–600.
update public.funded_plan_regeln
   set zeiten = jsonb_set(coalesce(zeiten, '{}'::jsonb), '{abstand_id_min}', '5'::jsonb), updated_at = now()
 where id = 1 and coalesce((zeiten->>'abstand_id_min')::numeric, -1) <> 5;
-- Funded CFD Planer steht auf 10 min (Finn nannte nur den Futures-Fall). Falls dort auch 5 gewünscht, diese Zeile einkommentieren:
-- update public.funded_cfd_plan_regeln set zeiten = jsonb_set(coalesce(zeiten, '{}'::jsonb), '{abstand_id_min}', '5'::jsonb), updated_at = now()
--  where id = 1 and coalesce((zeiten->>'abstand_id_min')::numeric, -1) <> 5;

-- 3) Tagesdeckel je ID AUS (Finn: „wir haben ja die Regel, dass nie mehr als zwei Orbit-Trades gleichzeitig laufen“): KEIN SQL.
--    Futures: zeiten.max_je_id_tag kennt kein „aus“ (app.py fdp_planen: int(… or 2) → 0 wird 2; Grenzen 1–6) — braucht Code (S6, siehe Meldung).
--    CFD: der Planer hat keinen Tagesdeckel je ID (nur je Konto und Tag) — nichts zu tun.

-- 4) Break-even-Toleranz im Funded Futures Planer 500 → 300 $ (Finn: „Break-even-Toleranz 300“): konst.breakeven_tol (Grenzen 0–5.000 $, fdp_konst).
--    Wirkt im Standard-Weg (fdp_tp: mehr als 300 $ unter dem Zyklus-Start → Trade zurück auf Break-even). Pump (pump2) und FTMO-Rest-Modus rechnen ohne Break-even.
update public.funded_plan_regeln
   set konst = coalesce(konst, '{}'::jsonb) || '{"breakeven_tol": 300}'::jsonb, updated_at = now()
 where id = 1 and coalesce((konst->>'breakeven_tol')::numeric, -1) <> 300;

-- Kontrolle nach dem Einspielen:
-- select zeiten->>'abstand_id_min' as abstand_id, zeiten->>'max_je_id_tag' as deckel, konst->>'breakeven_tol' as be_tol from public.funded_plan_regeln where id = 1;
--   → 5 · 3 · 300
-- Rückbau: zeiten.abstand_id_min = 90, konst - 'breakeven_tol' (Code-Standard 500).
