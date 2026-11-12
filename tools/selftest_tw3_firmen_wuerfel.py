#!/usr/bin/env python3
"""Selbsttest TW3 — Firmen-Würfel je ID × Firma × Tag (Finn 12.11.2026: „die Prop-Firma der jeweiligen ID soll zu 20 % an einem Tag gar nicht getradet werden").

Aufruf:  python3 tools/selftest_tw3_firmen_wuerfel.py
Ohne Netz, Platzhalter-IDs. Lädt den TW1-Block und die TW2-Helfer aus app.py (exec mit Stubs) und prüft: über 1.000 ID × Firma × Tage ≈ 25 % Pause bei 75 %,
fest je Tag, alle fünf Planer gleich, „FundedNext“ ≠ „FundedNext Futures“, Konto-Wurf danach unabhängig, Hand-Rein überstimmt, Emins Unternehmen 100 %,
ohne Zeile / ohne Firma wie bisher; Route/Leser kennen firma_je_id, Vorschlag-Schutz gibt die Firma mit; Frontend (Karte, WD-Rückfall, Texte, Filter) und SQL."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
sql = open(os.path.join(WURZEL, "sql", "2026-11-12_tw3_firmen_wuerfel.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


i = src.index("# ══ TW1 HANDELS-WÜRFEL")
j = src.index('@app.route("/admin/handel-wuerfel"', i)
i2 = src.index("# ══ TW2 HAND ÜBERSTIMMT DEN PAUSE-TAG")
j2 = src.index("def tw_pause_dazu(", i2)
ZEILEN = {"tw": []}
MARKEN = {"rows": []}


def _sb_select(tab, params):
    assert tab == "planer_handel_wuerfel"
    return list(ZEILEN["tw"])


def _sb_all(tab, params):
    assert tab == "user_settings"
    vor = str(params.get("key"))[len("like."):-1].replace("\\_", "_")
    return [r for r in MARKEN["rows"] if str(r["key"]).startswith(vor)]


def _wd_num(v):
    try:
        return None if v is None or v == "" or isinstance(v, bool) else float(v)
    except (TypeError, ValueError):
        return None


ap_norm_src = src[src.index("def _ap_norm(name):"):src.index("def ap_regel_finden(")]
KTX = {"ok": True, "gid_von": {}}
a = {"hashlib": hashlib, "time": time, "threading": threading, "re": re, "_wd_num": _wd_num, "sb_select": _sb_select, "_sb_all": _sb_all,
     "ap_unt_kontext": lambda frisch=False: KTX, "print": lambda *x, **k: None, "datetime": __import__("datetime").datetime}
exec(ap_norm_src, a)
exec(src[i:j], a)
exec(src[i2:j2], a)
PG, FW, FH, WE = a["tw_pause_grund"], a["tw_firma_wurf"], a["tw_firma_handelt"], a["tw_werte"]
PLANER = ("challenge_cfd", "challenge_futures", "funded_cfd", "funded_futures", "winning_days")


def setze(firma_pct=75, konto_pct=75, emin=None):
    ZEILEN["tw"] = [{"planer": p, "gruppe": "", "pct": konto_pct} for p in PLANER] + ([{"planer": "firma_je_id", "gruppe": "", "pct": firma_pct}] if firma_pct is not None else [])
    if emin:
        ZEILEN["tw"] += emin
    MARKEN["rows"] = []
    a["_tw_hand"].clear()
    return WE(frisch=True)


def uid(x):
    return f"00000000-0000-0000-0000-{x:012d}"


TAGE = [f"2026-12-{d:02d}" for d in range(1, 26)]
FIRMEN = ["FundedNext", "FundedNext Futures", "The5%ers", "Tradeify CFD"]

print("1) Firmen-Wurf")
w = setze()
check(a["TW_FIRMA"] in a["TW_EINST"] and w.get(("firma_je_id", "")) == 75.0, "tw_werte liest die Zeile firma_je_id (75 %)")
n = pause = 0
for x in range(10):
    for f in FIRMEN:
        for t in TAGE:
            n += 1
            pause += not FH(uid(x), f, t, 75)
check(n == 1000 and 0.22 <= pause / n <= 0.28, f"1.000 ID × Firma × Tage: {pause / n:.1%} Pause bei 75 % (Ziel 25 % ±3, Finn 12.11.: „Zufalls-Propfirms bleiben bei 25 %“)")
check(all(FW(uid(1), "FundedNext", "2026-12-03") == FW(uid(1), "FundedNext", "2026-12-03T22:00:00Z") for _ in range(3)), "fest je ID × Firma × Tag (Uhrzeit egal)")
check(FW(uid(1), "FundedNext", "2026-12-03") != FW(uid(1), "FundedNext Futures", "2026-12-03") and FW(uid(1), "The5%ers", "x") == FW(uid(1), "the 5ers", "x"),
      "„FundedNext“ ≠ „FundedNext Futures“ (getrennte Firmen), Schreibweise egal (_ap_norm)")
check(FW(uid(1), "FundedNext", "2026-12-03") != FW(uid(2), "FundedNext", "2026-12-03") and FW(uid(1), "FundedNext", "2026-12-03") != FW(uid(1), "FundedNext", "2026-12-04"),
      "andere ID / anderer Tag = anderer Wurf")
check(FH(uid(1), "FundedNext", "t", 100) and FH(uid(1), "FundedNext", "t", None) and not any(FH(uid(x), "FundedNext", "t", 0) for x in range(50))
      and FH(None, "FundedNext", "t", 0) and FH(uid(1), "", "t", 0), "100 % / ohne Wert = immer, 0 % = nie, ohne ID/Firma = wie bisher")

print("2) Zusammenspiel mit dem Konto-Wurf (TW1) und allen Planern")
paare = [(uid(x), f, t) for x in range(10) for f in FIRMEN for t in TAGE]
fp = [(u, f, t) for u, f, t in paare if not FH(u, f, t, 75)]
u0, f0, t0 = fp[0]
konten = [{"id": f"k{y}-{u0[-3:]}", "user_id": u0, "firm": f0} for y in range(40)]
gr = [PG(pl, k, t0, w) for pl in PLANER for k in konten]
check(all(g and g.startswith("Pause-Tag Firma") for g in gr), "Firma pausiert → JEDES Konto dieser ID × Firma, in allen fünf Planern, Pause (Firmen-Grund)")
check(PG("challenge_cfd", konten[0], t0, w) == f"Pause-Tag Firma (Firmen-Würfel 75 %) — heute kein Trade bei {f0} für diese ID, morgen neu"
      and PG("winning_days", konten[0], t0, w) == a["TW_GRUND_FIRMA_WD"], "Grund-Text mit Prozent + Firma; WD fester Schlüssel-Text")
fremd = {"id": "k-fremd", "user_id": uid(99), "firm": f0}
andere = {"id": "k-andere", "user_id": u0, "firm": next(f for f in FIRMEN if f != f0 and FH(u0, f, t0, 75))}
check(not str(PG("challenge_cfd", andere, t0, w) or "").startswith("Pause-Tag Firma"), "dieselbe ID bei einer anderen Firma: kein Firmen-Pause-Tag")
frei = [(u, f, t) for u, f, t in paare if FH(u, f, t, 75)]
kp = sum(1 for u, f, t in frei for y in range(5) if PG("challenge_cfd", {"id": f"k{y}-{f}", "user_id": u, "firm": f}, t, w))
check(0.20 <= kp / (len(frei) * 5) <= 0.30 and all(not str(PG("challenge_cfd", {"id": f"k{y}-{f}", "user_id": u, "firm": f}, t, w) or "").startswith("Pause-Tag Firma")
                                                  for u, f, t in frei[:50] for y in range(5)),
      f"Firma handelt → danach der Konto-Wurf wie bisher: {kp / (len(frei) * 5):.1%} Konto-Pause bei 75 % (unabhängig vom Firmen-Wurf)")
gesamt = sum(1 for u, f, t in paare for y in range(3) if PG("funded_cfd", {"id": f"z{y}-{f}", "user_id": u, "firm": f}, t, w))
check(0.39 <= gesamt / (len(paare) * 3) <= 0.49, f"zusammen ≈ 1 − 0,75 × 0,75 ≈ 44 % der Konto-Tage Pause ({gesamt / (len(paare) * 3):.1%})")
check(PG("challenge_cfd", {"id": "k", "user_id": u0, "master_firm": f0}, t0, w) is not None and PG("challenge_cfd", {"id": "k", "user_id": u0}, t0, w) != PG("challenge_cfd", konten[0], t0, w),
      "Firma auch aus master_firm (Plan-Zeile); ohne Firma kein Firmen-Wurf")

print("3) Hand-Rein, Unternehmen, ohne Zeile")
MARKEN["rows"] = [{"key": a["tw_hand_key"](t0, konten[0]["id"])}]
a["_tw_hand"].clear()
check(PG("challenge_cfd", konten[0], t0, w) is None and PG("winning_days", konten[0], t0, w) is None and bool(PG("challenge_cfd", konten[1], t0, w)),
      "„heute rein“ (TW2) überstimmt den Firmen-Pause-Tag für GENAU dieses Konto, die anderen Konten der Firma bleiben in Pause")
w = setze()
GID = "00000000-0000-0000-0000-0000000000a1"
KTX.update(gid_von={u0: GID})
check(PG("challenge_cfd", konten[0], t0, w) is None, "Emins Unternehmen ohne eigene Zeile: 100 % (erbt den HT-Wert nicht)")
w = setze(emin=[{"planer": "firma_je_id", "gruppe": GID, "pct": 0}])
check(str(PG("challenge_cfd", konten[0], t0, w) or "").startswith("Pause-Tag Firma (Firmen-Würfel 0 %)"), "eigene Zeile des Unternehmens gilt (0 % = nie)")
KTX.update(gid_von={})
w = setze(firma_pct=None)
check(not str(PG("challenge_cfd", konten[0], t0, w) or "").startswith("Pause-Tag Firma"), "ohne Zeile firma_je_id: kein Firmen-Wurf (wie vor TW3)")
KTX.update(ok=False)
w = setze()
check(PG("challenge_cfd", konten[0], t0, w) is None, "Unternehmens-Kontext nicht lesbar → 100 % (handelt wie bisher)")
KTX.update(ok=True)

print("4) Backend-Anker")
check('if planer not in TW_EINST:' in src and '{p: werte.get((p, str(gid or ""))) for p in TW_EINST}' in src and '"firma_je_id": "Firma je ID"' in src,
      "Route GET/POST kennt firma_je_id")
check('"firm": p.get("master_firm")}' in src, "Vorschlag-Schutz (_tw_pause_plan) gibt die Firma mit")
check('uebersprungen.append({"master_account_id": mid, "grund": _tw_g}); continue' in src and '"grund": TW_GRUND_WD}' not in src,
      "WD-POST schreibt den passenden Grund (Konto- oder Firmen-Pause), nicht immer TW_GRUND_WD (Prüfer SOLLTE 1)")
check("sql/2026-11-12_tw3_firmen_wuerfel.sql eingespielt?" in src, "Speichern des Firmen-Felds vor dem SQL: Hinweis nennt die TW3-Datei (Prüfer KANN 2)")
_hpo = src[src.index("HAND_PLANER_OHNE = re.compile("):]
_hpo = eval(_hpo[len("HAND_PLANER_OHNE = "):_hpo.index("\n")], {"re": re})
check(_hpo.search(PG("challenge_cfd", konten[0], t0, setze())) is not None and _hpo.search(a["TW_GRUND_FIRMA_WD"]) is not None,
      "HAND_PLANER_OHNE fängt „Pause-Tag Firma“ (kein Hand-Fall, echte Regex)")
check("planer_handel_wuerfel_planer_check" in sql and "'firma_je_id'" in sql and "values ('firma_je_id', '', 75)" in sql and "on conflict (planer, gruppe) do nothing" in sql,
      "SQL: Check-Liste erweitert, HT 75 %, idempotent")

print("5) Frontend")
check("const WD_HINWEIS_PAUSE_FIRMA = 'Pause-Tag Firma (Firmen-Würfel) – heute kein Trade bei dieser Firma für diese ID, morgen neu'" in html
      and a["TW_GRUND_FIRMA_WD"] == "Pause-Tag Firma (Firmen-Würfel) – heute kein Trade bei dieser Firma für diese ID, morgen neu", "WD-Text app.py = prophos.html")
hw = html[html.index("async function hwWdPause("):html.index("window._hw = {")]
check(hw.index("hwFirmaWurf(uid, acc.firm, tag)") < hw.index("hwWurf('winning_days'") < hw.index("hwHandMarke(acc, tag, uid)")
      and "`tw3|${uid}|${norm}|${String(tag || '').slice(0, 10)}`" in hw and ".replace(/[^a-z0-9]/g, '')" in hw,
      "WD-Rückfall am PC-Tab: Firmen-Wurf (gleicher Schlüssel wie app.py) → Konto-Wurf → Hand-Marke")
check("return { fehler: _hwp === true ? WD_HINWEIS_PAUSE : _hwp }" in html, "Rückfall schreibt den passenden Hinweis (Konto- oder Firmen-Pause)")
check("k.hinweis === WD_HINWEIS_PAUSE || k.hinweis === WD_HINWEIS_PAUSE_FIRMA" in html, "WD „heute wieder rein“ setzt die Hand-Marke auch auf einem Firmen-Pause-Tag")
check("^Pause-Tag Firma \\(Firmen-Würfel/.test(g)) continue" in html, "„Braucht dich“ zeigt den Firmen-Pause-Tag nicht als Handarbeit")
check("hwZeileHtml(HW_FIRMA, 'Firma je ID handelt je Tag'" in html and "data-hw-speichern=\"${escapeHtml(key)}\"" in html, "Karte: Feld „Firma je ID handelt je Tag“ in jeder Planer-Karte")
kn = html[html.index("  function twHandKnopf(c){"):html.index("  async function twHandRein(")]
fn = html[html.index("  function hwZeileHtml("):html.index("  function hwZeichnen(el){")]
js = """
const escapeHtml = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
const _twHand = new Map();
const HW_PLANER = { challenge_cfd: 'Challenge-Planer CFD' };
const hwZahl = v => (v == null || v === '' || !isFinite(Number(v))) ? null : Number(v);
const hwPct = v => String(Math.round(Number(v) * 10) / 10);
const HW_FIRMA = 'firma_je_id';
""" + kn + fn + """
const r = {};
r.knopfFirma = twHandKnopf({ r: { konto_id: 'k1', grund: 'Pause-Tag Firma (Firmen-Würfel 80 %) — heute kein Trade bei FundedNext für diese ID, morgen neu' }, tag: '2026-11-13' });
r.knopfWd = twHandKnopf({ r: { konto_id: 'k1', grund: 'Pause-Tag Firma (Firmen-Würfel) – heute kein Trade bei dieser Firma für diese ID, morgen neu' }, tag: '2026-11-13' });
const D = { werte: { challenge_cfd: 75, firma_je_id: 80 }, standard_pct: 100, darf: true };
r.karte = hwInnenHtml('challenge_cfd', D, null, null, null, null);
r.karteAlt = hwInnenHtml('challenge_cfd', { werte: { challenge_cfd: 75 }, standard_pct: 100, darf: true }, null, null, null, null);
r.karteAnsehen = hwInnenHtml('challenge_cfd', Object.assign({}, D, { darf: false }), null, null, null, null);
r.norm = ['FundedNext', 'FundedNext Futures', 'The5%ers', 'Tradeify CFD'].map(f => String(f).toLowerCase().replace(/[^a-z0-9]/g, ''));
JSON.stringify(r);
"""
js = js.replace("  function hwZeileHtml(", "  function hwZeileHtml(").replace("function hwInnenHtml(", "function hwInnenHtml(")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
try:
    aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
    r = json.loads(aus.stdout.strip() or "{}")
    if not r:
        r = {"_fehler": aus.stderr[:300]}
except Exception as e:
    r = {"_fehler": f"{type(e).__name__}: {e}"}
finally:
    os.unlink(f.name)
check('data-tw-hand="k1"' in r.get("knopfFirma", "") and r.get("knopfWd") == "", "JS: „heute rein“ am Firmen-Pause-Chip (Planer-Format), nicht am WD-Text " + str(r.get("_fehler") or ""))
check('data-hw-in="challenge_cfd"' in r.get("karte", "") and 'data-hw-in="firma_je_id"' in r.get("karte", "") and "Firma je ID handelt je Tag" in r.get("karte", "")
      and "≈ 20 % der Tage" in r.get("karte", ""), "JS: Karte mit zwei Feldern (Konten / Firma je ID) und Erklärung")
check('data-hw-in="firma_je_id"' not in r.get("karteAlt", "") and "<input" not in r.get("karteAnsehen", "") and "80 %" in r.get("karteAnsehen", ""),
      "JS: altes Backend ohne Wert → keine Firmen-Zeile; ohne Recht nur ansehen")
check(r.get("norm") == [a["_ap_norm"](f) for f in FIRMEN], "JS-Firmen-Norm = app.py _ap_norm")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER")
    sys.exit(1)
print("alles grün")
