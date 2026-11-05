#!/usr/bin/env python3
"""Selbsttest NG1 (Finn 05.11.2026: „Warum sind Trades nicht gelaufen und wurden trotzdem hier gestartet? … Fix es."): Echo-Pläne, die N2 über die
Deals als „nicht gelaufen" bewiesen hat (kein Deal, keine Position, keine Order, Balance unverändert), werden gelöscht statt mit +0,00 $ zum
Abhaken liegen zu bleiben — wie der Tagesreset „weg" (app.py). Prüft die Verdrahtung in prophos.html (deTick) und spielt deWegUrteil nach.
Die JS-Regel selbst prüft der Browser über window._deWegUrteil. Aufruf: python3 tools/selftest_ng1_nicht_gelaufen.py"""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def weg_urteil(r):
    """Python-Spiegel von deWegUrteil: '' = darf weg, sonst der Grund."""
    if not r:
        return "kein Plan"
    if r.get("status") != "review":
        return "nicht in Überprüfen"
    if r.get("route") not in ("mt5", "mt5v2"):
        return "kein Echo-Plan"
    if r.get("started_at") or r.get("orbit_gesendet_at"):
        return "Plan war gestartet"
    if r.get("master_pl") is not None and float(r["master_pl"]) != 0:
        return "Master-P&L am Plan"
    if r.get("slave_pl") is not None and float(r["slave_pl"]) != 0:
        return "Fusion-P&L am Plan"
    b = r.get("mt5_baseline") or {}
    f = b.get("final") or {}
    if f.get("art") != "nicht_gelaufen" or f.get("quelle") != "deals_leer":
        return "kein Deal-Beleg"
    if b.get("manuell"):
        return "Manuelle Arbeit"
    if b.get("hedge") or b.get("ticket") or b.get("versuche_alt") or (b.get("live") or {}).get("offen") or b.get("polar"):
        return "Hedge/Ticket/Position am Plan"
    if b.get("puls_unklar") or b.get("puls_pause") or (isinstance(b.get("tv"), dict) and b["tv"]):
        return "Puls-Marke am Plan"
    return ""


def main():
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    w = html[html.index("function deWegUrteil(r){"):html.index("window._deWegUrteil = deWegUrteil")]
    check("if(r.status !== 'review') return" in w and "if(r.started_at || r.orbit_gesendet_at) return" in w
          and "f.art !== 'nicht_gelaufen' || f.quelle !== 'deals_leer'" in w and "if(b.manuell) return" in w
          and "b.hedge || b.ticket || b.versuche_alt || (b.live && b.live.offen) || b.polar" in w
          and "Number(r.master_pl) !== 0" in w and "Number(r.slave_pl) !== 0" in w, "JS-Regel = Spiegel hier")
    dw = html[html.index("async function deWeg(r, warum){"):html.index("async function deTick(){")]
    check(".delete().eq('id', r.id).eq('status', 'review').is('started_at', null)" in dw and "q.eq('updated_at', r.updated_at)" in dw
          and "q.is('master_pl', null) : q.eq('master_pl', 0)" in dw, "Löschen nur mit Guard: noch Überprüfen, nie gestartet, P&L leer/0, unverändert seit dem Lesen")
    t = html[html.index("async function deTick(){"):html.index("setInterval(deTick, 60000)")]
    ng = t[t.index("if(u.art === 'nicht_gelaufen'){"):t.index("if(u.art === 'unklar'){")]
    check("!deWegUrteil(probe) && await deWeg(r, u.grund)) continue" in ng, "bewiesen nicht gelaufen → löschen statt 0,00 $ buchen")
    check(t.index("const u = deUrteil(res, refBal)") < t.index("if(u.art === 'nicht_gelaufen'){"), "Löschen erst nach dem Deal-Urteil (Balance-Gegenprobe)")
    check(t.index("if(u.art === 'offen') continue") < t.index("if(u.art === 'nicht_gelaufen'){"), "offene Position → nie löschen")
    au = t[t.index("// NG1: schon als"):t.index("const kand = (rows || [])")]
    check(".eq('status', 'review').eq('master_pl', 0)" in au and ".is('started_at', null)" in au and "if(!deWegUrteil(r)) await deWeg(" in au,
          "Altfälle (vor NG1 mit 0,00 $ gebucht) werden mit derselben Regel aufgeräumt")
    check("finally{ _deLaeuft = false }" in t and "if(startNah || _suLaeuft) return" in t, "wie N2: nie während ein Echo-Start fällig/geclaimt ist")

    base = {"status": "review", "route": "mt5", "started_at": None, "master_pl": 0, "slave_pl": None,
            "mt5_baseline": {"final": {"art": "nicht_gelaufen", "quelle": "deals_leer", "grund": "nie_gefuellt_tagesende"}, "start_fehler": {"unklar": True}}}
    def mit(**kw):
        r = {**base, "mt5_baseline": {**base["mt5_baseline"], "final": dict(base["mt5_baseline"]["final"])}}
        for k, v in kw.items():
            if k.startswith("b_"):
                r["mt5_baseline"][k[2:]] = v
            elif k.startswith("f_"):
                r["mt5_baseline"]["final"][k[2:]] = v
            else:
                r[k] = v
        return r
    check(weg_urteil(base) == "", "Fall Chris …7785: Deal-Beleg nicht gelaufen, 0,00 $, nie gestartet → weg")
    check(weg_urteil(mit(master_pl=None)) == "", "frisch bewiesen (master_pl noch leer) → weg")
    check(weg_urteil(mit(started_at="2026-11-05T00:00:00Z")) != "", "gestartet → bleibt")
    check(weg_urteil(mit(status="completed")) != "", "schon abgehakt (completed) → bleibt")
    check(weg_urteil(mit(master_pl=-12.5)) != "" and weg_urteil(mit(slave_pl=3.1)) != "", "P&L am Plan → bleibt")
    check(weg_urteil(mit(f_quelle="hand")) != "" and weg_urteil(mit(f_art="unklar")) != "", "ohne Deal-Beleg → bleibt")
    check(weg_urteil(mit(b_hedge={"status": "offen"})) != "" and weg_urteil(mit(b_ticket=123)) != "" and weg_urteil(mit(b_live={"offen": True})) != "",
          "Hedge/Ticket/offene Position → bleibt")
    check(weg_urteil(mit(b_manuell=True)) != "", "Manuelle Arbeit → bleibt")
    check(weg_urteil(mit(b_puls_unklar=True)) != "" and weg_urteil(mit(b_puls_pause={"at": "x"})) != "" and weg_urteil(mit(b_tv={"balance_start": 1})) != "",
          "Puls unklar / Puls-Pause / TradingView-Spur → bleibt (Gegenprüfung NG1)")
    check("if(b.puls_unklar || b.puls_pause || (b.tv && typeof b.tv === 'object' && Object.keys(b.tv).length)) return" in w, "JS: Puls-Marken ausgeschlossen")
    check(weg_urteil(mit(route="tvv2")) != "", "kein Echo → bleibt")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
