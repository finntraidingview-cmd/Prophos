-- VORRAT: Hauptregel „ca. 25 %" (Finn 06.10.2026 spät, über den Master): Die Wahrscheinlichkeit, mit Vorrat + Funnel die Untergrenze
-- zu erreichen, soll bei etwa 25 % liegen — darunter wird nachgekauft (Kaufregel 'sicherheit', Monte Carlo, app.py VORRAT2_STD).
-- Der Regler „Mindest-Chance aufs Ziel" auf der Seite schickt 0,15 / 0,25 / 0,35 / 0,5 — der alte Check erlaubte nur 0,5–0,95.

alter table public.vorrat_einstellung drop constraint if exists vorrat_einstellung_sicherheit_check;
alter table public.vorrat_einstellung add constraint vorrat_einstellung_sicherheit_check
  check (sicherheit >= 0.1 and sicherheit <= 0.95);
alter table public.vorrat_einstellung alter column sicherheit set default 0.25;
update public.vorrat_einstellung set sicherheit = 0.25, updated_at = now() where id = 1;
