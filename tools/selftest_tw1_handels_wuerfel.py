#!/usr/bin/env python3
"""Selbsttest TW1 Handels-Würfel (app.py tw_*, Finn 11.11.2026: „75 % aller Trades aller Accounts machen einen Trade, und die anderen 25 % nicht …
Es wird einfach gewürfelt … für jedes einzelne Ding diese Wahrscheinlichkeit selber einstellen").

Aufruf:  python3 tools/selftest_tw1_handels_wuerfel.py
Ohne Netz, Platzhalter-IDs. Lädt nur den TW1-Block aus app.py (exec mit Stubs) und prüft: Wurf fest je Planer × Konto × Tag und gleichverteilt (75 % ≈ 75 %),
100 % = immer, 0 % = nie, Lesefehler/keine Zeile = 100 %, Unternehmen erbt den HT-Wert nicht, Kontext unlesbar = 100 %; Gründe (Schlüssel-Texte) passen zu
HAND_PLANER_OHNE, prophos.html WD_AUTO_HINWEISE und dem Braucht-dich-Filter; die vier Planer-Strecken rufen den Würfel (ap_planen vor dem Tagesdeckel,
fcp/fdp nur im Planen-Zweig, WD nach dem Verknüpfen), „Pause-Tag“ steht NICHT in den festen Nachplan-Gründen; SQL-Datei idempotent mit 5 × 75 %."""
import hashlib
import os
import re
import sys
import threading
import time

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
APP = os.path.join(WURZEL, "app.py")
HTML = os.path.join(WURZEL, "prophos.html")
SQL = os.path.join(WURZEL, "sql", "2026-11-11_tageswuerfel_75.sql")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


src = open(APP, encoding="utf-8").read()
html = open(HTML, encoding="utf-8").read()
i = src.index("# ══ TW1 HANDELS-WÜRFEL")
j = src.index('@app.route("/admin/handel-wuerfel"', i)


class _Fehler(Exception):
    pass


ZEILEN = {"rows": [], "wirf": False}


def _sb_select(tab, params):
    assert tab == "planer_handel_wuerfel"
    if ZEILEN["wirf"]:
        raise _Fehler("weg")
    return list(ZEILEN["rows"])


def _wd_num(v):
    try:
        return None if v is None or v == "" or isinstance(v, bool) else float(v)
    except (TypeError, ValueError):
        return None


KTX = {"ok": True, "gid_von": {}}
a = {"hashlib": hashlib, "time": time, "threading": threading, "_wd_num": _wd_num, "sb_select": _sb_select,
     "ap_unt_kontext": lambda frisch=False: KTX, "print": lambda *x, **k: None,
     "ap_regel_finden": lambda firmen, firm: next((f for f in firmen if firm in f.get("namen", [])), None),
     "ap_klasse": lambda route=None, firma=None: "futures" if str(route or "").startswith("tv") else "cfd"}
exec(src[i:j], a)
W, H, PV, WE, PCT, PG = a["tw_wurf"], a["tw_handelt"], a["tw_pct_von"], a["tw_werte"], a["tw_pct"], a["tw_pause_grund"]

HT, EMIN, GID = "00000000-0000-0000-0000-0000000000b1", "00000000-0000-0000-0000-0000000000b2", "00000000-0000-0000-0000-0000000000a1"
K = "00000000-0000-0000-0000-0000000000c1"

# 1) Wurf: fest, Bereich, gleichverteilt
w1 = W("challenge_cfd", K, "2026-11-12")
check(w1 == W("challenge_cfd", K, "2026-11-12") == W("challenge_cfd", K, "2026-11-12T03:00:00Z") and 0 <= w1 < 1,
      "Wurf fest je Planer × Konto × Tag (Nachtlauf/Nachplanen/Knopf/Probelauf gleich), in [0, 1)")
