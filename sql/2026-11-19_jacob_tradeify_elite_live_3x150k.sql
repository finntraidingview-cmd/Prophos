-- Jacob: 3 × Tradeify 150k ELITE LIVE neu anlegen (Finn 19.11.2026 ~18:30 Dubai, Screenshot Tradovate-Kontoliste: 2332402, 2332403, 2332404,
-- je 0,00 USD). Elite Live (Stand Tradeify-Support/AI-Chat 18./19.11.2026): Start 0 $, EOD-Drawdown 4.500 $, Lock ab EOD-Balance 4.600 $
-- (Grenze dann +100 $), tägliche Payouts 80/20, Payout auf 0 $ schließt das Konto, Reward Pool. Tradeify hat NIE ein Daily Loss Limit.
-- Name nach Namensregel „<Größe> <External ID> → <Phase> · <Zusatz>“. account_type 'funded' (Tradeify-Funded wie bisher), Start 0.
-- AUTO-PLANER UND WD-FARMER AUS: echtes Geld, Strategie für Elite Live (halten, Pool, Payout-Takt) ist noch offen (Antwort Risk Manager
-- steht aus) — es wird nichts automatisch geplant, bis Finn den Weg festlegt. purchase_cost leer (kein eigener Kauf).
insert into public.accounts (user_id, name, firm, account_type, account_size, starting_balance, balance, max_drawdown, max_daily_drawdown,
                             external_id, currency, wd_farm, auto_planer)
select '368076fd-67c1-460c-aa86-38d81ae69350', '150k ' || v.ext || ' → Funded · Elite Live', 'Tradeify', 'funded', 150000, 0, 0, 4500, null,
       v.ext, 'USD', false, false
from (values ('2332402'), ('2332403'), ('2332404')) v(ext)
where not exists (select 1 from public.accounts a where a.user_id = '368076fd-67c1-460c-aa86-38d81ae69350' and a.external_id = v.ext);
