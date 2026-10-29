-- ============================================================================
-- Prophos: KAPITAL — kapital_ketten SCHNELL (29.10.2026)
--
-- Finn 29.10.2026 (Screenshot .1849): Admin → Gruppe Hermann Technologies → Kapital zeigt „Kapital nicht verfügbar: HTTPError: 500 …
-- /rest/v1/rpc/kapital_ketten", Emin geht. Ursache (explain analyze): kapital_ketten für HT 7,6 s bei 871 Ketten — der authenticator hat
-- statement_timeout 8 s. Die Zeit steckte zu > 99 % in den korrelierten Unterabfragen von „eigen" (Hedge je Konto, Payouts je Konto):
-- eigen wurde eingebettet und dabei je Konto ZWEIMAL ausgewertet, jede Hedge-Unterabfrage ein Seq Scan über trade_plans (kein Index auf
-- master_account_id) → 1.081 Konten × 4 × ~1,7 ms. Dazu je Kopf zwei Unterabfragen über arch/kette (~0,3 s).
--
-- Neu: Hedge und Payouts einmal gruppiert je Konto (h_live, h_ohne, po_tx, po_pend → eigen MATERIALIZED), archiviert und Glieder per Join.
-- Logik, Filter, Rundung und Rückgabe unverändert (alle Beträge numeric → Summen exakt gleich). Kein Index nötig.
-- Gemessen (nur gelesen, Funktionsrumpf mit Parametern): HT 7.567 ms → 45 ms. Gegenprobe alt (laufende Funktion) vs. neu (Rumpf aus dieser
-- Datei), fx 0,8982: HT 871 = 871 Zeilen, (alt except neu) = 0, (neu except alt) = 0; HT + Emin zusammen 1.042 = 1.042, beide except = 0.
--
-- Dasselbe Muster in kapital_rueckblick_tag / kapital_rueckblick_je_id (Hedge bis Tag als korrelierte Unterabfrage je Glied, exists je Zeile;
-- HT ~1,2 s je Tag): hedge_bis + kopf_ab einmal je Aufruf. Gemessen HT 22.10.: 1.160 ms → 44 ms. Gegenprobe: rueckblick_tag HT 22.10.
-- alt = neu (1181,98 $ · 15 Wallets · 114.506,71 € · 170 Ketten); rueckblick_je_id HT 26.10. 15 = 15 Zeilen, beide except = 0.
-- Beide laufen nur über den Service-Key.
--
-- RÜCKNAHME: die alten Fassungen erneut einspielen —
--   kapital_rueckblick_tag:   Funktionsblock aus sql/2026-10-29_kapital_rueckblick.sql
--   kapital_rueckblick_je_id: Funktionsblock aus sql/2026-10-29_kapital_rueckblick_je_id.sql
--   kapital_ketten (bis 29.10.2026, = sql/2026-10-29_kapital_im_system.sql):
--   create or replace function public.kapital_ketten(p_gruppe uuid, p_fx numeric default 0.85)
--   returns table (
--     kopf_id uuid, user_id uuid, name text, firm text, account_type text, external_id text,
--     archiviert boolean, glieder int, kauf_eur numeric, hedge_eur numeric, payouts_eur numeric, gk_eur numeric
--   )
--   language sql stable
--   set search_path = public
--   as $$
--   with recursive
--   mit as (select m.user_id from id_gruppe_mitglied m where m.gruppe_id = p_gruppe),
--   acc as (
--     select a.id, a.user_id, a.name, a.firm, a.account_type, a.external_id, coalesce(a.purchase_cost, 0) kauf
--     from accounts a where a.user_id in (select user_id from mit)
--   ),
--   arch as (
--     select distinct on (e.key) e.key acc_id,
--            coalesce((e.value->>'archived')::boolean, false) archiviert,
--            nullif(e.value->>'successorId', '') succ
--     from user_settings s
--     cross join lateral jsonb_each(case when jsonb_typeof(s.value) = 'object' then s.value else '{}'::jsonb end) e
--     join acc on acc.id::text = e.key
--     where s.key = 'archive' and jsonb_typeof(e.value) = 'object'
--     order by e.key, (s.user_id = acc.user_id) desc, s.updated_at desc
--   ),
--   eigen as (
--     select a.id,
--       a.kauf,
--       coalesce((select sum(-p.slave_pl * case when p.slave_firm ilike '%fusion%' then 1 else p_fx end)
--                 from trade_plans p join accounts sa on sa.id = p.slave_account_id
--                 where p.status = 'completed' and p.master_account_id = a.id and sa.account_type = 'live' and p.slave_pl is not null), 0)
--       + coalesce((select sum(-p.slave_pl) from trade_plans p
--                 where p.status = 'completed' and p.master_account_id = a.id and p.slave_account_id is null and p.slave_pl is not null
--                   and (coalesce(p.hedge_eur, 0) > 0 or (jsonb_typeof(p.mt5_baseline) = 'object' and p.mt5_baseline ? 'hedge'))), 0) hedge,
--       coalesce((select sum(t.amount) from transactions t where t.kind = 'payout' and t.account_id = a.id), 0)
--       -- offene Payouts (pending_payouts status pending) wie empfangene abziehen: sie stehen auf der Ist-Seite als „offene Payouts",
--       -- sonst zählte dasselbe Geld im Konto UND unterwegs. USD-Anträge × p_fx in €, wie die Konten-Kosten.
--       + coalesce((select sum(pp.amount * case when pp.currency = 'USD' then p_fx else 1 end) from pending_payouts pp
--                 where pp.status = 'pending' and pp.account_id = a.id), 0) payouts
--     from acc a
--   ),
--   koepfe as (
--     select a.* from acc a
--     where a.account_type is distinct from 'live'
--       and not exists (select 1 from arch r join acc n on n.id::text = r.succ where r.acc_id = a.id::text)
--   ),
--   kette as (
--     select k.id kopf, k.id cur, 0 tiefe from koepfe k
--     union
--     select kt.kopf, v.id, kt.tiefe + 1
--     from kette kt
--     join arch r on r.succ = kt.cur::text
--     join acc v on v.id::text = r.acc_id
--     where kt.tiefe < 50
--   )
--   select k.id, k.user_id, k.name, k.firm, k.account_type, k.external_id,
--          coalesce((select r.archiviert from arch r where r.acc_id = k.id::text), false),
--          (select count(distinct kt.cur)::int from kette kt where kt.kopf = k.id),
--          round(sum(e.kauf), 2), round(sum(e.hedge), 2), round(sum(e.payouts), 2), round(sum(e.kauf + e.hedge - e.payouts), 2)
--   from koepfe k
--   join (select distinct kopf, cur from kette) kt on kt.kopf = k.id
--   join eigen e on e.id = kt.cur
--   group by k.id, k.user_id, k.name, k.firm, k.account_type, k.external_id;
--   $$;
--
--   revoke all on function public.kapital_ketten(uuid, numeric) from public, anon, authenticated;
--   grant execute on function public.kapital_ketten(uuid, numeric) to service_role;
-- ============================================================================

