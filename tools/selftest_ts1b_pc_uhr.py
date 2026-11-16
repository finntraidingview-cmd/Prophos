#!/usr/bin/env python3
"""Selbsttest TS1b „PC-Uhr nicht synchron" (Master 16.11.2026 zu TS1): Puls klickt in TopstepX „Time Sync Warning" weg und meldet es in puls_diagnose
(schritt „zeitsync", Spur „Time Sync Warning weggeklickt …"). app.py pc_uhr_ereignisse/pc_uhr_tick → ⚪ an die Master-IDs, je PC höchstens einmal am Tag,
nur frische Läufe, nur eigene Gruppe. Geprüft ohne Netz/DB: Ereignisse (schritt/Spur, Frische, Schlüssel je PC×Tag, Text mit „PC von <Name> (<pc>)"),
der Tick mit nachgebauten sb_select/_sb_all/alarm_senden (Gruppen-Filter, Dedupe über alarm_log und Merker), die Einbindung in alarm_tick, dazu
ein Syntax-Check von app.py (ast) und die Verbindung zum Bot (derselbe Satz wie in order_bot.py). Aufruf: python3 tools/selftest_ts1b_pc_uhr.py"""
import ast
import os
import re
import time
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
bot = open(os.path.join(W, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


try:
    ast.parse(app)
    check(True, "app.py: Syntax OK (ast)")
except SyntaxError as e:
    check(False, f"app.py: Syntax ({e})")

i, j = app.index("# PC-UHR NICHT SYNCHRON (TS1b"), app.index("\ndef pc_uhr_tick(")
k = app.find("\n\n\n", j)
ns = {"datetime": datetime, "timezone": timezone, "time": time}
exec(app[i:k], ns)
ev = ns["pc_uhr_ereignisse"]
jetzt = datetime(2026, 11, 16, 10, 0, tzinfo=timezone.utc).timestamp()
frisch = datetime(2026, 11, 16, 9, 30, tzinfo=timezone.utc).isoformat()
alt = datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc).isoformat()
NAMEN = {"pc-l5o8bv": {"name": "Mike"}}
rows = [{"pc_id": "pc-l5o8bv", "at": frisch, "schritt": "zeitsync", "spur": "…"},
        {"pc_id": "pc-aaaa11", "at": frisch, "schritt": "tsx_probe_cdp", "spur": "K2 … > Time Sync Warning weggeklickt (2026-11-16T09:29:00Z, pc-aaaa11) — PC-Uhr …"},
        {"pc_id": "pc-bbbb22", "at": frisch, "schritt": "tsx_probe_cdp", "spur": "nichts Besonderes"},
        {"pc_id": "pc-cccc33", "at": alt, "schritt": "zeitsync", "spur": ""},
        {"pc_id": "pc-l5o8bv", "at": frisch, "schritt": "zeitsync", "spur": ""}]
e = ev(rows, jetzt, "2026-11-16", NAMEN, {"pc-l5o8bv": "u-mike"})
keys = [x[0] for x in e]
check(keys == ["pc_uhr|pc-l5o8bv|2026-11-16", "pc_uhr|pc-aaaa11|2026-11-16"], f"schritt zeitsync oder Satz in der Spur, frisch, je PC einmal ({keys})")
check("PC von Mike (pc-l5o8bv)" in e[0][1] and e[0][1].startswith("PC-Uhr nicht synchron — Windows-Zeit synchronisieren") and e[0][2] == "u-mike",
      f"Text „PC-Uhr nicht synchron — Windows-Zeit synchronisieren (PC von Mike (pc-l5o8bv))“, ID aus mt5_live ({e[0][1][:90]})")
check(e[1][1].count("(pc-aaaa11)") == 1 and e[1][2] is None, "PC ohne Namen/ID: pc-Kennung, ohne ID")
check(ev([{"pc_id": "pc-x1y2z3", "at": "kaputt", "schritt": "zeitsync"}], jetzt, "t") == [] and ev(None, jetzt, "t") == [], "kaputte Zeit / keine Zeilen → nichts")
check(ns["PC_UHR_SPUR"] in bot and "Time Sync Warning weggeklickt (" in bot and '_puls_diagnose_senden(list(trail), "zeitsync")' in bot,
      "Bot schreibt genau diesen Satz und schritt „zeitsync“ (order_bot.py)")

# Tick mit nachgebauter DB/Alarm
gesendet, log_keys = [], set()
ns.update({
    "sb_select": lambda t, p: ([{"pc_id": "pc-l5o8bv", "at": frisch, "schritt": "zeitsync", "spur": ""},
                                {"pc_id": "pc-emin01", "at": frisch, "schritt": "zeitsync", "spur": ""},
                                {"pc_id": "pc-bbbb22", "at": frisch, "schritt": "x", "spur": ""}] if t == "puls_diagnose" else []),
    "_sb_all": lambda t, p: [{"pc_name": "pc-l5o8bv", "user_id": "u-mike"}, {"pc_name": "pc-emin01", "user_id": "u-emin"}],
    "_alarm_fremd_verwaltet": lambda uid: uid == "u-emin",
    "_pc_namen_daten": lambda: NAMEN,
    "_ap_tz": lambda n: timezone(timedelta(hours=4)),
    "_alarm": {"gemeldet": {}},
    "alarm_im_log": lambda keys, s: {k_ for k_ in keys if k_ in log_keys},
    "alarm_senden": lambda prio, art, titel, text, **kw: gesendet.append((prio, art, titel, text, kw)),
})
ns["pc_uhr_tick"]([], jetzt)
check(len(gesendet) == 1 and gesendet[0][0] == 3 and gesendet[0][1] == "pc_uhr" and gesendet[0][4]["schluessel"] == "pc_uhr|pc-l5o8bv|2026-11-16",
      f"Tick: ⚪ (prio 3) für Mikes PC, Emins Gruppe nie ({[(g[0], g[4].get('schluessel')) for g in gesendet]})")
ns["pc_uhr_tick"]([], jetzt + 120)
check(len(gesendet) == 1, "zweiter Takt: Merker hält (kein zweiter Alarm)")
ns["_alarm"]["gemeldet"].clear()
log_keys.add("pc_uhr|pc-l5o8bv|2026-11-16")
ns["pc_uhr_tick"]([], jetzt + 240)
check(len(gesendet) == 1, "nach Neustart (Merker leer): alarm_log hält — je PC höchstens einmal am Tag")
ns["pc_uhr_tick"](["u-mike"], jetzt + 360)
check(len(gesendet) == 1, "ID ausgeschlossen (aus) → nichts")
m = re.search(r"try:\n\s+pc_uhr_tick\(aus, jetzt\.timestamp\(\)\)[^\n]*\n\s+except Exception as e:", app)
check(bool(m) and app.index("update_wartet_tick(aus, jetzt.timestamp())") < m.start() < app.index("sb_delete(\"alarm_log\""),
      "alarm_tick ruft pc_uhr_tick mit eigenem try (nach der Update-Wache)")
check("sb_upsert" not in app[i:k] and "sb_update" not in app[i:k] and "sb_insert" not in app[i:k], "PC-Uhr-Wache schreibt nichts außer dem Alarm")

print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
raise SystemExit(1 if FEHLER else 0)
