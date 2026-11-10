#!/usr/bin/env python3
"""Selbsttest WS2E Trades pro Tag bei Echo (Master 10.11.2026, Finn: „Lass uns jetzt an die mehreren Trades bei Echo machen.“).

Aufruf:  python3 tools/selftest_ws2e_echo_kette.py
Ohne Netz, Platzhalter-IDs. Prüft:
  1. tt_abhak_werte: Orbit/Topstep ohne Hedge bitgleich (tv, slave_pl None), Orbit mit Fusion-Solo nie, Echo (mt5) nur mit belegtem Fusion-P&L
     (slave_pl am Plan, sonst final.closed_sum), Echo V2 wie bisher bei Finn, ohne genaue Lesung nie.
  2. tt_zschluss_versucht: status geschlossen/war_flach/fehler, begonnener Versuch (versuche/letzter_versuch_at) ohne status, nie 'uebersprungen'.
  3. tt_tick: Echo-Teil mit Nachfolger + Fusion-P&L → automatisch abgehakt (master_pl aus bal_nach, slave_pl, pl_quelle echo); ohne Beleg bleibt er bei
     Finn; Orbit-Teil wie bisher; begonnener Zufalls-Schluss ohne status → kein Folge-Teil, Tag fertig (zschluss); 'uebersprungen' → Folge-Teil kommt.
  4. Radar wdlEchoKetteWartet (prophos.html, per jsc): nicht-letzter Echo-Teil, genau gelesen (kette_gelesen) und mit Fusion-P&L, wartet, sonst
     Abhak-Zeile wie bisher; /admin/live-trades liefert kette_gelesen aus tt_echt."""
import os as _os_mk, sys as _sys_mk
_sys_mk.path.insert(0, _os_mk.path.dirname(_os_mk.path.abspath(__file__)))
import modell_name_test  # noqa: F401 — MODELL_NAME aus app.py für die exec-Ausschnitte
import json
import os
import random
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402
import selftest_ws2_tagesteilung as w2  # noqa: E402

