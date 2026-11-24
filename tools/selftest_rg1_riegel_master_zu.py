#!/usr/bin/env python3
"""Selbsttest RG1 (24.11.2026, KC1-Befund D2): Review-Plan vom Vortag sperrte per Riegel Gegenrichtung das Schwesterkonto still bis zu 72 h —
Simon FundedNext …9853 → …9852 (Master zu + gelesen, nur Hedge-P&L fehlte), Blue Guardian 631978 → 631979 (Start UNKLAR). Kein Netz, keine DB.

Aufruf:  python3 tools/selftest_rg1_riegel_master_zu.py
Prüft:
 (1) sql/2026-11-24_rg1_riegel_master_zu.sql: der Riegel prophos_gegenrichtung_frei_konto weicht vom letzten Stand (2026-11-05, = live) GENAU in der
     review-Zeile (gelesen ODER prophos_plan_master_zu) und dem zusätzlichen Ausgabe-Feld 'seit' ab; prophos_plan_gelesen wird nicht angefasst;
 (2) prophos_plan_master_zu verlangt review + mt5/mt5v2 + ended_at + master_pl + final.master_balance > 0, nie bei UNKLAR, nie bei offener
     Master-Position laut mt5_live/mt5_live_flotte;
 (3) prophos_riegel_alt: nur heute geplante Pläne, nur Sperren über review/unklar, älter als p_stunden oder vom Vortag, liest nur;
 (4) app.py rg1_*: Kontoformat „ID · Firma Größe …4 · Unternehmen“, je sperrendem Plan genau eine 🟠 (prio 2), zweiter Takt still (alarm_log),
     ohne SQL (HTTP 404) still, alarm_log unlesbar → nichts;
 (5) prophos.html rkMasterZu wie die DB-Regel (ohne Live-Check) und in beiden gelesen-Stellen des Tab-Riegels.
Live-Gegenprobe (24.11.2026, nur lesend mit pg_temp-Kopien): …9852 alt gesperrt → neu frei; 631979 bleibt gesperrt; prophos_riegel_alt meldet genau
631979 (sperrt: 2106d28f review seit 23.11. 00:30); von allen heute geplanten Plänen ändert sich nur …9852."""
import difflib
import json
import os
import re
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import app  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


NEU = open(os.path.join(WURZEL, "sql", "2026-11-24_rg1_riegel_master_zu.sql"), encoding="utf-8").read()
ALT = open(os.path.join(WURZEL, "sql", "2026-11-05_gegenrichtung_nichts_gesendet.sql"), encoding="utf-8").read()


def body(s, name):
    i = s.index(f"function public.{name}")
    return s[i:s.index("end $function$", i)]


def norm(t):
    return [re.sub(r"\s+", " ", z).strip().lower() for z in t.splitlines() if z.strip() and not z.strip().startswith("--")]


# (1)
diff = [z for z in difflib.unified_diff(norm(body(ALT, "prophos_gegenrichtung_frei_konto")), norm(body(NEU, "prophos_gegenrichtung_frei_konto")),
                                        lineterm="", n=0) if z[:1] in "+-" and not z.startswith(("+++", "---"))]
check(diff == ["-and not (p.status = 'review' and public.prophos_plan_gelesen(p.id))",
               "+and not (p.status = 'review' and (public.prophos_plan_gelesen(p.id) or public.prophos_plan_master_zu(p.id)))",
               "+'seit', g.seit,"], f"Riegel: nur review-Zeile + Feld 'seit' geändert ({diff})")
check("function public.prophos_plan_gelesen" not in NEU, "prophos_plan_gelesen bleibt unverändert (nicht in der Datei)")
check(NEU.count("create or replace function") == 3 and "drop " not in NEU.lower(), "idempotent: create or replace, kein drop")

