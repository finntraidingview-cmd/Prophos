#!/usr/bin/env python3
"""Selbsttest GEGENRICHTUNG DERSELBEN ID GESPERRT, SOLANGE DORT EIN TRADE LÄUFT (Finn 09.10.2026 ~09:25 Dubai: „90 s macht keinen Sinn —
Gegenrichtung ist verboten"; gleiche Richtung frei). Anlass: Topstep-Kette 1/2, 333d4791 BUY gegen d369e8d5 SELL derselben ID — der Start-
Wächter im PC-Tab (rkGilt) kannte Topstep V2 nicht, der DB-Riegel schob nur 90 s.
Aufruf:  python3 tools/selftest_gegenrichtung_gleiche_id.py
Prueft: (1) rkGilt (echt per osascript/JXA) gilt für tvv2, mt5v2 UND tsv2, nicht für Winning Days/Orbit V3/ohne Richtung; (2) faVorStart meldet
„gegen laufenden Trade gesperrt" statt „90-s-Abstand", wenn die RPC laeuft liefert; (3) SQL-Datei: gleiche ID + Gegenrichtung + status open →
Sperre (rollend jetzt + 5 min) VOR der 90-s-Regel, andere IDs weiter 90 s, gesucht wird nur die Gegenrichtung (gleiche Richtung nie),
Firmen-Abstand nicht angefasst, Protokoll-Präfix."""
import json
import os
import re
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(WURZEL, "sql", "2026-10-09_gegenhedge_nur_gegenrichtung.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# (1) rkGilt echt ausführen
m = re.search(r"  function rkGilt\(p\)\{\n.*?\n  \}", HTML, re.S)
check(bool(m), "rkGilt gefunden")
if m and shutil.which("osascript"):
    js = ("var tpIstWdPlan = function(p){ return !!p.wd }; var tpIstOrbitV3 = function(p){ return !!p.v3 };\n" + m.group(0) + "\n"
          "JSON.stringify([rkGilt({route:'tsv2',richtung:'buy'}), rkGilt({route:'tvv2',richtung:'sell'}), rkGilt({route:'mt5v2',richtung:'buy'}),"
          " rkGilt({route:'tvv2',richtung:'buy',wd:1}), rkGilt({route:'tvv2',richtung:'buy',v3:1}), rkGilt({route:'tsv2',richtung:null}),"
          " rkGilt({route:'mt5',richtung:'buy'})])")
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    try:
        v = json.loads(r.stdout.strip())
    except ValueError:
        v = None
    check(v == [True, True, True, True, True, False, False],
          f"rkGilt: tsv2/tvv2/mt5v2 ja, seit 09.10. auch Winning Day + Orbit V3; ohne Richtung, Echo (mt5) nein ({v or r.stderr.strip()[:80]})")
else:
    print("· rkGilt-Lauf übersprungen (kein osascript)")

# (2) Meldung beim Hand-Start / Start-Wächter
i = HTML.index("  async function faVorStart(plan){")
fa = HTML[i:HTML.index("\n  }\n", i)]
check("gh && d.laeuft" in fa and "gegen laufenden Trade gesperrt" in fa and "wartet 90-s-Abstand" in fa,
      "faVorStart: laufender Gegen-Trade → „gegen laufenden Trade gesperrt“, sonst wie bisher „90-s-Abstand“")

# (2b) Hand-Werte nie drehen (Master 09.10.2026) — nur verschieben, wie der Bot (AP_FEST_HAND)
i = HTML.index("  async function rkVorStart(plan){")
rv = HTML[i:HTML.index("\n  }\n", i)]
check("if(plan.autoPlan && !plan.handWerteAt){" in rv and "update({ richtung: ziel })" in rv.split("if(plan.autoPlan && !plan.handWerteAt){")[1],
      "rkVorStart: Plan mit Hand-Werten wird nie gedreht (nur verschoben)")
check("handWerteAt: row.hand_werte_at || null," in HTML, "rowToPlan liest hand_werte_at")

# (2c) Plan-Popup zählt geplante Hand-/WD-/Orbit-V3-Pläne von heute mit (Finn über Master 09.10.2026, Jacob: zweiter WD gegenläufig);
# Start-Wächter und harte Sperre weiter nur laufend — Auto-Vorschläge zählen nie
i = HTML.index("  async function v2RichtungKonflikt(o){")
vk = HTML[i:HTML.index("\n  }\n", i)]
check("!!(o && o.geplanteHand) && p.status === 'planned' && p.hand && p.heute" in vk and "verb: 'ist schon geplant', geplant: true" in vk,
      "v2RichtungKonflikt: geplante Hand-/WD-/V3-Pläne nur mit geplanteHand")
check("hand: !p.autoPlan || tpIstWdPlan(p) || tpIstOrbitV3(p), heute: rkPlanHeute(p)" in vk, "Auto-Vorschläge zählen nicht (hand = Hand-Plan oder WD/V3)")
check(HTML.count("geplanteHand: true") == 3 and "v2RichtungKonflikt({ firm: plan.masterFirm, ohneId: plan.id, frisch: true })" in HTML,
      "nur Popup-Anzeige + 2 Speicher-Prüfungen nutzen geplanteHand; Start-Wächter/harte Sperre unverändert")
m2 = re.search(r"  function rkGilt\(p\)\{\n.*?\n  \}", HTML, re.S)
check(m2 and "tpIstWdPlan" not in m2.group(0) and "tpIstOrbitV3" not in m2.group(0), "rkGilt nimmt Winning Day und Orbit V3 nicht mehr aus")

i = HTML.index("  async function rkVerschieben(")
rvs = HTML[i:HTML.index("\n  }\n", i)]
check("if(!aufgeben && tpIstWdPlan(neu)) await tpWdTagesplanStartSetzen(neu.id, neu.startUm)" in rvs and "async function tpWdTagesplanStartSetzen(" in HTML,
      "WD-Plan geschoben → Startzeit im wd_tagesplan mitgezogen (Prüfer T3)")
i = HTML.index("  async function tpWdTagesplanStartSetzen(")
ts = HTML[i:HTML.index("\n  }\n", i)]
check("q.eq('updated_at', x.updated_at)" in ts and "versuch < 2" in ts and ".select('tag')" in ts,
      "Tagesplan-Startzeit mit optimistischer Sperre (updated_at), höchstens 2 Versuche — überschreibt nie eine fremde Änderung")

# (3) SQL-Datei
k = SQL[SQL.index("create or replace function public.prophos_gegenhedge_konflikt"):SQL.index("create or replace function public.trade_plans_gegenhedge")]
neu = k.index("p.user_id = p_user")
alt90 = k.index("greatest(p.started_at, p.orbit_gesendet_at, p.start_um_gestartet_at) > now() - f")
check(neu < alt90 and "p.status = 'open'" in k[neu:alt90] and "p.richtung = gegen" in k[neu:alt90] and "now() + interval '10 minutes'" in k[neu:alt90]
      and "p.started_at > now() - interval '12 hours'" in k[neu:alt90],
      "gleiche ID, Gegenrichtung, open (≤ 12 h) → Sperre (jetzt + 10 min, rollend) vor der 90-s-Regel")
check("master_account_id is distinct from konto" in k[neu:alt90], "dasselbe Konto bleibt außen vor")
check(k.count("p.richtung = gegen") == 3 and "p.richtung = p_richtung" not in k, "gesucht wird nur die Gegenrichtung — gleiche Richtung nie ein Abstand")
check("p.user_id is distinct from p_user" in k[alt90 - 400:], "andere IDs weiter nur 90 s (prophos_gegenhedge_fenster)")
check(not re.search(r"create or replace function public\.\w*firmen_abstand", SQL), "Firmen-Abstand (1 min) nicht angefasst (keine Funktion neu angelegt)")
check(SQL.count("[Gegenrichtung gleiche ID] ") == 2 and "'laeuft'" in SQL, "Trigger + RPC: Präfix „[Gegenrichtung gleiche ID]“, RPC liefert laeuft")

print("\nALLES GRÜN" if not FEHLER else f"\nFEHLER: {FEHLER}")
sys.exit(1 if FEHLER else 0)
