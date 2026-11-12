#!/usr/bin/env python3
"""Selbsttest PA1 „Approved“-Schritt bei Payouts unterwegs (Finn 12.11.2026 ~20:05 Dubai: „Nach dem Anfragen steht erst nur ‚Approved‘ … Bei ‚Approved‘ wird das
Konto schon wieder freigeschaltet und für Winning Days gefahren. Bei ‚Erhalten‘ wird erst wirklich zu Finanzen gebucht.“).
Prüft die rein rechnenden Teile aus app.py (payout_sperrt, _payout_offen_ids mit gefälschtem Supabase, payout_approved_zurueck_urteil), die Einbau-Anker
(alle WD-Sperren, Route, Übersicht, Erhalten unverändert), prophos.html (Knöpfe, PC-Tab-Sperre, Handy) inkl. admPayoutSchrittHtml in JavaScriptCore, und die SQL.
Ohne Netz. Aufruf: python3 tools/selftest_pa1_payout_approved.py"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
SQL = os.path.join(W, "sql", "2026-11-12_pa1_payout_approved.sql")
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


def quelle(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^\S)", APP, re.S | re.M)
    if not m:
        raise LookupError(name)
    return m.group(0)


ns = {"datetime": datetime, "timezone": timezone, "timedelta": timedelta, "re": re}
for n in ("_ap_ts", "sb_spalte_fehlt", "payout_sperrt", "_payout_offen_ids", "payout_approved_zurueck_urteil"):
    try:
        exec(quelle(n), ns)
    except LookupError:
        check(False, f"app.py hat {n}")
if fehler:
    sys.exit(1)

# ── Sperre
ps = ns["payout_sperrt"]
check(ps({"status": "pending", "approved_at": None}) is True, "offene Anfrage ohne Approved sperrt (wie bisher)")
check(ps({"status": "pending", "approved_at": "2026-11-12T10:00:00Z"}) is False, "approved → sperrt nicht mehr (Konto fährt wieder)")
check(ps({"status": "received"}) is False, "erhalten → sperrt nicht")
check(ps({}) is True, "Zeile ohne Status/Spalte (alter Stand) → sperrt wie bisher")

# ── _payout_offen_ids mit gefälschtem Supabase
ZEILEN = [{"account_id": "a1", "approved_at": None}, {"account_id": "a2", "approved_at": "2026-11-12T10:00:00Z"}, {"account_id": "a3", "approved_at": None}]
aufrufe = []


class _Antwort:
    def __init__(self, code, text):
        self.status_code, self.text = code, text


class HTTPFehler(Exception):
    """wie requests.HTTPError: str() nennt nur Status + URL (mit approved_at im select), der PostgREST-Text steht in response.text"""
    def __init__(self, code, text):
        super().__init__(f"{code} Client Error for url: https://x.supabase.co/rest/v1/pending_payouts?select=account_id%2Capproved_at")
        self.response = _Antwort(code, text)


def sb_fake(tabelle, q):
    aufrufe.append(q)
    if "approved_at" in q["select"] and ns.get("_ohne_spalte"):
        raise HTTPFehler(400, '{"code":"42703","message":"column pending_payouts.approved_at does not exist"}')
    if ns.get("_kaputt"):
        raise HTTPFehler(503, "Service Unavailable")
    ids = None
    if "account_id" in q:
        ids = set(q["account_id"][4:-1].split(","))
    return [dict(z) if "approved_at" in q["select"] else {"account_id": z["account_id"]} for z in ZEILEN if ids is None or z["account_id"] in ids]


sf = ns["sb_spalte_fehlt"]
check(sf(HTTPFehler(400, '{"code":"42703","message":"column pending_payouts.approved_at does not exist"}'), "approved_at") is True, "Spalte fehlt: 400 + 42703 erkannt")
check(sf(HTTPFehler(503, "Service Unavailable"), "approved_at") is False, "503 (URL nennt approved_at) ist KEIN „Spalte fehlt“ (Prüfer PA1)")
check(sf(HTTPFehler(400, '{"code":"PGRST100","message":"failed to parse filter"}'), "approved_at") is False, "anderer 400er ist kein „Spalte fehlt“")
check(sf(RuntimeError("approved_at does not exist"), "approved_at") is False, "Fehler ohne Antwort zählt nie als „Spalte fehlt“")
ns["_sb_all"] = sb_fake
ns["sb_select"] = sb_fake
off = ns["_payout_offen_ids"]
check(off() == {"a1", "a3"}, f"alle offenen: approved a2 fehlt ({off()})")
check(off(["a2", "a3"]) == {"a3"}, "nur diese Konten: a2 approved → nur a3")
check(off([]) == set(), "leere Liste → nichts, keine Abfrage")
check(all(q.get("status") == "eq.pending" for q in aufrufe), "nur status pending gelesen")
ns["_ohne_spalte"] = True
check(off() == {"a1", "a2", "a3"}, "Spalte approved_at fehlt (SQL noch nicht eingespielt) → jede offene Anfrage sperrt wie vor PA1")
ns["_ohne_spalte"] = False
ns["_kaputt"] = True
try:
    off(["a1"])
    check(False, "echter Lesefehler wird weitergereicht (fail-closed beim WD-Anlegen)")
except HTTPFehler:
    check(True, "echter Lesefehler wird weitergereicht (fail-closed beim WD-Anlegen)")
ns["_kaputt"] = False
viele = [f"k{i:03d}" for i in range(170)]
aufrufe.clear()
off(viele)
check(len(aufrufe) == 3, f"Konten in Teilen zu 80 gelesen ({len(aufrufe)} Abfragen für 170)")

# ── Rückweg
zu = ns["payout_approved_zurueck_urteil"]
A = "2026-11-12T10:00:00+00:00"
check(zu(A, [])[0] is True, "Approved ohne Plan danach → zurücknehmbar")
check(zu(A, [{"started_at": "2026-11-12T09:00:00Z"}, {"start_um_gestartet_at": None}])[0] is True, "Plan vor dem Approved zählt nicht")
ok, g = zu(A, [{"master_name": "150k X", "started_at": "2026-11-12T11:00:00Z"}])
check(ok is False and "gestartet" in g, f"Trade nach dem Approved gestartet → Hinweis statt Rücknahme ({g})")
check(zu(A, [{"start_um_gestartet_at": "2026-11-12T10:05:00Z"}])[0] is False, "auch start_um_gestartet_at zählt")
check(zu(None, [])[0] is False, "nicht approved → nichts zurückzunehmen")

# ── Einbau-Anker app.py
check(APP.count("_payout_offen_ids(") >= 4, "drei WD-Sperren nutzen _payout_offen_ids (Abgleich, GET-Liste, Anlegen) + Definition")
check('offen = _payout_offen_ids()' in quelle("wd_payout_tick"), "wd_payout_tick (W1-Abgleich): approved = nicht mehr offen, das Konto kommt zurück")
check(not re.search(r'sb_select\("pending_payouts", \{"select": "account_id", "status": "eq\.pending",\s*"account_id"', APP), "keine alte WD-Sperre ohne approved_at mehr")
route = quelle("admin_payout_approved")
check('"/admin/payout-approved"' in APP and '"approved_at": "is.null"' in route and '"status": "eq.pending"' in route, "Route: Guard status pending + approved_at is.null (zweiter Klick → 409)")
check('"approved_at": f"eq.{p[\'approved_at\']}"' in route and "payout_approved_zurueck_urteil(" in route and '"or": f"(started_at.gte.{_ab},start_um_gestartet_at.gte.{_ab})"' in route
      and '"created_at": f"gte.' not in route, "Rückweg: Guard auf den gelesenen Wert + Prüfung „kein Trade gestartet“")
check(route.count("threading.Thread(target=wd_payout_tick") == 2, "Approved und Rücknahme stoßen wd_payout_tick sofort an")
check('"transactions"' not in route, "Approved bucht NICHTS (keine transactions-Zeile)")
check("_admin_voll()" in route and "_admin_verwalter()" in route and '"Nur Anfragen der eigenen Gruppe"' in route, "Rechte wie „Erhalten“ (Admin, Verwalter nur eigene Gruppe)")
erh = quelle("admin_payout_erhalten")
check('"transactions"' in erh and "approved" not in erh, "„Erhalten“ bucht unverändert")
check('"approved_at": t.get("approved_at") or None' in APP and ',approved_at,approved_von"' in APP, "Übersicht liefert approved_at/approved_von (mit Rückfall ohne Spalte)")

# ── prophos.html
check(".select('account_id,approved_at').eq('user_id', uid).eq('status', 'pending')" in HTML and ".filter(x => !x.approved_at)" in HTML,
      "PC-Tab wdKontenFrisch: approved sperrt nicht (wie payout_sperrt), Rückfall ohne Spalte")
check("${admPayoutSchrittHtml(t)}" in HTML and "admPayoutSchrittVerdrahten(tr, t)" in HTML, "Admin → Payouts unterwegs: Approved/Erhalten-Schritt")
check("window._admPayoutSchritt.html(t, { klein: true })" in HTML and "window._admPayoutSchritt.verdrahten(td, t, { naechsterTage: 14, waitingLeeren: true" in HTML,
      "Funded Planer → CFD „Payouts auf dem Weg“: derselbe Schritt")
check("/admin/payout-approved?ansicht=admin" in HTML and "zurueck: true" in HTML, "Frontend ruft die Route (auch Rücknahme)")
check("#dashboard-view #adm-f-pend-rows td:last-child" in HTML and "position:sticky;right:0;background:var(--surface, #fff)" in HTML, "Handy: Knopf-Spalte klebt rechts (Hintergrund --surface, auch dunkel)")

# admPayoutSchrittHtml echt in JavaScriptCore
m = re.search(r"    const admPayoutApprovedTxt = .*?\n    function admPayoutSchrittHtml\(t, o\)\{.*?\n    \}\n", HTML, re.S)
osa = shutil.which("osascript")
if m and osa:
    js = ("const escapeHtml = s => String(s);\n" + m.group(0) +
          "const a = admPayoutSchrittHtml({id:'x', approved_at:null}), b = admPayoutSchrittHtml({id:'y', approved_at:'2026-11-12T10:00:00Z'}), c = admPayoutSchrittHtml({approved_at:null});\n"
          "JSON.stringify([a.includes('pp-appr') && !a.includes('pp-ok'), b.includes('Approved am 12.11.') && b.includes('pp-ok') && b.includes('pp-appr-x'), c === ''])")
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
        f.write(js)
    try:
        out = subprocess.run([osa, "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30).stdout.strip()
    finally:
        os.unlink(f.name)
    check(out == "[true,true,true]", f"admPayoutSchrittHtml: ohne Approved nur [Approved], mit Approved „Approved am 12.11.“ + zurück + [✓ erhalten], ohne id nichts ({out})")
else:
    check(bool(m), "admPayoutSchrittHtml gefunden (JavaScriptCore fehlt → nur Anker)")

# ── SQL
sq = open(SQL, encoding="utf-8").read() if os.path.exists(SQL) else ""
code = "\n".join(z for z in sq.splitlines() if not z.strip().startswith("--"))
check("add column if not exists approved_at timestamptz" in code and "add column if not exists approved_von text" in code, "SQL: zwei Spalten, idempotent")
check(not re.search(r"\b(update|delete|insert)\b", code, re.I), "SQL: keine Daten geändert (bestehende Anfragen bleiben ohne Approved)")

print()
if fehler:
    print(f"ROT: {len(fehler)} Prüfung(en)")
    sys.exit(1)
print("GRÜN: PA1 Approved-Schritt (Sperre, Route, Rückweg, Anzeige, SQL)")
