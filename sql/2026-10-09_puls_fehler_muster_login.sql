-- Puls-Fehlermuster: Login-Namen und Lauf-Präfixe normalisieren (09.10.2026, Master, Terminal 2)
--
-- Anlass: puls_fehler_muster_text ersetzte nur Wörter MIT Ziffer durch '#'. Tradovate-Logins ohne Ziffer (z. B. 'mffu…', 'fnft…')
-- blieben stehen, dazu die Präfixe „Versuch N: “, „Nichts platziert · “ und „konto_nicht_erreicht: “ — das Muster
-- „Tradovate-Login … nicht geschafft (abmelden)“ zerfiel so in ~10 Zeilen. Probe gegen die letzten 7 Tage (nur gelesen):
-- 69 → 63 Muster gesamt, die Abmelde-Muster 9 → 5 (je Schritt × Variante).
--
-- Neu: (1) Präfixe am Anfang weg, (2) login '<irgendwas>' → login '…'. Alles andere wie in 2026-10-07_puls_fehler_muster.sql.
-- Gleiche Signatur → View puls_fehler_muster rechnet ohne weitere Änderung mit der neuen Funktion.

create or replace function public.puls_fehler_muster_text(schritt text, msg text) returns text
language sql immutable as $$
  select coalesce(nullif(schritt, ''), '?') || ': ' || left(trim(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
    lower(coalesce(msg, '')),
    '^(versuch [0-9]+: |nichts platziert · |konto_nicht_erreicht: )+', ''),
    '(login) ''[^'']*''', '\1 ''…''', 'g'),
    '[a-z]*[0-9][a-z0-9.,:/-]*', '#', 'g'), '„[^“”"]*[“”"]', '„…"', 'g'), '\s+', ' ', 'g')), 90)
$$;
