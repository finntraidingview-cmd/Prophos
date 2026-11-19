#!/usr/bin/env python3
# ════════════════════════════════════════════════════════════════════════════
# Prophos Backup-Prüfer (BK1, Finn 20.11.2026: „Mach eins live ready, das einmal
# pro Backup abcheckt, ob alle Backups drin sind.")
#
# Läuft täglich 07:20 per launchd com.prophos.backup-check, also nach dem Backup
# (com.prophos.backup, 06:30). Prüft den Lauf des Tages von außen — backup.py
# selbst bleibt unberührt:
#   a) ~/Prophos-Backups/<datum>/: _INFO.txt da, jede Tabelle aus Supabase public
#      (Soll = Liste von JETZT, nicht fest) mit CSV und ohne FEHLER, _SCHEMA.sql da,
#      Zeilenzahlen ggü. dem Vortag: Tabelle > 20 % weniger = Warnung,
#      alle Zeilen zusammen > 20 % weniger oder Tabelle ≥ 10 → 0 = Fehler
#   b) Notfall-Paket: ANLEITUNG.md, code/Prophos.git, wissen/, _STAND.txt von heute
#   c) iCloud-Archiv Prophos-Notfall-<Mo..So>.tar.gz mit Stand von heute
#   d) ~/Library/Logs/prophos-backup.log: „Fertig: n/n Tabellen" von heute
#
# Warum ein eigener Prüfer: bis 19.11.2026 hat ihn niemand gehabt — sonntags
# (25.10., 01.11., 08.11., 15.11.) erreichte das Backup Supabase nicht und ließ
# einen leeren Tagesordner zurück, das iCloud-Archiv scheitert seit dem 28.10.
# täglich (TCC „Operation not permitted" / „Resource deadlock avoided"). Beides
# stand nur im Log, in das keiner schaut.
#
# Ergebnis: ~/Library/Logs/prophos-backup-check.log. Grün → nur Log.
# Fehler → 🟠 an die Master-IDs über Railway POST /alarm/backup-check (alarm_senden,
# einmal je Datum), scheitert das → Mac-Mitteilung. Warnungen allein → nur Log.
#
# Von Hand:  python3 backup_check.py [--datum JJJJ-MM-TT] [--ohne-alarm]
# ════════════════════════════════════════════════════════════════════════════
import datetime
import json
import os
import re
import ssl
import subprocess
import sys
import time
import urllib.request

# launchd startet ohne Login-Shell — pg8000 liegt im User-Site (wie backup.py)
sys.path.insert(0, os.path.expanduser("~/Library/Python/%d.%d/lib/python/site-packages"
                                      % sys.version_info[:2]))

BASIS = os.path.expanduser("~/Prophos-Backups")
ICLOUD = os.path.expanduser("~/Library/Mobile Documents/com~apple~CloudDocs/Prophos-Backups")
BACKUP_LOG = os.path.expanduser("~/Library/Logs/prophos-backup.log")
CHECK_LOG = os.path.expanduser("~/Library/Logs/prophos-backup-check.log")
KONFIG = os.path.expanduser("~/.prophos/backup-config.json")
# Token für die Alarm-Route: eigener zuerst, sonst der vorhandene Fehlerbild-Token
# (Railway prüft BACKUP_CHECK_TOKEN, sonst PULS_FEHLERBILD_TOKEN — app.py alarm_backup_check)
TOKEN_DATEIEN = [os.path.expanduser("~/.prophos/backup-check-token"),
                 os.path.expanduser("~/.prophos/fehlerbild_token")]
