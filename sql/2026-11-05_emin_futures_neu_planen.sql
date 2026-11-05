-- EMINS FUTURES NEU PLANEN (NP2, Finn 05.11.2026 ~17:30 Dubai über den Master: „Wenn also alles perfekt steht, dann lassen wir sie einfach
-- neu planen"). Erst einspielen, wenn TM1 (Tradeify als orbit_prio2 wählbar) und JU1 (Justage) live sind und der Master firmen_modell der
-- Gruppe gesetzt hat — sonst plant der Planer mit dem alten Stand. NICHT von Slave 5 eingespielt.
--
-- Befund (Slave 5, nur lesend, 05.11.2026 17:30 Dubai, Code .2083):
--   b185a26e  Hand-Plan (auto_plan false), route tvplus (Duplikum), FundedNext Futures 50k …26243, ohne Startzeit, planned_for 05.11.
--             Seit .2083 startet tvplus nie mehr. Der Planer räumt Hand-Pläne NIE selbst weg (ap_plan_verfallen/_vorschlag: nur auto_plan) und
--             „hat schon einen geplanten/laufenden Plan" (ap_planen, Futures-Pfad) gilt für JEDEN planned-Plan des Kontos, egal welcher Tag —
--             das Konto bliebe ohne diese Datei dauerhaft aus dem Planer.
--   82a25d69 (…33807) · d393a628 / 80db9cfe / 6192f964 (Lucid …30003/4/5) · 86c6bb09 (…16923): Orbit-Prio-2-Vorschläge des Gruppen-
--             Nachtlaufs, alle unbestätigt, ohne Hedge-Freigabe, nie geclaimt (4 Startzeiten vorbei, 86c6bb09 18:08 Dubai).
--             Der volle Lauf („Jetzt planen" der Gruppe / Nachtlauf) ersetzt solche Vorschläge selbst (ap_planen _vorschlag → vor dem Anlegen
--             gelöscht). Der 5-min-NACHPLAN-Takt ersetzt dagegen nichts (nur_konten: jeder Vorschlag zählt als Plan) — für ein Neuplanen über
--             den Takt müssen sie weg. Darum hier mit, dieselben Bedingungen wie der Knopf „Löschen" (ap_eingriff_filter loeschen) plus
--             unbestätigt + ohne Hedge-Freigabe: ein inzwischen bestätigter oder freigegebener Plan bleibt stehen.
--
-- Warum löschen statt Status/Markierung: trade_plans.status kennt nur planned/open/review/completed. completed würde als „heute schon
-- gehandelt" zählen (_ap_plan_am_tag → Konto heute gesperrt) und eine P&L-Zeile anlegen, review sperrt mit „letzter Trade noch nicht
-- erledigt". Der übliche Weg für nie gestartete Vorschläge ist delete (Knopf „Löschen", Nachtlauf-Ersetzen, Leichen-Wegräumen 14.10.).
-- Keine P&L, kein Hedge, keine Order hängt an diesen Zeilen (alle started_at/orbit_gesendet_at/start_um_gestartet_at null). Einziger
-- Fremdschlüssel auf trade_plans ist polar_lauf (cascade) — 0 Zeilen für diese Pläne. b185a26e hat 4 order_signale mit status fehler
-- (Hand-Starts 04.11. 16:50–16:53 Dubai, nie gefüllt); plan_id ist dort Text ohne Fremdschlüssel → die Fehler-Zeilen bleiben für die
-- Fehler-Muster-Auswertung stehen.
--
-- HT bleibt unberührt: jede Zeile per Plan-ID UND user_id der beiden Gruppen-IDs UND Konto-ID. Wiederholbar: zweiter Lauf findet nichts mehr.
-- Danach: Nachplan-Takt (alle 5 min, bis 19:45 Dubai) plant die freien Konten von selbst; …26243 steht im letzten Gruppen-Lauf mit
-- „keine Regel für diese Firma" (Regel-Grund) — der zählt erst wieder, wenn die Gruppen-Regel nach dem Lauf geändert wurde (firmen_modell-
-- Umstellung des Masters → ap_gruppe_regel_geaendert). Sonst plant es spätestens der Nachtlauf 01:30 Dubai.

begin;

