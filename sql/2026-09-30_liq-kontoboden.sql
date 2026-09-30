-- 2026-09-30: liq_regeln, vierte Fassung — Konto-Boden aus dem Max Drawdown (Master-Auftrag LIQ-KONTOBODEN).
-- Finn 30.09.2026: „Der Account hat insgesamt 4.000 $ Drawdown. Ich habe schon 2.500 $ verloren, von 150.000 auf 147.500. Beim nächsten
-- Trade ist die Liquidation nur noch 1.500 $ entfernt, nicht wieder 4.000. Das bitte einrechnen. Relevant in der Challenge und bei Funded,
-- wenn ich den ersten Tag verliere."
-- Die Regel selbst (art fest/tagesstart/stufen/boden) bleibt unverändert. Neu daneben der absolute Konto-Boden:
--   statisch      Boden = Kontogröße − Max DD
--   eod_trailing  Boden = höchste belegte End-Balance (mindestens Kontogröße) − Max DD, höchstens Kontogröße + maxdd_lock_ueber_groesse_usd
-- Max DD aus accounts.max_drawdown, sonst maxdd_usd dieser Zeile. Effektive Liquidation (Radar) = die ENGERE (höhere) von Regel und Boden.
-- Ohne passende Zeile oder ohne maxdd_art gilt statisch. Nur Anzeige: Fusion-Hedge-Level (wd_sl_zeile, hedge.sl_level_nq, Hedge-Open)
-- bleiben unverändert.
-- Quelle für statisch vs. trailing: firm_rules.json (Tradeify, Apex Trader, Topstep, Alpha Futures). Firmen, die dort fehlen: statisch,
-- in der notiz „offen".
-- Im Supabase SQL Editor einfügen und auf 'Run' klicken. Idempotent.

alter table public.liq_regeln add column if not exists maxdd_art text;
alter table public.liq_regeln add column if not exists maxdd_lock_ueber_groesse_usd numeric;
alter table public.liq_regeln add column if not exists maxdd_usd numeric;
alter table public.liq_regeln drop constraint if exists liq_regeln_maxdd_art_check;
alter table public.liq_regeln add constraint liq_regeln_maxdd_art_check check (maxdd_art is null or maxdd_art in ('statisch', 'eod_trailing'));
comment on column public.liq_regeln.maxdd_art is 'Konto-Boden aus dem Max Drawdown: statisch (Größe − DD) | eod_trailing (höchste End-Balance − DD); null = statisch';
comment on column public.liq_regeln.maxdd_lock_ueber_groesse_usd is 'eod_trailing: Boden steigt nie über Kontogröße + diesen Betrag (Tradeify/Apex 100, Topstep/Alpha 0); null = kein Lock';
comment on column public.liq_regeln.maxdd_usd is 'Max Drawdown in $, falls accounts.max_drawdown fehlt';

-- Tradeify: „End-of-Day Trailing auf allen Tradeify-Accounts"; Lock nur auf Sim Funded (Floor Starting Balance + 100), NICHT auf Evaluations
update public.liq_regeln set maxdd_art = 'eod_trailing', maxdd_lock_ueber_groesse_usd = null
 where lower(firma) = 'tradeify' and kontotyp = 'challenge';
update public.liq_regeln set maxdd_art = 'eod_trailing', maxdd_lock_ueber_groesse_usd = 100
 where lower(firma) = 'tradeify' and kontotyp in ('funded', 'winning_days');

-- Apex Trader 4.0 EOD: MLL trailt bei Market Close, stoppt beim Safety Net (Starting Balance + DD + 100) → Boden höchstens Größe + 100.
-- Welcher Plan (EOD oder Intraday) gekauft wurde, ist nicht belegt — EOD angenommen, weil die Evaluation einen Daily Loss hat (nur EOD).
update public.liq_regeln set maxdd_art = 'eod_trailing', maxdd_lock_ueber_groesse_usd = 100
 where lower(firma) = 'apex trader' and kontotyp in ('challenge', 'funded');

-- Neue Zeilen ohne eigene Liq-Regel (art null) — nur für den Konto-Boden. Einmalig (nicht doppelt anlegen).
-- Topstep Combine: MLL trailt EOD, lockt bei Erreichen der Starting Balance. (Topstep V2 nimmt, wenn gelesen, die MLL direkt aus
-- TopstepX; Express/XFA startet bei 0 $ und bekommt keinen Konto-Boden.)
insert into public.liq_regeln (firma, kontotyp, art, maxdd_art, maxdd_lock_ueber_groesse_usd, notiz, quelle)
select 'Topstep', 'challenge', null, 'eod_trailing', 0,
       'firm_rules.json: MLL trailt End-of-Day nach höchster EOD-Balance, lockt bei Erreichen der Starting Balance (Combine). Keine eigene Liq-Regel — nur Konto-Boden.',
       'firm_rules.json (30.09.2026)'
 where not exists (select 1 from public.liq_regeln where lower(firma) = 'topstep' and kontotyp = 'challenge');

-- Alpha Futures: EOD Trailing auf ALLEN Accounts (Eval und Funded), stoppt bei der Initial Starting Balance
insert into public.liq_regeln (firma, kontotyp, art, maxdd_art, maxdd_lock_ueber_groesse_usd, notiz, quelle)
select 'Alpha Futures', null, null, 'eod_trailing', 0,
       'firm_rules.json: EOD Trailing Drawdown auf allen Accounts, MLL lockt bei der Initial Starting Balance. Keine eigene Liq-Regel — nur Konto-Boden.',
       'firm_rules.json (30.09.2026)'
 where not exists (select 1 from public.liq_regeln where lower(firma) in ('alpha futures', 'alpha future'));

-- Nicht in firm_rules.json → statisch (Finns Beispiel), offen
insert into public.liq_regeln (firma, kontotyp, art, maxdd_art, notiz, quelle)
select f, null, null, 'statisch',
       'Offen: Drawdown-Art nicht in firm_rules.json — statisch angenommen (Größe − Max DD). Keine eigene Liq-Regel — nur Konto-Boden.',
       'Annahme 30.09.2026 (Master-Auftrag LIQ-KONTOBODEN)'
  from (values ('Lucid Trading'), ('MyFundedFutures'), ('FundedNext Futures')) as v(f)
 where not exists (select 1 from public.liq_regeln r where lower(r.firma) = lower(v.f));

-- Prüfen:
-- select id, firma, kontotyp, art, betrag_usd, maxdd_art, maxdd_lock_ueber_groesse_usd, maxdd_usd, left(notiz, 60) from public.liq_regeln order by firma, kontotyp;