ALARM_URL = "https://web-production-bec81.up.railway.app/alarm/backup-check"
GESCHUETZT = ["auth.users", "auth.identities", "supabase_migrations.schema_migrations"]   # wie backup.py
WOCHENTAG = ["", "Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]                                  # wie notfall_paket.sh (date +%u)
EINBRUCH = 0.20            # > 20 % weniger Zeilen als am Vortag
LEER_AB = 10               # Tabelle hatte ≥ so viele Zeilen und ist jetzt leer → Fehler
WARTEN_MAX_S = 30 * 60     # läuft backup.py noch (Mac kam spät aus dem Schlaf), so lange warten
INFO_ZEILE = re.compile(r"^  (\S+)\s+(?:(\d+) Zeilen|FEHLER: (.*))$")


def log(msg):
    zeile = f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(zeile, flush=True)
    try:
        with open(CHECK_LOG, "a", encoding="utf-8") as f:
            f.write(zeile + "\n")
    except OSError:
        pass


def info_lesen(datum):
    """_INFO.txt eines Tages → {tabelle: zeilen | None (FEHLER)}, {tabelle: fehlertext}; fehlt die Datei → None, None."""
    pfad = os.path.join(BASIS, datum, "_INFO.txt")
    if not os.path.isfile(pfad):
        return None, None
    zeilen, fehler = {}, {}
    with open(pfad, encoding="utf-8") as f:
        for z in f:
            m = INFO_ZEILE.match(z.rstrip("\n"))
            if not m:
                continue
            if m.group(2) is not None:
                zeilen[m.group(1)] = int(m.group(2))
            else:
                zeilen[m.group(1)] = None
                fehler[m.group(1)] = m.group(3)
    return zeilen, fehler


def soll_tabellen():
    """Aktuelle Tabellen/Views in Supabase public (gleiche Abfrage wie backup.py) + die geschützten. Nur-Lese-Rolle backup_reader."""
    import pg8000.native
    cfg = json.load(open(KONFIG))
    ctx = ssl.create_default_context(cafile=os.path.expanduser(cfg["ca_file"]))
    letzter = None
    for kand in cfg["host_candidates"]:
        try:
            conn = pg8000.native.Connection(kand["user"], host=kand["host"], port=kand["port"], database=cfg["database"],
                                            password=cfg["password"], ssl_context=ctx, timeout=20)
            try:
                rows = conn.run("""select c.relname from pg_class c join pg_namespace n on n.oid = c.relnamespace
                                   where n.nspname = 'public' and c.relkind in ('r', 'p', 'v', 'm') order by c.relname""")
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
            return [r[0] for r in rows] + GESCHUETZT
        except Exception as e:
            letzter = e
    raise RuntimeError(f"Supabase nicht erreichbar: {letzter}")


def vortag_mit_info(datum):
    """Jüngster Tagesordner VOR datum mit _INFO.txt (sonntags fehlte sie zuletzt öfter)."""
    muster = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for d in sorted((x for x in os.listdir(BASIS) if muster.match(x) and x < datum), reverse=True):
        if os.path.isfile(os.path.join(BASIS, d, "_INFO.txt")):
            return d
    return None


def backup_laeuft():
    r = subprocess.run(["pgrep", "-f", "backup-agent/backup.py"], capture_output=True, text=True)
    return r.returncode == 0


def letzte_logzeile(datum):
    try:
        with open(BACKUP_LOG, encoding="utf-8", errors="replace") as f:
            heute = [z.rstrip("\n") for z in f if z.startswith(f"[{datum} ")]
        return heute[-1][:200] if heute else ""
    except OSError:
        return ""


def pruefe_datenbank(datum, fehler, warnungen):
    ordner = os.path.join(BASIS, datum)
    if not os.path.isdir(ordner):
        fehler.append(f"Tagesordner {datum} fehlt — Backup lief nicht. Letzte Log-Zeile: {letzte_logzeile(datum) or 'keine von heute'} "
                      f"→ von Hand: python3 /Applications/Prophos/backup-agent/backup.py")
        return 0
    ist, ist_fehler = info_lesen(datum)
    if ist is None:
        fehler.append(f"{datum}/_INFO.txt fehlt — Backup brach ab. Letzte Log-Zeile: {letzte_logzeile(datum) or 'keine von heute'} "
                      f"→ von Hand: python3 /Applications/Prophos/backup-agent/backup.py")
        return 0
    try:
        soll = soll_tabellen()
        quelle = "Supabase"
    except Exception as e:
        vt = vortag_mit_info(datum)
        soll = list((info_lesen(vt)[0] or {}).keys()) if vt else []
        quelle = f"Vortag {vt}"
        warnungen.append(f"Soll-Liste aus Supabase nicht lesbar ({str(e)[:120]}) — verglichen mit {quelle}")
    soll = [t for t in soll if t != "_SCHEMA.sql"]
    fehlend = [t for t in soll if t not in ist]
    if fehlend:
        fehler.append(f"{len(fehlend)} Tabelle(n) nicht im Backup: {', '.join(fehlend[:8])}{' …' if len(fehlend) > 8 else ''} "
                      f"(neu seit 06:30? sonst sql/2026-09-29_backup-reader-vollstaendig.sql einspielen)")
    if ist_fehler:
        t, msg = next(iter(ist_fehler.items()))
        fehler.append(f"{len(ist_fehler)} Tabelle(n) mit FEHLER in _INFO.txt, z. B. {t}: {msg[:120]}")
    ohne_csv = [t for t, z in ist.items() if z is not None and t != "_SCHEMA.sql"
                and not os.path.isfile(os.path.join(ordner, f"{t}.csv"))]
    if ohne_csv:
        fehler.append(f"{len(ohne_csv)} CSV fehlen trotz Eintrag in _INFO.txt: {', '.join(ohne_csv[:8])}")
    schema = os.path.join(ordner, "_SCHEMA.sql")
    if not os.path.isfile(schema) or os.path.getsize(schema) == 0:
        fehler.append(f"{datum}/_SCHEMA.sql fehlt oder ist leer")

    vt = vortag_mit_info(datum)
    if vt:
        alt, _ = info_lesen(vt)
        summe_alt = sum(z for z in alt.values() if z)
        summe_neu = sum(z for z in ist.values() if z)
        if summe_alt and summe_neu < summe_alt * (1 - EINBRUCH):
            fehler.append(f"Zeilen gesamt eingebrochen: {summe_alt} ({vt}) → {summe_neu} ({datum})")
        for t, a in alt.items():
            n = ist.get(t)
            if not a or n is None:
                continue
            if n == 0 and a >= LEER_AB:
                fehler.append(f"Tabelle {t} leer: {a} ({vt}) → 0")
            elif n < a * (1 - EINBRUCH):
                warnungen.append(f"{t}: {a} → {n} Zeilen (−{round(100 * (a - n) / a)} % ggü. {vt})")
    else:
        warnungen.append("kein Vortag mit _INFO.txt zum Vergleichen")
    zahl = sum(1 for z in ist.values() if z is not None)
    log(f"  a) Datenbank {datum}: {zahl}/{len(ist)} Einträge ok, Soll {len(soll)} Tabellen ({quelle}), "
        f"{sum(z for z in ist.values() if z)} Zeilen" + (f", Vortag {vt}" if vt else ""))
    return len(soll)


def pruefe_paket(datum, fehler, warnungen):
    teile = {"ANLEITUNG.md": os.path.join(BASIS, "ANLEITUNG.md"),
             "code/Prophos.git": os.path.join(BASIS, "code", "Prophos.git"),
             "wissen/": os.path.join(BASIS, "wissen"),
             "_STAND.txt": os.path.join(BASIS, "_STAND.txt")}
    weg = [n for n, p in teile.items() if not os.path.exists(p) or (os.path.isdir(p) and not os.listdir(p))]
    if weg:
        fehler.append(f"Notfall-Paket unvollständig, fehlt: {', '.join(weg)} → bash /Applications/Prophos/backup-agent/notfall_paket.sh")
    stand = teile["_STAND.txt"]
    if os.path.isfile(stand):
        with open(stand, encoding="utf-8", errors="replace") as f:
            zeilen = [z.rstrip("\n") for z in f]
        m = re.search(r"gebaut am (\d{4}-\d{2}-\d{2})", zeilen[0] if zeilen else "")
        gebaut = m.group(1) if m else "?"
        if not m:   # Prüfer 20.11.: "?" < "2026-…" ist als Text False — unlesbarer Stand wäre sonst still grün
            fehler.append(f"_STAND.txt unlesbar (erste Zeile: {(zeilen[0] if zeilen else 'leer')[:60]})")
        elif gebaut < datum:
            fehler.append(f"Notfall-Paket nicht von {datum} (_STAND.txt: gebaut am {gebaut})")
        # iCloud-Archiv prüft c) selbst. Nur „Obsidian-Vault Finn" ist Warnung (scheitert im launchd-Lauf seit 07.10. — TCC, bekannt);
        # jeder andere Teil-Fehler (Code, Anleitung, Memory …) ist Fehler — der alte Stand liegt dann noch da und sähe vollständig aus
        for z in zeilen:
            if not z.strip().startswith("FEHLER") or "iCloud-Archiv" in z:
                continue
            teil = z.strip()[7:].strip()[:140]
            (warnungen if teil.startswith("Obsidian-Vault Finn") else fehler).append("Paket-Teil " + teil)
        log(f"  b) Notfall-Paket: gebaut am {gebaut}, " + ("vollständig" if not weg else f"fehlt {', '.join(weg)}"))


def pruefe_icloud(datum, fehler):
    tag = datetime.date.fromisoformat(datum)
    name = f"Prophos-Notfall-{WOCHENTAG[tag.isoweekday()]}.tar.gz"
    pfad = os.path.join(ICLOUD, name)
    try:
        st = os.stat(pfad)
    except FileNotFoundError:
        fehler.append(f"iCloud-Archiv {name} fehlt")
        log(f"  c) iCloud: {name} fehlt")
        return
    except OSError as e:
        fehler.append(f"iCloud-Archiv {name} nicht prüfbar ({e.strerror}) — launchd ohne iCloud-Zugriff")
        log(f"  c) iCloud: {name} nicht prüfbar ({e.strerror})")
        return
    stand = datetime.datetime.fromtimestamp(st.st_mtime)
    if stand.date() < tag:
        # Ursache aus dem Backup-Log des Tages, wenn sie dort steht (seit 28.10.: „Operation not permitted" / „Resource deadlock avoided")
        grund = ""
        try:
            with open(BACKUP_LOG, encoding="utf-8", errors="replace") as f:
                for z in f:
                    if z.startswith(f"[{datum} ") and "FEHLER  iCloud-Archiv" in z:
                        grund = z.split(": ", 2)[-1].strip()[-60:]
        except OSError:
            pass
        # EINE Ursache mit Fix (ARBEITER §2): „not permitted" = TCC, „deadlock" = iCloud hält die alte Datei als Platzhalter
        if "deadlock" in grund:
            fix = f" → im Finder iCloud Drive/Prophos-Backups/{name} löschen (iCloud-Platzhalter blockiert das Überschreiben)"
        elif "not permitted" in grund:
            fix = " → Systemeinstellungen → Datenschutz & Sicherheit → Festplattenvollzugriff: /bin/bash eintragen"
        else:
            fix = " → Ursache im Backup-Log: grep iCloud-Archiv ~/Library/Logs/prophos-backup.log | tail -3"
        fehler.append(f"iCloud-Archiv {name} ist vom {stand:%d.%m.%Y}, nicht von {tag:%d.%m.}" + (f" — cp: …{grund}" if grund else "") + fix)
    log(f"  c) iCloud: {name} Stand {stand:%Y-%m-%d %H:%M}, {st.st_size // (1024 * 1024)} MB")


def pruefe_log(datum, fehler, soll):
    fertig = []
    try:
        with open(BACKUP_LOG, encoding="utf-8", errors="replace") as f:
            fertig = [z.rstrip("\n") for z in f if z.startswith(f"[{datum} ") and "] Fertig: " in z]
    except OSError as e:
        fehler.append(f"Backup-Log nicht lesbar: {e}")
        return
    if not fertig:
        fehler.append(f"kein „Fertig“ von {datum} in prophos-backup.log. Letzte Zeile: {letzte_logzeile(datum) or 'keine von heute'}")
        log(f"  d) Log: kein Fertig von {datum}")
        return
    m = re.search(r"Fertig: (\d+)/(\d+) Tabellen", fertig[-1])
    if m and m.group(1) != m.group(2):
        fehler.append(f"Backup-Log: nur {m.group(1)}/{m.group(2)} Tabellen gesichert ({fertig[-1][1:20]})")
    log(f"  d) Log: {fertig[-1][fertig[-1].find('Fertig'):][:90]}")


def alarm_senden(datum, fehler):
    text = (f"{len(fehler)} Befund(e): " if len(fehler) > 1 else "") + " · ".join(fehler)
    versucht = False
    for p in TOKEN_DATEIEN:   # jede vorhandene Token-Datei probieren — 404 mit der einen heißt nicht, dass die andere nicht passt
        try:
            token = open(p).read().strip()
        except OSError:
            continue
        if not token:
            continue
        versucht = True
        try:
            req = urllib.request.Request(ALARM_URL, method="POST",
                                         data=json.dumps({"datum": datum, "text": text[:600], "anzahl": len(fehler)}).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "X-Backup-Token": token})
            with urllib.request.urlopen(req, timeout=20) as r:
                antwort = json.loads(r.read().decode("utf-8") or "{}")
            log(f"  Alarm 🟠 an die Master-IDs: {antwort}")
            return
        except Exception as e:
            log(f"  Alarm mit {os.path.basename(p)} gescheitert ({type(e).__name__}: {str(e)[:120]})")
    log("  Mac-Mitteilung statt Alarm" + ("" if versucht else " (kein Token in ~/.prophos)"))
    try:
        kurz = fehler[0][:150].replace('"', "'").replace("\\", "/")
        subprocess.run(["osascript", "-e", f'display notification "{kurz}" with title "Prophos-Backup: {len(fehler)} Befund(e)" sound name "Basso"'],
                       timeout=10)
    except Exception:
        pass


