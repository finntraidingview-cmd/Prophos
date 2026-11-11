-- VF3 (Master 11.11.2026, Bericht berichte/2026-11-11_VF2_vorflug_blind.md): der Konto-Vorflug F-A war blind — 98 von 102 Lesungen „Terminal läuft nicht“,
-- weil Master-Terminals zwischen den Trades absichtlich zu sind (panel.py Terminal-Zu nach 1–2 min, Leerlauf-Wächter 15–19 min) und erst beim Vorwärmen
-- bei T−75 s aufgingen; der späteste Vorflug lag bei T−3 min. Variante A: Vorwärmen früher (240 s statt 75 s), der Vorflug-Slot b hängt im PC-Tab
-- (prophos.html vfFaellig/vfTick) am Vorwärmen: 30–60 s danach, frischer Snapshot, spätestens T−60 s. Nur Echo mit Hedge (Route mt5); mt5v2 hat kein Vorwärmen.
-- Kosten: das Master-Terminal ist ~3 min länger offen (Leerlauf-Wächter 15 min stört nicht). Grenze bleibt 0–300 (puls_heim_regel_echo_tempo_check,
-- Tab klemmt ebenfalls auf 0–300). Wirksam binnen 5 min (Tab liest puls_heim_regel select=*), kein Code-Push nötig. Idempotent.
-- Voraussetzung: sql/2026-11-05_echo_tempo.sql (Spalte echo_vorwaermen_s) ist eingespielt.
update public.puls_heim_regel set echo_vorwaermen_s = 240 where id = 1 and echo_vorwaermen_s is distinct from 240;

-- Rückbau (nur auf Finns Wort): update public.puls_heim_regel set echo_vorwaermen_s = 75 where id = 1;

-- Kontrolle
select id, echo_vorwaermen_s from public.puls_heim_regel;