n = 20000
ja = sum(1 for x in range(n) if H("challenge_cfd", f"konto-{x}", "2026-11-12", 75))
check(0.735 <= ja / n <= 0.765, f"75 % → {ja / n:.3%} der Konten handeln (Toleranz ±1,5 %)")
tage = sum(1 for d in range(1, 29) if H("funded_cfd", K, f"2026-12-{d:02d}", 75))
check(14 <= tage <= 28, f"ein Konto über 28 Tage: {tage} Handelstage (neu gewürfelt je Tag)")
gleich = sum(1 for x in range(4000) if H("challenge_cfd", f"k{x}", "2026-11-12", 50) == H("funded_cfd", f"k{x}", "2026-11-12", 50))
check(1700 <= gleich <= 2300, "Planer gehen in den Wurf ein (unabhängig, ~50 % gleich bei 50 %)")
check(H("winning_days", K, "2026-11-12", 100) and H("winning_days", K, "2026-11-12", None) and H("winning_days", K, "2026-11-12", 150)
      and not any(H("winning_days", f"k{x}", "2026-11-12", 0) for x in range(200)),
      "100 % / ohne Wert = immer, 0 % = nie")

# 2) Werte je Planer × Unternehmen
ZEILEN["rows"] = [{"planer": "challenge_cfd", "gruppe": "", "pct": 75}, {"planer": "funded_cfd", "gruppe": GID, "pct": 40},
                  {"planer": "kaputt", "gruppe": "", "pct": 10}]
w = WE(frisch=True)
check(w == {("challenge_cfd", ""): 75.0, ("funded_cfd", GID): 40.0}, "tw_werte: nur bekannte Planer, (planer, gruppe) → pct")
check(PV(w, "challenge_cfd", None) == 75 and PV(w, "challenge_futures", None) == 100, "Standard-Zeile gilt für HT, fehlende Zeile = 100 %")
check(PV(w, "challenge_cfd", GID) == 100 and PV(w, "funded_cfd", GID) == 40,
      "Unternehmen erbt den HT-Wert NICHT (ohne eigene Zeile 100 %), eigene Zeile gilt")
KTX.update(ok=True, gid_von={EMIN: GID})
check(PCT("challenge_cfd", HT, w) == 75 and PCT("challenge_cfd", EMIN, w) == 100 and PCT("funded_cfd", EMIN, w) == 40,
      "tw_pct: HT-ID → Standard, Emins ID → Zeile seines Unternehmens")
KTX.update(ok=False)
check(PCT("challenge_cfd", HT, w) == 100, "Unternehmens-Kontext nicht lesbar → 100 % (handelt wie bisher)")
KTX.update(ok=True)
ZEILEN["wirf"] = True
check(WE(frisch=True) == w and a["_tw"]["fehler"].endswith("letzter Stand gilt"), "kurzer Lesefehler → letzter guter Stand gilt weiter (Prüfer S3)")
a["_tw"]["gut_at"] = time.time() - 3600
check(WE(frisch=True) == {} and PCT("challenge_cfd", HT) == 100, "Lesefehler, letzter Stand > 15 min alt → {} → 100 %")
ZEILEN["wirf"] = False
WE(frisch=True)
check(a["_tw"]["fehler"] == "", "nach gutem Lesen kein Fehler mehr")

# 3) Gründe = Schlüssel-Texte
pausen = [x for x in range(400) if PG("challenge_cfd", {"id": f"k{x}", "user_id": HT}, "2026-11-12", w)]
g = PG("challenge_cfd", {"id": f"k{pausen[0]}", "user_id": HT}, "2026-11-12", w) if pausen else ""
check(60 <= len(pausen) <= 140 and g.startswith("Pause-Tag (Handels-Würfel 75 %)"), f"Pause-Grund mit Prozent ({len(pausen)}/400 Pause bei 75 %)")
check(PG("challenge_cfd", {"id": "x", "user_id": EMIN}, "2026-11-12", w) is None, "Emins Konten pausieren nicht, solange sein Unternehmen keinen Wert hat")
wd = a["TW_GRUND_WD"]
ZEILEN["rows"] = [{"planer": "winning_days", "gruppe": "", "pct": 0}]
check(PG("winning_days", {"id": K, "user_id": HT}, "2026-11-12", WE(frisch=True)) == wd, "WD-Grund = TW_GRUND_WD")
check(f"const WD_HINWEIS_PAUSE = '{wd}'" in html and wd not in html.split("const WD_AUTO_HINWEISE")[1].split("]")[0],
      "WD-Grund = prophos.html WD_HINWEIS_PAUSE und NICHT in WD_AUTO_HINWEISE (Prüfer MUSS: sonst heilt die Zeile alle 30 s und der Rückfall legt an)")
