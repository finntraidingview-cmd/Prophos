#!/usr/bin/env python3
"""Selbsttest LIEGENGEBLIEBENE AUTO-PLÄNE (app.py ap_planen, 08.10.2026, Slave-Terminal 4 — Master: Jacob 72c2a073 The5%ers und
1429b717 FundingPips, Chris 840c8097: Start-Fehler bis Tagesende, Plan blieb geclaimt auf planned, und „hat schon einen geplanten/
laufenden Plan" ließ das Konto in jedem folgenden Lauf aus, obwohl die Karte „der Nachtlauf plant neu" verspricht).
Rein rechnend auf der nachgebauten DB aus selftest_auto_delta (Probelauf, nichts wird geschrieben). Geprüft: (1) ohne Pläne wird das
Konto geplant (Ausgangslage); (2) Auto-Plan vom Vortag, bestätigt + geclaimt, nie gesendet → blockiert nicht mehr, steht in
erg.verfallen; (3) Handplan vom Vortag blockiert weiter (Finns Entscheidung); (4) heutiger Auto-Plan (Start am geplanten Tag) blockiert
weiter; (5) Auto-Plan vom Vortag mit Order draußen (orbit_gesendet_at) blockiert weiter; (6) Lauf für morgen übergeht heutige Pläne
nicht; (7) „Neu starten" (Backend _ap_neu_starten, Tab sfNeuEinplanen) lehnt verfallene Auto-Pläne ab (Prüfer Slave 2). Aufruf: python3 tools/selftest_auto_liegengeblieben.py"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    from zoneinfo import ZoneInfo
    jetzt = datetime.now(timezone.utc)
    tag = jetzt.astimezone(ZoneInfo("Europe/Berlin")) + timedelta(days=1)
    while tag.weekday() >= 5:
        tag += timedelta(days=1)
    tag_s = tag.strftime("%Y-%m-%d")
    mitt = datetime(tag.year, tag.month, tag.day, tzinfo=ZoneInfo("Europe/Berlin"))
    gestern = (mitt - timedelta(hours=30)).astimezone(timezone.utc)     # 18:00 dt am Tag VOR heute — sicher vor heute 00:00

    def plan(pid, konto, start, **kw):
        return dict({"id": pid, "user_id": sd.U1, "master_account_id": konto, "master_firm": "FundedNext", "status": "planned",
                     "richtung": "buy", "master_tp": 6000, "master_sl": 3000, "master_contracts": 3.0, "route": "mt5v2",
                     "start_um": start.isoformat(), "start_um_gestartet_at": start.isoformat(), "auto_plan": True,
                     "auto_bestaetigt_at": (start - timedelta(hours=2)).isoformat(), "created_at": (start - timedelta(hours=3)).isoformat(),
                     "started_at": None, "orbit_gesendet_at": None}, **kw)

    def lauf(geplant):
        a = sd.lade()
        sd.db_stubs(a, jetzt, geplant)
        erg = a["ap_planen"](tag_s, trocken=True, seed=4711)
        aus = {x.get("konto_id"): x.get("grund") for x in erg.get("ausgelassen") or []}
        gepl = {x.get("konto_id") for x in erg.get("geplant") or []}
        return erg, aus, gepl

    erg, aus, gepl = lauf([])
    check(erg.get("ok") and "k-2" in gepl, f"Ausgangslage: k-2 wird ohne Plan geplant ({aus.get('k-2')})")
    check(erg.get("verfallen") == [], "Ausgangslage: verfallen leer")

    erg, aus, gepl = lauf([plan("p-leiche", "k-2", gestern)])
    check("k-2" in gepl and "schon einen geplanten" not in str(aus.get("k-2")),
          f"Auto-Plan vom Vortag (Start-Fehler, geclaimt, nie gesendet) blockiert k-2 nicht mehr ({aus.get('k-2')})")
    check([v.get("plan_id") for v in erg.get("verfallen") or []] == ["p-leiche"], f"steht in erg.verfallen ({erg.get('verfallen')})")

    # Postgres-Form mit einer Nachkommastelle (live: „2026-10-08T13:57:25.2+00:00") — Python 3.9 fromisoformat würde scheitern
    p1 = plan("p-leiche1", "k-2", gestern)
    p1["start_um"] = gestern.strftime("%Y-%m-%dT%H:%M:%S") + ".2+00:00"
    erg, aus, gepl = lauf([p1])
    check("k-2" in gepl and [v.get("plan_id") for v in erg.get("verfallen") or []] == ["p-leiche1"],
          f"auch mit start_um „…:25.2+00:00“ erkannt ({p1['start_um']})")

    erg, aus, gepl = lauf([plan("p-hand", "k-2", gestern, auto_plan=False, auto_bestaetigt_at=None)])
    check("schon einen geplanten" in str(aus.get("k-2")) and "k-2" not in gepl and not erg.get("verfallen"),
          f"Handplan vom Vortag blockiert weiter ({aus.get('k-2')})")

    heute_start = mitt + timedelta(hours=9)
    erg, aus, gepl = lauf([plan("p-heute", "k-2", heute_start)])
    check("schon einen geplanten" in str(aus.get("k-2")) and not erg.get("verfallen"),
          f"Auto-Plan am geplanten Tag blockiert weiter ({aus.get('k-2')})")

    erg, aus, gepl = lauf([plan("p-raus", "k-2", gestern, orbit_gesendet_at=gestern.isoformat())])
    check("schon einen geplanten" in str(aus.get("k-2")) and not erg.get("verfallen"),
          f"Auto-Plan vom Vortag mit gesendeter Order blockiert weiter ({aus.get('k-2')})")

    # Hand-Lauf für MORGEN (Prüfer Slave 2): heutige Pläne erst nach start_bis tot — uhrzeitabhängig, darum unten mit festen Zeiten
    # Grenze mit festen Zeiten (Nachtlauf 01:30 Dubai = 23:30 dt ist noch „heute"; start_bis 16:30 dt = 990 min)
    a = sd.lade()
    G = a["ap_verfallen_grenze"]
    B = ZoneInfo("Europe/Berlin")
    m9 = datetime(2026, 10, 9, tzinfo=B)                      # geplanter Tag 09.10.
    h8 = datetime(2026, 10, 8, tzinfo=B)
    check(G(datetime(2026, 10, 8, 23, 30, tzinfo=B), m9, B, 990) == m9, "Nachtlauf 23:30 dt: heutige Pläne (08.10.) sind tot → Grenze = 09.10. 00:00")
    check(G(datetime(2026, 10, 8, 15, 0, tzinfo=B), m9, B, 990) == h8, "Hand-Lauf für morgen um 15:00 dt: Grenze = heute 00:00 (heutige noch startbar)")
    check(G(datetime(2026, 10, 9, 1, 0, tzinfo=B), m9, B, 990) == m9, "Lauf am geplanten Tag selbst (01:00 dt): Grenze = Mitternacht des Tages")
    V0 = a["ap_plan_verfallen"]
    zukunft = {"status": "planned", "auto_plan": True, "start_um": "2026-10-08T20:00:00+00:00"}
    check(not V0(zukunft, m9, datetime(2026, 10, 8, 21, 30, tzinfo=B)), "Start noch in der Zukunft (22:00 dt) → nie verfallen, auch vor der Grenze")

    # Helfer direkt
    V = a["ap_plan_verfallen"]
    g = datetime(2026, 10, 9, tzinfo=ZoneInfo("Europe/Berlin"))
    basis = {"status": "planned", "auto_plan": True, "start_um": "2026-10-08T13:57:25.2+00:00"}
    check(V(basis, g) and not V(dict(basis, auto_plan=False), g) and not V(dict(basis, started_at="x"), g)
          and not V(dict(basis, orbit_gesendet_at="x"), g) and not V(dict(basis, status="open"), g)
          and not V(dict(basis, start_um="2026-10-09T08:00:00+00:00"), g) and not V(dict(basis, start_um=None), g),
          "ap_plan_verfallen: nur Auto + planned + nie gesendet + Start vor der Grenze")

    src = open(sd.APP, encoding="utf-8").read()
    check("started_at,orbit_gesendet_at,mt5_baseline->final" in src, "ap_planen liest started_at/orbit_gesendet_at mit")
    ns = src[src.index("\ndef _ap_neu_starten("):src.index("\n\n\n", src.index("\ndef _ap_neu_starten("))]
    check(ns.index("ap_plan_verfallen(alt_p") < ns.index('rows = sb_update("trade_plans"') and '"verfallen": True' in ns and "409" in ns,
          "_ap_neu_starten lehnt verfallene Auto-Pläne VOR dem Schreiben ab (409, verfallen)")
    html = open(os.path.join(os.path.dirname(sd.APP), "prophos.html"), encoding="utf-8").read()
    sf = html[html.index("async function sfNeuEinplanen("):html.index("async function sfNeuEinplanen(") + 4000]
    check("sfTagDt(plan.startUm) < sfTagDt(new Date().toISOString())" in sf and sf.index("return false") < sf.index("if(!hand){"),
          "sfNeuEinplanen (auch von Hand) lehnt verfallene Auto-Pläne vor allem anderen ab")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
