-- 2026-09-29 · Kontotyp „Funded CFD" + Feld „Waiting for Payout"
--
-- Anlass (Finn 29.09.2026): „Es soll einmal Funded geben für Futures und einmal Funded für CFDs, damit die beiden
-- unterschieden werden. Plus ein neues Feld, das man bei CFDs setzen kann: Waiting for Payout — der Account ist
-- schon im Plus, wir warten nur auf den Payout. Wenn ich den Payout anfrage, resetet sich das Feld automatisch."
-- Nachtrag: „bei den bestehenden Accounts alles schon anwenden … dass ich es nicht für alle ändern muss".
--
-- Werte:
--   'funded'      = Funded FUTURES (bleibt bewusst der alte Wert — Winning Days, Farmer, Hedge-Quoten, app.py-Futures-Logik
--                   hängen alle an 'funded' und laufen unverändert weiter)
--   'funded_cfd'  = Funded CFD (neu)
-- Statistik (app.py _hq_typ/_hq_typ_trade) zählt 'funded_cfd' weiter als 'funded' — Gruppen „Firma|funded" und
-- HQ-Ziele bleiben stabil, alte Trades springen nicht in eine neue Gruppe.
--
-- waiting_payout_since: null = wartet nicht; Zeitstempel = seit wann „Waiting for Payout" gesetzt ist. Gesetzt von Hand im
-- Account-Modal (nur Funded CFD), geleert beim „Payout anfragen" bzw. direkt gebuchten Payout (Frontend, wie payout_ready_at).

-- Sperr-Limit: accounts ist ständig in Benutzung (Realtime, PC-Tabs) — ohne Limit hing das ALTER am 29.09.2026 im
-- MCP-Aufruf bis zum 503. Mit 5 s scheitert es sauber und kann wiederholt werden.
set lock_timeout = '5s';

-- 1) Waiting for Payout
alter table public.accounts add column if not exists waiting_payout_since timestamptz;

-- 2) Typ-Constraint um 'funded_cfd' erweitern (ein ALTER = atomar, kein Moment ohne Constraint)
alter table public.accounts
  drop constraint if exists accounts_account_type_check,
  add constraint accounts_account_type_check
    check (account_type = any (array['challenge'::text, 'phase1'::text, 'phase2'::text, 'funded'::text, 'funded_cfd'::text,
                                     'live'::text, 'winning_days'::text]));
comment on column public.accounts.waiting_payout_since is
  'Waiting for Payout (Funded CFD): seit wann das Konto im Plus ist und nur auf den Payout wartet. null = nein. Wird beim Payout-Anfragen geleert.';

-- 3) Bestand umstellen (lief NACH dem Frontend-Push, damit die alte Oberfläche den Wert nie roh zeigt): jedes Funded-Konto einer NICHT-Futures-Firma → 'funded_cfd'.
--    Futures-Liste = tpFirmIstFutures() in prophos.html (TP_FUTURES_FIRMEN). Stand beim Schreiben: 31 Konten
--    (FTMO 2, FundedNext 11, FundingPips 6, The5%ers 12); 63 Futures-Funded (Tradeify, Apex, Topstep, Alpha Future,
--    FundedNext Futures) bleiben 'funded'.
update public.accounts
   set account_type = 'funded_cfd'
 where account_type = 'funded'
   and lower(trim(coalesce(firm, ''))) not in ('topstep', 'tradeify', 'apex trader', 'lucid trading', 'fundednext futures',
                                               'myfundedfutures', 'myfoundedfutures', 'alpha future', 'alphafutures', 'alpha futures');
