#!/usr/bin/env python3
"""Selbsttest WINDOWS-ABFRAGE MELDEN (UA1, 06.11.2026 — Finn: „Wenn die Windows-Abfrage kommt, kannst du mir kurz Bescheid geben, dann kann ich es
kurz hinklicken."). Ohne Netz: (A) Panel rein rechnend (wann senden, welcher Updater gehört zur Abfrage), (B) Railway POST /pc/uac-spur mit
Flask-Testclient und Attrappen für Schlüssel, Namen, alarm_log und alarm_senden: 🔴 einmal, nach 30 min erneut, ✅ einmal wenn weg, nur HT-IDs,
Lesefehler im alarm_log → Merker im Speicher. Aufruf: python3 tools/selftest_uac_alarm.py"""
import os
import re
import sys
import time
from datetime import datetime, timezone

from flask import Flask, jsonify, request

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def block(src, kopf):
    i = src.index(kopf)
    i = src.rfind("\n", 0, i) + 1
    return src[i:src.find("\n\n\n", i)]


# ── (A) Panel ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
psrc = open(os.path.join(HIER, "..", "mt5-copier", "panel.py"), encoding="utf-8").read()
pns = {}
exec(re.search(r"^UAC_ALARM_TAKT_S, UAC_ALARM_HALTEN_S, UAC_ALARM_FEHL_S = .*$", psrc, re.M).group(0), pns)
for fn in ("uac_alarm_senden_noetig", "uac_ausloeser_waehlen"):
    exec(block(psrc, f"def {fn}("), pns)
S, A = pns["uac_alarm_senden_noetig"], pns["uac_ausloeser_waehlen"]
check(S({}, {"1|5": 1}, 0, 100) and S({"1|5": 1}, {}, 100, 101), "Panel: neue Abfrage und weggegangene Abfrage → sofort senden")
check(not S({"1|5": 1}, {"1|5": 1}, 100, 200) and S({"1|5": 1}, {"1|5": 1}, 100, 401), "Panel: offen → alle 5 min erneut, dazwischen still")
check(not S({}, {}, 0, 10 ** 9), "Panel: nichts offen, nichts weg → nie senden")
upd = [(1000.0, r"C:\MT5-100k1Phase1"), (5000.0, r"C:\MT5-100k2Phase1")]
check(A(5001.0, upd) == r"C:\MT5-100k2Phase1" and A(1001.0, upd) == r"C:\MT5-100k1Phase1", "Panel: Updater, der kurz vor der Abfrage startete")
check(A(9000.0, upd) == "" and A(None, [(1.0, r"C:\MT5-x")]) == r"C:\MT5-x" and A(None, []) == "", "Panel: unklar → leer, genau einer → der")
check("threading.Thread(target=_uac_alarm_waechter, daemon=True).start()" in psrc and '"/pc/uac-spur"' in psrc, "Panel: Wächter gestartet, meldet an /pc/uac-spur")
w = block(psrc, "def _uac_abfragen_lesen(")
check('"seit": int(s or 0), "gesehen": int(gesehen)' in w, "Gegenprüfung: Schlüssel-seit nur echte Startzeit (sonst 0), „gesehen“ nur Anzeige")
wl = block(psrc, "def _uac_alarm_waechter(")
check("read_json(UAC_ALARM_DATEI" in wl and "os.replace(tmp, UAC_ALARM_DATEI)" in wl and 'UAC_ALARM["fehl_bis"] = time.time() + UAC_ALARM_FEHL_S' in wl
      and 'time.time() >= UAC_ALARM["fehl_bis"]' in wl, "Gegenprüfung: Stand übersteht Panel-Neustart; nach Fehler 5 min Pause statt alle 30 s")
check("CreateToolhelp32Snapshot(0x2, 0)" in w and "subprocess" not in w and "OpenProcess(0x1000" in w and w.index("return []") < w.index("def start_und_pfad"),
      "Panel: ohne consent.exe nur ein Snapshot (kein Unterprozess, kein Öffnen fremder Prozesse)")

