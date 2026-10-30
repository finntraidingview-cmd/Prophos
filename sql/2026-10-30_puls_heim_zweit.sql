-- ZWEI ORBIT, Schalter (30.10.2026, Auftrag ZWEI-ORBIT Stück 1/2, Bauplan S5; Finn ~07:50: „2 Orbit je Fenster, Spanne 2.500 $ für den
-- Start des Zweiten"). puls_heim_regel (id=1) bekommt:
--   big_max_je_id   Big Trades je ID und Fenster (TradingView / TopstepX) gleichzeitig. 1 = heute (nur einer). 2 erst auf Finns Wort,
--                   zuerst für eine Test-ID — bis dahin bleibt alles wie heute.
--   zweit_usd       ein weiterer Big Trade startet nur, wenn jeder laufende derselben ID im Fenster mehr als so viele $ vor TP UND Liq steht
--   zweit_takt_von_s / zweit_takt_bis_s   Takt des Sofort-Start-Wächters im PC-Tab (S7), gewürfelt (Puls-Jitter-Regel)
-- app.py liest mit select=* (puls_heim_zweit_regel): fehlen die Spalten, gelten 1 / 2.500 — also wie heute. Die Spanne für fremde
-- Puls-Aktionen (tp_usd/liq_usd, heute 2.000) bleibt hier unberührt: 2.500 erst auf Finns Wort. Idempotent.
alter table public.puls_heim_regel add column if not exists big_max_je_id integer not null default 1;
alter table public.puls_heim_regel add column if not exists zweit_usd numeric not null default 2500;
alter table public.puls_heim_regel add column if not exists zweit_takt_von_s integer not null default 20;
alter table public.puls_heim_regel add column if not exists zweit_takt_bis_s integer not null default 40;
do $c$ begin
  alter table public.puls_heim_regel add constraint puls_heim_regel_big_max_je_id_check check (big_max_je_id between 1 and 3);
exception when duplicate_object then null; end $c$;
comment on column public.puls_heim_regel.big_max_je_id is 'Big Trades je ID und Fenster gleichzeitig (1 = nur einer, Stand bis Finns Freigabe; 30.10.2026)';
comment on column public.puls_heim_regel.zweit_usd is 'Weiterer Big Trade derselben ID im Fenster nur, wenn jeder laufende > zweit_usd vor TP und Liq (30.10.2026)';