FEHLER = []
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    a = w2.lade()
    AW, ZV = a["tt_abhak_werte"], a["tt_zschluss_versucht"]

    # ── 1 tt_abhak_werte ─────────────────────────────────────────────────────────────────────────────────────────────
    e = (100000.0, 100500.0)
    check(AW({"route": "tvv2", "mt5_baseline": {}}, e) == (500.0, None, "tv") and AW({"route": "tsv2", "mt5_baseline": {}}, e) == (500.0, None, "tv"),
          "Orbit/Topstep ohne Hedge: wie bisher (P&L aus der Lesung, slave_pl None, Quelle tv)")
    check(AW({"route": "tvv2", "mt5_baseline": {"hedge": {"status": "geschlossen"}}}, e) is None, "Orbit mit Fusion-Solo-Hedge: bleibt bei Finn")
    check(AW({"route": "mt5", "slave_pl": 12.5, "mt5_baseline": {"final": {"closed_sum": -3}}}, e) == (500.0, 12.5, "echo"),
          "Echo mit Hedge: slave_pl am Plan (aus closed_sum) gewinnt")
    check(AW({"route": "mt5", "slave_pl": None, "mt5_baseline": {"final": {"closed_sum": -30.456}}}, e) == (500.0, -30.46, "echo"),
          "Echo mit Hedge: ohne slave_pl final.closed_sum")
    check(AW({"route": "mt5", "slave_pl": 0, "mt5_baseline": {"final": {}}}, e) == (500.0, 0.0, "echo"), "Echo: slave_pl 0 ist ein Wert")
    check(AW({"route": "mt5", "mt5_baseline": {"final": {"closed_sum": None}}}, e) is None and AW({"route": "mt5", "mt5_baseline": {}}, e) is None,
          "Echo ohne belegten Fusion-P&L (closed_sum null = Hedge extern zu / Ring gekürzt): bleibt bei Finn")
    check(AW({"route": "mt5v2", "slave_pl": 0, "mt5_baseline": {}}, e) is None, "Echo V2 (mt5v2): bleibt wie bisher bei Finn (slave_pl 0 nie überschrieben)")
    check(AW({"route": "mt5", "slave_pl": 5}, None) is None and AW({"route": "tvplus"}, e) is None and AW({"route": "polar"}, e) is None,
          "ohne genaue Lesung bzw. andere Wege: nie")

    # ── 2 tt_zschluss_versucht ───────────────────────────────────────────────────────────────────────────────────────
    check(all(ZV({"nach_min": 30, "status": s}) for s in ("geschlossen", "war_flach", "fehler")), "status geschlossen/war_flach/fehler → Tag fertig (wie bisher)")
    check(ZV({"nach_min": 30, "versuche": 1, "letzter_versuch_at": "2026-11-10T09:00:00Z"}) and ZV({"nach_min": 30, "versuche": 1})
          and ZV({"nach_min": 30, "letzter_versuch_at": "x"}), "Versuch begonnen, status steht noch aus → Tag fertig (Race Echo-Nachlesung vor status)")
    check(not ZV({"nach_min": 30}) and not ZV({}) and not ZV(None) and not ZV({"nach_min": 30, "status": "uebersprungen"})
          and not ZV({"nach_min": 30, "status": "uebersprungen", "versuche": 0}), "kein Versuch / übersprungen → kein Ende")

    # ── 3 tt_tick ────────────────────────────────────────────────────────────────────────────────────────────────────
    BER = ZoneInfo("Europe/Berlin")
    mitt = datetime(2026, 11, 10, tzinfo=BER)
    jetzt = (mitt + timedelta(hours=10, minutes=2)).astimezone(timezone.utc)
    std = a["tt_param"]({})
    k1 = {"nr": 1, "von": 3, "rolle": "haupt", "plan": {"n": 3, "haupt_an": 1, "anteile": [0.8, 0.12, 0.08]}, "tagesziel": 6000, "haupt_menge": 2.6,
          "ppl": 1.0, "menge_schritt": 0.1}
    T1 = "00000000-0000-0000-0000-0000000e0001"
    ende_at = (mitt + timedelta(hours=9, minutes=55)).isoformat()
    tc = {"id": T1, "user_id": sd.U1, "master_account_id": "k-fn", "master_firm": "FundedNext", "master_name": "FN-000000", "master_symbol": None,
          "richtung": "buy", "route": "mt5", "status": "review", "auto_plan": True, "auto_bestaetigt_at": "2026-11-09T22:00:00Z", "ended_at": ende_at,
          "planned_for": "2026-11-10", "konto_typ": "phase1", "updated_at": "u1", "slave_pl": 14.2, "master_pl": 480,
          "mt5_baseline": {"kette": dict(k1), "master_balance": 100000, "final": {"master_balance": 100490, "closed_sum": 14.2, "at": ende_at},
                           "bal_nach": {"ok": True, "quelle": "nachlesung", "balance": 100500, "at": ende_at}}}
    CFDR = dict(w2.CFD, namen=["fundednext"])
    db = {"plaene": [tc], "ins": [], "upd": [], "patch": [], "nachfolger": []}
    REG = {"id": 1, "zeiten": {"tz": "Europe/Berlin", "fenster": [["00:00", "14:30", 50], ["14:30", "16:30", 50]], "start_bis": "16:30"},
           "regeln": {"firmen": [w2.TRADEIFY, CFDR], "ausgleich": {"laufzeit_min": 180}, "tagesteilung": dict(std, an=True)}}

    def sb_select(table, params):
        if table == "auto_plan_regeln":
            return [REG]
        if table == "accounts":
            return [{"id": "k-fn", "user_id": sd.U1, "firm": db.get("firm", "FundedNext"), "account_type": db.get("typ", "phase1"), "account_size": 100000}]
        if table == "trade_plans" and "mt5_baseline->kette->>von" in params:
            return [dict(x) for x in db["plaene"]]
        if table == "trade_plans" and "mt5_baseline->kette->>vor" in params:
            want = params["mt5_baseline->kette->>vor"]
            alle = [{"id": "n", "status": "planned", "vor": v} for v in db["nachfolger"]] + \
                   [{"id": "n", "status": "planned", "vor": z["mt5_baseline"]["kette"]["vor"]} for z in db["ins"]]
            return [x for x in alle if want.startswith("in.") or want == "eq." + x["vor"]]
        if table == "trade_plans" and "mt5_baseline->kette->>tag_id" in params:
            return []
        if table == "trade_plans" and params.get("id"):
            return [dict(x) for x in db["plaene"] if "eq." + x["id"] == params["id"]]
        return []

    def stand(reg, uid, j=None, **k_):
        return {"mitternacht": mitt, "jetzt_min": (j - mitt).total_seconds() / 60.0, "zeiten": reg["zeiten"], "offen": [], "geplant": [], "folgetag": [],
                "starts_heute": [], "id_fest": {}, "firmen": [w2.TRADEIFY, CFDR]}
    a.update(sb_select=sb_select, sb_insert=lambda t, z: db["ins"].append(z) or z, sb_update=lambda t, f, u: db["upd"].append((f, u)) or [u],
             _ap_stand_fuer_uid=stand, _ap_sperren=lambda: set(), requests=__import__("requests"),
             _tt_patch=lambda pid, patch, key="kette": db["patch"].append((pid, patch)) or True,
             ap_regel_unternehmen=lambda uid, firmen, firm, **k_: a["ap_regel_finden"](firmen, firm),
             ap_echo_hedge_anlegen=lambda zeilen, konten, regeln: (zeilen[0].update(route="mt5") or {"echo": 1, "weg": []}))
    a.setdefault("_firm_norm", lambda n: str(n or ""))

    def lauf(plaene, nachfolger=(), seed=21):
        db.update(plaene=plaene, ins=[], upd=[], patch=[], nachfolger=list(nachfolger))
        return a["tt_tick"](jetzt, random.Random(seed))

    erg = lauf([tc], nachfolger=[T1])
    up = [u for f, u in db["upd"] if f.get("id") == f"eq.{T1}"]
    check(len(up) == 1 and up[0].get("status") == "completed" and up[0].get("master_pl") == 500 and up[0].get("slave_pl") == 14.2
          and up[0].get("pl_quelle") == "echo" and [f for f, _u in db["upd"]][0].get("status") == "eq.review" and erg.get("abgehakt") == [T1],
          f"Echo-Teil 1/3 mit Nachfolger + Fusion-P&L: automatisch abgehakt (master_pl aus Nachlesung 500, slave_pl 14,2, Quelle echo) ({up})")
    check([f for f, _u in db["upd"]][0].get("updated_at") == "eq.u1", "Abhaken mit optimistischer Sperre (updated_at)")
    lauf([dict(tc, slave_pl=None, mt5_baseline=dict(tc["mt5_baseline"], final={"master_balance": 100490, "closed_sum": None}))], nachfolger=[T1])
    check(not db["upd"], "Echo-Teil ohne belegten Fusion-P&L: bleibt bei Finn (kein Update)")
    lauf([dict(tc, status="completed")], nachfolger=[T1])
    check(not db["upd"], "schon von Finn abgehakt (completed): nichts")
    lauf([dict(tc, mt5_baseline=dict(tc["mt5_baseline"], bal_nach={"ok": False, "code": "kein_snapshot"}))], nachfolger=[T1])
    check(not db["upd"], "Echo-Teil ohne genaue Nachlesung: nie abgehakt")
    to = dict(tc, route="tvv2", master_firm="Tradeify", slave_pl=None,
              mt5_baseline={"kette": dict(k1), "tv": {"balance_start": 150000}, "final": {"quelle": "puls", "balance_end": 150400, "at": ende_at}})
    lauf([to], nachfolger=[T1])
    up = [u for _f, u in db["upd"]]
    check(len(up) == 1 and up[0].get("master_pl") == 400 and up[0].get("slave_pl") is None and up[0].get("pl_quelle") == "tv",
          "Orbit-Teil mit Nachfolger: unverändert (P&L 400, slave_pl None, Quelle tv)")

    # Race: Zufalls-Schluss begonnen (versuche/letzter_versuch_at), status fehlt noch, Nachlesung schon da
    zs_lauf = {"nach_min": 30, "versuche": 1, "letzter_versuch_at": ende_at, "pc": "pc-x", "art": "normal"}
    lauf([dict(tc, mt5_baseline=dict(tc["mt5_baseline"], zschluss=zs_lauf))])
    te = next((p["tagesende"] for _pid, p in db["patch"] if p.get("tagesende")), {})
    check(not db["ins"] and te.get("ende_grund") == "zschluss" and "Versuch" in str(te.get("ende_text")),
          f"Zufalls-Schluss begonnen, status fehlt: kein Folge-Teil, Tag fertig ({te.get('ende_text')})")
    lauf([dict(tc, mt5_baseline=dict(tc["mt5_baseline"], zschluss={"nach_min": 30, "status": "geschlossen", "versuche": 1}))])
    te = next((p["tagesende"] for _pid, p in db["patch"] if p.get("tagesende")), {})
    check(not db["ins"] and te.get("ende_grund") == "zschluss" and "(geschlossen)" in str(te.get("ende_text")), "Zufalls-Schluss geschlossen: wie bisher")
    lauf([dict(tc, mt5_baseline=dict(tc["mt5_baseline"], zschluss={"nach_min": 30, "status": "uebersprungen", "grund": "orbit_v3"}))])
    check(len(db["ins"]) == 1 and db["ins"][0]["route"] == "mt5" and db["ins"][0]["mt5_baseline"]["kette"]["nr"] == 2
          and db["ins"][0]["mt5_baseline"]["kette"]["balance_vor"] == 100500,
          "zschluss übersprungen (kein Versuch): Folge-Teil 2/3 kommt aus der Nachlesung 100.500")
    lauf([dict(tc, mt5_baseline=dict(tc["mt5_baseline"], zschluss={"nach_min": 30}))])
    check(len(db["ins"]) == 1, "zschluss gewürfelt, nie ausgelöst (Trade vorher zu): Folge-Teil kommt")

    # ── 4 Radar wdlEchoKetteWartet (jsc) ──────────────────────────────────────────────────────────────────────────────
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    i = html.index("  function wdlEchoKetteWartet(t, jetzt){")
    j = html.index("\n  }\n", i) + 4
    fn = html[i:j]
    stubs = "const wdlIstEcho = t => !!t && t.plattform === 'echo';\n"
    jetzt_ms = int(jetzt.timestamp() * 1000)
    bis = (jetzt + timedelta(hours=3)).isoformat()
    B = {"plattform": "echo", "route": "mt5", "status": "review", "kette_nr": 1, "kette_von": 3, "kette_lesen_bis": bis, "balance_start": 100000,
         "slave_pl": 14.2, "kette_gelesen": True, "kette_tag": None, "blown": False, "kette_grund": "Trade 2/3 angelegt: Neben buy 0.4 · TP 380 / SL 600 $"}
    FAELLE = [("nicht-letzter Echo-Teil mit Fusion-P&L", {}, True), ("letzter Teil (nr = von)", {"kette_nr": 3}, False),
              ("ohne kette_von (kein Ketten-Plan)", {"kette_von": None, "kette_nr": None}, False), ("kette_von ungültig", {"kette_von": "x"}, False),
              ("Fusion-P&L fehlt", {"slave_pl": None}, False), ("nicht genau gelesen (bal_nach fehlt/gescheitert)", {"kette_gelesen": False}, False),
              ("ohne kette_gelesen (altes Backend)", {"kette_gelesen": None}, False), ("Fusion-P&L 0", {"slave_pl": 0}, True), ("Fenster vorbei", {"kette_lesen_bis": jetzt.isoformat()}, False),
              ("ohne lesen_bis", {"kette_lesen_bis": None}, False), ("Tagesende steht", {"kette_tag": {"tag_pl": 1}}, False), ("geblowt", {"blown": True}, False),
              ("ohne Start-Balance", {"balance_start": None}, False), ("Grund unplausibel", {"kette_grund": "Ergebnis unplausibel — von Hand abhaken"}, False),
              ("Echo V2 (mt5v2)", {"route": "mt5v2"}, False), ("Orbit-Zeile", {"plattform": "orbit", "route": "tvv2"}, False),
              ("abgehakt (completed)", {"status": "completed"}, False), ("läuft (open)", {"status": "open"}, False)]
    js = stubs + fn + "\nconst F = " + json.dumps([dict(B, **f[1]) for f in FAELLE], ensure_ascii=False) + \
        f"; print(JSON.stringify(F.map(t => wdlEchoKetteWartet(t, {jetzt_ms}))));"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
        d.write(js)
    r = subprocess.run([JSC, d.name], capture_output=True, text=True)
    os.unlink(d.name)
    check(r.returncode == 0, f"jsc läuft ({r.stderr[:200]})")
    erg = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else []
    for (name, _f, soll), g in zip(FAELLE, erg):
        check((g is not None and g.get("kette") == "t2") is soll, f"Radar: {name} → {'Wartet' if g else 'Abhak-Zeile/wie bisher'}")
    check('wt = echo ? wdlEchoKetteWartet(t) : wdlWartet(t)' in html
          and '(wdlIstEcho(t) ? !!wdlEchoKetteWartet(t) : wdlWartet(t))' in html, "Radar: Wartet-Gruppe und Zeile nutzen wdlEchoKetteWartet nur für Echo")
    src = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()
    check('z["kette_gelesen"] = bool(tt_echt(q)) if "tt_echt" in globals() else None' in src, "/admin/live-trades: kette_gelesen aus tt_echt (wie tt_tick)")

    print(f"\n{'selftest_ws2e_echo_kette: alle Prüfungen grün' if not FEHLER else f'✗ {len(FEHLER)} Fehler'}")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
