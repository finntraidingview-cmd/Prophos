-- FREMD-POSITIONEN (08.10.2026, Finn über Master: „alle Sicherheitssachen einbauen", auch für Trades, die er direkt in TradingView oder
-- MT5 klickt, ohne Plan in Prophos). Prophos kann solche Positionen nicht verhindern — es ERKENNT sie, meldet Gegenhedge und (über
-- prophos_gegenhedge_konflikt, Slave 4) zählt ihr erstes Erscheinen (seit) als Start für Finns Gegenhedge-Fenster (90 s): kein
-- gegenläufiger Start derselben Firma binnen 90 s. seit = erste Lesung der Wache (15-s-Takt) → bis ~15 s nach dem echten Klick.
--
-- Nie eingetragen (Kopien/Hedges, Slave-2-Prüfung): Fusion-Konten, Hedge-Logins der Copier, accounts.duplikum_linked, Gegenkonten
-- (slave_account_id) laufender Pläne, Plan-Tickets (mt5_baseline.ticket) — Regeln und Probe in app.py fp_erkennen.
--
-- Quellen: MT5 (quelle 'mt5') = mt5_live.status.master_positions, alle offenen Positionen des Prop-Kontos aus dem Lese-EA, gültig nur
-- frisch und ohne note; master_login = MT5-Login, ident = Ticket. TradingView/Tradovate (quelle 'tv') = echoplus_live (Userscript
-- „Prophos TV-Reader") = das gerade aktive Tradovate-Konto je PC mit positionen_ok; master_login = Kontonummer, ident =
-- Symbol:Richtung:Einstieg. TopstepX liefert keine laufenden Positionsdaten → noch nicht.
--
-- Schreiber: app.py fp_tick (Railway, eigener 15-s-Takt, Service-Key). Keine Realtime (Tabelle nicht in supabase_realtime), kein
-- Frontend-Zugriff (RLS an, keine Policy) — das Frontend bekommt die Zeilen über GET /admin/auto-plan/delta (fremd[]).
-- Aktiv = weg_at is null and zuletzt_gesehen > now() - 3 min (ohne frische Lesung verfällt eine Zeile still, statt zu raten).

create table if not exists public.fremd_positionen (
  id bigserial primary key,
  quelle text not null default 'mt5',
  master_login text not null,
  ident text not null,                       -- MT5: Ticket · TV: Symbol:Richtung:Einstieg
  konto_id uuid references public.accounts(id) on delete set null,
  user_id uuid,
  firma text,
  firma_key text generated always as (public.prophos_firma_key(firma)) stored,
  konto_name text,
  account_type text,
  richtung text not null check (richtung in ('buy', 'sell')),
  symbol text,
  menge numeric,
  seit timestamptz not null default now(),
  zuletzt_gesehen timestamptz not null default now(),
  weg_at timestamptz,
  gegen jsonb,                               -- letzte Konflikt-Lesung von fp_tick (prophos_fremd_konflikte)
  alarm_keys text[] not null default '{}',   -- schon gemeldete Konflikte (je Gegenüber einmal Push)
  unique (quelle, master_login, ident)
);

create index if not exists fremd_positionen_offen on public.fremd_positionen (firma_key, richtung) where weg_at is null;

alter table public.fremd_positionen enable row level security;   -- nur Service-Key (app.py)

-- Konflikte der aktiven Fremd-Positionen nach Finns Gegenhedge-Fenster (08.10.2026: erst 3 min, dann „stellt das Ganze bitte auf 90
-- Sekunden"): ein gegenläufiger START derselben Firma binnen ± Fenster um das erste Erscheinen der Fremd-Position (seit) — anderes Konto
-- (jede andere ID oder ein anderes Konto derselben ID; ohne Konto zählt als anderes). Ein laufender Trade allein ist kein Konflikt.
-- Start eines Plans = started_at, sonst Orbit gesendet / Start-Claim; Hand gegen Hand = beide seit. Fenster aus Slave 4s
-- prophos_gegenhedge_fenster() (sql/2026-10-08_gegenhedge_90s.sql, „hier und nur hier ändern") — fehlt sie noch, 90 s; die Reihenfolge
-- beider Dateien ist damit egal. Nur für Alarm (Push) und die rote Zeile; den Start-Riegel macht prophos_gegenhedge_konflikt.
create or replace function public.prophos_fremd_konflikte()
returns table(fremd_id bigint, art text, gegen_id text, gegen_user uuid, gegen_konto text, gegen_richtung text, gegen_seit timestamptz)
language plpgsql stable security definer set search_path to 'public'
as $$
declare
  w interval := interval '90 seconds';
begin
  if to_regprocedure('public.prophos_gegenhedge_fenster()') is not null then
    execute 'select public.prophos_gegenhedge_fenster()' into w;
  end if;
  return query
  with f as (
    select * from public.fremd_positionen x
     where x.weg_at is null and x.zuletzt_gesehen > now() - interval '3 minutes'
  ), p as (
    select t.id, t.user_id, t.master_name, t.master_account_id, t.richtung,
           public.prophos_firma_key(t.master_firm) as firma_key,
           coalesce(t.started_at, t.orbit_gesendet_at, t.start_um_gestartet_at) as start
      from public.trade_plans t
     where t.status in ('planned', 'open', 'review', 'completed')
       and coalesce(t.started_at, t.orbit_gesendet_at, t.start_um_gestartet_at) > now() - interval '1 day'
  )
  select f.id, 'plan'::text, p.id::text, p.user_id, p.master_name, p.richtung, p.start
    from f
    join p on p.firma_key = f.firma_key
          and p.richtung = case f.richtung when 'buy' then 'sell' else 'buy' end
          and p.master_account_id is distinct from f.konto_id
          and p.start between f.seit - w and f.seit + w
  union all
  select f.id, 'hand'::text, g.id::text, g.user_id, g.konto_name, g.richtung, g.seit
    from f
    join public.fremd_positionen g
      on g.firma_key = f.firma_key and g.richtung <> f.richtung and g.id <> f.id
     and g.konto_id is distinct from f.konto_id
     and g.seit between f.seit - w and f.seit + w;
end $$;

revoke all on function public.prophos_fremd_konflikte() from public, anon, authenticated;
grant execute on function public.prophos_fremd_konflikte() to service_role;
