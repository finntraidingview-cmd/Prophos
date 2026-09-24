-- ============================================================================
-- Prophos: echoplus_live — Konto + Positions-Frische des Readers (25.09.2026)
--
-- Reader 0.8.3/0.8.5 liefert in GET /positions: konto (Text des Konto-
-- Umschalters, z. B. 'PAAPEX6416990000007'), positionen_ok (true nur, wenn
-- Script UND Server nicht blind sind = Beweis), positionen_ts (letzte
-- vollständige Lesung). Die Brücke schreibt sie je PC mit — damit sich aus
-- der Cloud belegen lässt, welches Konto der Reader sah und ob die Positions-
-- liste ein Beweis war (Wächter-Linie „Master weg laut Reader"). Idempotent.
-- ============================================================================
alter table public.echoplus_live add column if not exists konto text;
alter table public.echoplus_live add column if not exists positionen_ok boolean;
alter table public.echoplus_live add column if not exists positionen_ts timestamptz;
