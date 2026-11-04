-- WD-FIRMEN-REGELN (E4, Finn 05.11.2026 ~05:30 Dubai über den Master: „Bei Winning Days die Consistency Rule hinzufügen, z. B. bei Apex, und das Minimum-Payout bzw.
-- den Mindest-Net-Profit, den man in jedem Zyklus machen muss — bei Tradeify und Topstep nach dem ersten Payout, bei Lucid genauso.").
-- Neue Spalte wd_farmer_regeln.firmen_regeln (jsonb): je WD-Firma (Schlüssel wie TP_VP_FIRMEN: apex, apex100, tradeify, lucid, fnfutures, topstep, sonst)
--   { "konsistenz": {"an": bool, "pct": 1–100}, "min_netto": {"an": bool, "usd": ≥ 0, "ab_zyklus": 1–20} }
-- Eigene Spalte statt vorplan.regeln: wdHedgeSpeichern baut vorplan beim Speichern neu und ließe fremde Schlüssel fallen.
-- NULL bzw. fehlende Firma/Feld = Standardwerte aus dem Code (app.py WD_FIRMEN_REGELN_STD = prophos.html E4_WD_FIRMEN_STD) — darum KEINE Startwerte hier:
-- so bleibt das Verhalten nach dem Einspielen gleich (Tradeify Zyklus im Plus 1 $ ab Zyklus 2 wie bisher). Schreiben wie die übrigen Spalten nur Admins (RLS der Tabelle).
-- Gelesen von: app.py _wd_firmen_regeln_lesen (Spalte fehlt → Standard) und prophos.html Funded Planer → Winning Days → Einstellungen → Firmen (e4Regel/e4Speichern).
-- REIHENFOLGE: egal (Code liest mit Rückfall); zum Speichern im Frontend muss die Spalte da sein. Wiederholbar. Rückbau: alter table … drop column firmen_regeln.
-- NICHT vom Slave eingespielt.

alter table public.wd_farmer_regeln add column if not exists firmen_regeln jsonb;

comment on column public.wd_farmer_regeln.firmen_regeln is
  'E4 05.11.2026: Payout-Regeln je WD-Firma {konsistenz {an, pct}, min_netto {an, usd, ab_zyklus}} — NULL = Standard aus dem Code; wirkt heute nur tradeify.min_netto (Zyklus im Plus)';
