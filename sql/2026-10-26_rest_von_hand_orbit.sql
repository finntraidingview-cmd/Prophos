-- REST VON HAND MIT HEDGE (26.10.2026, Finn im Radar → Bestanden → Rest von Hand, Marc Tradeify 150k …1388 „fehlen noch 51 $"):
--   „Wenn noch so wenig fehlt, will ich das sicher gegenhedgen … auf ‚Trade planen' drücken und einfach einen Orbit-Trade machen,
--   bei dem ich das Verhältnis so auswählen kann, wie ich es will."
-- Bisher sperrte die Hedge-Kategorien-Regel (sql/2026-10-12_hedge_kategorien_regel.sql) Challenge/Phase-Konten MIT Hedge, außer mit
-- dem Schalter „Challenges mit Hedge" (je ID). Neu: Kennung rest_hedge am Plan — gesetzt nur vom Trade-Popup, wenn es über den
-- Radar-Knopf „Trade planen" für genau dieses Konto auf Orbit (tvv2 + orbit_v3) geöffnet wurde. Mit ihr lässt der Riegel den Plan durch.
-- Alles andere (normales Popup, Auto-Planer, andere Wege) bleibt unverändert gesperrt.
-- Wiederholbar. Rückbau: Funktion aus 2026-10-12_hedge_kategorien_regel.sql neu einspielen, dann
--   alter table public.trade_plans drop column if exists rest_hedge;

alter table public.trade_plans add column if not exists rest_hedge boolean not null default false;
comment on column public.trade_plans.rest_hedge is
  'Rest von Hand mit Hedge (26.10.2026): Orbit-Plan aus dem Radar-Knopf „Trade planen" — Challenge/Phase-Konto darf mit Fusion-Hedge laufen';

create or replace function public.trade_plans_kontoart_weg() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  typ text;
  kname text;
  mit boolean;
  schalter boolean := false;
begin
  if new.master_account_id is null or coalesce(new.status, 'planned') <> 'planned' then
    return new;
  end if;
  select lower(coalesce(a.account_type, '')), a.name into typ, kname from public.accounts a where a.id = new.master_account_id;
  if typ is null then
    return new;
  end if;
  mit := public.prophos_hedge_weg(new.route, new.hedge_eur, new.orbit_v3, new.winning_day);
  if mit is null then
    return new;
  end if;
  if typ in ('funded', 'funded_cfd', 'winning_days') and not mit then
    raise exception 'Funded-Konto „%" nur mit Hedge: Weg % ohne Hedge ist für Challenges — im Trade-Popup Echo, Orbit V3, Winning Day oder Topstep (mit Hedge) wählen.',
      coalesce(kname, '?'), coalesce(new.route, '?')
      using errcode = 'check_violation', hint = 'hedge_kategorien_regel';
  end if;
  -- Rest von Hand mit Hedge (26.10.2026): Orbit-Plan aus dem Radar-Knopf — nur tvv2 + orbit_v3, sonst gilt die Kennung nicht
  if coalesce(new.rest_hedge, false) and coalesce(new.route, '') = 'tvv2' and coalesce(new.orbit_v3, false) then
    return new;
  end if;
  if typ in ('challenge', 'phase1', 'phase2') and mit and coalesce(new.route, '') in ('mt5', 'mt5v2', 'tvv2', 'tsv2') then
    select coalesce((s.value->>'an')::boolean, false) into schalter
      from public.user_settings s where s.user_id = new.user_id and s.key = 'tp_challenges_mit_hedge';
    if not coalesce(schalter, false) then
      raise exception 'Challenge-/Phase-Konto „%" nur ohne Hedge: Echo V2, Orbit V2 oder Topstep V2 wählen — oder im Trade-Popup oben „Challenges mit Hedge" einschalten.',
        coalesce(kname, '?')
        using errcode = 'check_violation', hint = 'hedge_kategorien_regel';
    end if;
  end if;
  return new;
end $$;

drop trigger if exists trade_plans_kontoart_weg on public.trade_plans;
create trigger trade_plans_kontoart_weg
  before insert or update of route, hedge_eur, orbit_v3, winning_day, master_account_id, rest_hedge on public.trade_plans
  for each row execute function public.trade_plans_kontoart_weg();
