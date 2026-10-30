-- KONTO DEAKTIVIERT (Finn 30.10.2026 14:2x: „The5ers lässt nur einen 200k-Account gleichzeitig zu. …0448 wurde temporär deaktiviert. Markier den in Prophos als deaktiviert, ich aktiviere
-- ihn später wieder."). Reiner Merker am Konto: accounts.deaktiviert_at (null = aktiv). Planer schlagen das Konto nicht vor, Puls startet dort nichts. Kein Archiv, kein Waiting, kein
-- Kosten-/Bilanz-Effekt. auto_planer reicht nicht: er ist Finns eigener Haken (beim Aktivieren wüsste niemand mehr, wie er stand) und hält keinen Start auf.
-- Netz am Claim (wie trade_plans_a0_hedge_freigabe): Plan eines deaktivierten Kontos startet nicht, start_um rückt je 15–30 min weiter, Marke mt5_baseline.start_sperre art 'konto_deaktiviert',
-- damit ein alter Plan beim Aktivieren nicht „überfällig" losläuft. Fehlt die Spalte, gibt es den Trigger nicht: Datei läuft als Ganzes. Wiederholbar.
-- REIHENFOLGE: vor dem Push einspielen ist nicht nötig (app.py: Spalte fehlt → niemand deaktiviert), aber das Frontend-Setzen braucht sie.
-- Rückbau: drop trigger trade_plans_a00_konto_deaktiviert on public.trade_plans; Spalte kann bleiben.
alter table public.accounts add column if not exists deaktiviert_at timestamptz;
comment on column public.accounts.deaktiviert_at is 'Konto vorübergehend deaktiviert (z. B. Firma erlaubt nur ein Konto dieser Größe): kein Vorschlag, kein Start. null = aktiv (30.10.2026)';

create or replace function public.trade_plans_konto_deaktiviert()
 returns trigger
 language plpgsql
 security definer
 set search_path to 'public'
as $function$
declare
  ziel timestamptz;
  ss jsonb;
begin
  if new.status is distinct from 'planned' or new.master_account_id is null then
    return new;
  end if;
  if not exists (select 1 from public.accounts a where a.id = new.master_account_id and a.deaktiviert_at is not null) then
    return new;
  end if;
  ss := new.mt5_baseline->'start_sperre';
  ziel := greatest(coalesce(old.start_um, now()), now()) + interval '15 minutes' + make_interval(secs => floor(random() * 900));
  update public.trade_plans
     set start_um = ziel,
         mt5_baseline = coalesce(mt5_baseline, '{}'::jsonb) || jsonb_build_object('start_sperre', jsonb_build_object(
           'art', 'konto_deaktiviert', 'text', 'Konto ist deaktiviert — startet erst nach „Aktivieren"', 'at', now(), 'naechster', ziel,
           'versuche', case when ss->>'art' = 'konto_deaktiviert' then coalesce((ss->>'versuche')::int, 0) + 1 else 1 end))
   where id = new.id;
  return null;
end $function$;

drop trigger if exists trade_plans_a00_konto_deaktiviert on public.trade_plans;
create trigger trade_plans_a00_konto_deaktiviert
  before update of start_um_gestartet_at on public.trade_plans
  for each row when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_konto_deaktiviert();
