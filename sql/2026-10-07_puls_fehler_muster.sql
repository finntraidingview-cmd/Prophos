-- PULS-FEHLER-MUSTER (07.10.2026, Finn: „wie wir Fehlstarts von Puls-Bots analysieren können, und wenn es öfter die gleichen sind,
-- genau diese Fehler eliminieren"). Bisher stand ein Fehlstart zur Startzeit nur in trade_plans.mt5_baseline.start_fehler und wurde
-- beim nächsten Versuch überschrieben. Jetzt:
--   puls_fehlstarts      jeder rote Start (prophos.html sfMelden schreibt eine Zeile, eigene ID per RLS)
--   puls_fehler_muster   Auswertung beider Quellen (puls_fehlstarts + order_signale status 'fehler') je Muster:
--                        Schritt + Meldung ohne Zahlen/Kontonummern → Anzahl 24 h / 7 Tage / 30 Tage, PCs, IDs, letzte Meldung.
-- Abfrage für Claude steht in .claude/fehler-analyse.md.

create table if not exists public.puls_fehlstarts (
  id bigserial primary key,
  at timestamptz not null default now(),
  user_id uuid not null default auth.uid(),
  plan_id text, route text, firma text, konto text, pc text, login text,
  schritt text, msg text, unklar boolean default false,
  quelle text default 'start_um'
);
create index if not exists puls_fehlstarts_at on public.puls_fehlstarts (at desc);
alter table public.puls_fehlstarts enable row level security;
drop policy if exists puls_fehlstarts_ins on public.puls_fehlstarts;
create policy puls_fehlstarts_ins on public.puls_fehlstarts for insert to authenticated with check (user_id = auth.uid());
drop policy if exists puls_fehlstarts_sel on public.puls_fehlstarts;
create policy puls_fehlstarts_sel on public.puls_fehlstarts for select to authenticated using (user_id = auth.uid());

-- Muster: klein, Kontonummern/Zahlen → #, Anführungs-Inhalte → …, auf 90 Zeichen
create or replace function public.puls_fehler_muster_text(schritt text, msg text) returns text
language sql immutable as $$
  select coalesce(nullif(schritt, ''), '?') || ': ' || left(trim(regexp_replace(regexp_replace(regexp_replace(lower(coalesce(msg, '')),
    '[a-z]*[0-9][a-z0-9.,:/-]*', '#', 'g'), '„[^“”"]*[“”"]', '„…"', 'g'), '\s+', ' ', 'g')), 90)
$$;

create or replace view public.puls_fehler_ereignisse with (security_invoker = true) as
  select f.at, f.user_id, f.plan_id, f.route, f.pc, f.schritt, f.msg, f.unklar, 'start_um'::text as quelle
    from public.puls_fehlstarts f
  union all
  select s.created_at, s.user_id, s.plan_id, null, s.pc,
         coalesce(s.ergebnis->>'schritt', s.ergebnis->>'code', s.params->>'aktion', 'signal'), s.ergebnis->>'msg',
         coalesce((s.ergebnis->>'unklar')::boolean, false), 'signal'
    from public.order_signale s where s.status = 'fehler';

create or replace view public.puls_fehler_muster with (security_invoker = true) as
  select public.puls_fehler_muster_text(e.schritt, e.msg) as muster,
         count(*) filter (where e.at > now() - interval '24 hours') as n_24h,
         count(*) filter (where e.at > now() - interval '7 days') as n_7d,
         count(*) filter (where e.at > now() - interval '30 days') as n_30d,
         count(*) filter (where e.unklar) as n_unklar,
         array_agg(distinct e.pc) filter (where e.pc is not null) as pcs,
         count(distinct e.user_id) as ids,
         max(e.at) as zuletzt,
         (array_agg(e.msg order by e.at desc))[1] as beispiel
    from public.puls_fehler_ereignisse e
   group by 1;

-- Rückwirkend: die heute noch stehenden start_fehler der Pläne (je Plan nur der letzte Stand)
insert into public.puls_fehlstarts (at, user_id, plan_id, route, firma, konto, pc, login, schritt, msg, unklar, quelle)
select coalesce((tp.mt5_baseline->'start_fehler'->>'at')::timestamptz, tp.updated_at), tp.user_id, tp.id::text, tp.route, tp.master_firm,
       tp.master_name, tp.mt5_baseline->'start_fehler'->>'pc', tp.mt5_baseline->'start_fehler'->>'login',
       tp.mt5_baseline->'start_fehler'->>'schritt', tp.mt5_baseline->'start_fehler'->>'msg',
       coalesce((tp.mt5_baseline->'start_fehler'->>'unklar')::boolean, false), 'rueckwirkend'
  from public.trade_plans tp
 where tp.mt5_baseline->'start_fehler' is not null
   and not exists (select 1 from public.puls_fehlstarts f where f.plan_id = tp.id::text and f.quelle = 'rueckwirkend');