# (2)
mz = body(NEU, "prophos_plan_master_zu")
for teil, name in ((("p.status is distinct from 'review'", "p.route not in ('mt5', 'mt5v2')", "p.ended_at is null", "p.master_pl is null"),
                    "nur review + Echo-Route + ended_at + master_pl"),
                   (("(fin->>'master_balance')::numeric > 0",), "final.master_balance > 0"),
                   (("puls_unklar", "->'start_fehler'->>'unklar' = 'true'", "fin->>'art' = 'unklar'"), "nie bei UNKLAR"),
                   (("public.mt5_live l", "public.mt5_live_flotte l", "jsonb_array_length(l.status->'master_positions') > 0"),
                    "nie bei offener Master-Position laut mt5_live/mt5_live_flotte")):
    check(all(t in mz for t in teil), f"prophos_plan_master_zu: {name}")
check(mz.index("return false;\n  end if;\n  return true;") > 0 or mz.rstrip().endswith("return true;"), "sonst true")

# (3)
ra = body(NEU, "prophos_riegel_alt")
check("tp.status = 'planned' and tp.planned_for = heute" in ra and "f->>'art' not in ('review', 'unklar')" in ra
      and "make_interval(secs => p_stunden * 3600)" in ra and "(s at time zone 'Asia/Dubai')::date >= heute" in ra,
      "prophos_riegel_alt: heute geplant, nur review/unklar, älter als p_stunden ODER Vortag")
check(not re.search(r"\b(update|insert|delete)\b", ra, re.I), "prophos_riegel_alt liest nur")
check("if f->>'art' = 'review' then\n      select coalesce(tp.ended_at, s) into s" in ra, "Alter bei review ab dem Ende (Prüfer RG1: kein Fehlalarm ab Start)")
check("revoke all on function public.prophos_riegel_alt(numeric) from public, anon, authenticated;" in NEU
      and "revoke all on function public.prophos_plan_master_zu(uuid) from public, anon, authenticated;" in NEU
      and "to authenticated" not in NEU, "security definer: EXECUTE nur service_role (Prüfer RG1)")

# (4) app.py
check(app.RG1_STUNDEN == 6 and app.RG1_LOG_TAGE >= 1, "6 h, alarm_log-Entprellung")
acc = {"firm": "FundedNext", "name": "100k 14419853 → Phase 1", "external_id": "14419853"}
check(app.rg1_konto_text("Simon", acc, {}, "HT") == "Simon · FundedNext 100k …9853 · HT", "Kontoformat „ID · Firma Größe …4 · Unternehmen“")
check(app.rg1_konto_text("", None, {"master_firm": "Blue Guardian", "master_name": "100k 631978 → Phase 1"}, "") == "? · Blue Guardian 100k …1978",
      "ohne Konto-Zeile aus dem Plan")
daten = {"gruppen": [{"id": "g1", "name": "Emin Capital", "verwalter_id": "v1"}, {"id": "g0", "name": "HT"}],
         "mitglieder": [{"user_id": "u1", "gruppe_id": "g0"}, {"user_id": "u2", "gruppe_id": "g1"}]}
check(app.rg1_unternehmen_name("u1", daten) == "HT" and app.rg1_unternehmen_name("v1", daten) == "Emin Capital"
      and app.rg1_unternehmen_name("u9", daten) == "ohne Unternehmen", "Unternehmen: HT / Gruppenname / ohne")
Z = [{"gesperrt_plan": "q1", "sperrt_plan": "p1", "art": "review", "seit": "2026-11-23T08:13:32+00:00", "grund": "x"},
     {"gesperrt_plan": "q2", "sperrt_plan": "p1", "art": "review", "seit": "2026-11-23T08:13:32+00:00", "grund": "x"},
     {"gesperrt_plan": "q3", "sperrt_plan": "p2", "art": "unklar", "seit": "2026-11-23T00:30:00+00:00", "grund": "y"}]