rf = html[html.index("  async function wdPlanAnlegen("):html.index("\n  }\n", html.index("  async function wdPlanAnlegen("))]
check(0 < rf.find("await hwWdPause(acc, tagKey, currentUserId)") < rf.find("supabase.from('trade_plans').insert(row)") and "!(extra && extra.id)" in rf,
      "WD-Rückfall am PC-Tab würfelt vor dem direkten Insert (Selbstheilung nicht)")
# TW1b (Prüfer TW1, 11.11.2026): Tag ohne planned_for = heute in DUBAI wie app.py; Wert des Unternehmens des Konto-Besitzers (nicht des Logins)
check("const tagDubai = tag || new Date().toLocaleDateString('en-CA', { timeZone: 'Asia/Dubai' })" in rf and "const tagKey = row.planned_for || tagDubai" in rf
      and "toLocaleDateString('en-CA'))" not in rf, "TW1b: Rückfall-Tag (Plan + Wurf) in Dubai, nie das lokale PC-Datum")
_hw = html[html.index("  async function hwWdGid("):html.index("  window._hw = {")]
check("await wdUnternehmenVon(uid)" in _hw and "hwLaden(g)" in _hw and "d.unternehmen.name != null" in _hw and "(_hw.d[g] || {}).werte" in _hw,
      "TW1b: hwWdPause liest den Wert des Unternehmens des Konto-Besitzers (Planer-Unternehmen → eigene Zeile, sonst Standard wie tw_pct)")
check("return parseInt(hex.slice(0, 13), 16) / 16 ** 13" in html and "`tw1|${planer}|${kontoId}|${String(tag || '').slice(0, 10)}`" in html,
      "Frontend-Wurf = app.py tw_wurf (gleicher Text, 13 Hex-Stellen)")
m = re.search(r'HAND_PLANER_OHNE = re\.compile\(r"([^"]+)"', src)
check(bool(m) and re.search(m.group(1), g or "Pause-Tag (Handels-Würfel 75 %)", re.I), "HAND_PLANER_OHNE fängt den Pause-Grund (kein „Braucht dich“)")
check("^Pause-Tag \\(Handels-Würfel" in html, "Frontend-Filter „Braucht dich“ lässt Pause-Tage weg")
check(a["_tw_pct_txt"](75.0) == "75" and a["_tw_pct_txt"](62.5) == "62,5", "Prozent-Text deutsch, ohne ,0")

ZEILEN["rows"] = [{"planer": "challenge_cfd", "gruppe": "", "pct": 50}]
w2 = WE(frisch=True)
konten = [{"id": f"k{x}", "user_id": HT, "firm": "fundednext"} for x in range(200)] + [{"id": f"t{x}", "user_id": HT, "firm": "tradeify"} for x in range(50)]
firmen = [{"namen": ["fundednext"], "route": "mt5v2"}, {"namen": ["tradeify"], "route": "tvv2"}]
kand = [k["id"] for k in konten]
f = a["tw_nachplan_filter"](kand, konten, "2026-11-12", firmen)
erw = [k["id"] for k in konten if not PG("challenge_futures" if k["firm"] == "tradeify" else "challenge_cfd", k, "2026-11-12", w2)]
check(f == erw and 60 <= sum(1 for x in f if x.startswith("k")) <= 140 and all(("t" + str(x)) in f for x in range(50)),
      "tw_nachplan_filter: CFD 50 % gefiltert wie ap_planen, Futures (kein Wert) bleiben alle")
ZEILEN["wirf"] = True
a["_tw"].update(gut=None, bis=0.0)
check(a["tw_nachplan_filter"](kand, konten, "2026-11-12", firmen) == kand, "tw_nachplan_filter: Lesefehler ohne guten Stand → Liste unverändert")
ZEILEN["wirf"] = False
ZEILEN["rows"] = [{"planer": "challenge_cfd", "gruppe": "", "pct": 75}, {"planer": "funded_cfd", "gruppe": GID, "pct": 40}]
WE(frisch=True)

# 4) Einhängepunkte
ap = src[src.index("\ndef ap_planen("):src.index("\ndef ", src.index("\ndef ap_planen(") + 10)]
check(ap.find("tw_pause_grund(") != -1 and ap.find("tw_pause_grund(") < ap.find("ap_tagesdeckel(firmen, kandidaten"),
      "ap_planen: Würfel vor dem Tagesdeckel")
