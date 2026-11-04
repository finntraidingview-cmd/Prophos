-- FUNDED-CFD-PLANER: PARAMETER IN DER DB (E1b, Finn 05.11.2026 ~03:55 Dubai: „Nimm dir Winning Days als Beispiel: Da kann ich die Uhrzeit ändern, das
-- Verhältnis ändern, die Lots ändern, alles … So soll es bei den anderen Planern auch sein."). Werte, die die Pläne beeinflussen und bis .2035 nur im Code
-- standen (app.py FCP_*), sind jetzt unter Admin → Funded Planer → CFD → Einstellungen → Bearbeiten änderbar. Sie liegen in einer neuen Spalte
-- funded_cfd_plan_regeln.parameter (jsonb). LEER = jeder Schlüssel fehlt = der bisherige Code-Wert gilt (fcp_param) — das Einspielen ändert an den Plänen nichts.
--
-- Schlüssel (alle optional, Grenzen prüft POST /admin/funded-cfd-plan/regel):
--   tp_min_usd               Mindest-TP in $ (Rest bis zum Ziel kleiner → TP so groß)            Code 250       erlaubt 1–5.000
--   consistency_start_usd    TP am Zyklus-Beginn bei Consistency 50 % (wenn die Größe keinen hat) Code 750      erlaubt 1–20.000
--   tp_deckel_plus_standard  TP höchstens Ziel + so viel $ (wenn die Firma keinen eigenen Deckel hat) Code 1.000 erlaubt 0–50.000
--   refund_tp_min_usd        Mindest-TP des Refund-Trades in $                                    Code 25        erlaubt 1–1.000
--   refund_lots_verhaeltnis  Refund-Lots = Normal-Lots × (Refund-TP ÷ Normal-Ziel) × dieser Faktor  Code 2         erlaubt 0,1–10
--   refund_lots_rueckfall    Refund-Lots-Faktor, wenn kein Normal-Ziel rechenbar ist                Code 0,1       erlaubt 0,01–1
--   richtung_laufend         Richtungsschutz: laufender Trade derselben ID × Firma gibt die Richtung vor  Code false
--
-- Ohne neue Spalte, im bestehenden jsonb (kein SQL nötig, nur zur Doku):
--   zeiten.fenster = {"von": "HH:MM", "bis": "HH:MM"}  eigenes Startfenster (Zone wie der Challenge-Planer, Dubai); fehlt → Fenster des Challenge-Planers
--   firmen[].erster_payout = false | {ziel, hedge_eur_je_dd[, lots_faktor]}  Refund-Trade an/aus je Firma
--   firmen[].ohne_namen = ["flex", …]  Konten mit diesem Wort im Namen werden nicht geplant
--   firmen[].tp_modus = "consistency50" | "ziel"  ("ziel" = aufs Ziel, auch wo der Code consistency50 vorgibt, z. B. The5%ers)
--
-- Idempotent. Bis die Datei eingespielt ist, liest der Planer ohne die Spalte (Code-Werte); Änderungen an parameter meldet der Server mit
-- „Spalte parameter fehlt noch".
alter table public.funded_cfd_plan_regeln add column if not exists parameter jsonb not null default '{}'::jsonb;

comment on column public.funded_cfd_plan_regeln.parameter is
  'E1b 05.11.2026: Planer-Parameter (tp_min_usd, consistency_start_usd, tp_deckel_plus_standard, refund_tp_min_usd, refund_lots_verhaeltnis, refund_lots_rueckfall, richtung_laufend). Fehlender Schlüssel = Code-Wert (app.py FCP_PARAM_STANDARD).';

-- Prüfen: select parameter from public.funded_cfd_plan_regeln where id = 1;   -- erwartet {}
