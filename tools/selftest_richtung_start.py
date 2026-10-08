#!/usr/bin/env python3
"""Selbsttest RICHTUNG AM START (app.py, Finn 07.10.2026: ein geplanter Auto-Trade soll nicht ausfallen, weil bei derselben ID+Firma
inzwischen eine gegenläufige Position läuft — der Richtungsschutz bleibt hart, der Konflikt wird vorher aufgelöst).

Aufruf:  python3 tools/selftest_richtung_start.py
Teil A rein rechnend (ap_richtung_konflikte): unbestätigter Auto-Plan wird gedreht, bestätigter/Hand-Plan nur markiert, vorher
geplante Gegenrichtung zählt, später geplante nicht, außerhalb 60 min / Hedge-Wege / Widerspruch bleiben unberührt, Bot-Flag wird
gelöscht, wenn der Konflikt weg ist. Teil B Rauch-Lauf ohne Netz (nachgebaute DB aus selftest_auto_delta): ap_ausgleichen dreht
den unbestätigten Plan mit Guard auto_bestaetigt_at IS NULL + Protokoll „Richtungsschutz: läuft schon short", markiert den
bestätigten per RPC mt5_baseline_patch, ändert im Trockenlauf nichts. Teil C: Protokollzeile des PC-Tabs (quelle 'start')."""
import os
import re
import sys
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as basis  # noqa: E402

NEU = ("ap_richtung_konflikte", "_ap_rk_flag", "ap_richtungsschutz", "ap_start_protokoll_zeile")
KONST = ("AP_RS_HORIZONT_MIN", "AP_RS_NACHLAUF_MIN", "AP_RS_ROUTEN")


def lade():
    ns = basis.lade()
    src = open(basis.APP, encoding="utf-8").read()

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    exec("\n".join([re.search(rf"^{k} = .*$", src, re.M).group(0) for k in KONST] + [block(f) for f in NEU]), ns)
    # ap_ausgleichen/_ap_stand_plaene/_ap_aenderungen_anwenden neu laden: sie greifen auf die eben geladenen Namen zu
    exec("\n".join(block(f) for f in ("_ap_stand_plaene", "_ap_aenderungen_anwenden", "ap_ausgleichen", "_ap_stand_laden")), ns)
    return ns


def stubs(a, jetzt, geplant):
    """db_stubs aus selftest_auto_delta + Antwort mit json() (RPC mt5_baseline_patch liefert das neue mt5_baseline)."""
    reg, geschrieben = basis.db_stubs(a, jetzt, geplant)

    class R:
        status_code = 201
        text = ""

        def json(self):
            return {"richtung_konflikt": {}}
    a["_sb_anfrage"] = lambda *x, **k: (geschrieben["post"].append((x, k)), R())[1]
    return reg, geschrieben


