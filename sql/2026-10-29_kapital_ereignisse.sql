-- ============================================================================
-- Prophos: KAPITAL — EREIGNISSE JE TAG für den Verlauf-Grafen (29.10.2026)
--
-- Finn 29.10.2026 05:37 (Screenshot .1849, Emin, 30 Tage): „Ich versteh nicht, warum der Chart manchmal so dumm um so 3–4k [springt]."
-- Die Sprünge der Kontowerte sind Käufe, Blows und Hedge-Ergebnisse. Der Graf markiert sie; dafür je Tag und ID:
--   gekauft_n   = Ketten, deren erstes Konto an dem Tag angelegt wurde (neu gekauft)
--   gekauft_eur = Kaufpreise aller an dem Tag angelegten Konten (auch Folge-Phasen mit Kaufpreis)
--   geblowt_n   = Ketten, deren Kopf an dem Tag archiviert wurde (archive.at)
--   geblowt_eur = Wert dieser Ketten bis zu dem Tag (Kauf + Hedge) — so viel fällt aus den Kontowerten
--   hedge_eur   = Hedge-Ergebnis der an dem Tag abgeschlossenen Pläne (+ = Hedge hat verloren, Kontowert steigt)
-- Regel wie kapital_rueckblick_tag / kapital_ketten (Kette = ID des Kopfes; archivierte Ketten ohne Datum zählen nie). Damit gilt je Tag:
--   Kontowerte(D) − Kontowerte(D−1) = gekauft_eur + hedge_eur − geblowt_eur   (Gegenprobe unten).
-- Nur über den Service-Key (app.py) — für anon/authenticated gesperrt. kapital_app liest die Funktion nur, fehlt sie, bleibt der Graf ohne Marken.
-- Rücknahme: drop function public.kapital_ereignisse(uuid, numeric);
-- ============================================================================

create or replace function public.kapital_ereignisse(p_gruppe uuid, p_fx numeric default 0.89)
returns table(tag date, user_id uuid, gekauft_n integer, gekauft_eur numeric, geblowt_n integer, geblowt_eur numeric, hedge_eur numeric)
language sql stable
set search_path to 'public'
as $function$
  with recursive
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
  hedge as materialized (
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
  start as (select g.kopf, min(c.ab) tag from glied g join acc c on c.id = g.cur group by g.kopf),
  -- Ketten, die im Verlauf vorkommen (archiviert ohne Datum zählt nie), mit Blow-Tag
  kk as materialized (
    select k.id kopf, k.user_id, s.tag start, coalesce(ka.archiviert, false) archiviert, ka.arch_tag
    from koepfe k join start s on s.kopf = k.id left join arch ka on ka.acc_id = k.id::text
    where not (coalesce(ka.archiviert, false) and ka.arch_tag is null)
  ),
  -- Glieder mit ihrer Kette; nach dem Blow zählt nichts mehr (wie die Rückblick-Regel)
  gk as materialized (
    select kk.kopf, kk.user_id, kk.archiviert, kk.arch_tag, c.id acc_id, c.ab, c.kauf
    from kk join glied g on g.kopf = kk.kopf join acc c on c.id = g.cur
  ),
  neu as (select kk.start tag, kk.user_id, count(*)::int n from kk group by 1, 2),
  kauf as (select gk.ab tag, gk.user_id, sum(gk.kauf) eur from gk where not gk.archiviert or gk.ab <= gk.arch_tag group by 1, 2),
  hed as (
    select h.tag, gk.user_id, sum(h.betrag) eur from gk join hedge h on h.acc_id = gk.acc_id
    where not gk.archiviert or h.tag <= gk.arch_tag group by 1, 2
  ),
  bk as (select gk.kopf, sum(gk.kauf) s from gk where gk.archiviert and gk.ab <= gk.arch_tag group by 1),
  bh as (select gk.kopf, sum(h.betrag) s from gk join hedge h on h.acc_id = gk.acc_id where gk.archiviert and h.tag <= gk.arch_tag group by 1),
  blow as (
    select kk.arch_tag tag, kk.user_id, count(*)::int n, sum(coalesce(bk.s, 0) + coalesce(bh.s, 0)) eur
    from kk left join bk on bk.kopf = kk.kopf left join bh on bh.kopf = kk.kopf
    where kk.archiviert group by 1, 2
  ),
  tage as (select n.tag, n.user_id from neu n union select k.tag, k.user_id from kauf k union select b.tag, b.user_id from blow b
           union select h.tag, h.user_id from hed h)
  select t.tag, t.user_id, coalesce(n.n, 0), round(coalesce(k.eur, 0), 2), coalesce(b.n, 0), round(coalesce(b.eur, 0), 2), round(coalesce(h.eur, 0), 2)
  from tage t
  left join neu n on n.tag = t.tag and n.user_id = t.user_id
  left join kauf k on k.tag = t.tag and k.user_id = t.user_id
  left join blow b on b.tag = t.tag and b.user_id = t.user_id
  left join hed h on h.tag = t.tag and h.user_id = t.user_id
  where t.tag is not null
$function$;
revoke all on function public.kapital_ereignisse(uuid, numeric) from public, anon, authenticated;