create or replace function public.kapital_ketten(p_gruppe uuid, p_fx numeric default 0.85)
returns table (
  kopf_id uuid, user_id uuid, name text, firm text, account_type text, external_id text,
  archiviert boolean, glieder int, kauf_eur numeric, hedge_eur numeric, payouts_eur numeric, gk_eur numeric
)
language sql stable
set search_path = public
as $$
with recursive
mit as (select m.user_id from id_gruppe_mitglied m where m.gruppe_id = p_gruppe),
acc as materialized (
  select a.id, a.user_id, a.name, a.firm, a.account_type, a.external_id, coalesce(a.purchase_cost, 0) kauf
  from accounts a where a.user_id in (select user_id from mit)
),
arch as materialized (
  select distinct on (e.key) e.key acc_id,
         coalesce((e.value->>'archived')::boolean, false) archiviert,
         nullif(e.value->>'successorId', '') succ
  from user_settings s
  cross join lateral jsonb_each(case when jsonb_typeof(s.value) = 'object' then s.value else '{}'::jsonb end) e
  join acc on acc.id::text = e.key
  where s.key = 'archive' and jsonb_typeof(e.value) = 'object'
  order by e.key, (s.user_id = acc.user_id) desc, s.updated_at desc
),
-- Hedge und Payouts EINMAL je Konto gruppiert (statt korrelierter Unterabfrage je Konto — die lief doppelt und je Konto als Seq Scan
-- über trade_plans: HT 1.081 Konten × 4 × ~1,7 ms ≈ 7,6 s). Gleiche Filter wie vorher, gleiche Summen (alles numeric).
h_live as (
  select p.master_account_id id, sum(-p.slave_pl * case when p.slave_firm ilike '%fusion%' then 1 else p_fx end) s
  from trade_plans p join accounts sa on sa.id = p.slave_account_id
  where p.status = 'completed' and sa.account_type = 'live' and p.slave_pl is not null and p.master_account_id in (select id from acc)
  group by p.master_account_id
),
h_ohne as (
  select p.master_account_id id, sum(-p.slave_pl) s from trade_plans p
  where p.status = 'completed' and p.slave_account_id is null and p.slave_pl is not null and p.master_account_id in (select id from acc)
    and (coalesce(p.hedge_eur, 0) > 0 or (jsonb_typeof(p.mt5_baseline) = 'object' and p.mt5_baseline ? 'hedge'))
  group by p.master_account_id
),
po_tx as (
  select t.account_id id, sum(t.amount) s from transactions t
  where t.kind = 'payout' and t.account_id in (select id from acc) group by t.account_id
),
-- offene Payouts (pending_payouts status pending) wie empfangene abziehen: sie stehen auf der Ist-Seite als „offene Payouts",
-- sonst zählte dasselbe Geld im Konto UND unterwegs. USD-Anträge × p_fx in €, wie die Konten-Kosten.
po_pend as (
  select pp.account_id id, sum(pp.amount * case when pp.currency = 'USD' then p_fx else 1 end) s from pending_payouts pp
  where pp.status = 'pending' and pp.account_id in (select id from acc) group by pp.account_id
),
eigen as materialized (
  select a.id, a.kauf,
         coalesce(hl.s, 0) + coalesce(ho.s, 0) hedge,
         coalesce(pt.s, 0) + coalesce(pe.s, 0) payouts
  from acc a
  left join h_live hl on hl.id = a.id
  left join h_ohne ho on ho.id = a.id
  left join po_tx pt on pt.id = a.id
  left join po_pend pe on pe.id = a.id
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
  from kette kt
  join arch r on r.succ = kt.cur::text
  join acc v on v.id::text = r.acc_id
  where kt.tiefe < 50
)
-- archiviert und Glieder per Join statt Unterabfrage je Kopf (arch hat je Konto genau eine Zeile; kt ist schon distinct je Kopf × Glied)
select k.id, k.user_id, k.name, k.firm, k.account_type, k.external_id,
       coalesce(ra.archiviert, false),
       count(distinct kt.cur)::int,
       round(sum(e.kauf), 2), round(sum(e.hedge), 2), round(sum(e.payouts), 2), round(sum(e.kauf + e.hedge - e.payouts), 2)