def main():
    a = lade()
    ok = True

    def check(bed, text):
        nonlocal ok
        print(("  ✓ " if bed else "  ✗ ") + text)
        ok = ok and bool(bed)

    U1, U2 = basis.U1, basis.U2

    def plan(pid, user, firma, richtung, start, auto=True, best=False, aend=True, route="tvv2", gehedgt=False, fest=None, rk=None):
        return {"plan_id": pid, "user_id": user, "user": user[-2:], "firma": firma, "firma_name": firma.title(), "richtung": richtung,
                "start_min": start, "route": route, "gehedgt": gehedgt, "auto_plan": auto, "bestaetigt": best,
                "aenderbar": aend, "fest_durch": fest, "richtung_konflikt": rk}

    print("A) ap_richtung_konflikte (rein rechnend)")
    k = a["ap_richtung_konflikte"]
    offen = [{"user_id": U1, "firma": "tradeify", "richtung": "sell"}]
    e = k([plan("p1", U1, "tradeify", "buy", 630)], offen, 600)
    check(len(e["drehen"]) == 1 and e["drehen"][0]["nach_richtung"] == "sell" and e["drehen"][0]["grund"].startswith("Richtungsschutz: läuft schon short"),
          f"unbestätigter Auto-Plan long, short läuft → gedreht ({e['drehen'][0]['grund'] if e['drehen'] else '—'})")
    e = k([plan("p1", U1, "tradeify", "buy", 630, best=True)], offen, 600)
    check(not e["drehen"] and len(e["markieren"]) == 1 and e["markieren"][0]["gegen"] == "sell" and e["markieren"][0]["durch"] == "läuft",
          "bestätigter Auto-Plan → nur markiert, nicht gedreht")
    e = k([plan("p1", U1, "tradeify", "buy", 630, auto=False, best=True, aend=False, fest="Handplan")], offen, 600)
    check(not e["drehen"] and len(e["markieren"]) == 1 and "Hand-Plan" in e["markieren"][0]["text"], "Hand-Plan → nur markiert")
    e = k([plan("p1", U1, "tradeify", "buy", 700)], offen, 600)
    check(not e["drehen"] and not e["markieren"], "Start in mehr als 60 min → unberührt")
    e = k([plan("p1", U1, "tradeify", "buy", 595)], offen, 600)
    check(len(e["drehen"]) == 1, "fällig, aber noch nicht gestartet (bis 10 min zurück) → gedreht")
    e = k([plan("p1", U1, "tradeify", "buy", 630)], [{"user_id": U2, "firma": "tradeify", "richtung": "sell"}], 600)
    check(not e["drehen"] and not e["markieren"], "andere ID derselben Firma short → kein Konflikt (Richtungsschutz je ID+Firma)")
    e = k([plan("p1", U1, "tradeify", "buy", 630)], [{"user_id": U1, "firma": "apex", "richtung": "sell"}], 600)
    check(not e["drehen"], "andere Firma derselben ID short → kein Konflikt")
    e = k([plan("p1", U1, "tradeify", "buy", 630, route="mt5")], offen, 600)
    check(not e["drehen"] and not e["markieren"], "klassischer Hedge-Weg (route mt5) → unberührt")
    e = k([plan("p1", U1, "tradeify", "buy", 630, gehedgt=True)], offen, 600)
    check(not e["drehen"] and not e["markieren"], "Plan mit Hedge (WD/Orbit V3) → unberührt")
    e = k([plan("p1", U1, "tradeify", "buy", 630)], offen + [{"user_id": U1, "firma": "tradeify", "richtung": "buy"}], 600)
    check(not e["drehen"] and not e["markieren"], "läuft long UND short (Widerspruch) → nichts entschieden")
    # seit 09.10.2026 ~03:45 (Finn: Richtung je Trade frei, nur nie gleichzeitig): ein bloß GEPLANTER Gegen-Plan legt nichts fest —
    # weder ein Hand-Plan davor noch danach; der Start-Wächter im PC-Tab klärt es, falls beim Start doch etwas läuft
    pl = [plan("h1", U1, "tradeify", "sell", 620, auto=False, best=True, aend=False, fest="Handplan"), plan("p1", U1, "tradeify", "buy", 630)]
    e = k(pl, [], 600)
    check(not e["drehen"] and not e["markieren"], "Hand-Plan short VOR dem Auto-Plan geplant → nichts gedreht, nichts markiert")
    pl = [plan("p1", U1, "tradeify", "buy", 620), plan("h1", U1, "tradeify", "sell", 640, auto=False, best=True, aend=False, fest="Handplan")]
    e = k(pl, [], 600)
    check(not e["drehen"] and not e["markieren"], "Hand-Plan short NACH dem Auto-Plan long → nichts gedreht, nichts markiert")
    pl = [plan("h1", U1, "tradeify", "sell", 610, auto=False, best=True, aend=False, fest="schon gestartet"), plan("p1", U1, "tradeify", "buy", 630)]
    e = k(pl, [], 615)
    check([d["plan_id"] for d in e["drehen"]] == ["p1"], "geclaimter Short (Start läuft) 10:10 → Auto-Plan long 10:30 gedreht")
    pl = [plan("p1", U1, "tradeify", "buy", 630), plan("p2", U1, "tradeify", "buy", 632)]
    e = k(pl, offen, 600)
    check(sorted(d["plan_id"] for d in e["drehen"]) == ["p1", "p2"], "Tranche (zwei Konten derselben ID+Firma) → beide gedreht")
    e = k([plan("s1", U1, "tradeify", "sell", 590, aend=False, fest="schon gestartet"), plan("p1", U1, "tradeify", "buy", 630)], [], 600)
    check([d["plan_id"] for d in e["drehen"]] == ["p1"], "geclaimter Plan (Start läuft) zählt als laufend")
    e = k([plan("p1", U1, "tradeify", "sell", 630, best=True, rk={"quelle": "bot", "status": "konflikt"})], offen, 600)
    check(e["frei"] == ["p1"] and not e["markieren"] and not e["drehen"], "gleiche Richtung wie laufend → kein Konflikt, altes Bot-Flag frei")
    e = k([plan("p1", U1, "tradeify", "buy", 630, best=True, rk={"quelle": "bot", "status": "konflikt"})], [], 600)
    check(e["frei"] == ["p1"], "Bot-Flag ohne Konflikt → frei (wird gelöscht)")
    e = k([plan("p1", U1, "tradeify", "buy", 630, best=True, rk={"quelle": "start", "status": "wartet"})], [], 600)
    check(e["frei"] == [], "Flag des PC-Tabs (wartet) fasst der Bot nicht an")

    print("B) ap_ausgleichen mit Richtungsschutz (nachgebaute DB, kein Netz)")
    from zoneinfo import ZoneInfo
    jetzt = datetime.now(timezone.utc)
    tz = ZoneInfo("Europe/Berlin")
    d = jetzt.astimezone(tz)
    mitt = datetime(d.year, d.month, d.day, tzinfo=tz)
    t_jetzt = max(jetzt, mitt + timedelta(minutes=30))
    if (t_jetzt - mitt) > timedelta(hours=22):       # spät abends: Plan + 20 min bleibt am selben deutschen Tag
        t_jetzt = mitt + timedelta(hours=12)
    t_plan = t_jetzt + timedelta(minutes=20)
    # Fixture: U3 Tradeify-WD läuft SHORT (k-6). Auto-Pläne bei U3 Tradeify (gleiche ID+Firma): unbestätigt long + bestätigt long
    geplant = [
        {"id": "p-a1", "user_id": basis.U3, "master_account_id": "k-6", "master_firm": "Tradeify", "status": "planned", "richtung": "buy",
         "master_tp": 3500, "master_sl": None, "master_contracts": 3, "master_symbol": "NQZ6", "route": "tvv2",
         "start_um": t_plan.isoformat(), "auto_plan": True, "auto_bestaetigt_at": None, "created_at": jetzt.isoformat()},
        {"id": "p-a2", "user_id": basis.U3, "master_account_id": "k-6", "master_firm": "Tradeify", "status": "planned", "richtung": "buy",
         "master_tp": 3500, "master_sl": None, "master_contracts": 3, "master_symbol": "NQZ6", "route": "tvv2",
         "start_um": (t_plan + timedelta(minutes=30)).isoformat(), "auto_plan": True, "auto_bestaetigt_at": jetzt.isoformat(),
         "created_at": jetzt.isoformat()},
    ]
    reg, geschrieben = stubs(a, jetzt, geplant)
    erg = a["ap_ausgleichen"](trocken=True, seed=1, jetzt=t_jetzt)
    rs = erg.get("richtungsschutz") or {}
    check([g["plan_id"] for g in rs.get("gedreht", [])] == ["p-a1"] and rs.get("markiert") == ["p-a2"] and not geschrieben["patch"]
          and not geschrieben["post"], f"trocken: würde p-a1 drehen, p-a2 markieren, schreibt nichts ({rs})")
    reg, geschrieben = stubs(a, jetzt, geplant)
    erg = a["ap_ausgleichen"](trocken=False, seed=1, jetzt=t_jetzt)
    rs = erg.get("richtungsschutz") or {}
    pat = [(p[1].get("id"), p[1].get("auto_bestaetigt_at"), "or" in p[1], p[2]) for p in geschrieben["patch"] if p[0] == "trade_plans"]
    check(("eq.p-a1", "is.null", False, {"richtung": "sell"}) in pat, f"p-a1 mit Guard auto_bestaetigt_at IS NULL auf short gedreht ({pat})")
    check(all(not (i == "eq.p-a2" and "richtung" in body) for i, _g, _o, body in pat), "bestätigter p-a2 nicht gedreht (Richtung unverändert)")
    posts = [(x[0][1], x[1].get("json")) for x in geschrieben["post"]]
    prot = [z for url, j in posts if url.endswith("/auto_plan_umplanung") for z in (j or [])]
    check(any(z["plan_id"] == "p-a1" and z["grund"].startswith("Richtungsschutz: läuft schon short") and z["quelle"] == "bot" for z in prot),
          "Protokoll: „Richtungsschutz: läuft schon short“, quelle bot")
    rpc = [j for url, j in posts if url.endswith("/rpc/mt5_baseline_patch")]
    check(any(j["p_plan"] == "p-a2" and j["p_status"] == "planned" and j["p_patch"]["richtung_konflikt"]["status"] == "konflikt"
              and j["p_patch"]["richtung_konflikt"]["gegen"] == "sell" for j in rpc),
          "p-a2: Flag richtung_konflikt per RPC mt5_baseline_patch (Guard planned)")
    check(rs.get("gedreht") and rs["gedreht"][0]["plan_id"] == "p-a1" and erg["umplanungen"][0]["plan_id"] == "p-a1",
          "Antwort: richtungsschutz{gedreht, markiert} + Drehung vorn in umplanungen[]")
    # Delta-Monitor zeigt das Flag (Spalte aus mt5_baseline->richtung_konflikt)
    g2 = [dict(geplant[0], richtung="sell"), dict(geplant[1], rk={"quelle": "bot", "status": "konflikt", "gegen": "sell", "durch": "läuft",
                                                                 "text": "Richtungskonflikt"})]
    reg, geschrieben = stubs(a, jetzt, g2)
    st = a["_ap_stand_laden"](reg, jetzt=t_jetzt)
    dl = a["ap_delta_antwort"](st)
    gp = {x["plan_id"]: x for x in dl["geplant"]}
    check(gp["p-a2"].get("richtung_konflikt", {}).get("status") == "konflikt" and gp["p-a1"].get("richtung_konflikt") is None,
          "GET /admin/auto-plan/delta: geplant[].richtung_konflikt")
    erg = a["ap_ausgleichen"](trocken=False, seed=1, jetzt=t_jetzt)
    rpc = [x[1].get("json") for x in geschrieben["post"] if x[0][1].endswith("/rpc/mt5_baseline_patch")]
    check(not rpc, "schon so markiert → kein zweiter Schreibvorgang")

    print("C) Protokollzeile des PC-Tabs")
    z, f = a["ap_start_protokoll_zeile"]({"id": "x", "user_id": U1, "master_firm": "Tradeify"},
                                        {"von_richtung": "buy", "nach_richtung": "sell", "von_start": "2026-10-07T10:00:00Z",
                                         "nach_start": "2026-10-07T10:00:00Z", "grund": "Richtungsschutz am Start"}, "2026-10-07T10:00:05+00:00")
    check(f is None and z["quelle"] == "start" and z["nach_richtung"] == "sell" and z["firma"] == "Tradeify", "gültiger Eintrag → quelle start")
    z, f = a["ap_start_protokoll_zeile"]({"id": "x", "user_id": U1}, {"von_richtung": "rauf", "grund": "x"}, "t")
    check(z is None and "buy" in f, "ungültige Richtung → Klartext")
    z, f = a["ap_start_protokoll_zeile"]({"id": "x", "user_id": U1}, {"von_richtung": "buy"}, "t")
    check(z is None and f == "grund fehlt", "ohne Grund → Klartext")

    print("ALLES OK" if ok else "FEHLER")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
