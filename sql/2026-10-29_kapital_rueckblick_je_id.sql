-- ============================================================================
-- Prophos: KAPITAL — RÜCKBLICK JE ID (29.10.2026)
--
-- Finn 29.10.2026 09:35 (über den Master): „Chart größer machen, mit cleaneren Linien, und auch nach IDs filtern." Der ID-Filter im
-- Admin-Reiter „Kapital" braucht die Teile, die einer ID gehören (Kontowerte, Wallets), auch für die Rückblick-Tage 08.10.–28.10.
-- Ab 29.10. schreibt kapital_app sie selbst in teile.ist.je_id (je_id_rechnen); diese Datei ergänzt nur die Rückblick-Zeilen.
--
--   1. kapital_rueckblick_je_id(gruppe, tag, fx): dieselbe Rechnung wie kapital_rueckblick_tag (sql/2026-10-29_kapital_rueckblick.sql),
--      nur je ID — Kette = ID des Kopfes, Wallet = id_wallets.person_uid. Σ über die IDs = Gruppenwert der Rückblick-Zeile.
--      Gegenprobe 29.10.2026 (nur gelesen, Emin-Gruppe): 29.10. Σ Konten je ID 26.978,61 € = Gruppe; 08./15./22.10. ebenso.
--   2. UPDATE nur der Zeilen mit quelle = 'rueckblick': teile.ist.je_id = {user_id: {wallets, wallets_usd, wallets_n, konten, konten_n,
--      payouts_offen: 0}}, Kurs = der in der Zeile gespeicherte teile.fx (gleiche Werte wie die Gruppensumme). ist_eur, Soll und echte
--      Tageswerte bleiben unberührt.
--
-- Nur über den Service-Key (app.py) — Funktion für anon/authenticated gesperrt. Idempotent (überschreibt je_id derselben Zeilen); zurück:
--   update public.kapital_tageswerte set teile = teile #- '{ist,je_id}' where quelle = 'rueckblick';
-- ============================================================================

create or replace function public.kapital_rueckblick_je_id(p_gruppe uuid, p_tag date, p_fx numeric default 0.89)
returns table(user_id uuid, wallets_usd numeric, wallets_n integer, konten_eur numeric, konten_n integer)
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
    select t.tag, k.user_id, count(distinct g.kopf) filter (where c.ab <= t.tag) n,
           coalesce(sum(case when c.ab <= t.tag then c.kauf else 0 end), 0)
           + coalesce(sum((select coalesce(sum(h.betrag), 0) from hedge h where h.acc_id = g.cur and h.tag <= t.tag)), 0) eur
    from tage t
    cross join glied g
    join koepfe k on k.id = g.kopf
    join acc c on c.id = g.cur
    left join arch ka on ka.acc_id = g.kopf::text
    where not (coalesce(ka.archiviert, false) and coalesce(ka.arch_tag, '1900-01-01'::date) <= t.tag)
      and exists (select 1 from glied g2 join acc c2 on c2.id = g2.cur where g2.kopf = g.kopf and c2.ab <= t.tag)
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

update public.kapital_tageswerte t
set teile = jsonb_set(t.teile, '{ist,je_id}', coalesce((
      select jsonb_object_agg(r.user_id::text, jsonb_build_object(
               'wallets', round(r.wallets_usd * coalesce((t.teile->>'fx')::numeric, 0.89), 2), 'wallets_usd', r.wallets_usd,
               'wallets_n', r.wallets_n, 'konten', r.konten_eur, 'konten_n', r.konten_n, 'payouts_offen', 0))
      from public.kapital_rueckblick_je_id(t.gruppe_id, t.tag, coalesce((t.teile->>'fx')::numeric, 0.89)) r
    ), '{}'::jsonb), true)
where t.quelle = 'rueckblick' and jsonb_typeof(t.teile->'ist') = 'object';

-- Gegenprobe nach dem Einspielen (Σ je ID gegen den gespeicherten Gruppenwert der Zeile; Abweichung nur, wenn sich seit dem Rückblick-Insert
-- alte Daten geändert haben — Kaufpreis, Mitglieder, nachgetragene Snapshots):
--   select tag, gruppe_id,
--          (teile->'ist'->>'konten')::numeric - (select sum((v->>'konten')::numeric) from jsonb_each(teile->'ist'->'je_id') e(k, v)) d_konten,
--          (teile->'ist'->>'wallets_usd')::numeric - (select sum((v->>'wallets_usd')::numeric) from jsonb_each(teile->'ist'->'je_id') e(k, v)) d_wallets_usd
--   from public.kapital_tageswerte where quelle = 'rueckblick' order by tag;
