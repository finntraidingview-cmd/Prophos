-- MG3 (23.11.2026, Finn ~04:47: „Pass es an und plane alle Trades bei <Gruppe> neu.“) — NUR DATEI, vom Master einzuspielen,
-- und erst NACH dem Push von MG3 (Railway mit Lots-Deckel live). Sonst plant der Nachplan-Takt der Gruppe wieder ohne Deckel.
--
-- Was die Datei tut (eine Transaktion):
--   0) Ziel: die heutigen Pläne (planned_for 2026-11-23) der Verwalter-Gruppe mit eigenem Planer (auto_plan_gruppe, Mitglieder aus
--      id_gruppe_mitglied), status planned, started_at null, nie an Orbit gesendet, NUR CFD (route mt5v2/mt5: nur dort wirkt der
--      Lots-Deckel; Futures/Orbit-Pläne entstünden mit derselben Logik nur gleich neu) und NUR Planer-Pläne (Auto-Planer bzw.
--      Funded-CFD-Planer, ohne Hand-Werte), keine Folge-Teile einer Tages-Kette (kette.nr > 1). Geclaimte Pläne (start_um_gestartet_at)
--      nur, wenn DIESER Claim belegt in der Vorprüfung endete („… nichts gesendet“, start_fehler.at nach dem Claim).
--      Laufende/erledigte/review nie. Stand der Lesung 23.11. ~05:30 Dubai: 48 Pläne (Blue Guardian 18, Tradeify CFD 11, The5%ers 8,
--      FundedNext 8, FTMO 2, FundingPips 1), alle bestätigt (auto_bestaetigt_at) — die neuen Pläne brauchen ihre Bestätigung wie jeder neue Plan.
--   1) Sicherung der Zeilen in mg3_gruppe_plaene_20261123 (bricht ab, falls die Tabelle schon existiert = Datei lief schon), RLS an.
--   2) Lernwerte „Marge je Lot“ je Konto in user_settings (key marge_je_lot) sichern (je Konto der jüngste) — der Planer (mg3_marge_laden)
--      liest sie zusätzlich zu den trade_plans und sichert neue Werte seit MG3 auch selbst.
--   3) Löschen (dieselben Bedingungen noch einmal im DELETE gegen ein Rennen mit dem PC-Tab). polar_lauf hängt per ON DELETE CASCADE.
--   Danach plant der Nachplan-Takt der Gruppe (ap_gruppen_nachplan_tick, alle Konten ohne Plan im Fenster) bzw. der Funded-CFD-Planer neu,
--   jetzt mit dem Lots-Deckel (Blue Guardian 100k bei 100.000 $ frei: höchstens 3,4 Lots statt 4,0–5,3).

begin;

create temp table mg3_ziel on commit drop as
select p.id
from trade_plans p
where p.user_id in (select m.user_id from id_gruppe_mitglied m
                    where m.gruppe_id in (select a.gruppe_id from auto_plan_gruppe a where a.gruppe_id = '90c616f3-3ec1-49cb-b3ba-8a267d0a43df'))
  and p.planned_for = '2026-11-23'
  and p.status = 'planned'
  and p.started_at is null
  and p.orbit_gesendet_at is null
  and p.route in ('mt5v2', 'mt5')
  and (p.auto_plan is true or p.notes like 'Funded-CFD-Planer%')
  and p.hand_werte_at is null
  and coalesce((p.mt5_baseline->'kette'->>'nr')::int, 1) = 1
  and (p.start_um_gestartet_at is null
       or (p.mt5_baseline->'start_fehler'->>'msg' ilike '%Vorprüfung: nötig%nichts gesendet%'
           and (p.mt5_baseline->'start_fehler'->>'at')::timestamptz >= p.start_um_gestartet_at));

-- 1) Sicherung (Kopie von trade_plans-Zeilen → nie über die API lesbar)
create table mg3_gruppe_plaene_20261123 as
select p.*, now() as gesichert_at from trade_plans p where p.id in (select id from mg3_ziel);
alter table public.mg3_gruppe_plaene_20261123 enable row level security;

-- 2) Lernwerte je Konto sichern (Marge je Lot = „Vorprüfung: nötig X“ ÷ Plan-Lots, je Konto der jüngste), Einträge anderer Konten bleiben
insert into user_settings (user_id, key, value)
select l.user_id, 'marge_je_lot',
       jsonb_object_agg(l.master_account_id::text, jsonb_build_object('mpl', l.mpl, 'firma', l.master_firm, 'at', l.fehler_at, 'quelle', 'MG3 Vorprüfung'))
from (select distinct on (s.master_account_id)
             s.user_id, s.master_account_id, s.master_firm, s.mt5_baseline->'start_fehler'->>'at' as fehler_at,
             round(regexp_replace(substring(s.mt5_baseline->'start_fehler'->>'msg' from 'Vorprüfung: nötig ([0-9][0-9   .]*?), frei'),
                                  '[   ]', '', 'g')::numeric / nullif(s.master_contracts, 0), 2) as mpl
      from mg3_gruppe_plaene_20261123 s
      where s.mt5_baseline->'start_fehler'->>'msg' ilike '%Vorprüfung: nötig%'
      order by s.master_account_id, s.mt5_baseline->'start_fehler'->>'at' desc) l
where l.mpl > 0
group by l.user_id
on conflict (user_id, key) do update set value = user_settings.value || excluded.value, updated_at = now();

-- 3) Löschen — gleiche Bedingungen wie oben, falls der PC-Tab seit Schritt 0 etwas geclaimt/gestartet hat
delete from trade_plans p
where p.id in (select id from mg3_ziel)
  and p.status = 'planned'
  and p.started_at is null
  and p.orbit_gesendet_at is null
  and (p.start_um_gestartet_at is null
       or (p.mt5_baseline->'start_fehler'->>'msg' ilike '%Vorprüfung: nötig%nichts gesendet%'
           and (p.mt5_baseline->'start_fehler'->>'at')::timestamptz >= p.start_um_gestartet_at));

-- Kontrolle (vor dem commit ansehen): gesichert = gelöscht (noch_da 0), Lernwerte da
select (select count(*) from mg3_gruppe_plaene_20261123) as gesichert,
       (select count(*) from trade_plans where id in (select id from mg3_ziel)) as noch_da,
       (select count(*) from user_settings where key = 'marge_je_lot') as lern_zeilen;

commit;

-- Rückweg (nur falls nötig, VOR dem Neuplanen): die Sicherung hat alle Spalten von trade_plans + gesichert_at am Ende —
--   insert into trade_plans (<Spaltenliste von trade_plans>) select <dieselbe Spaltenliste> from mg3_gruppe_plaene_20261123 on conflict (id) do nothing;
