-- ============================================================================
-- Prophos: KAPITAL — RÜCKBLICK ab 08.10.2026 für den Verlauf-Grafen (29.10.2026)
--
-- Finn 29.10.2026 07:00 (über den Master): „Rückblick: ja, Wallets + Kontowerte rückwirkend ab 08.10. eintragen (Kontowert-Regel neu:
-- Kauf + Hedge ohne Payout-Abzug, geblowt = 0), Fusion/Geschäftskonto/offene Payouts erst ab heute … Rückblick-Werte als eigene Zeilen
-- mit quelle 'rueckblick' (nicht als echte Tageswerte tarnen)."
--
--   1. kapital_tageswerte bekommt die Spalte quelle ('takt' = echter Tageswert über GET/Railway-Takt, 'rueckblick' = nachgerechnet);
--      soll_eur/abweichung_eur dürfen leer sein — für Rückblick-Tage gibt es kein Soll (Einlagen/Reibung je Tag nicht rekonstruierbar).
--   2. kapital_rueckblick_tag(gruppe, tag, fx): Wallets + Kontowerte, wie sie am Tag D standen —
--        Wallets   = jüngster wallet_snapshots-Tag je Wallet der Gruppe bis D (höchstens 30 Tage alt, wie kapital_app._daten_lesen)
--        Konten    = je Kette (Aufbau wie kapital_ketten), die an D lief: Kauf der bis D angelegten Glieder + Hedge-Ergebnis der bis D
--                    abgeschlossenen Pläne. Läuft = ein Glied bis D angelegt und der Kopf nicht bis D archiviert (archive.at); geblowt = 0.
--      Gegenprobe 29.10.2026 (nur gelesen): für heute trifft die Funktion die Live-Regel genau — Emin 42 Ketten / 26.978,61 €,
--      Hermann Technologies 193 Ketten / 135.255 € (= Σ kauf_eur + hedge_eur der laufenden kapital_ketten).
--   3. Einmal-Insert 08.10. … 28.10. für jede Gruppe, je Tag zum EZB-Referenzkurs (frankfurter.dev, Wochenende = letzter Kurs davor).
--      ON CONFLICT DO NOTHING: ein echter Tageswert wird nie überschrieben. teile.quelle = 'rueckblick' zusätzlich im JSON, damit
--      kapital_app die Zeilen auch ohne die neue Spalte erkennt.
--
-- Nur über den Service-Key (app.py) — Funktion für anon/authenticated gesperrt wie kapital_ketten. Idempotent; zurück:
--   delete from public.kapital_tageswerte where quelle = 'rueckblick';
-- ============================================================================

alter table public.kapital_tageswerte add column if not exists quelle text not null default 'takt';
do $$ begin
  if not exists (select 1 from pg_constraint where conname = 'kapital_tageswerte_quelle_chk') then
    alter table public.kapital_tageswerte add constraint kapital_tageswerte_quelle_chk check (quelle in ('takt', 'rueckblick'));
  end if;
end $$;
alter table public.kapital_tageswerte alter column soll_eur drop not null;
alter table public.kapital_tageswerte alter column abweichung_eur drop not null;