# ── (B) Railway ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────
src = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()
HT, EMIN, PC = "11111111-0000-4000-8000-000000000001", "22222222-0000-4000-8000-000000000002", "pc-abc123"
LOG, GES = [], []
ZUSTAND = {"log_kaputt": False, "jetzt": 1_800_000_000.0, "wer": (HT, PC)}


def alarm_im_log(keys, seit_s):
    if ZUSTAND["log_kaputt"]:
        return None
    return {k for k, t in LOG if k in set(keys) and ZUSTAND["jetzt"] - t <= seit_s}


def alarm_senden(prio, art, titel, text, uid=None, schluessel=None, zeichen=None, push_prio=None, **kw):
    GES.append({"prio": prio, "art": art, "titel": titel, "text": text, "schluessel": schluessel, "zeichen": zeichen, "push_prio": push_prio})
    if not ZUSTAND.get("log_schreibt_nicht"):
        LOG.append((schluessel, ZUSTAND["jetzt"]))
    return 1, 1


class _Zeit:
    @staticmethod
    def time():
        return ZUSTAND["jetzt"]


app = Flask("selftest")
ns = {"re": re, "datetime": datetime, "timezone": timezone, "jsonify": jsonify, "request": request, "app": app, "time": _Zeit,
      "_wd_num": None, "_code_zugang": lambda: ZUSTAND["wer"], "_ap_namen": lambda: ({HT: "Chris", EMIN: "Emin"}, set()),
      "_alarm_fremd_verwaltet": lambda u: u == EMIN, "_pc_namen_daten": lambda: {PC: {"name": "Chris"}},
      "alarm_im_log": alarm_im_log, "alarm_senden": alarm_senden}
exec(block(src, "def _wd_num("), ns)
exec(re.search(r"^UAC_ALARM_WIEDER_S, UAC_ALARM_MAX = .*$", src, re.M).group(0) + "\n_UAC_ALARM_MERK = {}", ns)
for fn in ("uac_spur_eintraege", "uac_alarm_schluessel", "uac_alarm_texte"):
    exec(block(src, f"def {fn}("), ns)
exec(block(src, '@app.route("/pc/uac-spur"'), ns)
cl = app.test_client()
E = {"pid": 4932, "seit": 1_799_998_000, "ausloeser": r"MT5-Update terminal64.exe für C:\MT5-100k1Phase1"}


def post(offen=(), weg=()):
    GES.clear()
    return cl.post("/pc/uac-spur", json={"offen": list(offen), "weg": list(weg)}).get_json()


post([E])
check(len(GES) == 1 and GES[0]["prio"] == 1 and GES[0]["zeichen"] is None and GES[0]["art"] == "uac_offen", "Railway: neue Abfrage → genau ein 🔴 (Prio 1)")
t = GES[0]["text"] if GES else ""
from zoneinfo import ZoneInfo
hhmm = datetime.fromtimestamp(E["seit"], ZoneInfo("Asia/Dubai")).strftime("%H:%M")
check("PC von Chris (pc-abc123)" in t and f"seit {hhmm}" in t and r"C:\MT5-100k1Phase1" in t and "Parsec mit Ja" in t,
      "Railway: Text nennt PC mit Namen, seit (Dubai), Auslöser und Handgriff")
ZUSTAND["jetzt"] += 300
post([E])
check(not GES, "Railway: nach 5 min noch offen → still (Entprellung über alarm_log)")
ZUSTAND["jetzt"] += 1501
post([E])
check(len(GES) == 1 and "noch offen" in GES[0]["text"], "Railway: nach 30 min noch offen → erneut, „noch offen“")
ZUSTAND["jetzt"] += 60
post(weg=[E])
check(len(GES) == 1 and GES[0]["zeichen"] == "✅ " and GES[0]["prio"] == 1 and GES[0]["push_prio"] == 3 and GES[0]["art"] == "uac_erledigt",
      "Railway: weg → einmal ✅ (Empfänger wie 🔴, Push leise wie ⚪)")
