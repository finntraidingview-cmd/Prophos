-- TW3 FIRMEN-WÜRFEL (Finn 12.11.2026 über den Master: „IDs haben Propfirms, Propfirms haben Accounts. Heute wird zu 25 % der einzelne Account an einem Tag
-- übersprungen. Jetzt eine Ebene höher: die Prop-Firma der jeweiligen ID soll zu 20 % an einem Tag gar nicht getradet werden — Risiko verteilen, nicht immer
-- so viele Trades an einem Tag.“) — KORREKTUR Finn 12.11.2026: „Die Zufallskonten bleiben bei 25 %, und die Zufalls-Propfirms bleiben bei 25 %.“ → HT 75 % handelt.
-- Code (Commit TW3, app.py tw_firma_wurf/tw_firma_handelt/tw_pause_grund): fester Wurf je ID × Firma × Dubai-Tag („tw3|<user_id>|<firma_norm>|<tag>“, Firma nach
-- _ap_norm — „FundedNext“ und „FundedNext Futures“ sind getrennt). Trifft er, plant KEIN Planer (Challenge CFD/Futures, Funded CFD/Futures, Winning Days) für
-- diese ID × Firma an diesem Tag einen neuen Trade; danach greift wie bisher der Konto-Wurf (TW1). Bestehende/laufende/von Hand angelegte Pläne bleiben,
-- „heute rein“ (TW2) überstimmt auch den Firmen-Pause-Tag für genau das Konto.
-- Einstellung = eine weitere Zeile in planer_handel_wuerfel: planer 'firma_je_id', pct = % der Tage, an denen eine ID bei einer Firma handelt.
-- Ohne Zeile 100 % (= wie vor TW3); ein Unternehmen erbt den HT-Wert NICHT (eigene Zeile, sonst 100 %). Idempotent.
-- REIHENFOLGE: erst Code + Bump (der alte Code ignoriert die Zeile, tw_werte liest nur bekannte Planer), dann diese Datei.

-- 1) Planer-Liste der Tabelle um 'firma_je_id' erweitern
alter table public.planer_handel_wuerfel drop constraint if exists planer_handel_wuerfel_planer_check;
alter table public.planer_handel_wuerfel add constraint planer_handel_wuerfel_planer_check
  check (planer in ('challenge_cfd', 'challenge_futures', 'funded_cfd', 'funded_futures', 'winning_days', 'firma_je_id'));

-- 2) Hermann Technologies (Standard): Firma je ID handelt an 75 % der Tage (= 25 % Pause, wie der Konto-Würfel)
insert into public.planer_handel_wuerfel (planer, gruppe, pct) values ('firma_je_id', '', 75)
on conflict (planer, gruppe) do nothing;   -- erneut eingespielt: in der Karte geänderte Werte bleiben stehen

-- Prüfen:  select * from public.planer_handel_wuerfel order by planer, gruppe;
-- Zurück auf das Verhalten vor TW3:  delete from public.planer_handel_wuerfel where planer = 'firma_je_id';
