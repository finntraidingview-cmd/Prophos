-- 19.10.2026 (Finn, ~00:40 Dubai): „Wenn wir relativ knapp am Take Profit oder am Stoploss sind, darf der Puls nicht mehr raus
-- [aus dem Big-Trade-Konto], damit das Tampermonkey-Skript auf keinen Fall was verpasst … fest 2.000 $ vor TP und 2.000 $ vor der
-- Liq, ohne Hälfte-Regel, Werte in der DB." Der Stoploss ist bei uns die Liquidation (liq_regeln / Konto-Boden / Bracket — die engste
-- Grenze gilt), bei Apex der Daily Loss der Stufe.
-- Riegel „Puls bleibt zu Hause": Railway POST /richtung/frei (das Panel fragt vor jedem scharfen Klick, fail-closed) prüft zusätzlich
-- puls_heim_pruefen (app.py): läuft auf DIESEM PC ein Big Trade (open, tvv2/tsv2, Hedge-Weg, kein Winning Day), dessen Abstand zum TP
-- ≤ tp_usd oder zur Liq ≤ liq_usd ist (oder nicht prüfbar: kein frischer NQ-Kurs, kein Level), klickt Puls nicht — der Plan bleibt
-- Geplant und wird später neu versucht. Werte hier ändern = sofort wirksam (60 s Cache), kein Code-Push.
--   tp_usd / liq_usd   Abstand in $ (bei den Kontrakten des Big Trades), ab dem der Puls das Konto nicht mehr verlässt
--   firmen             optional je Firma überschreiben, z. B. {"apex": {"tp_usd": 2000, "liq_usd": 1500}} (Schlüssel wie _ap_norm: klein, nur a–z0–9)
--   aktiv              false = Riegel aus (Gegenrichtungs-Riegel bleibt)
-- Lesen darf jeder Eingeloggte (PC-Tab/Karten dürfen die Regel anzeigen), schreiben nur service_role. Wiederholbar.
create table if not exists public.puls_heim_regel (
  id        smallint primary key default 1 check (id = 1),
  aktiv     boolean not null default true,
  tp_usd    numeric not null default 2000 check (tp_usd >= 0),
  liq_usd   numeric not null default 2000 check (liq_usd >= 0),
  firmen    jsonb not null default '{}'::jsonb check (jsonb_typeof(firmen) = 'object'),
  notiz     text,
  updated_at timestamptz not null default now()
);
alter table public.puls_heim_regel enable row level security;
drop policy if exists puls_heim_regel_lesen on public.puls_heim_regel;
create policy puls_heim_regel_lesen on public.puls_heim_regel for select to authenticated using (true);
insert into public.puls_heim_regel (id, aktiv, tp_usd, liq_usd, notiz)
values (1, true, 2000, 2000, 'Finn 19.10.2026: fest 2.000 $ vor TP und 2.000 $ vor der Liq, ohne Hälfte-Regel')
on conflict (id) do nothing;

select * from public.puls_heim_regel;