-- (1) Amirs alter Duplikum-Hand-Plan …26243
delete from public.trade_plans
 where id = 'b185a26e-4c48-4bc8-85af-04cd9febfb4e'
   and user_id = 'd55671f9-d587-4ef1-95f3-95622008fe98'
   and master_account_id = '8e8289ed-233a-4aa3-bcb7-e12307a6c420'
   and status = 'planned' and route = 'tvplus' and auto_plan is not true
   and started_at is null and start_um_gestartet_at is null and orbit_gesendet_at is null;

-- (2) die fünf unbestätigten Orbit-Prio-2-Vorschläge (Emin 4, Amir 1)
delete from public.trade_plans
 where (id, user_id, master_account_id) in (
         ('82a25d69-cce5-4c3b-89e9-adcc7c31c457'::uuid, '6cceb3f3-dc78-48ee-8668-26081da3e70f'::uuid, '949cac4b-6859-4a75-8596-80297cc00062'::uuid),
         ('d393a628-2170-4e00-a7c1-ca3e81323d88'::uuid, '6cceb3f3-dc78-48ee-8668-26081da3e70f'::uuid, '5de61735-50ef-4815-9051-fc74f37b6166'::uuid),
         ('80db9cfe-53a1-4aec-a666-63d81470ce6d'::uuid, '6cceb3f3-dc78-48ee-8668-26081da3e70f'::uuid, '3c0ddd9c-300e-4f88-b761-2a0f27de9ae9'::uuid),
         ('6192f964-72d7-43ba-82cb-2c652d4f15ef'::uuid, '6cceb3f3-dc78-48ee-8668-26081da3e70f'::uuid, 'd328abae-ea67-4fec-bdec-042f42a4353e'::uuid),
         ('86c6bb09-8b46-4bca-9e4e-50c2c1425342'::uuid, 'd55671f9-d587-4ef1-95f3-95622008fe98'::uuid, '74fb037e-f7b3-4620-89fd-2cd67c50aec1'::uuid))
   and status = 'planned' and auto_plan = true
   and auto_bestaetigt_at is null and hedge_freigabe_at is null and hand_werte_at is null
   and started_at is null and start_um_gestartet_at is null and orbit_gesendet_at is null;

commit;

-- VOR dem Einspielen (Fremd-Review): hat inzwischen ein voller Lauf („Jetzt planen"/Nachtlauf) die fünf Vorschläge durch NEUE IDs ersetzt,
-- löscht Teil 2 nichts, und die neuen unbestätigten Vorschläge halten den Nachplan-Takt weiter — dann diese Liste ansehen statt blind einspielen:
-- select left(id::text,8), master_account_id, status, route, auto_plan, auto_bestaetigt_at, start_um at time zone 'Asia/Dubai' from public.trade_plans
--  where status in ('planned','open') and master_account_id in ('949cac4b-6859-4a75-8596-80297cc00062','5de61735-50ef-4815-9051-fc74f37b6166',
--    '3c0ddd9c-300e-4f88-b761-2a0f27de9ae9','d328abae-ea67-4fec-bdec-042f42a4353e','74fb037e-f7b3-4620-89fd-2cd67c50aec1','8e8289ed-233a-4aa3-bcb7-e12307a6c420');
-- Kontrolle (nach dem Einspielen): 0 Zeilen erwartet; bleibt eine stehen, war sie inzwischen bestätigt/freigegeben/gestartet → nicht anfassen.
-- select left(id::text,8), status, route, auto_bestaetigt_at, hedge_freigabe_at, start_um_gestartet_at from public.trade_plans
--  where id in ('b185a26e-4c48-4bc8-85af-04cd9febfb4e','82a25d69-cce5-4c3b-89e9-adcc7c31c457','d393a628-2170-4e00-a7c1-ca3e81323d88',
--               '80db9cfe-53a1-4aec-a666-63d81470ce6d','6192f964-72d7-43ba-82cb-2c652d4f15ef','86c6bb09-8b46-4bca-9e4e-50c2c1425342');
-- Gegenprobe Duplikum weg: kein planned/open-Plan mit route tvplus/dup in der Gruppe
-- select count(*) from public.trade_plans where status in ('planned','open') and route in ('tvplus','dup')
--  and user_id in ('6cceb3f3-dc78-48ee-8668-26081da3e70f','d55671f9-d587-4ef1-95f3-95622008fe98');