create or replace function public.kapital_rueckblick_tag(p_gruppe uuid, p_tag date, p_fx numeric default 0.89)
returns table(wallets_usd numeric, wallets_n integer, konten_eur numeric, konten_n integer)
language sql stable
set search_path to 'public'
as $function$
  with recursive
  tage as (select p_tag tag),
  mit as (select m.user_id from id_gruppe_mitglied m where m.gruppe_id = p_gruppe),
  acc as (
    select a.id, a.user_id, a.account_type, coalesce(a.purchase_cost, 0) kauf, (a.created_at at time zone 'Asia/Dubai')::date ab
    from accounts a where a.user_id in (select user_id from mit)
  ),
  arch as (
    select distinct on (e.key) e.key acc_id,
           coalesce((e.value->>'archived')::boolean, false) archiviert,
           nullif(e.value->>'successorId', '') succ,
           case when coalesce(e.value->>'at', '') ~ '^\d{4}-\d{2}-\d{2}' then ((e.value->>'at')::timestamptz at time zone 'Asia/Dubai')::date end arch_tag
    from user_settings s
    cross join lateral jsonb_each(case when jsonb_typeof(s.value) = 'object' then s.value else '{}'::jsonb end) e
    join acc on acc.id::text = e.key
    where s.key = 'archive' and jsonb_typeof(e.value) = 'object'
    order by e.key, (s.user_id = acc.user_id) desc, s.updated_at desc
  ),
  -- Hedge je Konto und Tag (Abschluss des Plans, Dubai-Tag) — dieselben zwei Wege wie kapital_ketten
  hedge as (
    select p.master_account_id acc_id, (coalesce(p.completed_at, p.ended_at, p.updated_at) at time zone 'Asia/Dubai')::date tag,
           -p.slave_pl * case when p.slave_firm ilike '%fusion%' then 1 else p_fx end betrag
    from trade_plans p join accounts sa on sa.id = p.slave_account_id
    where p.status = 'completed' and sa.account_type = 'live' and p.slave_pl is not null and p.master_account_id in (select id from acc)
    union all
    select p.master_account_id, (coalesce(p.completed_at, p.ended_at, p.updated_at) at time zone 'Asia/Dubai')::date, -p.slave_pl
    from trade_plans p
    where p.status = 'completed' and p.slave_account_id is null and p.slave_pl is not null and p.master_account_id in (select id from acc)
      and (coalesce(p.hedge_eur, 0) > 0 or (jsonb_typeof(p.mt5_baseline) = 'object' and p.mt5_baseline ? 'hedge'))
  ),
  koepfe as (
    select a.* from acc a
    where a.account_type is distinct from 'live'
      and not exists (select 1 from arch r join acc n on n.id::text = r.succ where r.acc_id = a.id::text)
  ),
  kette as (
    select k.id kopf, k.id cur, 0 tiefe from koepfe k
    union
    select kt.kopf, v.id, kt.tiefe + 1
    from kette kt join arch r on r.succ = kt.cur::text join acc v on v.id::text = r.acc_id
    where kt.tiefe < 50
  ),
  glied as (select distinct kopf, cur from kette),
  -- Kette am Tag D: läuft, wenn ein Glied bis D angelegt war und der Kopf nicht bis D archiviert (geblowt) wurde.
  -- Wert = Kauf der bis D angelegten Glieder + Hedge-Ergebnis bis D (Finn 29.10.2026 06:45: Kauf + Hedge, Payouts nicht abgezogen, geblowt = 0)
  konten as (
    select t.tag, count(distinct g.kopf) filter (where c.ab <= t.tag) n,
           coalesce(sum(case when c.ab <= t.tag then c.kauf else 0 end), 0)
           + coalesce(sum((select coalesce(sum(h.betrag), 0) from hedge h where h.acc_id = g.cur and h.tag <= t.tag)), 0) eur
    from tage t
    cross join glied g
    join koepfe k on k.id = g.kopf
    join acc c on c.id = g.cur
    left join arch ka on ka.acc_id = g.kopf::text
    where not (coalesce(ka.archiviert, false) and coalesce(ka.arch_tag, '1900-01-01'::date) <= t.tag)
      and exists (select 1 from glied g2 join acc c2 on c2.id = g2.cur where g2.kopf = g.kopf and c2.ab <= t.tag)
    group by t.tag
  ),
  -- Wallets am Tag D: jüngster Snapshot je Wallet bis D (höchstens 30 Tage alt, wie kapital_fuer)
  wal as (
    select t.tag, count(s.wallet_id) n, coalesce(sum(s.usd), 0) usd
    from tage t
    left join lateral (
      select distinct on (ws.wallet_id) ws.wallet_id, coalesce(ws.usdt, 0) + coalesce(ws.coin_usdt, 0) usd
      from wallet_snapshots ws join id_wallets w on w.id = ws.wallet_id
      where w.person_uid in (select user_id::text from mit) and ws.day <= t.tag and ws.day >= t.tag - 30
      order by ws.wallet_id, ws.day desc, ws.id
    ) s on true
    group by t.tag
  )
  select round(coalesce(w.usd, 0), 2), coalesce(w.n, 0)::int, round(coalesce(k.eur, 0), 2), coalesce(k.n, 0)::int
  from tage t left join wal w on w.tag = t.tag left join konten k on k.tag = t.tag
$function$;
revoke all on function public.kapital_rueckblick_tag(uuid, date, numeric) from public, anon, authenticated;

with kurse(tag, fx) as (values
    ('2026-10-08'::date, 0.89397),
    ('2026-10-09'::date, 0.89238),
    ('2026-10-12'::date, 0.89437),
    ('2026-10-13'::date, 0.89381),
    ('2026-10-14'::date, 0.89326),
    ('2026-10-15'::date, 0.89222),
    ('2026-10-16'::date, 0.88865),
    ('2026-10-19'::date, 0.89087),
    ('2026-10-20'::date, 0.89166),
    ('2026-10-21'::date, 0.89015),
    ('2026-10-22'::date, 0.89246),
    ('2026-10-23'::date, 0.89342),
    ('2026-10-26'::date, 0.89381),
    ('2026-10-27'::date, 0.89686),
    ('2026-10-28'::date, 0.89823)
),
tage as (
  select d::date tag,
         (select k.fx from kurse k where k.tag <= d::date order by k.tag desc limit 1) fx
  from generate_series('2026-10-08'::date, '2026-10-28'::date, interval '1 day') d
)
insert into public.kapital_tageswerte (gruppe_id, tag, ist_eur, soll_eur, abweichung_eur, teile, quelle)
select g.id, t.tag,
       round(r.wallets_usd * t.fx + r.konten_eur, 2), null, null,
       jsonb_build_object(
         'quelle', 'rueckblick', 'fx', t.fx,
         'hinweis', 'nachgerechnet 29.10.2026: nur Wallets + Kontowerte (Kauf + Hedge), Fusion/Geschäftskonto/offene Payouts erst ab 29.10.',
         'ist', jsonb_build_object('summe', round(r.wallets_usd * t.fx + r.konten_eur, 2), 'wallets', round(r.wallets_usd * t.fx, 2),
                                   'wallets_usd', r.wallets_usd, 'wallets_n', r.wallets_n, 'konten', r.konten_eur, 'konten_n', r.konten_n,
                                   'konten_regel', 'kauf_plus_hedge')),
       'rueckblick'
from public.id_gruppen g
cross join tage t
cross join lateral public.kapital_rueckblick_tag(g.id, t.tag, t.fx) r
on conflict (gruppe_id, tag) do nothing;
