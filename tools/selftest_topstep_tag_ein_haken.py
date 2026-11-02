#!/usr/bin/env python3
"""Selbsttest TOPSTEP-TAG: NUR EINMAL ABHAKEN (Finn 02.11.2026 ~19:15 Dubai: „ja — der zweite Trade: wenn ich einmal abhaken würde, zusammenfassen,
was im ersten und im zweiten passiert ist, jeweils. Aber ich will nur einmal abhaken.")

Aufruf:  python3 tools/selftest_topstep_tag_ein_haken.py
Ohne Netz. Geprüft:
  app.py   ap_kette_lesen_bis (Fensterende t2_bis am Handelstag des Endes, nur Trade 1 mit möglichem Trade 2), ap_kette_abhaken schreibt es einmal
           an Trade 1, lt_kette_teil/lt_kette_teile (Richtung, Ende, P&L gelesen/eingetragen/geschätzt, Trade 1 über kette.vor oder kette.e1).
  Radar    wdlKetteT1Offen / wdlWartet (Trade 1 bleibt in „Wartet", auch nach 8 Versuchen und gelesen ohne Trade 2), wdlKetteTagChip (je Trade eine Zeile,
           ≈ bei Schätzung, Summe ohne Tagesergebnis), tpKetteLesenWeiter (PC-Tab liest bis zum Fensterende weiter)."""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
APP = os.path.join(HIER, "..", "app.py")
HTML = os.path.join(HIER, "..", "prophos.html")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


src = open(APP, encoding="utf-8").read()


