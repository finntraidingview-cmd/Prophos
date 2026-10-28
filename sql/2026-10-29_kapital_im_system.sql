-- ============================================================================
-- Prophos: KAPITAL IM SYSTEM je Gruppe (29.10.2026)
--
-- Finn (50 % an der Emin-Gruppe, legt demnächst weitere 5.000 $ nach) will eine Zahl, die zeigt, ob Geld abgezweigt wird.
-- Seine Logik: jedes Prop-Konto ist auf Fusion gegengehedgt, also bleibt das Kapital im System nahezu gleich — blowt ein Konto,
-- gewinnt der Hedge ungefähr dessen Wert; besteht es, steckt das Geld im Konto und wird zum Payout. Weniger wird es nur durch
-- Reibung. Fällt die Zahl deutlich stärker als die Reibung, fehlt Geld.
--
--   Ist  = Wallets (letzter wallet_snapshots-Tag) + Fusion-Balance (eingetragen) + Σ Gesamtkosten der laufenden Ketten (Boden 0)
--          + offene Payouts (pending_payouts status pending)
--   Soll = Σ Einlagen − Reibung (beendete Ketten, deren Kosten der Hedge nicht zurückgeholt hat) + Gewinne (beendete Ketten im
--          Plus + laufende Ketten im Plus) − Gebühren (wallet_tx Kategorie „Gebühr")
--
-- Finn hat am 29.10.2026 bestätigt: laufendes Konto = Gesamtkosten wie die Accounts-Kachel (Kauf + Hedge der ganzen Kette − Payouts,
-- Boden 0), Funded genauso, ein Konto im Plus zählt 0 und sein Überschuss geht als Gewinn in die Soll-Linie; Kasse 0xc27c… wird
-- Gruppen-Wallet (unter Emin); gerechnet wird in US-Dollar.
--
-- Gelesen und geschrieben wird NUR über app.py (/admin/kapital, Service-Key, nur Voll-Admins wie Liquide/Kunden-Zahlungen) — die
-- Tabellen haben RLS ohne Policy, die Funktion ist für anon/authenticated gesperrt. Idempotent.
-- ============================================================================

-- Einlagen der Investoren (Betrag, Datum, Ziel-Wallet). quelle_tx = wallet_tx.tx_key, wenn die Einlage aus einem Zufluss übernommen
-- wurde (Knopf „als Einlage") — unique, damit derselbe Zufluss nie zweimal zählt.
create table if not exists public.kapital_einlagen (
  id           uuid primary key default gen_random_uuid(),
  gruppe_id    uuid not null references public.id_gruppen(id) on delete cascade,
  betrag_usd   numeric not null check (betrag_usd > 0),
  datum        date not null default current_date,
  ziel_wallet  text,
  notiz        text,
  quelle_tx    text unique,
  angelegt_von text,
  created_at   timestamptz not null default now()
);
create index if not exists kapital_einlagen_gruppe_idx on public.kapital_einlagen (gruppe_id, datum);

-- Fusion-Balance von Hand (Prophos liest Fusion nicht live: meta_api_balance der Fusion-Konten steht seit 22.09.2026). Jede Eingabe
-- eine Zeile, es gilt die jüngste. Fusion rechnet in Euro (FIRM_PRESETS fusion currency €) → waehrung mitspeichern.
create table if not exists public.kapital_fusion (
  id          uuid primary key default gen_random_uuid(),
  gruppe_id   uuid not null references public.id_gruppen(id) on delete cascade,
  betrag      numeric not null check (betrag >= 0),
  waehrung    text not null default 'EUR' check (waehrung in ('EUR','USD')),
  stand_am    date not null default current_date,
  notiz       text,
  angelegt_von text,
  created_at  timestamptz not null default now()
);
create index if not exists kapital_fusion_gruppe_idx on public.kapital_fusion (gruppe_id, created_at desc);

-- Tageswerte für den Verlauf (eine Zeile je Gruppe und Tag, der letzte Lauf des Tages gewinnt). teile = Aufschlüsselung.
create table if not exists public.kapital_tageswerte (
  gruppe_id      uuid not null references public.id_gruppen(id) on delete cascade,
  tag            date not null,
  ist_usd        numeric not null,
  soll_usd       numeric not null,
  abweichung_usd numeric not null,
  teile          jsonb not null default '{}'::jsonb,
  updated_at     timestamptz not null default now(),
  primary key (gruppe_id, tag)
);

alter table public.kapital_einlagen   enable row level security;
alter table public.kapital_fusion     enable row level security;
alter table public.kapital_tageswerte enable row level security;

-- Ketten je Gruppe — 1:1 calcReingesteckdEur(acc, {netPayouts:true, mitWdHedge:true}) aus prophos.html, nur serverseitig für alle
-- IDs der Gruppe auf einmal: je Kette (Kopf = Konto ohne gültigen Nachfolger, rückwärts über archive.successorId)
--   Kauf (purchase_cost) + Live-Hedge (abgeschlossene Pläne mit Live-Slave: −slave_pl, Fusion in €, sonst × p_fx)
--   + WD-Fusion-Hedge (Pläne ohne Slave-Konto mit hedge_eur > 0 oder mt5_baseline.hedge: −slave_pl, schon €) − Payouts (€)
--   − offene Payouts (Abweichung zur Accounts-Kachel, s. u.).
-- Archiv-Status liegt in user_settings key=archive (aus dem localStorage gesynct, zwischen Profilen vermischt) — je Konto gilt der
-- Eintrag aus dem Profil des Besitzers, sonst der jüngste.
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
acc as (
  select a.id, a.user_id, a.name, a.firm, a.account_type, a.external_id, coalesce(a.purchase_cost, 0) kauf
  from accounts a where a.user_id in (select user_id from mit)
),
arch as (
  select distinct on (e.key) e.key acc_id,
         coalesce((e.value->>'archived')::boolean, false) archiviert,
         nullif(e.value->>'successorId', '') succ
  from user_settings s
  cross join lateral jsonb_each(case when jsonb_typeof(s.value) = 'object' then s.value else '{}'::jsonb end) e
  join acc on acc.id::text = e.key
  where s.key = 'archive' and jsonb_typeof(e.value) = 'object'
  order by e.key, (s.user_id = acc.user_id) desc, s.updated_at desc
),
eigen as (
  select a.id,
    a.kauf,
    coalesce((select sum(-p.slave_pl * case when p.slave_firm ilike '%fusion%' then 1 else p_fx end)
              from trade_plans p join accounts sa on sa.id = p.slave_account_id
              where p.status = 'completed' and p.master_account_id = a.id and sa.account_type = 'live' and p.slave_pl is not null), 0)
    + coalesce((select sum(-p.slave_pl) from trade_plans p
              where p.status = 'completed' and p.master_account_id = a.id and p.slave_account_id is null and p.slave_pl is not null
                and (coalesce(p.hedge_eur, 0) > 0 or (jsonb_typeof(p.mt5_baseline) = 'object' and p.mt5_baseline ? 'hedge'))), 0) hedge,
    coalesce((select sum(t.amount) from transactions t where t.kind = 'payout' and t.account_id = a.id), 0)
    -- offene Payouts (pending_payouts status pending) wie empfangene abziehen: sie stehen auf der Ist-Seite als „offene Payouts",
    -- sonst zählte dasselbe Geld im Konto UND unterwegs. USD-Anträge × p_fx in €, wie die Konten-Kosten.
    + coalesce((select sum(pp.amount * case when pp.currency = 'USD' then p_fx else 1 end) from pending_payouts pp
              where pp.status = 'pending' and pp.account_id = a.id), 0) payouts
  from acc a
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
select k.id, k.user_id, k.name, k.firm, k.account_type, k.external_id,
       coalesce((select r.archiviert from arch r where r.acc_id = k.id::text), false),
       (select count(distinct kt.cur)::int from kette kt where kt.kopf = k.id),
       round(sum(e.kauf), 2), round(sum(e.hedge), 2), round(sum(e.payouts), 2), round(sum(e.kauf + e.hedge - e.payouts), 2)
from koepfe k
join (select distinct kopf, cur from kette) kt on kt.kopf = k.id
join eigen e on e.id = kt.cur
group by k.id, k.user_id, k.name, k.firm, k.account_type, k.external_id;
$$;

revoke all on function public.kapital_ketten(uuid, numeric) from public, anon, authenticated;
grant execute on function public.kapital_ketten(uuid, numeric) to service_role;

-- Kasse der Emin-Gruppe als Gruppen-Wallet (Finn 29.10.2026: „Als Gruppen-Wallet"): unter Emin in id_wallets, damit Stand und Transfers
-- im Reiter Meta Wallet mitlaufen und Emin → Kasse als interner Transfer zählt. Gleiche EVM-Adresse auf Ethereum und Arbitrum
-- (beide Ketten tragen Transfers mit der Kasse). Nur einfügen, wenn noch nicht da.
insert into public.id_wallets (person_uid, person_name, chain, address)
select '6cceb3f3-dc78-48ee-8668-26081da3e70f', 'Emin', c.chain, '0xc27cCb6c7e64F4A2567E447B2cC9a475886c3c00'
from (values ('ethereum'), ('arbitrum')) c(chain)
where not exists (select 1 from public.id_wallets w
                  where lower(w.address) = lower('0xc27cCb6c7e64F4A2567E447B2cC9a475886c3c00') and w.chain = c.chain);
