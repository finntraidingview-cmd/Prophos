-- WINNING DAYS SIND KEINE BIG TRADES (14.10.2026, Finn 16:20 Dubai: „das sind ja Winning Days und keine Big Trades … einfach nur
-- kleine Mini-Trades, das hat nicht die Priorität von echten Dingern").
-- Vorfall heute: die Hedge-Kategorien-Regel vom 12.10. (sql/2026-10-12_hedge_kategorien_regel.sql, Regel 4 „ein Big Trade je Fenster")
-- zählte jeden Winning Day als Big Trade. Der WD-Farmer startet je ID aber mehrere Konten im Abstand von 80 s — sobald das erste WD
-- lief (stundenlang bis zum TP), verweigerte trade_plans_big_trade den Claim aller Folge-Konten derselben ID und schob start_um um
-- 15 min; der Farmer-Abgleich zog die Zeit sofort auf die Kettenzeit zurück (Chris …4657: 75 Einträge „[Big Trade]" in 63 min). Nach
-- 60 min ließ die Ausnahme des Triggers den Claim durch, der PC-Tab sah „60 min verpasst" und startete nicht (Chris 3 Konten, Jacob 1).
-- Jetzt: ein Plan mit winning_day = true ist nie ein Big Trade — weder als Blocker (prophos_big_trade_laeuft) noch als Blockierter
-- (Trigger/RPC prüfen prophos_big_trade des eigenen Plans). Orbit V3, Fusion-Hedge ohne WD-Marke und Topstep mit Hedge bleiben Big Trades.
-- prophos_hedge_weg bleibt unverändert (WD läuft weiter MIT Hedge, Regel 2). Wiederholbar.
create or replace function public.prophos_big_trade(p_route text, p_hedge_eur numeric, p_orbit_v3 boolean, p_winning_day boolean)
returns boolean language sql immutable as $$
  select not coalesce(p_winning_day, false)   -- Winning Day = Mini-Trade, kein Big Trade (14.10.2026)
     and (coalesce(p_route, '') = 'polar'
          or (coalesce(p_route, '') in ('tvv2', 'tsv2') and coalesce(public.prophos_hedge_weg(p_route, p_hedge_eur, p_orbit_v3, p_winning_day), false)))
$$;
