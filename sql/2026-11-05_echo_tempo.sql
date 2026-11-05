-- ECHO-TEMPO (05.11.2026, Auftrag ES2, Finn: „Es ist ja auch per Zufallsprinzip mit Variablen, aber es sollte nicht über 1 Minute
-- dauern … die Orders sollen viel schneller prozessiert werden, wie es ganz am Anfang war"). Messung ES1: Echo vom Claim bis zur Order
-- im Median 48 s statt 28 s am 23.–27.10., p90 ~170 s, keine Überlast. Die Wartezeiten des Echo-Starts im PC-Tab (prophos.html,
-- echoTempo) stehen jetzt hier statt im Code. puls_heim_regel (id=1) bekommt:
--   echo_versatz_max_ms   Versatz zur Startzeit, gewürfelt 0..max (kurze häufiger). Vorher fest 4000 (0–4 s), Vorschlag 1500
--   echo_pause_min_ms     Pause zwischen zwei Echo-Starts an einem PC: Minimum (vorher 5000) …
--   echo_pause_streu_ms   … plus gewürfelt 0..Streuung (vorher 25000 → 5–30 s). Vorschlag 3000 + 7000 = 3–10 s. Nicht-Echo-Wege
--                         (Orbit, Polar) halten nach einem Echo-Start weiter 5–30 s ein; ein Echo-Plan wartet zusätzlich, bis der
--                         vorige Echo-Lauf an diesem PC fertig getippt hat (wie die PC-Tipp-Sperre)
--   echo_scharf_max_ms    Höchstwartezeit Scharf-Beweis (Copier meldet armed für die Config), danach Start-Fehler. Vorher 30000, bleibt
--   echo_vorwaermen_s     Master-Terminal eines Echo-mit-Hedge-Plans so viele Sekunden vor der Startzeit öffnen und einloggen (nur das
--                         Terminal, kein Trade-Fenster, keine Order; gestreut 0–10 s früher). 0 = aus (= vorher). Vorschlag 75
-- Der Tab liest mit select=* (alle 5 min): fehlt eine Spalte, gilt der Wert von vorher — ohne diese Datei ändert sich nichts.
-- Grenzen im Tab (Untergrenzen bleiben auch bei kleineren Werten hier): Versatz 0–10 s, Pause-Minimum ≥ 1 s, Scharf 10–120 s,
-- Vorwärmen 0–300 s. Werte hier ändern = binnen 5 min wirksam, kein Code-Push. Idempotent. NICHT eingespielt (Finns Wort abwarten).
alter table public.puls_heim_regel add column if not exists echo_versatz_max_ms integer not null default 1500;
alter table public.puls_heim_regel add column if not exists echo_pause_min_ms   integer not null default 3000;
alter table public.puls_heim_regel add column if not exists echo_pause_streu_ms integer not null default 7000;
alter table public.puls_heim_regel add column if not exists echo_scharf_max_ms  integer not null default 30000;
alter table public.puls_heim_regel add column if not exists echo_vorwaermen_s   integer not null default 75;
do $c$ begin
  alter table public.puls_heim_regel add constraint puls_heim_regel_echo_tempo_check check (
    echo_versatz_max_ms between 0 and 10000 and echo_pause_min_ms between 1000 and 60000 and echo_pause_streu_ms between 0 and 60000
    and echo_scharf_max_ms between 10000 and 120000 and echo_vorwaermen_s between 0 and 300);
exception when duplicate_object then null; end $c$;
comment on column public.puls_heim_regel.echo_versatz_max_ms is 'Echo: Versatz zur Startzeit 0..max ms gewürfelt (vorher 4000; ES2 05.11.2026)';
comment on column public.puls_heim_regel.echo_pause_min_ms is 'Echo: Pause zwischen zwei Echo-Starts am PC, Minimum ms (vorher 5000; ES2 05.11.2026)';
comment on column public.puls_heim_regel.echo_pause_streu_ms is 'Echo: Pause zwischen zwei Echo-Starts, Streuung ms obendrauf (vorher 25000; ES2 05.11.2026)';
comment on column public.puls_heim_regel.echo_scharf_max_ms is 'Echo: Höchstwartezeit Scharf-Beweis ms, danach Start-Fehler (vorher 30000; ES2 05.11.2026)';
comment on column public.puls_heim_regel.echo_vorwaermen_s is 'Echo mit Hedge: Master-Terminal x s vor Start öffnen + einloggen, 0 = aus (ES2 05.11.2026)';

-- Rückbau (nur auf Finns Wort): Spalten weg = Tab fällt auf die Werte von vorher zurück
-- alter table public.puls_heim_regel drop constraint if exists puls_heim_regel_echo_tempo_check;
-- alter table public.puls_heim_regel drop column if exists echo_versatz_max_ms, drop column if exists echo_pause_min_ms,
--   drop column if exists echo_pause_streu_ms, drop column if exists echo_scharf_max_ms, drop column if exists echo_vorwaermen_s;

-- Kontrolle
select id, echo_versatz_max_ms, echo_pause_min_ms, echo_pause_streu_ms, echo_scharf_max_ms, echo_vorwaermen_s from public.puls_heim_regel;