PL = {"p1": {"user_id": "u1", "master_account_id": "a1", "master_firm": "FundedNext", "master_name": "100k 14419853 → Phase 1"},
      "q1": {"user_id": "u1", "master_account_id": "a2", "master_firm": "FundedNext", "master_name": "100k 14419852 → Phase 1"},
      "q2": {"user_id": "u1", "master_account_id": "a2", "master_firm": "FundedNext", "master_name": "100k 14419852 → Phase 1"},
      "p2": {"user_id": "u2", "master_account_id": None, "master_firm": "Blue Guardian", "master_name": "100k 631978 → Phase 1"},
      "q3": {"user_id": "u2", "master_account_id": None, "master_firm": "Blue Guardian", "master_name": "100k 631979 → Phase 1"}}
KO = {"a1": acc, "a2": dict(acc, name="100k 14419852 → Phase 1", external_id="14419852")}
m = app.rg1_meldungen(Z, PL, KO, {"u1": "Simon", "u2": "Amir"}, lambda u: "HT")
check(len(m) == 2 and {x[0] for x in m} == {"riegel_alt|p1", "riegel_alt|p2"}, "je SPERRENDEM Plan genau eine Meldung")
t1 = [x for x in m if x[4] == "p1"][0]
check(t1[1] == "u1" and "Simon · FundedNext 100k …9853 · HT" in t1[3] and t1[3].count("…9852") == 1 and "Sperre bleibt" in t1[3]
      and "12:13 Dubai" in t1[2], f"Text: wer sperrt, wen (doppelte zusammen), Sperre bleibt, Zeit in Dubai ({t1[2]})")
t2 = [x for x in m if x[4] == "p2"][0]
check("UNKLARER Start" in t2[3] and "Amir · Blue Guardian 100k …1978 · HT" in t2[3], "UNKLAR-Fall mit eigenem Handgriff")

# rg1_tick mit Attrappen
class R:
    def __init__(self, code, d):
        self.status_code, self._d = code, d

    def json(self):
        return self._d


alt = {n: getattr(app, n) for n in ("_sb_anfrage", "alarm_im_log", "sb_select", "_ap_namen", "admin_gruppen_daten", "alarm_senden", "_alarm_empfaenger",
                                    "_alarm_fremd_verwaltet")}
try:
    gesendet = []
    app._alarm_empfaenger = lambda: {"m1": 2}
    app._sb_anfrage = lambda *a, **k: R(200, Z)
    app.sb_select = lambda t, p: list(PL.items()) and [dict(v, id=k) for k, v in PL.items()] if t == "trade_plans" else [dict(v, id=k) for k, v in KO.items()]
    app._ap_namen = lambda: ({"u1": "Simon", "u2": "Amir"}, set())
    app.admin_gruppen_daten = lambda: {}
    app.alarm_senden = lambda prio, art, titel, text, **k: gesendet.append((prio, art, titel, text, k))
    app._alarm_fremd_verwaltet = lambda uid: str(uid) == "u3"
    app.alarm_im_log = lambda keys, s: set()
    app._rg1["at"] = 0.0
    n = app.rg1_tick()
    check(n == 2 and all(g[0] == 2 and g[1] == "riegel_alt" for g in gesendet) and {g[4]["schluessel"] for g in gesendet} == {"riegel_alt|p1", "riegel_alt|p2"},
          f"Takt: zwei 🟠 (prio 2) mit eigenem alarm_log-Schlüssel ({n})")
    gesendet.clear()
    app._rg1["at"] = 0.0
    app.alarm_im_log = lambda keys, s: set(keys)
    check(app.rg1_tick() == 0 and not gesendet, "zweiter Takt: schon im alarm_log → nichts")
    app._rg1["at"] = 0.0
    app.alarm_im_log = lambda keys, s: None
    check(app.rg1_tick() is None and not gesendet, "alarm_log unlesbar → nichts (nie doppelt)")
    app._rg1["at"] = 0.0
    app._sb_anfrage = lambda *a, **k: R(404, {"message": "function not found"})
    check(app.rg1_tick() is None and not gesendet and "404" in app._rg1["fehler"], "SQL nicht eingespielt (404) → still, Grund gemerkt")
    app._rg1["at"] = 1e18
    check(app.rg1_tick() is None, "Takt RG1_TAKT_S")
    # Prüfer RG1: nur HT-Sicht — ausgeblendete IDs und fremd verwaltete Gruppen nie an die HT-Master-IDs
    PL.update({"p4": {"user_id": "u3", "master_firm": "FundedNext", "master_name": "100k 11110001 → Phase 1"},
               "q4": {"user_id": "u3", "master_firm": "FundedNext", "master_name": "100k 11110002 → Phase 1"},
               "p5": {"user_id": "u9", "master_firm": "FundedNext", "master_name": "100k 22220001 → Phase 1"},
               "q5": {"user_id": "u9", "master_firm": "FundedNext", "master_name": "100k 22220002 → Phase 1"}})
    app._sb_anfrage = lambda *a, **k: R(200, [{"gesperrt_plan": "q4", "sperrt_plan": "p4", "art": "review", "seit": "2026-11-23T08:00:00+00:00"},
                                             {"gesperrt_plan": "q5", "sperrt_plan": "p5", "art": "review", "seit": "2026-11-23T08:00:00+00:00"}])
    app._ap_namen = lambda: ({"u3": "Emin-ID", "u9": "Aus"}, {"u9"})
    app.alarm_im_log = lambda keys, s: set()
    app._rg1["at"] = 0.0
    gesendet.clear()
    check(app.rg1_tick() == 0 and not gesendet, "fremd verwaltete (Emin) und ausgeblendete IDs → keine Meldung an HT")
