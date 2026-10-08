-- TEILWEISE ÜBERHOLT (08.10.2026): trade_plans_firmen_abstand ersetzt durch sql/2026-10-08_firmen_abstand_1min.sql (1 min, jede ID).
-- prophos_firma_key und der Trigger selbst kommen weiter aus dieser Datei. Nicht erneut einspielen, sonst gilt wieder 5 min.
-- FIRMEN-ABSTAND AM START (08.10.2026, Slave-Terminal 3 — Finn zu The5%ers Finn + Pascal 04:24, Jacob 04:23 Dubai: „Was ich auch
-- nicht will: dass bei zwei verschiedenen IDs zur selben Uhrzeit bei derselben Prop-Firm zwei Trades aufgehen. Das ist mies
-- auffällig. Immer mindestens 5 Minuten Abstand, wenn eine ID bei einer Prop-Firm einen Trade öffnet … Korrelation").
--
-- Planer (ap_zeiten_verteilen) und Ausgleichs-Bot (ap_verteilung) halten AP_FIRMA_ABSTAND_MIN = 5 schon beim Planen. Dieser Riegel
-- hält ihn AM START — Neustarts, verpasste Starts, „Neu einplanen", Handpläne und jede Tab-Version schieben Pläne sonst nachträglich
-- zusammen. Er sitzt genau am Claim (trade_plans.start_um_gestartet_at NULL → gesetzt), den jeder Startweg des PC-Tabs nimmt
-- (tpStartUmTick: Update mit Guard status=planned + start_um_gestartet_at IS NULL, „nur wer eine Zeile trifft, darf feuern").
--
-- Hat eine ANDERE ID bei derselben Firma (Schlüssel wie app.py _firm_norm) in den letzten 5 min WIRKLICH gestartet (started_at oder
-- orbit_gesendet_at) — oder läuft dort gerade ein Start (Claim ohne Start, höchstens 2 min alt: sonst rutschte eine zweite ID in den
-- Sekunden zwischen Claim und Kauf-Klick der ersten durch) —, dann (Prüfer 08.10.2026: ein gescheiterter Start, z. B. „Popup
-- geschlossen", sperrt die Firma nicht 5 min; der bloße Claim zählt nur 2 min):
--   * wird der Claim NICHT geschrieben — der Trigger gibt NULL zurück, das Update trifft keine Zeile, der Tab startet nicht
--     (suClaimFehlgriff: kurze Pause, Plan neu lesen). Bewusst kein „Claim still auf NULL" — der Tab prüft nur, ob eine Zeile
--     zurückkommt, und würde sonst starten;
--   * rückt start_um auf „deren Start + 5 min + 20–90 s Jitter" (nur wenn er nicht schon dort liegt — kein Protokoll-Spam);
--   * steht eine Zeile in auto_plan_umplanung (quelle 'start', Grund „[Firmen-Abstand] …").
-- pg_advisory_xact_lock je Firma: zwei PCs im selben Augenblick werden nacheinander geprüft, der zweite sieht den ersten Claim.
-- Ausnahme: Pläne, deren Startzeit über 60 min zurückliegt (der Tab claimt sie nur noch als „verpasst", ohne zu starten).
-- Gleiche ID, andere Firma oder Pläne ohne Firma: unberührt.
--
-- Wiederholbar. Rückbau:  drop trigger if exists trade_plans_firmen_abstand on public.trade_plans;

create or replace function public.prophos_firma_key(name text) returns text
language plpgsql immutable as $$
declare
  f text := lower(btrim(coalesce(name, '')));
begin
  -- gleiche Reihenfolge wie app.py _firm_norm / _FIRM_RULES (tools/selftest_auto_firmen_abstand.py prüft den Gleichlauf)
  if f = '' then return '—'; end if;
  if strpos(f, '5%er') > 0 or strpos(f, '5ers') > 0 or strpos(f, 'five percent') > 0 then return 'The5%ers'; end if;
  if strpos(f, 'futur') > 0 and (strpos(f, 'fundednext') > 0 or strpos(f, 'funded next') > 0
                                 or strpos(f, 'foundednext') > 0 or strpos(f, 'founded next') > 0) then return 'FundedNext Futures'; end if;
  if (strpos(f, 'funded') > 0 or strpos(f, 'founded') > 0) and strpos(f, 'futur') > 0 then return 'MyFundedFutures'; end if;
  if strpos(f, 'apex') > 0 then return 'Apex Trader'; end if;
  if strpos(f, 'tradeify') > 0 then return 'Tradeify'; end if;
  if strpos(f, 'fundednext') > 0 or strpos(f, 'founded next') > 0 or strpos(f, 'foundednext') > 0 then return 'FundedNext'; end if;
  if strpos(f, 'fundingpips') > 0 or strpos(f, 'funding pips') > 0 then return 'FundingPips'; end if;
  if strpos(f, 'topstep') > 0 then return 'Topstep'; end if;
  if strpos(f, 'ftmo') > 0 then return 'FTMO'; end if;
  if strpos(f, 'alpha') > 0 then return 'Alpha Future'; end if;
  if strpos(f, 'fusion') > 0 then return 'Fusion Markets'; end if;
  if strpos(f, 'lucid') > 0 then return 'Lucid Trading'; end if;
  return btrim(coalesce(name, ''));
end $$;

create or replace function public.trade_plans_firmen_abstand() returns trigger
language plpgsql security definer set search_path = public as $$
declare
  k text;
  letzter timestamptz;
  ziel timestamptz;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;                                   -- „verpasst"-Claim: startet nichts, nicht aufhalten
  end if;
  k := public.prophos_firma_key(new.master_firm);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  -- echter Start (started_at/orbit_gesendet_at) zählt 5 min; ein Claim ohne Start nur 2 min (Start unterwegs), danach gilt er als
  -- gescheitert und sperrt nicht mehr
  select max(case when p.started_at is not null or p.orbit_gesendet_at is not null
                  then greatest(coalesce(p.started_at, '-infinity'::timestamptz), coalesce(p.orbit_gesendet_at, '-infinity'::timestamptz))
                  else p.start_um_gestartet_at end)
    into letzter
    from public.trade_plans p
   where p.id <> new.id
     and p.user_id is distinct from new.user_id
     and (p.started_at > now() - interval '5 minutes'
          or p.orbit_gesendet_at > now() - interval '5 minutes'
          or (p.start_um_gestartet_at > now() - interval '2 minutes' and p.started_at is null and p.orbit_gesendet_at is null))
     and public.prophos_firma_key(p.master_firm) = k;
  if letzter is null or letzter <= now() - interval '5 minutes' then
    return new;                                   -- frei: Claim normal schreiben
  end if;
  ziel := letzter + interval '5 minutes' + make_interval(secs => 20 + floor(random() * 70));
  if old.start_um is null or old.start_um < ziel - interval '2 minutes' then
    update public.trade_plans set start_um = ziel where id = new.id;   -- Spalte start_um: dieser Trigger feuert dafür nicht
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            '[Firmen-Abstand] ' || k || ': eine andere ID hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
            || ' Dubai gestartet — Start frühestens 5 min danach (' || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ')',
            'start');
  end if;
  return null;                                    -- Claim nicht schreiben → Update trifft keine Zeile → der Tab startet nicht
end $$;

drop trigger if exists trade_plans_firmen_abstand on public.trade_plans;
create trigger trade_plans_firmen_abstand
  before update of start_um_gestartet_at on public.trade_plans
  for each row
  when (old.start_um_gestartet_at is null and new.start_um_gestartet_at is not null)
  execute function public.trade_plans_firmen_abstand();
