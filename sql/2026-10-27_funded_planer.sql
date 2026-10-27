-- FUNDED-PLANER (27.10.2026, Finn: „Wir müssen einen Trade-Planer bauen, erst mal für alle Fundeds von Apex, weil die Trades nicht mehr
-- durchkommen … Erst mal alle Profile auswählbar, aber am Anfang nur Apex"). Regeln + Schalter des Funded-Planers (app.py fdp_*), getrennt
-- von auto_plan_regeln (Challenge-Planer bleibt unberührt), und 15 min Firmen-Abstand für Funded im bestehenden Firmen-Abstand-Trigger.
-- Einspielen macht der Master nach der S2-Prüfung; aktiv bleibt false, bis Finn die Vorschau (Admin → Funded-Planer) gesehen hat.

-- 1) Eine Zeile (id = 1), wie auto_plan_regeln. user_ids = IDs, für die geplant wird (stehen nur in der DB, Repo ist öffentlich).
-- firmen[]: name, namen = Firmenname nach _ap_norm (klein, nur a–z0–9), an = wird geplant, symbol, lock_usd = Lock des EOD-Trailing über
-- der Größe. je_groesse: ziel_gewinn (Ziel = Zyklus-Start + ziel_gewinn), max_trade (höchster TP je Trade), kosten_eur (Kontokosten =
-- Start der offenen Kosten des Hedges, Finn: 150k 550 €, 100k 350 €), dd (Max Drawdown), kontrakte = Wahrscheinlichkeit je NQ-Anzahl
-- (Finn: 100k 1/2 je 50 %, 150k 2 mit 75 % / 3 mit 25 %; gedeckelt auf die Minis der Stufe).
-- zeiten: max_je_id_tag (Funded-Trades je ID und Tag), firma_abstand_min (zwischen zwei Starts derselben Firma, alle IDs + Challenge),
-- abstand_id_min (Mindestabstand zweier Funded derselben ID, 90 min — sonst schiebt die Big-Trade-Sperre), vorlauf_min (frühester Start ab jetzt). Das Startfenster selbst ist das des
-- Challenge-Planers (auto_plan_regeln.zeiten.fenster/fenster_tz/start_bis), Startzeiten darin zufällig.
-- auto_bestaetigen (Finn 27.10.2026: „jeden Funded-Trade einzeln von Hand bestätigen"): false = der Planer legt Vorschläge OHNE start_um an,
-- erst Admin → Funded-Planer → Bestätigen setzt die Startzeit; true = gleich bestätigt (wie der Schalter beim Challenge-Planer). Standard aus.
create table if not exists public.funded_plan_regeln (
  id smallint primary key default 1 check (id = 1),
  aktiv boolean not null default false,
  auto_bestaetigen boolean not null default false,
  user_ids uuid[] not null default '{}',
  firmen jsonb not null default '[]'::jsonb,
  zeiten jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);
alter table public.funded_plan_regeln add column if not exists auto_bestaetigen boolean not null default false;
alter table public.funded_plan_regeln enable row level security;
-- Keine Policy: nur Railway (Service-Key) liest und schreibt, wie bei auto_plan_regeln.

insert into public.funded_plan_regeln (id, aktiv, auto_bestaetigen, user_ids, firmen, zeiten) values (1, false, false,
  -- alle IDs der Gruppe Hermann Technologies (die Emin-Gruppe nicht) OHNE wd_farmer_regeln.ids_aus (archivierte ID „Finn" u. a., dieselbe
  -- Liste wie der WD-Farmer); geplant werden ohnehin nur Funded-Konten einer Firma mit an = true. Pflege danach im Admin → „IDs verwalten".
  coalesce((select array_agg(m.user_id) from public.id_gruppe_mitglied m join public.id_gruppen g on g.id = m.gruppe_id
            where g.name = 'Hermann Technologies'
              and m.user_id::text not in (select jsonb_array_elements_text(coalesce(to_jsonb(w.ids_aus), '[]'::jsonb))
                                            from public.wd_farmer_regeln w where w.id = 1)), '{}'),
'[
  {"name": "Apex Trader", "namen": ["apextrader", "apex"], "an": true, "symbol": "NQ", "lock_usd": 100,
   "je_groesse": {"150000": {"ziel_gewinn": 15000, "max_trade": 7500, "kosten_eur": 550, "dd": 4000, "kontrakte": {"2": 0.75, "3": 0.25}},
                  "100000": {"ziel_gewinn": 12000, "max_trade": 6000, "kosten_eur": 350, "dd": 3000, "kontrakte": {"1": 0.5, "2": 0.5}}}},
  {"name": "Tradeify", "namen": ["tradeify"], "an": false},
  {"name": "Topstep", "namen": ["topstep"], "an": false},
  {"name": "Lucid Trading", "namen": ["lucidtrading", "lucid"], "an": false},
  {"name": "FundedNext Futures", "namen": ["fundednextfutures"], "an": false},
  {"name": "FTMO Futures", "namen": ["ftmofutures"], "an": false}
]'::jsonb,
'{"max_je_id_tag": 2, "firma_abstand_min": 15, "abstand_id_min": 90, "vorlauf_min": 15}'::jsonb)
on conflict (id) do nothing;

