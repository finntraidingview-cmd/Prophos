-- ES3 (05.11.2026, Finn: „Es ist ja per Zufallsprinzip mit Variablen, aber es sollte nicht über 1 Minute dauern … Orders sollen viel
-- schneller prozessiert werden, wie es ganz am Anfang war"). Befund ES1: der Echo-Bot braucht bis zum Fill 24 s statt 16 s seit .1798
-- („alles aus Zufall", 28.10.2026) — Tippen je Zeichen mit Haltezeit/Takt/Stocken, Denkpausen in jeder Pause, 0–1,2 s Versatz.
-- Einstellung für den Echo-Bot (mt5-copier/order_bot.py), gelesen über Railway GET /puls-regel/<pc_id> (Schlüssel „echo_tempo",
-- 60 s Cache, app.py puls_echo_tempo_stand); der Bot merkt sie lokal (echo_tempo.json) und nimmt sie ab dem nächsten Lauf je PC.
--   tipp_faktor  1,0 = heutiger Zeichen-Takt; 0,3–0,99 = Feld-Takt (Haltezeit/Abstand einmal je Feld gewürfelt, ×Faktor, kein Stocken)
--   denkpausen   true = heute; false = im F9-Dialog keine Denkpause, Pausen-Faktor höchstens 1 (Streuung bleibt)
--   versatz_s    Bot-Versatz vor dem ersten Schritt 0..versatz_s Sekunden (heute 1,2; 0 = keiner; höchstens 3)
-- Fehlt die Spalte, ist sie null oder fehlt ein Schlüssel: der Bot nimmt für diesen Schlüssel den heutigen Wert. Additiv, wiederholbar.
-- NICHT eingespielt — nur auf Finns Wort. Teil 1 = Spalte (additiv, ändert nichts). Teil 2 = Vorschlagswerte, bewusst AUSKOMMENTIERT:
-- erst einkommentieren/ausführen, wenn Finn das neue Tempo will. Rückbau unten (null → Railway sendet {} → jeder PC nimmt die heutigen Werte).

-- Teil 1: Spalte (null = heutige Werte, ändert nichts)
alter table public.wd_farmer_regeln add column if not exists puls_echo_tempo jsonb
  check (puls_echo_tempo is null or jsonb_typeof(puls_echo_tempo) = 'object');
comment on column public.wd_farmer_regeln.puls_echo_tempo is
  'ES3 05.11.2026: Echo-Bot-Tempo {tipp_faktor 0,3–1, denkpausen bool, versatz_s 0–3}; null/fehlender Schlüssel = heutiger Wert';

-- Teil 2: Vorschlag ES1/ES3 (Bot bis Fill wieder ~16 s): Feld-Takt ×0,5, Denkpausen im F9-Dialog aus, Versatz 0–0,6 s
-- update public.wd_farmer_regeln
--    set puls_echo_tempo = '{"tipp_faktor": 0.5, "denkpausen": false, "versatz_s": 0.6}'::jsonb
--  where id = 1;

-- Kontrolle
select id, puls_echo_tempo from public.wd_farmer_regeln where id = 1;

-- Rückbau (Tempo wie vor ES3; der Löschversuch-Wegfall bleibt, er ist Code): update public.wd_farmer_regeln set puls_echo_tempo = null where id = 1;