finally:
    for k, v in alt.items():
        setattr(app, k, v)
    app._rg1["at"], app._rg1["fehler"] = 0.0, ""
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
check("if rg1_tick() is not None:" in src and src.index("ohne_unternehmen_tick()           # UNT0") < src.index("if rg1_tick() is not None:"),
      "rg1_tick im ap_loop (eigener try, nach UNT0)")

# (5) Tab
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check(html.count("|| rkMasterZu(") == 2, "Tab-Riegel: beide gelesen-Stellen mit rkMasterZu")
m_ = re.search(r"  function rkMasterZu\(.*?\n  \}\n", html, re.S)
if shutil.which("osascript") and m_:
    faelle = [("review", "mt5", "x", -69.27, {"master_balance": 99930.73}, None, True),
              ("review", "mt5", "x", None, {"master_balance": 99930.73}, None, False),
              ("review", "mt5", "x", 1, {"master_balance": 0}, None, False),
              ("review", "mt5", "x", 1, {"master_balance": 5, "art": "unklar"}, None, False),
              ("review", "mt5", "x", 1, {"master_balance": 5}, {"unklar": True}, False),
              ("review", "tvv2", "x", 1, {"master_balance": 5}, None, False),
              ("open", "mt5", "x", 1, {"master_balance": 5}, None, False),
              ("review", "mt5v2", None, 1, {"master_balance": 5}, None, False)]
    faelle = [x[:6] + (None, x[6]) for x in faelle] + [("review", "mt5", "x", 1, {"master_balance": 5}, None, {"at": "x"}, False)]
    js = m_.group(0) + "JSON.stringify([" + ",".join(
        f"rkMasterZu({json.dumps(a)},{json.dumps(b)},{json.dumps(c)},{json.dumps(d)},{json.dumps(e)},{json.dumps(f)},{json.dumps(g)})" for a, b, c, d, e, f, g, _ in faelle) + "])"
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    try:
        erg = json.loads(r.stdout.strip())
    except Exception:
        erg = None
    check(erg == [x[-1] for x in faelle], f"rkMasterZu: zu nur mit allen Belegen, nie UNKLAR/puls_unklar/andere Route/ohne Ende ({erg or r.stderr[:100]})")
else:
    print("· JS-Prüfung übersprungen (kein osascript)")

print()
print("ALLES OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