post(weg=[E])
check(not GES, "Railway: zweites „weg“ → kein zweites ✅")
post(weg=[dict(E, pid=777)])
check(not GES, "Railway: weg ohne vorheriges 🔴 → kein ✅")
ZUSTAND["wer"] = (EMIN, "pc-emin01")
post([dict(E, pid=1)])
check(not GES, "Railway: ID mit Verwalter (nicht HT) → nichts an die Master-IDs")
ZUSTAND["wer"] = (HT, PC)
ZUSTAND["log_kaputt"] = True
post([dict(E, pid=2, ausloeser="")])
n1 = len(GES)
ZUSTAND["jetzt"] += 300
post([dict(E, pid=2, ausloeser="")])
check(n1 == 1 and not GES, "Railway: alarm_log nicht lesbar → Merker im Speicher entprellt")
ZUSTAND["log_kaputt"] = False
post([{"pid": "x"}, {"pid": -3}, {"pid": 5, "seit": 12}] + [dict(E, pid=100 + i) for i in range(9)])
check(len(GES) == 5 and GES[0]["schluessel"] == "uac|pc-abc123|5|0" and all(g["schluessel"].startswith("uac|pc-abc123|10") for g in GES[1:]),
      "Railway: Unsinn verworfen (pid kein/negativ), unplausible seit → 0, höchstens 5 gültige Abfragen je Meldung")
# Railway-Neustart: Merker leer, alarm_log lesbar → kein zweites 🔴
E2 = dict(E, pid=3333)
post([E2])
ns["_UAC_ALARM_MERK"].clear()
ZUSTAND["jetzt"] += 300
post([E2])
check(not GES, "Gegenprüfung: Railway-Neustart (Merker leer) → alarm_log entprellt, kein zweites 🔴")
# Panel-Neustart ohne lesbare Startzeit: seit 0 bleibt, nur gesehen ändert sich → derselbe Schlüssel, kein zweites 🔴
E3 = {"pid": 4444, "seit": 0, "gesehen": 1_799_990_000, "ausloeser": ""}
post([E3])
t3 = GES[0]["text"] if GES else ""
ZUSTAND["jetzt"] += 300
post([dict(E3, gesehen=1_799_999_999)])
check(not GES and "seit spätestens" in t3, "Gegenprüfung: Panel-Neustart (neues gesehen) → kein zweites 🔴; Text „seit spätestens …“")
post(weg=[dict(E3, gesehen=1_799_999_999)])
check(len(GES) == 1 and GES[0]["art"] == "uac_erledigt", "Gegenprüfung: ✅ kommt auch nach Panel-Neustart")
# alarm_log lesbar, Schreiben scheitert → Merker entprellt trotzdem
ZUSTAND["log_schreibt_nicht"] = True
post([dict(E, pid=5555)])
n5 = len(GES)
ZUSTAND["jetzt"] += 300
post([dict(E, pid=5555)])
check(n5 == 1 and not GES, "Gegenprüfung: alarm_log-Schreiben scheitert → kein 🔴 alle 5 min")
ZUSTAND["log_schreibt_nicht"] = False
r = cl.post("/pc/uac-spur", json={"offen": [{"pid": float("inf")}, {"pid": 1e400}]}, headers={"Content-Type": "application/json"})
check(r.status_code == 200, "Gegenprüfung: pid inf → verworfen, kein 500")
r = cl.post("/pc/uac-spur", json={})
check(r.status_code == 200 and r.get_json().get("ok"), "Railway: leerer Body → ok, nichts gesendet")
ZUSTAND["wer"] = None
check(cl.post("/pc/uac-spur", json={"offen": [E]}).status_code == 403, "Railway: ohne gültigen PC-Schlüssel → 403")
check("zeichen=None, push_prio=None" in src[src.index("def alarm_senden("):src.index("def alarm_senden(") + 400] and "renotify=renotify or stufe == 1, prio=stufe" in src
      and "ALARM_ZEICHEN[prio] if zeichen is None else str(zeichen)" in src, "alarm_senden: zeichen optional, ohne Angabe wie bisher")

print(f"\n{'selftest_uac_alarm: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
sys.exit(1 if FEHLER else 0)