from koepfe k
join (select distinct kopf, cur from kette) kt on kt.kopf = k.id
join eigen e on e.id = kt.cur
left join arch ra on ra.acc_id = k.id::text
group by k.id, k.user_id, k.name, k.firm, k.account_type, k.external_id, ra.archiviert;
$$;

revoke all on function public.kapital_ketten(uuid, numeric) from public, anon, authenticated;
grant execute on function public.kapital_ketten(uuid, numeric) to service_role;

create or replace function public.kapital_rueckblick_tag(p_gruppe uuid, p_tag date, p_fx numeric default 0.89)
returns table(wallets_usd numeric, wallets_n integer, konten_eur numeric, konten_n integer)
language sql stable
set search_path to 'public'
as $function$
  with recursive
  tage as (select p_tag tag),
  mit as (select m.user_id from id_gruppe_mitglied m where m.gruppe_id = p_gruppe),
  acc as materialized (
    select a.id, a.user_id, a.account_type, coalesce(a.purchase_cost, 0) kauf, (a.created_at at time zone 'Asia/Dubai')::date ab
    from accounts a where a.user_id in (select user_id from mit)
  ),
  arch as materialized (
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
  glied as materialized (select distinct kopf, cur from kette),
  -- Hedge bis zum Tag EINMAL je Konto summiert und der früheste Anlagetag je Kette (statt korrelierter Unterabfrage bzw. exists je Zeile —
  -- HT ~1,2 s je Tag, 29.10.2026). Gleiche Summen: Σ je Glied über die Glieder einer Kette, Konten ohne Hedge zählen 0.
  hedge_bis as (select h.acc_id, sum(h.betrag) s from hedge h join tage t on h.tag <= t.tag group by h.acc_id),
  kopf_ab as (select g.kopf, min(c.ab) ab from glied g join acc c on c.id = g.cur group by g.kopf),
  -- Kette am Tag D: läuft, wenn ein Glied bis D angelegt war und der Kopf nicht bis D archiviert (geblowt) wurde.
  -- Wert = Kauf der bis D angelegten Glieder + Hedge-Ergebnis bis D (Finn 29.10.2026 06:45: Kauf + Hedge, Payouts nicht abgezogen, geblowt = 0)
  konten as (
    select t.tag, count(distinct g.kopf) filter (where c.ab <= t.tag) n,
           coalesce(sum(case when c.ab <= t.tag then c.kauf else 0 end), 0)
           + coalesce(sum(hb.s), 0) eur
    from tage t
    cross join glied g
    join koepfe k on k.id = g.kopf
    join acc c on c.id = g.cur
    left join arch ka on ka.acc_id = g.kopf::text
    left join hedge_bis hb on hb.acc_id = g.cur
    join kopf_ab kb on kb.kopf = g.kopf
    where not (coalesce(ka.archiviert, false) and coalesce(ka.arch_tag, '1900-01-01'::date) <= t.tag)
      and kb.ab <= t.tag
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

create or replace function public.kapital_rueckblick_je_id(p_gruppe uuid, p_tag date, p_fx numeric default 0.89)
returns table(user_id uuid, wallets_usd numeric, wallets_n integer, konten_eur numeric, konten_n integer)
language sql stable
set search_path to 'public'
as $function$
  with recursive
  tage as (select p_tag tag),
  mit as (select m.user_id from id_gruppe_mitglied m where m.gruppe_id = p_gruppe),
  acc as materialized (
    select a.id, a.user_id, a.account_type, coalesce(a.purchase_cost, 0) kauf, (a.created_at at time zone 'Asia/Dubai')::date ab
    from accounts a where a.user_id in (select user_id from mit)
  ),
  arch as materialized (
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
  glied as materialized (select distinct kopf, cur from kette),
  -- Hedge bis zum Tag EINMAL je Konto summiert und der früheste Anlagetag je Kette (statt korrelierter Unterabfrage bzw. exists je Zeile —
  -- HT ~1,2 s je Tag, 29.10.2026). Gleiche Summen: Σ je Glied über die Glieder einer Kette, Konten ohne Hedge zählen 0.
  hedge_bis as (select h.acc_id, sum(h.betrag) s from hedge h join tage t on h.tag <= t.tag group by h.acc_id),
  kopf_ab as (select g.kopf, min(c.ab) ab from glied g join acc c on c.id = g.cur group by g.kopf),
  -- Kette am Tag D: läuft, wenn ein Glied bis D angelegt war und der Kopf nicht bis D archiviert (geblowt) wurde.
  -- Wert = Kauf der bis D angelegten Glieder + Hedge-Ergebnis bis D (Finn 29.10.2026 06:45: Kauf + Hedge, Payouts nicht abgezogen, geblowt = 0)
  konten as (
    select t.tag, k.user_id, count(distinct g.kopf) filter (where c.ab <= t.tag) n,
           coalesce(sum(case when c.ab <= t.tag then c.kauf else 0 end), 0)
           + coalesce(sum(hb.s), 0) eur
    from tage t
    cross join glied g
    join koepfe k on k.id = g.kopf
    join acc c on c.id = g.cur
    left join arch ka on ka.acc_id = g.kopf::text
    left join hedge_bis hb on hb.acc_id = g.cur
    join kopf_ab kb on kb.kopf = g.kopf
    where not (coalesce(ka.archiviert, false) and coalesce(ka.arch_tag, '1900-01-01'::date) <= t.tag)
      and kb.ab <= t.tag
    group by t.tag, k.user_id
  ),
  -- Wallets am Tag D: jüngster Snapshot je Wallet bis D (höchstens 30 Tage alt, wie kapital_fuer)
  wal as (
    select t.tag, s.uid, count(s.wallet_id) n, coalesce(sum(s.usd), 0) usd
    from tage t
    join lateral (
      select distinct on (ws.wallet_id) ws.wallet_id, w.person_uid uid, coalesce(ws.usdt, 0) + coalesce(ws.coin_usdt, 0) usd
      from wallet_snapshots ws join id_wallets w on w.id = ws.wallet_id
      where w.person_uid in (select user_id::text from mit) and ws.day <= t.tag and ws.day >= t.tag - 30
      order by ws.wallet_id, ws.day desc, ws.id
    ) s on true
    group by t.tag, s.uid
  )
  select m.user_id, round(coalesce(w.usd, 0), 2), coalesce(w.n, 0)::int, round(coalesce(k.eur, 0), 2), coalesce(k.n, 0)::int
  from tage t cross join mit m
  left join wal w on w.tag = t.tag and w.uid = m.user_id::text
  left join konten k on k.tag = t.tag and k.user_id = m.user_id
$function$;
revoke all on function public.kapital_rueckblick_je_id(uuid, date, numeric) from public, anon, authenticated;