def fertig_im_log(datum):
    try:
        with open(BACKUP_LOG, encoding="utf-8", errors="replace") as f:
            return any(z.startswith(f"[{datum} ") and "] Fertig: " in z for z in f)
    except OSError:
        return False


def main():
    argv = sys.argv[1:]
    datum = f"{datetime.date.today():%Y-%m-%d}"
    von_hand = "--datum" in argv or "--ohne-alarm" in argv
    if "--datum" in argv:
        i = argv.index("--datum")
        datum = argv[i + 1] if i + 1 < len(argv) else ""
        datetime.date.fromisoformat(datum)   # wirft bei Unsinn
    ohne_alarm = "--ohne-alarm" in argv

    # Mac kam spät aus dem Schlaf → launchd holt 06:30 und 07:20 fast gleichzeitig nach, der Prüfer kann vor backup.py starten
    # (Prüfer 20.11.: dann sähe pgrep nichts, und es käme ein 🟠 ohne Entwarnung). Deshalb im launchd-Lauf: warten, bis backup.py
    # nicht mehr läuft UND „Fertig" von heute im Log steht, höchstens 30 min. Von Hand (--datum / --ohne-alarm) sofort prüfen.
    if not von_hand:
        start = time.time()
        time.sleep(60)
        while (backup_laeuft() or not fertig_im_log(datum)) and time.time() - start < WARTEN_MAX_S:
            time.sleep(30)
        if backup_laeuft():
            log(f"backup.py läuft seit über {WARTEN_MAX_S // 60} min — prüfe trotzdem")

    log(f"Prüfung Backup {datum}" + (" (ohne Alarm)" if ohne_alarm else ""))
    fehler, warnungen = [], []
    try:
        soll = pruefe_datenbank(datum, fehler, warnungen)
        pruefe_paket(datum, fehler, warnungen)
        pruefe_icloud(datum, fehler)
        pruefe_log(datum, fehler, soll)
    except Exception as e:   # Prüfer 20.11.: ein Absturz darf nicht still enden — genau den stillen Fall soll der Prüfer abfangen
        fehler.append(f"Backup-Prüfer abgestürzt: {type(e).__name__}: {str(e)[:160]} → python3 /Applications/Prophos/backup-agent/backup_check.py --ohne-alarm")
    for w in warnungen:
        log(f"  WARNUNG {w}")
    for f in fehler:
        log(f"  FEHLER  {f}")
    if not fehler:
        log(f"GRÜN: Backup {datum} vollständig" + (f" ({len(warnungen)} Warnung(en))" if warnungen else ""))
        return 0
    log(f"ROT: {len(fehler)} Fehler im Backup {datum}")
    if not ohne_alarm:
        alarm_senden(datum, fehler)
    return 1


if __name__ == "__main__":
    sys.exit(main())
