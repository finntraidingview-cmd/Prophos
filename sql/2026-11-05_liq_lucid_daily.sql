-- LQ1c (05.11.2026, Finn über den Master: „Lucid-Daily = Tagespause, das Konto lebt“; Anlass Finn 21:35 Dubai zu Lucid 150k Flex Eval: „Der Max
-- Drawdown ist 4k, aber wir haben hier ein Daily von 2,7k“ — „also im Radar dann auch 2.700 Daily“).
-- Weiche Anzeige des Lucid-Daily im Radar über liq_regeln: art 'tagesstart' → liq_regel_soft → Radar „Tageslimit, Konto lebt“, kein 💀 am Daily, echter
-- Blow nur am Konto-Boden (Max Loss EOD). NICHT über soft in auto_plan_regeln.regeln.firmen[lucid] — das schaltet im Planer das Modell auf „tage“
-- (app.py ~9932) und nimmt die Tagesgrenze aus der Prüfung (~23990). Mit dieser Zeile greift der Kernwert-Weg aus c74bd705/09a83c06 für Lucid nicht mehr
-- (die Regel kennt das Tageslimit selbst); FTMO Futures bleibt dort hart, bis Finn etwas anderes sagt.
-- Je Größe eine Challenge-Zeile; maxdd_art 'eod_trailing' wie id 12 mitgetragen (liq_regel_waehlen nimmt nur die spezifischste Zeile, sonst fiele der
-- EOD-Boden weg). Nachgerechnet (tools/selftest_liq_daily.py): 150k Liq 147.300 weich, Boden 145.500; 50k 48.800; unter dem EOD-Hoch gilt der engere Boden.
-- Wirkung: Radar-Liq-Linie/Demo/„Konto weg“ der Lucid-Challenges. Orbit Prio 2 (prophos.html hedgeLiqDllApex) nimmt weiter min(Zeile, Konto-Daily) =
-- 2.700 bzw. 1.200; Winning Days (id 14) und Funded unberührt. Idempotent (where not exists). MIT dem Backend-Push (c74bd705) einspielen — ohne die Zeile
-- zeigt der Radar das Lucid-Daily aus den Kernwerten als hart (Konto weg am Daily).

insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, maxdd_art, notiz, quelle)
select 'Lucid Trading', 'challenge', 150000, 'tagesstart', 2700, 'eod_trailing',
       'Lucid 150k Flex Eval: Daily Loss 2.700 $ ab Tagesstart = Tagespause, Konto lebt; Blow nur am Max Loss 4.500 EOD (Boden wie id 12).',
       'Finn 05.11.2026 (über den Master, LQ1c)'
where not exists (select 1 from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'challenge' and groesse = 150000);

insert into public.liq_regeln (firma, kontotyp, groesse, art, betrag_usd, maxdd_art, notiz, quelle)
select 'Lucid Trading', 'challenge', 50000, 'tagesstart', 1200, 'eod_trailing',
       'Lucid 50k Flex Eval: Daily Loss 1.200 $ ab Tagesstart = Tagespause, Konto lebt; Blow nur am Max Loss 2.000 EOD (Boden wie id 12).',
       'Finn 05.11.2026 (über den Master, LQ1c)'
where not exists (select 1 from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'challenge' and groesse = 50000);

-- Kontrolle:
-- select id, firma, kontotyp, groesse, art, betrag_usd, maxdd_art from public.liq_regeln where firma = 'Lucid Trading' order by id;

-- RÜCKBAU:
-- delete from public.liq_regeln where firma = 'Lucid Trading' and kontotyp = 'challenge' and groesse in (50000, 150000);
