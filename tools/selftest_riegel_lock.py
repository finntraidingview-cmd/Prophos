#!/usr/bin/env python3
"""Selbsttest: RIEGEL-LOCK (30.10.2026, Crosscheck Richtungsschutz S5 Punkt 3/4). Quelltext-Prüfung der SQL-Fassung (Lock vor der harten
Prüfung, 60-min-Ausnahme erst danach, Start-Trigger blockiert nie) und 🔴 aus alarm_ereignisse. Ohne Netz, ohne Postgres.
Aufruf: PROPHOS_FRONTEND=1 python3 tools/selftest_riegel_lock.py"""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


sql = open(os.path.join(WURZEL, "sql", "2026-10-30_riegel_lock.sql"), encoding="utf-8").read()
alt = open(os.path.join(WURZEL, "sql", "2026-10-13_start_sperre_meldung.sql"), encoding="utf-8").read()
f = sql[sql.index("FUNCTION public.trade_plans_gegenhedge()"):sql.index("FUNCTION public.trade_plans_gegenrichtung_start()")]
i_lock, i_hart, i_60 = f.index("pg_advisory_xact_lock"), f.index("prophos_gegenrichtung_frei"), f.index("interval '60 minutes'")
print("1) Claim-Trigger trade_plans_gegenhedge")
check(i_lock < i_hart < i_60, "Lock → harte Prüfung → 60-min-Ausnahme (überfällige Pläne laufen jetzt auch unter dem Lock)")
check(f.count("pg_advisory_xact_lock") == 1, "genau ein Lock (kein zweiter im harten Zweig)")
check("prophos_gegenhedge_konflikt" in f and "'[Gegenhedge 90 s] '" in f and "start_sperre" in f, "Rest der Live-Fassung vollständig (90-s-Teil, start_sperre, Protokoll)")
norm = lambda t: re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", t))   # noqa: E731
a = alt[alt.index("FUNCTION public.trade_plans_gegenhedge()"):]
a = a[:a.index("end $function$")]
for stueck in ("txt := k || ': dein Konto ' || coalesce(hart->>'grund', 'läuft dort in Gegenrichtung');",
               "ziel := c.ziel + make_interval(secs => 20 + floor(random() * 20));",
               "case when c.grund like 'Hand-Position%' then 'eine ' when c.wer = new.user_id then 'dein Konto '"):
    check(stueck in norm(a) and stueck in norm(f), f"Wortlaut wie bisher: {stueck[:60]}…")
print("2) Start-Trigger trade_plans_gegenrichtung_start")
s = sql[sql.index("FUNCTION public.trade_plans_gegenrichtung_start()"):]
check("return null" not in s.split("end $function$")[0], "blockiert nie (kein return null)")
check("exception when others" in s and "'unklar', true" in s, "Fehler in der Prüfung → Start geht durch, Marke unklar")
check("before update of started_at" in s and "old.started_at is null and new.started_at is not null" in s, "nur beim ersten started_at")
check("72" not in sql.replace("72-h", ""), "72-h-Grenze nicht angefasst")
print("3) 🔴 aus alarm_ereignisse")
jetzt = datetime.now(timezone.utc)
p = {"id": "p1", "user_id": "u1", "status": "open", "route": "tvv2", "master_name": "100k …0001", "master_firm": "Apex Trader",
     "started_at": jetzt.isoformat(), "rv": {"at": jetzt.isoformat(), "richtung": "sell", "grund": "Long läuft auf …0002"}}
ev = [e for e in app.alarm_ereignisse([p], {"u1": "Jacob"}, jetzt, (jetzt - timedelta(minutes=5)).isoformat()) if "richtung_verstoss" in e[0]]
check(len(ev) == 1 and ev[0][1] == 1 and "SELL gestartet" in ev[0][4], f"🔴 einmal je Plan ({ev[:1]})")
alt_p = dict(p, rv={"at": (jetzt - timedelta(hours=1)).isoformat()})
check(not [e for e in app.alarm_ereignisse([alt_p], {}, jetzt, (jetzt - timedelta(minutes=5)).isoformat()) if "richtung_verstoss" in e[0]],
      "alter Verstoß nicht erneut")
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check("rv:mt5_baseline->richtung_verstoss" in src, "alarm_tick liest die Marke")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
