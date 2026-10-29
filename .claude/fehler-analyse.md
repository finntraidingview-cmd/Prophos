# Puls-Fehler-Analyse — Anleitung für Claude

Seit 07.10.2026 (Finn: „wenn es öfter mal die gleichen Probleme sind, genau diese Fehler eliminieren").
Ziel: wiederkehrende Fehlstarts erkennen und an der Ursache abstellen, nicht einzeln wegklicken.

## Datenquellen

| Quelle | Was | Wer schreibt |
|---|---|---|
| `puls_fehlstarts` | jeder rote Start zur Startzeit (Echo-V2-Check, Puls ohne Order, Start-Fenster verpasst, Ziel erreicht) | `prophos.html` `sfMelden` (PC-Tab) |
| `order_signale` status `fehler` | jeder gescheiterte Puls-Lauf über Signal (Orbit, Topstep, Endlesung, Balance lesen …) | PC-Tab beim Abschluss |
| View `puls_fehler_ereignisse` | beide zusammen, eine Zeile je Ereignis | — |
| View `puls_fehler_muster` | gebündelt nach Muster (Schritt + Meldung ohne Zahlen/Kontonummern) | — |

Muster-Funktion: `puls_fehler_muster_text(schritt, msg)`. SQL: `sql/2026-10-07_puls_fehler_muster.sql`.

## Abfragen

Top-Muster der letzten 7 Tage:

```sql
select muster, n_24h, n_7d, n_30d, n_unklar, pcs, ids, zuletzt, beispiel
from puls_fehler_muster where n_7d > 0 order by n_7d desc limit 20;
```

Alle Ereignisse eines Musters (für den Einzelfall):

```sql
select at, pc, plan_id, quelle, msg from puls_fehler_ereignisse
where puls_fehler_muster_text(schritt, msg) = '<muster>' order by at desc limit 30;
```

Rohdaten eines Laufs: `order_signale.ergebnis` (trail, diagnose) bzw. `puls_diagnose` (pc_id, at) zur selben Zeit.

## Fehlerfoto (seit 29.10.2026)

Finn: „Wenn Fehler kommt, immer mit Screenshots arbeiten.“ Endet ein Puls-Lauf mit `ok: false`, fotografiert der Bot entkoppelt den
ganzen Bildschirm des PCs (fängt MT5-/Windows-Dialoge wie `consent.exe`) und bei TradingView-/TopstepX-Läufen zusätzlich den Tab im
Puls-Chrome. Deckel: dasselbe (Weg, Code) höchstens alle 10 min, je PC höchstens 12 Fotos je Stunde. Belegt-Antworten
(`puls_beschaeftigt`, `polar_aktiv`, …) bekommen nie ein Foto. Code: `order_bot.py` (Block PULS-FEHLERFOTO), `app.py` (Routen
`/puls-fehlerbild*`), SQL `sql/2026-10-29_puls_fehlerbilder.sql`.

- **Wo steht der Pfad?** `puls_fehlstarts.bild_pfad`, `order_signale.ergebnis->>'fehlerbild'`, in den Views als `bild_pfad`
  (`puls_fehler_ereignisse`) bzw. `bild` (jüngstes Bild je Muster, `puls_fehler_muster`). Beim gescheiterten Heimweg steht er am Ende
  der Meldung („· Bild <pfad>“). Form: `<pc>/<JJJJ-MM-TT>/<id>`.
- **Dateien im privaten Bucket `puls-fehlerbilder`:** `<pfad>-bildschirm.jpg` und, falls da, `<pfad>-tab.jpg`. Ohne Policies, nur der
  Service-Key kommt dran.
- **Ansehen (Claude am Mac / Routine):** Bild laden, dann mit dem Read-Werkzeug öffnen:

```bash
curl -s "https://web-production-bec81.up.railway.app/puls-fehlerbild-datei?pfad=<pfad>&art=bildschirm&token=$PULS_FEHLERBILD_TOKEN" -o /tmp/fehlerbild.jpg
```

  `art=tab` für das Bild des Puls-Chrome-Tabs. Der Token steht in der Railway-Variable `PULS_FEHLERBILD_TOKEN` (fehlt sie → 404).
  Im Browser mit Admin-Login geht auch `GET /admin/puls-fehlerbild?pfad=<pfad>&art=bildschirm` (5-min-Link, Gate wie Admin → Mail).
- **Welche Fehler haben Bilder?**

```sql
select at, pc, quelle, schritt, left(msg, 80) msg, bild_pfad from puls_fehler_ereignisse
where bild_pfad is not null and at > now() - interval '24 hours' order by at desc;
select name, created_at from storage.objects where bucket_id = 'puls-fehlerbilder' order by created_at desc limit 20;
```

- **Kein Bild, obwohl Fehler?** Auf dem PC liegt neben dem Bot `fehlerfoto.log` (je Foto eine Zeile: Größe oder Fehler — PowerShell,
  kein Puls-Chrome, Upload). Gegen Spam greift der Deckel (siehe oben).
- Ein Bild ist ein Beleg, kein Beweis für die Ursache: immer mit `trail`/`puls_diagnose` derselben Minute zusammen lesen.

## Vorgehen

1. Bei „Was steht an?", nach einem gemeldeten Fehlstart oder wenn Finn nach Fehlern fragt: Top-Muster abfragen.
2. Ein Muster mit **≥ 3 Ereignissen in 7 Tagen** oder **≥ 2 verschiedenen PCs** gilt als wiederkehrend → Ursache suchen (Code per CODEMAP, Spur/trail im Ergebnis), Fix vorschlagen bzw. bauen.
3. Muster, das nur an EINEM PC auftritt → eher Einrichtung des PCs (Terminal, Login, EA) als Code. Finn mit PC-Kennung und konkretem Handgriff melden.
4. Unklare Ergebnisse (`n_unklar`) zuerst: dort kann eine Order liegen, die Prophos nicht kennt.
5. Nach einem Fix im Commit das Muster nennen. Danach prüfen, ob `n_24h` für das Muster auf 0 fällt.

Keine Regel-/Risiko-Prüfungen daraus bauen (Prophos = Ausführung). Es geht nur um technische Fehlstarts.

## Liegen gebliebene Pläne (seit 20.10.2026)

Finn, 20.10.2026: „Alle 6 Stunden geht eine Routine rein und checkt: Was genau ist schiefgelaufen? Worauf genau wartet der Fehler?"
Ein Plan ist liegen geblieben, wenn seine Startzeit ≥ 10 min vorbei ist und er noch `planned` ist (nicht gestartet, nicht archiviert).
Die Routine (`.claude/routinen/puls-fehler.md` Abschnitt 4) und Menschen nehmen dieselben Abfragen.

Wo die Gründe stehen (alles in `trade_plans.mt5_baseline`, außer Lebenszeichen und Signale):

| Feld | Bedeutung |
|---|---|
| `start_fehler {schritt, msg, pc, login, versuche, status}` | roter Auto-Start (seit .1131): `status` neu/rot/tagesende/behoben; `versuche ≥ 3` = Deckel SF_MAX, sfTick plant nicht mehr neu |
| `puls_pause` (+ `puls_pause_at`, `best_war`) | Puls-Pause je ID (Memory prophos-puls-pause-lehren) — nur Finn hebt sie auf |
| `richtung_konflikt` (dict) | Long/Short-Widerspruch am Start (app.py `ap_richtung_konflikte`) — Finn entscheidet |
| `start_sperre {art, text, …}` | Server-Sperre mit Grund (z. B. Big Trade nah) — nicht anfassen |
| `vorcheck {status, seit, versuche, grund, pc, verpasst_at}` | Slave-Vorprüfung des PC-Tabs vor Orbit/Topstep-Starts mit Fusion-Hedge (seit 29.09.2026): `slave_nicht_bereit` = Tab prüft alle 20–40 s weiter (Copier/Terminal/Algo/Fusion-Marge), kein Claim; `verpasst_slave` = im ganzen Start-Fenster nicht bereit, Plan bleibt Geplant. `grund` nennt den Check (z. B. „Fusion-Marge: frei … nötig …“) — Hedge/Finanzen, nie anfassen |
| `start_um_gestartet_at` (Spalte) | Claim des PC-Tabs; Claim + `start_fehler` ohne Start = der Tab hat es versucht |
| `mt5_live` (`status->>'user_id'`, `updated_at`) | Lebenszeichen des PC-Tabs der ID (≤ 3 min = lebt) |
| `order_signale` / `puls_diagnose` / `puls_fehlstarts` | Rohdaten des Versuchs (trail, Spur, code `konto_weg`) |

**A — Liste mit Grund** (Rangfolge der `case`-Zweige = Rangfolge der Gründe):

```sql
select left(p.id::text,8) as plan, left(p.user_id::text,8) as id, p.master_firm as firma, p.route, p.start_um,
       p.start_um_gestartet_at as claim, p.auto_plan, p.auto_bestaetigt_at is not null as bestaetigt,
       y.sf->>'schritt' as schritt, y.sf->>'status' as sf_status, (y.sf->>'versuche')::int as versuche,
       y.sf->>'pc' as pc, left(y.sf->>'msg',160) as msg,
       case when coalesce(x.b->>'puls_pause','') <> '' then 'puls_pause: '||(x.b->>'puls_pause')
            when jsonb_typeof(x.b->'richtung_konflikt') = 'object' and coalesce(x.b->'richtung_konflikt'->>'status','') <> 'gedreht'   -- 21.10.2026: Schlüssel steht oft mit JSON null drin (= kein Konflikt); 23.10.2026: status 'gedreht' = erledigt, der Plan lief mit der neuen Richtung weiter
                 then 'richtung_konflikt: '||coalesce(x.b->'richtung_konflikt'->>'status','?')
            when coalesce((y.sf->>'versuche')::int,0) >= 3 then 'deckel_voll'
            when y.sf->>'status' = 'tagesende' then 'tagesende'
            when x.b->'vorcheck'->>'status' in ('slave_nicht_bereit','verpasst_slave')   -- 22.10.2026: Slave-Vorprüfung (Fusion-Copier/-Marge) hält den Start, kein Claim, kein start_fehler
                 then 'vorcheck/'||(x.b->'vorcheck'->>'status')||': '||left(coalesce(x.b->'vorcheck'->>'grund',''),90)
            when p.start_um_gestartet_at is not null and y.sf is null then 'claim_ohne_fehler'
            when p.start_um_gestartet_at is not null then 'claim+'||coalesce(y.sf->>'schritt','?')
            when y.sf is not null then coalesce(y.sf->>'status','?')||'/'||coalesce(y.sf->>'schritt','?')
            when l.zuletzt is null or l.zuletzt < now() - interval '3 minutes' then 'pc_aus'
            when p.auto_plan and p.auto_bestaetigt_at is null then 'unbestaetigt'
            else 'nie_geclaimt' end as grund,
       l.pc_name as pc_live, l.zuletzt as pc_zuletzt
from trade_plans p
cross join lateral (select coalesce(p.mt5_baseline,'{}'::jsonb) as b) x
cross join lateral (select x.b->'start_fehler' as sf) y
left join lateral (select pc_name, max(updated_at) as zuletzt from mt5_live
                   where status->>'user_id' = p.user_id::text group by pc_name order by 2 desc limit 1) l on true
where p.status = 'planned' and p.started_at is null and p.orbit_gesendet_at is null
  and p.start_um < now() - interval '10 minutes'
order by p.start_um;
```

**B — Muster der Start-Fehler** (wie `puls_fehler_muster`, aber je Plan; `liegt_noch` = davon noch `planned`):

```sql
select puls_fehler_muster_text(sf->>'schritt', sf->>'msg') as muster, count(*) as n_7d,
       count(*) filter (where status = 'planned') as liegt_noch,
       array_agg(distinct sf->>'pc') as pcs, count(distinct user_id) as ids, max((sf->>'at')::timestamptz) as zuletzt
from (select user_id, status, mt5_baseline->'start_fehler' as sf from trade_plans where mt5_baseline ? 'start_fehler') t
where (sf->>'at')::timestamptz > now() - interval '7 days'
group by 1 order by n_7d desc limit 20;
```

**C — Rohdaten eines Plans** (Signale, Spur des PCs rund um die Startzeit, rote Starts):

```sql
select created_at, pc, status, params->>'aktion' as aktion, left(ergebnis::text, 600) as ergebnis
from order_signale where plan_id::text like '<plan>%' order by created_at desc limit 10;
select at, left(diagnose::text, 600) from puls_diagnose
where pc_id = '<pc>' and at between '<start_um - 5 min>' and '<start_um + 20 min>' order by at;
select at, schritt, msg, unklar, quelle from puls_fehlstarts where plan_id::text like '<plan>%' order by at desc;
```

**D — Handgriffe** (nur die Routine nach Abschnitt 4 der Arbeitsanweisung bzw. der Master; immer als Datei
`sql/JJJJ-MM-TT_thema.sql` mit Kommentar: Plan-IDs, Grund, Datum, wer):

```sql
-- D1: Deckel lösen nach einem Bot-Fix für GENAU dieses Muster (sfTick plant dann selbst neu)
update trade_plans
   set mt5_baseline = jsonb_set(mt5_baseline, '{start_fehler,versuche}', '0'::jsonb)
 where id::text like '<plan>%' and status = 'planned' and started_at is null and orbit_gesendet_at is null
   and (mt5_baseline->'start_fehler'->>'versuche')::int >= 3;

-- D2: neu einplanen, wenn der Grund behoben ist — jede Zeile eine andere Minute (Jitter), Claim leer, Marke weg.
--     Nur Mo–Fr, neue Zeit vor 16:00 Dubai; sonst liegen lassen (Nachtlauf 01:30 Dubai plant neu).
with ziel as (
  select id, row_number() over (order by random()) as n
  from trade_plans
  where id::text like any (array['<plan1>%', '<plan2>%'])
    and status = 'planned' and started_at is null and orbit_gesendet_at is null
    and not coalesce(mt5_baseline ? 'puls_pause', false) and not coalesce(mt5_baseline ? 'richtung_konflikt', false)
)
update trade_plans p
   set start_um = now() + interval '2 min' + z.n * interval '90 seconds' + random() * interval '45 seconds',
       start_um_gestartet_at = null,
       mt5_baseline = coalesce(p.mt5_baseline, '{}'::jsonb) - 'start_fehler'
  from ziel z where z.id = p.id;
-- Kontrolle: Abfrage A — die Pläne dürfen nicht mehr erscheinen (start_um liegt jetzt in der Zukunft).
```

Nie per SQL: `puls_pause` aufheben, `richtung_konflikt`/`start_sperre` löschen, Pläne archivieren/löschen, Konten, Hedge.
Muster (≥ 3 Pläne in 7 Tagen oder ≥ 2 PCs) werden am Code gefixt, nicht per SQL weggeräumt — SQL nur für den Rest,
nachdem der Fix auf den PCs ist (`mt5_live.status->>'bot_version'`).
