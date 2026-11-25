-- T5C (25.11.2026, Slave 3) · The5%ers High Stakes 2-Step „New" (wie bisher, Phase 1 8 %) und „Classic" (Phase 1 10 %, Phase 2 5 %, sonst gleich: Max Loss
-- 10 % statisch, Daily Loss 3 %, Hebel 1:100, kein Zeitlimit; Funded unverändert). Finn: alle bestehenden The5%ers-Konten sind New; ohne „Classic" im
-- Namen = New. Erkennung im Code (ap_konto_variante): Kontoname enthält das Wort „Classic" (Add-on „ · Classic") → regel.varianten.classic.
-- NICHT EINGESPIELT — ERST NACH dem Backend-Push mit T5C (vorher kennt der Code regel.varianten nicht: die Classic-Schablonen legten dann Konten an,
-- die mit 8 % geplant würden).
--
--   1. Sicherung: auto_plan_regeln id 1 + die The5%ers-Schablonen (t5c_*_20261125, RLS an, Rechte entzogen).
--   2. auto_plan_regeln (the5ers): varianten.classic = {ziel_pct {phase1 10, phase2 5}, kauf_eur {200000: 245}}. 245 € = 269,10 $ (Aktionspreis 200k)
--      × 0,91216 (Live-Kurs 24.11.2026). 100k-Classic-Preis OFFEN (nicht belegt) → ohne Eintrag gilt der Firmen-Kauf 100k (146 €) im Kontowert, bis
--      Finn den Preis nennt. TP/SL/Lots wie New — mit 10 % braucht Phase 1 eine Etappe mehr (100k: Ziel 10.000 bei TP 5.400–6.300).
--   3. bulk_vorlagen (Finn: Schablonen IMMER nur für Phase 1 — Phase 2/Funded entstehen über den Nachfolger-Assistenten, der das Add-on „ · Classic"
--      im Namen weiterträgt): die zwei bestehenden („The5ers 100k/200k Summerplan Phase 1") → „The5%ers 100k/200k New Phase 1" (umbenannt, Werte
--      unverändert); neu „The5%ers 100k Classic Phase 1" (Kaufpreis leer = offen) und „The5%ers 200k Classic Phase 1" (245 €). Classic-Namen enthalten
--      „Classic" → der Konto-Name bekommt beim Anlegen das Add-on „ · Classic" (prophos.html kontoVorlageZusatz).
-- Idempotent: zweimal einspielen ändert nichts. Rückbau unten (auskommentiert).

begin;

create table if not exists t5c_auto_plan_regeln_20261125 as
  select id, regeln, updated_at, now() as gesichert_at from public.auto_plan_regeln where id = 1;
alter table t5c_auto_plan_regeln_20261125 enable row level security;
revoke all on t5c_auto_plan_regeln_20261125 from public, anon, authenticated;

create table if not exists t5c_bulk_vorlagen_20261125 as
  select *, now() as gesichert_at from public.bulk_vorlagen where firm = 'The5%ers';
alter table t5c_bulk_vorlagen_20261125 enable row level security;
revoke all on t5c_bulk_vorlagen_20261125 from public, anon, authenticated;

-- 2. Regel: Variante Classic
update public.auto_plan_regeln r
   set regeln = jsonb_set(r.regeln, array['firmen', (x.i - 1)::text, 'varianten'],
                          '{"classic": {"ziel_pct": {"phase1": 10, "phase2": 5}, "kauf_eur": {"200000": 245}}}'::jsonb),
       updated_at = now()
  from (select f.i from public.auto_plan_regeln r2, jsonb_array_elements(r2.regeln->'firmen') with ordinality f(v, i)
         where r2.id = 1 and f.v->'namen' ? 'the5ers') x
 where r.id = 1
   and (r.regeln->'firmen'->(x.i - 1)::int->'varianten') is distinct from
       '{"classic": {"ziel_pct": {"phase1": 10, "phase2": 5}, "kauf_eur": {"200000": 245}}}'::jsonb;

-- 3a. Bestehende Schablonen = New (umbenennen, nicht löschen)
update public.bulk_vorlagen set name = 'The5%ers 100k New Phase 1', updated_at = now()
 where id = 'cccc8778-e5ff-434b-a669-a365824dd355' and name = 'The5ers 100k Summerplan Phase 1';
update public.bulk_vorlagen set name = 'The5%ers 200k New Phase 1', updated_at = now()
 where id = '1ab6da88-3f90-4ab2-908a-18b40ec85e2c' and name = 'The5ers 200k Summerplan Phase 1';

-- 3b. Neue Schablonen (nur wenn der Name noch fehlt); DD 10 % statisch, Daily 3 %, MT5 wie die Bestehenden
insert into public.bulk_vorlagen (name, firm, account_type, account_size, starting_balance, max_drawdown, max_daily_drawdown, purchase_cost, purchase_ccy,
                                  name_template, plattform, aktiv, sortierung, consistency_pct)
select v.name, 'The5%ers', v.typ, v.gr, v.gr, v.gr * 0.10, v.gr * 0.03, v.kauf, 'EUR', v.vorlage, 'MT5', true, v.sort, v.cons
  from (values
    ('The5%ers 100k Classic Phase 1',    'phase1',     100000::numeric, null::numeric, '100k The5ers Classic {ex}', 45, null::numeric),
    ('The5%ers 200k Classic Phase 1',    'phase1',     200000,          245,           '200k The5ers Classic {ex}', 46, null)
  ) as v(name, typ, gr, kauf, vorlage, sort, cons)
 where not exists (select 1 from public.bulk_vorlagen b where b.name = v.name);

commit;

-- Prüfen:
-- select f->'varianten', f->'ziel_pct', f->'kauf_eur' from auto_plan_regeln r, jsonb_array_elements(r.regeln->'firmen') f
--  where r.id = 1 and f->'namen' ? 'the5ers';            -- {"classic": {...10/5, 200000: 245}}, {"phase1": 8, "phase2": 5}, {"100000": 146, "200000": 226}
-- select name, account_type, account_size, max_drawdown, max_daily_drawdown, purchase_cost, consistency_pct, sortierung
--   from bulk_vorlagen where firm = 'The5%ers' order by sortierung;                                    -- 4 Zeilen (New P1 100k/200k, Classic P1 100k/200k)

-- Rückbau (nur falls nötig):
-- delete from public.bulk_vorlagen where name in ('The5%ers 100k Classic Phase 1', 'The5%ers 200k Classic Phase 1')
--    and id not in (select id from t5c_bulk_vorlagen_20261125);   -- nur die von dieser Datei angelegten (Review)
-- update public.bulk_vorlagen b set name = s.name from t5c_bulk_vorlagen_20261125 s where b.id = s.id;
-- update public.auto_plan_regeln r set regeln = r.regeln #- array['firmen', (x.i - 1)::text, 'varianten'], updated_at = now()
--   from (select f.i from public.auto_plan_regeln r2, jsonb_array_elements(r2.regeln->'firmen') with ordinality f(v, i)
--          where r2.id = 1 and f.v->'namen' ? 'the5ers') x where r.id = 1;