def block(name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


ns = {"datetime": datetime, "timezone": timezone, "re": re}
exec("\n\n".join(block(f) for f in ("_wd_num", "_ap_ts", "_ap_hhmm", "_ap_tz", "ap_kette_t1_fertig", "ap_kette_lesen_bis", "lt_kette_teil", "lt_kette_teile")), ns)
TZ = ZoneInfo("Europe/Berlin")
KR = {"t2_bis": "19:30"}

# ── ap_kette_lesen_bis ──
lb = ns["ap_kette_lesen_bis"]
check(lb({"nr": 1}, "2026-11-02T08:00:00Z", KR, TZ) == "2026-11-02T18:30:00Z", "Trade 1: Fensterende 19:30 dt = 18:30 UTC (Winterzeit)")
check(lb({"nr": 1}, "2026-10-20T08:00:00Z", KR, TZ) == "2026-10-20T17:30:00Z", "Sommerzeit: 19:30 dt = 17:30 UTC")
check(lb({"nr": 2}, "2026-11-02T08:00:00Z", KR, TZ) is None, "Trade 2: kein Fensterende")
check(lb({"nr": 1, "reparatur": True}, "2026-11-02T08:00:00Z", KR, TZ) is None, "Reparatur-Tag: kein Trade 2")
check(lb({"nr": 1, "ein_trade": True}, "2026-11-02T08:00:00Z", KR, TZ) is None, "ein_trade: kein Trade 2")
check(lb({"nr": 1}, "2026-11-02T08:00:00Z", KR, TZ, "Asia/Dubai") == "2026-11-02T15:30:00Z", "fenster_tz Dubai: 19:30 Dubai = 15:30 UTC (wie ap_start_bis)")
check(lb({"nr": 1}, None, KR, TZ) is None and lb({"nr": 1}, "2026-11-02T08:00:00Z", None, TZ) is None, "ohne Ende oder Regel: None")

# ── lt_kette_teil / lt_kette_teile ──
def plan(nr, b0=None, b1=None, quelle="puls", mpl=None, grund=None, **k):
    fin = {"balance_end": b1, "quelle": quelle, "plattform": "tsx"} if b1 is not None else {}
    if grund:
        fin["grund"] = grund
    return {"id": f"t{nr}", "richtung": "buy", "master_pl": mpl,
            "mt5_baseline": {"kette": dict({"nr": nr}, **k), "tv": {"balance_start": b0} if b0 is not None else {}, "final": fin}}


teile = ns["lt_kette_teile"]
t1 = plan(1, 150000, 152322.44)
z1 = {"richtung": "buy", "demo": {"status": "tp", "pl_usd": 2300}}
t2 = plan(2, 152322.44, 147114.88, vor="t1", e1=2322.44)
z2 = {"richtung": "sell", "demo": {"status": "liquidiert", "stop": "sl", "pl_usd": -5100}}
r = teile(t2, z2, t1, z1)
check([x["nr"] for x in r] == [1, 2], "Trade 2: zwei Teile")
check(r[0] == {"nr": 1, "richtung": "buy", "pl": 2322.44, "art": "gelesen", "ende": "tp"}, f"Trade 1 Long · TP · gelesen ({r[0]})")
check(r[1] == {"nr": 2, "richtung": "sell", "pl": -5207.56, "art": "gelesen", "ende": "sl"}, f"Trade 2 Short · SL · gelesen ({r[1]})")
r = teile(t2, z2, None, None)
check(r[0]["pl"] == 2322.44 and r[0]["art"] == "gelesen" and r[0]["richtung"] is None, "Trade 1 nicht in der Liste: P&L aus kette.e1")
t2u = plan(2, 152322.44, None, vor="t1", e1=2322.44)
r = teile(t2u, {"richtung": "sell", "demo": {"status": "tp", "pl_usd": 2172}}, t1, z1)
check(r[1]["art"] == "geschaetzt" and r[1]["pl"] == 2172 and r[1]["ende"] == "tp", "Trade 2 ungelesen: Demo-Schätzung, als geschätzt markiert")
t2f = plan(2, 152322.44, 152000, quelle="folgetrade", vor="t1")
check(teile(t2f, {"demo": {}}, t1, z1)[1]["art"] is None, "Folgetrade-Balance zählt nicht als Lesung, ohne Demo kein Wert")
t1h = plan(1, 150000, None, mpl=-1777.56, grund="hand")
r = teile(t1h, {"richtung": "buy", "demo": {"status": "offen", "pl_usd": -1700}})
check(r == [{"nr": 1, "richtung": "buy", "pl": -1777.56, "art": "eingetragen", "ende": "hand"}], f"Trade 1 von Hand eingetragen, Hand-Ende ({r})")
t2s = plan(2, 152322.44, None, mpl=1650, vor="t1")
t2s["mt5_baseline"]["final"] = {"master_pl_schaetzung": 1650}
check(teile(t2s, {"demo": {"status": "tp"}}, t1, z1)[1]["art"] == "geschaetzt", "master_pl = Vorbelegung mit der Schätzung → geschätzt, nicht eingetragen")
check(teile({"mt5_baseline": {}}, {}) is None, "ohne Kette: None")
check(teile({"mt5_baseline": {"kette": {"nr": 3}}}, {}) is None, "Kette nr 3: None")

# ── ap_kette_abhaken schreibt lesen_bis einmal an Trade 1 ──
import selftest_kette_tagesende as te  # noqa: E402
k1 = dict(te.GESUND, nr=1)
u1 = te.plan("t1", k1, 150000, None)
u1["mt5_baseline"]["final"] = {}
_w, u, rp = te.abhaken([u1])
x = (te.LESEN_BIS or [{}])[0]
check((x.get("p_patch") or {}).get("lesen_bis") and x.get("p_key") == "kette", f"Trade 1 ungelesen: lesen_bis geschrieben ({x.get('p_patch')})")
check(not u, "Trade 1 ungelesen: nichts abgehakt")
u1b = te.plan("t1", dict(k1, lesen_bis="2026-10-30T18:30:00Z", lesen_bis_at="2026-10-30T09:01:00Z"), 150000, None)
u1b["mt5_baseline"]["final"] = {}
_w, u, rp = te.abhaken([u1b])
check(not rp and not te.LESEN_BIS, "lesen_bis schon gerechnet: kein neues Schreiben")
_w, u, rp = te.abhaken([u1], regeln_fehler=True)
check(not rp and not te.LESEN_BIS, "Regeln nicht lesbar: nichts geschrieben, nächster Takt versucht neu")
_w, u, rp = te.abhaken([te.plan("t2", dict(te.GESUND, nr=2), 150000, None)])
check(not te.LESEN_BIS, "Trade 2: kein lesen_bis")
check(x.get("p_patch", {}).get("lesen_bis") == "2026-10-30T18:30:00Z", f"lesen_bis = 19:30 dt am 30.10. (Winterzeit) ({x.get('p_patch')})")
_w, u, rp = te.abhaken([te.plan("t1", k1, 150000, 148500)])
check(_w == ["t1"] and not te.LESEN_BIS, "Trade 1 gelesen mit Trade 2: abgehakt wie bisher, kein lesen_bis vor dem gesperrten Schreiben (updated_at)")
_w, u, rp = te.abhaken([te.plan("t1", k1, 150000, 148500)], t2_da=False)
check(not _w and u.get("t1", {}).get("master_pl") == -1500.0 and te.LESEN_BIS, "Trade 1 gelesen, wartet auf Trade 2: erst P&L, danach lesen_bis")

# ── Frontend in JavaScriptCore ──
html = open(HTML, encoding="utf-8").read()


def fn(name):
    i = html.index(f"\n  function {name}(") + 1
    e = html.index("\n  }\n", i)
    return html[i:e + 4]


STUBS = """
const escapeHtml = s => String(s), TV_ENDLESUNG_MAX = 8, TV_ENDLESUNG_KETTE_MAX = 30, wdlIstPolar = () => false, wdlTpUndWeg = t => !!(t && t._tpweg);
const tvV2LoginBremse = () => null, tvV2NachleseAb = () => 1;
"""
JETZT = "Date.parse('2026-11-02T12:00:00Z')"
js = STUBS + "\n".join(fn(n) for n in ("tpKetteLesenWeiter", "wdlKetteT1Offen", "wdlWartet", "wdlWartetLesung", "wdlKetteTeilZeile", "wdlKetteTagChip"))
js += f"\nDate.now = () => {JETZT};\n"
BIS, VORBEI = "2026-11-02T18:30:00Z", "2026-11-02T11:00:00Z"
T1 = {"id": "a", "route": "tsv2", "status": "review", "kette_nr": 1, "kette_lesen_bis": BIS, "balance_start": 150000, "balance_end": None,
      "endlesung": {"puls_versuche": 8, "puls_at": "2026-11-02T04:14:00Z"}}
FAELLE = {
    "t1_8_versuche": T1,
    "t1_fenster_vorbei": dict(T1, kette_lesen_bis=VORBEI),
    "t1_ohne_marke": dict(T1, kette_lesen_bis=None),
    "t1_gelesen_wartet_t2": dict(T1, balance_end=152322, endlesung={"balance_end": 152322, "quelle": "puls"}),
    "t1_tagesende": dict(T1, balance_end=152322, endlesung={"balance_end": 152322}, kette_tag={"tag_pl": 2322, "t1_pl": 2322, "trades": 1}),
    "t1_konto_weg": dict(T1, endlesung={"puls_versuche": 8, "konto_weg": True, "puls_aufgegeben": True}),
    "t1_geblowt": dict(T1, blown=True),
    "t1_bestanden": dict(T1, _tpweg=True),
    "t2_8_versuche": dict(T1, kette_nr=2, kette_lesen_bis=None),
    "t1_ohne_start": dict(T1, balance_start=None),
    "t1_unplausibel": dict(T1, balance_end=152322, endlesung={"balance_end": 152322, "quelle": "puls"}, kette_grund="Ergebnis unplausibel (+40.000 $) — von Hand abhaken"),
    "t1_30_versuche": dict(T1, endlesung={"puls_versuche": 30}),
    "t1_folgetrade": dict(T1, balance_end=152322, endlesung={"balance_end": 152322, "quelle": "puls", "balance_quelle": "folgetrade", "puls_versuche": 8}),
}
js += "const F = " + json.dumps(FAELLE) + ";\n"
js += "const W = {}; for(const k in F){ const w = wdlWartet(F[k]); W[k] = w ? (w.kette || 'lesung') : null }\n"
TEILE = [{"nr": 1, "richtung": "buy", "pl": 2322.44, "art": "gelesen", "ende": "tp"}, {"nr": 2, "richtung": "sell", "pl": -5207.56, "art": "gelesen", "ende": "sl"}]
CHIPS = {
    "mit_tagesende": {"status": "review", "kette_tag": {"tag_pl": -2714, "t1_pl": 2493.66, "t2_pl": -5207.56, "balance": 151777}, "kette_teile": TEILE},
    "ohne_tagesende_geschaetzt": {"status": "review", "route": "tsv2", "kette_nr": 2, "kette_teile": [TEILE[0], dict(TEILE[1], art="geschaetzt", pl=2172)]},
    "t1_wartet": dict(T1, kette_teile=[TEILE[0]]),
    "t1_nach_fenster": dict(T1, kette_lesen_bis=VORBEI, kette_teile=[dict(TEILE[0], art="geschaetzt", pl=-1723, ende="sl")]),
    "alt_ohne_teile": {"status": "review", "kette_tag": {"tag_pl": 4495, "t1_pl": 2322.44, "t2_pl": 2172.44, "balance": 158991}},
}
js += "const C = " + json.dumps(CHIPS) + "; const K = {}; for(const k in C) K[k] = wdlKetteTagChip(C[k]);\n"
P = {"lesen": {"mt5Baseline": {"kette": {"nr": 1, "lesen_bis": BIS}}}, "cap": {"mt5Baseline": {"kette": {"nr": 1, "lesen_bis": BIS}, "final": {"puls_versuche": 30}}}, "vorbei": {"mt5Baseline": {"kette": {"nr": 1, "lesen_bis": VORBEI}}},
     "t2": {"mt5Baseline": {"kette": {"nr": 2, "lesen_bis": BIS}}}, "tagesende": {"mt5Baseline": {"kette": {"nr": 1, "lesen_bis": BIS, "tagesende": {"tag_pl": 1}}}},
     "ohne": {"mt5Baseline": {}}}
js += "const P = " + json.dumps(P) + f"; const L = {{}}; for(const k in P) L[k] = tpKetteLesenWeiter(P[k], {JETZT});\n"
js += "print(JSON.stringify({ W, K, L }));\n"
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0 and r.stdout.strip(), f"jsc läuft ({(r.stderr or r.stdout)[:300]})")
erg = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {"W": {}, "K": {}, "L": {}}
W, K, L = erg["W"], erg["K"], erg["L"]
check(W.get("t1_8_versuche") == "lesen", "Trade 1 nach 8 Versuchen, Fenster offen: bleibt in Wartet (liest weiter)")
check(W.get("t1_fenster_vorbei") is None, "Trade 1, Fenster vorbei: nicht mehr Wartet → Abhak-Zeile mit Schätzung")
check(W.get("t1_ohne_marke") is None, "Trade 1 ohne lesen_bis (alter Weg): wie bisher")
check(W.get("t1_gelesen_wartet_t2") == "t2", "Trade 1 gelesen, Trade 2 noch nicht da: Wartet „Trade 2 folgt“")
check(W.get("t1_tagesende") is None, "Trade 1 letzter Trade (Tagesende): Abhak-Zeile")
check(W.get("t1_konto_weg") is None and W.get("t1_geblowt") is None and W.get("t1_bestanden") is None, "Konto weg / geblowt / bestanden: sofort abhakbar")
check(W.get("t1_ohne_start") is None, "Trade 1 ohne Start-Balance: nie Trade 2 → abhakbar")
check(W.get("t1_unplausibel") is None, "Trade 1 „von Hand abhaken“ (unplausibel): sofort abhakbar")
check(W.get("t1_30_versuche") is None, "Trade 1 nach 30 Versuchen: Puls hört auf → abhakbar mit Schätzung")
check(W.get("t1_folgetrade") is None, "Trade 1 mit Folgetrade-Balance: keine genaue Lesung → nicht „Trade 2 folgt“")
check(W.get("t2_8_versuche") is None, "Trade 2 nach 8 Versuchen: wie bisher (Haken mit Schätzung)")
c = K.get("mit_tagesende") or ""
check("Tag +2.494 $ − 5.208 $ =" in c and "T1 Long · TP · +2.322 $" in c and "T2 Short · SL · −5.208 $" in c and "Balance 151.777 $" in c, f"Chip mit Tagesergebnis: je Trade eine Zeile ({c})")
c = K.get("ohne_tagesende_geschaetzt") or ""
check("≈ +4.494 $" in c and "T2 Short · SL · ≈ +2.172 $" in c, f"Chip ohne Tagesergebnis: Summe aus den Teilen mit ≈ ({c})")
check(K.get("t1_wartet") == "", "wartender Trade 1: kein Chip")
c = K.get("t1_nach_fenster") or ""
check("(1 Trade)" in c and "≈ −1.723 $" in c, f"Trade 1 nach dem Fenster: (1 Trade) ≈ ({c})")
c = K.get("alt_ohne_teile") or ""
check("Tag +2.322 $ + 2.172 $ =" in c and "T1" not in c, "alte Zeile ohne kette_teile: Chip wie bisher")
check(L == {"lesen": True, "cap": False, "vorbei": False, "t2": False, "tagesende": False, "ohne": False}, f"tpKetteLesenWeiter ({L})")
check("!tpKetteLesenWeiter(p, jetzt)) return `${versuche} Versuche erfolglos`" in html, "Endlesung gibt Kette-Trade 1 nicht nach 8 Versuchen auf")
check("!wt.kette && (wt.login || wdlLesungVerloren(wt, jetzt))" in html, "Wartet-Zeile: kein „Jetzt abhaken“ für Kette-Trade 1")

print("\nselftest_topstep_tag_ein_haken: " + ("alle Prüfungen grün" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}"))
sys.exit(1 if FEHLER else 0)
