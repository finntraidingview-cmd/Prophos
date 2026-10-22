-- PULS BLEIBT ZU HAUSE AUCH FÜR WINNING DAYS (Finn 22.10.2026: „wenn es 100 $ vor Take Profit oder SL ist, darf PULS keine Order senden").
-- Eigene Grenzen in puls_heim_regel (id=1), getrennt von den 2.000 $ der Big Trades. app.py liest sie mit select=* (fehlen die Spalten,
-- gelten 100/100 aus PULS_HEIM_WD_USD). wd_aktiv = false schaltet nur den WD-Teil aus.
-- Einspielen VOR dem Railway-Deploy ist nicht nötig (Code hat Standardwerte), aber so stehen die Werte änderbar in der DB.
alter table public.puls_heim_regel add column if not exists wd_aktiv boolean not null default true;
alter table public.puls_heim_regel add column if not exists wd_tp_usd numeric not null default 100;
alter table public.puls_heim_regel add column if not exists wd_liq_usd numeric not null default 100;
comment on column public.puls_heim_regel.wd_tp_usd is 'Winning Day: Rest bis TP in $ (Kontrakte × Punktwert), ab dem Puls auf diesem PC kein anderes Konto mehr bedient (22.10.2026)';
comment on column public.puls_heim_regel.wd_liq_usd is 'Winning Day: Rest bis zur Liq in $, ab dem Puls auf diesem PC kein anderes Konto mehr bedient (22.10.2026)';
