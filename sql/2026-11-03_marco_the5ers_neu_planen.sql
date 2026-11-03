-- MARCO THE5%ERS 100k NEU PLANEN (Finn 03.11.2026 17:15 Dubai über den Eingang: „einfach neu planen").
-- Befund (Slave 5, nur lesend):
--   abc02a19 (Echo mt5, SELL 24 Lot) stand seit 02.11. 14:31 Dubai 19× hinter dem Richtungsschutz (UNKLAR-Start auf dem 200k derselben ID),
--   wurde 01:51 Dubai geclaimt und vom Server mit „Market closed“ abgelehnt — keine Position, Balance davor = danach 97.119,63, kein Hedge
--   (Echo spiegelt nur eine offene Master-Position). Tagesreset setzte ihn auf review (final.grund tagesende_unklar).
--   e74ee368 (Folge-Plan, mt5v2 SELL 20 Lot) und ed83d9bb (200k derselben ID, mt5v2 BUY) sind Auto-Vorschläge OHNE auto_bestaetigt_at —
--   Testphase seit 29.10. (auto_bestaetigen aus): suKandidaten/suStartetNichtWeil lassen sie aus („startet erst nach Bestätigung“),
--   der Claim-Guard SU_CLAIM_GUARD hielte sie ebenfalls. Darum nie gestartet, Startzeiten unverändert.
-- Was diese Datei tut:
--   (1) abc02a19 abschließen wie der Radar-Knopf „Abhaken“ (PATCH /admin/wd-plaene aktion erledigt, _wd_erledigt_upd): completed,
--       master_pl 0 (Vorbelegung = Balance nachher − vorher), slave_pl null (Fusion am Plan, nichts gebucht), completed_at jetzt;
--       ended_at und mt5_baseline.final stehen schon. Konto bleibt (konto_status none).
--   (2) e74ee368 bekommt eine neue Startzeit jetzt + 15–25 min (gestreut, wie AP_NACHPLAN_VORLAUF_MIN), höchstens 17:59 Dubai
--       (zeiten.cfd_bis 18:00) — gleiche Balance wie beim Planen, TP/SL bleiben gültig. Ab 17:45 Dubai ändert (2) nichts mehr; dann ersetzt
--       der Nachtlauf (01:30 Dubai) den Vorschlag für den nächsten Handelstag (abc02a19 ist dann erledigt, sperrt nichts mehr).
--   Bestätigen bleibt Finns Klick (Admin → Challenge-Planer → Zu bestätigen → ✓). Nachplanen hülfe hier nicht: es ersetzt keine Vorschläge,
--   und ein heute abgehakter Trade belegt das Konto für heute (_ap_plan_am_tag, completed_at).
--   ed83d9bb bleibt unberührt und unbestätigt (Start 13:09 Dubai verpasst; BUY gegen den SELL derselben ID × Firma — der Claim-Riegel
--   prophos_gegenrichtung_frei hielte ihn, solange der SELL open/review ist). Der Nachtlauf ersetzt ihn.
-- Wiederholbar: (1) nur aus review, (2) nur solange die Startzeit in der Vergangenheit liegt und nichts geclaimt/bestätigt ist.

update public.trade_plans
   set status = 'completed', master_pl = 0, slave_pl = null, completed_at = now()
 where id = 'abc02a19-e4dc-4ded-8475-5d8347adf084'
   and status = 'review' and started_at is null;

update public.trade_plans
   set start_um = least(now() + interval '15 minutes' + make_interval(secs => floor(random() * 600)),
                        (date_trunc('day', now() at time zone 'Asia/Dubai') + interval '17 hours 59 minutes') at time zone 'Asia/Dubai')
 where id = 'e74ee368-c519-4739-95d6-712298fc4ecf'
   and status = 'planned' and start_um_gestartet_at is null and auto_bestaetigt_at is null and hand_werte_at is null
   and start_um < now()
   and now() + interval '15 minutes' <= ((date_trunc('day', now() at time zone 'Asia/Dubai') + interval '18 hours') at time zone 'Asia/Dubai');

-- Kontrolle
select id, status, richtung, route, start_um at time zone 'Asia/Dubai' as start_dubai, auto_bestaetigt_at, master_pl, completed_at
  from public.trade_plans
 where id in ('abc02a19-e4dc-4ded-8475-5d8347adf084', 'e74ee368-c519-4739-95d6-712298fc4ecf', 'ed83d9bb-549a-4147-9d65-f105b3076a10');