check('"challenge_futures" if ap_klasse(' in ap, "ap_planen: CFD/Futures über ap_klasse")
fcp = src[src.index("\ndef fcp_planen("):src.index("\ndef ", src.index("\ndef fcp_planen(") + 10)]
k1 = fcp.find('tw_pause_grund("funded_cfd"')
check(k1 != -1 and fcp.rfind('if r.get("aktion") == "planen":', 0, k1) > fcp.find('if r.get("aktion") == "ziel" and fcp_anfrage_ohne_trade')
      and k1 < fcp.find("ziel_schreiben[aid] ="), "fcp_planen: nur im Planen-Zweig, nach Ziel/Anfrage, vor dem Festschreiben des Zyklus-Ziels")
fdp = src[src.index("\ndef fdp_planen("):src.index("\ndef ", src.index("\ndef fdp_planen(") + 10)]
k2 = fdp.find('tw_pause_grund("funded_futures"')
check(k2 != -1 and fdp.find('elif r["aktion"] != "planen":') < k2 < fdp.find("rech[aid] = (a, r)"), "fdp_planen: nur im Planen-Zweig, vor Tagesdeckel/Startzeit")
wdp = src[src.index('                if blockiert == "verknuepft":'):]
check(wdp.find('tw_pause_grund("winning_days"') != -1 and wdp.find('tw_pause_grund("winning_days"') < wdp.find('body["status"] = "planned"'),
      "WD: nach dem Verknüpfen, vor dem Anlegen")
check("and not _tw_pause_plan(p)" in ap and ap.find("def _tw_pause_plan") < ap.find("def _vorschlag"),
      "Hand-Lauf ersetzt keinen Vorschlag eines Pause-Kontos (Prüfer S2)")
check('weg["id"] = "not.in.(" + ",".join(_tw_behalt_ids) + ")"' in ap and ap.find('weg["id"] = "not.in.("') < ap.find('params=dict(weg, hand_werte_at="is.null")')
      and "master_firm,route,status" in ap and "ap_klasse(p.get(\"route\"), p.get(\"master_firm\"))" in ap,
      "Hand-/Nachtlauf löscht den Vorschlag eines Pause-Kontos auch in der DB nicht (Prüfer Runde 2), Klasse über die Route des Vorschlags")
nr = src[src.index("\ndef _ap_nachplan_rechnen("):src.index("\ndef ", src.index("\ndef _ap_nachplan_rechnen(") + 10)]
check(0 < nr.find("tw_nachplan_filter(kand") < nr.find("    if not kand:"), "Nachplanen filtert Pause-Konten vorab (Prüfer S4)")
fest = re.search(r"AP_NACHPLAN_FEST_GRUENDE = \(([^)]*)\)", src, re.S)
check(bool(fest) and "Pause-Tag" not in fest.group(1), "„Pause-Tag“ nicht in AP_NACHPLAN_FEST_GRUENDE (höherer Wert tagsüber wird nachgeplant)")
check(src.count('@app.route("/admin/handel-wuerfel"') == 1 and "_planer_schreib_gate()" in src[j:j + 2500] and "_fd_unternehmen(admin, uid)" in src[j:j + 2500],
      "Route /admin/handel-wuerfel mit Schreib-Riegel und Unternehmen wie die Funded-Einstellungen")

# 5) Frontend + SQL
for host in ("'challenge_futures' : 'challenge_cfd'", "hwPlatz(w, 'funded_cfd'", "hwPlatz(box, 'funded_futures'", "'winning_days', '')"):
    check(host in html, f"Karte eingehängt: {host}")
sql = open(SQL, encoding="utf-8").read()
check("create table if not exists public.planer_handel_wuerfel" in sql and "enable row level security" in sql and "primary key (planer, gruppe)" in sql,
      "SQL: idempotent, RLS an, PK (planer, gruppe)")
check(all(f"('{p}', '', 75)" in sql for p in a["TW_PLANER"]) and "on conflict (planer, gruppe) do nothing" in sql, "SQL: HT 5 × 75 %, erneut eingespielt wertschonend")

print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "alles grün")
sys.exit(1 if FEHLER else 0)