-- 2) Lauf-Protokoll: der Funded-Planer schreibt in auto_plan_lauf mit quelle = 'funded' (nur Läufe mit neuen Plänen/Ziel-Konten).
-- Der Unique-Index des Challenge-Nachtlaufs (quelle = 'nacht') ist davon nicht berührt — keine Änderung nötig.

-- 3) FIRMEN-ABSTAND 15 MIN FÜR FUNDED (Finn 27.10.2026: „zwischen zwei Starts bei derselben Prop-Firma immer mindestens 15 Minuten,
-- übergreifend, also über alle IDs UND gegen die Starts des Challenge-Planers bei derselben Firma … am besten dort mit einhängen, nicht als
-- zweite Mechanik. Für die Challenge-Trades untereinander bleibt alles wie es ist"). Eingehängt in den bestehenden Claim-Trigger
-- trade_plans_firmen_abstand (zuletzt sql/2026-10-13_gruppen_planer.sql, live gleich): der alte Teil (1 min, andere ID, gleiche Gruppe)
-- bleibt Wort für Wort. Neu: ist der startende Plan ODER der letzte Start derselben Firma ein Funded-Konto (accounts.account_type
-- 'funded'), gilt prophos_firmen_abstand_funded_fenster() = 15 min — auch bei derselben ID. Nur für Firmen, die im Funded-Planer an sind
-- (funded_plan_regeln.firmen[].an, Firmen-Schlüssel wie prophos_firma_key; Prüfung S2 27.10.2026: ohne Filter hätte es in 7 Tagen auch 4
-- Tradeify-Challenge- und 2 Tradeify-Funded-Starts geschoben). Gilt dort für jeden Funded-Plan mit Startzeit (auch von Hand), nicht nur
-- für den Funded-Planer. Der Trigger selbst (before update of start_um_gestartet_at) bleibt unverändert.
create or replace function public.prophos_firmen_abstand_funded_fenster() returns interval
  language sql immutable as $$ select interval '15 minutes' $$;

CREATE OR REPLACE FUNCTION public.trade_plans_firmen_abstand()
 RETURNS trigger
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  k text;
  f interval := public.prophos_firmen_abstand_fenster();
  ff interval := public.prophos_firmen_abstand_funded_fenster();
  letzter timestamptz;
  letzter_f timestamptz;
  ziel timestamptz;
  grp uuid;
  neu_funded boolean;
  firma_an boolean;
  grund text;
begin
  if new.status is distinct from 'planned' or coalesce(btrim(new.master_firm), '') = '' then
    return new;
  end if;
  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then
    return new;
  end if;
  k := public.prophos_firma_key(new.master_firm);
  grp := public.prophos_gruppe_von(new.user_id);
  perform pg_advisory_xact_lock(hashtext('prophos_firmen_abstand:' || k));
  -- 13.10.2026 (Gruppen-Planer Emin): nur IDs derselben Gruppe zählen — Emin-Gruppe und HT sind getrennte Systeme
  select coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at)
    into letzter
    from public.trade_plans p
   where p.id <> new.id
     and p.user_id is distinct from new.user_id
     and public.prophos_gruppe_von(p.user_id) is not distinct from grp
     and coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) > now() - f
     and public.prophos_firma_key(p.master_firm) = k
   order by 1 desc
   limit 1;
  -- 27.10.2026 Funded: 15 min zu jedem Start derselben Firma (alle IDs der Gruppe, auch dieselbe), sobald einer der beiden Funded ist —
  -- nur für Firmen, die im Funded-Planer an sind
  firma_an := exists (select 1 from public.funded_plan_regeln r, jsonb_array_elements(r.firmen) fr
                       where r.id = 1 and coalesce((fr->>'an')::boolean, false) and public.prophos_firma_key(fr->>'name') = k);
  neu_funded := firma_an and exists (select 1 from public.accounts a where a.id = new.master_account_id and a.account_type = 'funded');
  select coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at)
    into letzter_f
    from public.trade_plans p
   where p.id <> new.id
     and public.prophos_gruppe_von(p.user_id) is not distinct from grp
     and coalesce(p.start_um_gestartet_at, p.orbit_gesendet_at, p.started_at) > now() - ff
     and public.prophos_firma_key(p.master_firm) = k
     and firma_an
     and (neu_funded or exists (select 1 from public.accounts a where a.id = p.master_account_id and a.account_type = 'funded'))
   order by 1 desc
   limit 1;
  if letzter is not null and letzter > now() - f then
    ziel := letzter + f + make_interval(secs => 10 + floor(random() * 21));
    grund := '[Firmen-Abstand 1 min] ' || k || ': eine andere ID hat um ' || to_char(letzter at time zone 'Asia/Dubai', 'HH24:MI:SS')
             || ' Dubai gestartet — Start frühestens 1 min danach (';
  end if;
  if letzter_f is not null and letzter_f > now() - ff and (ziel is null or letzter_f + ff > ziel) then
    ziel := letzter_f + ff + make_interval(secs => 10 + floor(random() * 21));
    grund := '[Firmen-Abstand Funded 15 min] ' || k || ': Start derselben Firma um ' || to_char(letzter_f at time zone 'Asia/Dubai', 'HH24:MI:SS')
             || ' Dubai (Funded beteiligt) — Start frühestens 15 min danach (';
  end if;
  if ziel is null then
    return new;
  end if;
  if old.start_um is null or old.start_um < ziel - interval '30 seconds' then
    update public.trade_plans set start_um = ziel where id = new.id;
    insert into public.auto_plan_umplanung (plan_id, user_id, firma, von_richtung, nach_richtung, von_start, nach_start, grund, quelle)
    values (new.id, new.user_id, new.master_firm, new.richtung, new.richtung, old.start_um, ziel,
            grund || to_char(ziel at time zone 'Asia/Dubai', 'HH24:MI:SS') || ' Dubai)', 'start');
  end if;
  return null;
end $function$;

-- Prüfen:
-- select aktiv, auto_bestaetigen, cardinality(user_ids), jsonb_path_query_array(firmen, '$[*] ? (@.an == true).name'), zeiten from public.funded_plan_regeln;
-- select public.prophos_firmen_abstand_funded_fenster();   -- 00:15:00
-- Scharf schalten (erst nach Finns OK zur Vorschau):
-- update public.funded_plan_regeln set aktiv = true, updated_at = now() where id = 1;
