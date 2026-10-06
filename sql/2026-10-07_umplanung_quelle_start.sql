-- RICHTUNG AM START (07.10.2026, Finn: ein geplanter Auto-Trade soll nicht ausfallen, nur weil bei derselben ID+Firma inzwischen
-- eine gegenläufige Position läuft). Der PC-Tab dreht bzw. verschiebt den Plan kurz vor dem Start und protokolliert das über
-- POST /admin/auto-plan/start-protokoll in auto_plan_umplanung mit quelle 'start'. Bis diese Datei eingespielt ist, schreibt das
-- Backend solche Zeilen als quelle 'bot' mit „[Start]" vor dem Grund — es geht also nichts verloren.
-- Wiederholbar.

alter table public.auto_plan_umplanung drop constraint if exists auto_plan_umplanung_quelle_check;
alter table public.auto_plan_umplanung
  add constraint auto_plan_umplanung_quelle_check check (quelle in ('bot', 'hand', 'start'));
