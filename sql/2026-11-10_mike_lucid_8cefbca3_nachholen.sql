-- NACHHOLEN Mike · Lucid 150k LFE15098258480006 → Challenge (Plan 8cefbca3), Master 10.11.2026 nach TP1/S5.
-- Befund S5: Puls hat KEINE Order platziert (keine order_geklickt-Datei, Fehlerfoto 02:43 UTC „tvkonto asset“ = Kontowechsel gescheitert).
-- start_fehler stand auf unklar = true (puls_still „Geclaimt vor 11 min, danach kein Ergebnis“) → sperrte über prophos_gegenrichtung_frei_konto die
-- Gegenrichtung (sell) auf Mikes anderen Lucid-Konten und wird von sfTick nie nachgeholt.
-- Felder wie die bestehenden Code-Wege:
--   * Beleg „nichts gesendet“ → unklar = false (wie sfStillUrteil/sfEinmal mit Beleg), Original-Meldung bleibt.
--   * Neu einplanen wie sfNeuEinplanen / app.py _ap_neu_starten: start_um neu, start_um_gestartet_at = null; start_fehler.status = 'neu',
--     versuche + 1, behoben, neu_at, neu_start, hand = true. Bestätigung (auto_bestaetigt_at) bleibt.
--   * Guard wie dort: status planned, started_at / orbit_gesendet_at leer, dazu der Claim von 02:41:28 UTC unverändert (nichts dazwischen).
-- Startzeit: jetzt + 15–24 min gestreut (Jitter-Regel). Geprüft 07:18 Dubai: Mikes nächste Starts 08:11/08:12/08:13/08:15 (WD), 08:18 Lucid sell —
-- ≥ 5 min Abstand je ID (ap_nachhol_minute gap_pc); keine Lucid-Starts anderer IDs in 07:28–08:18 (±3 min gegenläufig frei); laufend bei Mike Lucid
-- nur …0003 buy (gleiche Richtung, kein Richtungsschutz). Läuft dieser Buy um 08:18 noch, dreht/verschiebt der Start-Riegel den Sell (db233356) selbst.
with neu as (select now() + interval '15 min' + random() * interval '9 min' as t)
update public.trade_plans p
   set start_um = neu.t,
       start_um_gestartet_at = null,
       mt5_baseline = jsonb_set(p.mt5_baseline, '{start_fehler}',
         (p.mt5_baseline->'start_fehler') || jsonb_build_object(
           'unklar', false,
           'status', 'neu',
           'versuche', coalesce((p.mt5_baseline->'start_fehler'->>'versuche')::int, 0) + 1,
           'behoben', 'S5-Beleg: Puls hat nichts platziert (keine order_geklickt-Datei, Fehlerfoto 02:43 UTC tvkonto asset) — von Hand neu eingeplant (Master TP1)',
           'neu_at', to_jsonb(now()),
           'neu_start', to_jsonb(neu.t),
           'hand', true))
  from neu
 where p.id = '8cefbca3-c2d9-46c2-a3c8-b8b2ce324539'
   and p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null
   and p.start_um_gestartet_at = '2026-11-10 02:41:28.166+00'
returning p.id, p.start_um at time zone 'Asia/Dubai' as start_dubai, p.start_um_gestartet_at, p.mt5_baseline->'start_fehler' as start_fehler;
