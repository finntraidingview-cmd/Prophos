#!/usr/bin/env python3
"""Selbsttest SL-PFLICHT (09.11.2026, WS1c — Marc Topstep-Challenge …1094, Plan 272809d8: „Risk 1497 $ nicht gesetzt (Risk-Zelle verdeckt,
gesperrt oder ohne Rechteck)", SELL 2 NQ lief ohne SL ins Tageslimit). Geprüft mit nachgebauter TopstepX-Sitzung:
  tsv2 (Risk erst NACH dem Fill in der Positions-Tabelle):
    a) Risk normal setzbar → wie bisher, kein Nachsetzen, keine Warnung
    b) Zelle in den drei Runden „Mitte außerhalb des Fensters", danach frei → SL NACHSETZEN setzt Risk, nur To Make fehlt
    c) Zelle bleibt unerreichbar → ORDER OHNE SL in der Spur, brackets_fehlen.risk (🔴-Weg), genaue Ursache in der Warnung,
       genau EIN Order-Klick, nie ein Close
    d) kein Plan-SL → keine Nachsetz-Runden (wie heute)
  tvv2 (SL im Ticket VOR der Order): cdp_ticket_ruecklesung lässt ohne bewiesenen SL nicht senden; die Rücklesung steht im Code vor
  dem einzigen Senden-Klick.
  Dazu tsx_k4_zelle_zu_grund (rein rechnend) und der Warnungs-Parser von app.py (_tsx_brackets_kern-Regeln).
Aufruf: python3 tools/selftest_tsx_k4_sl_pflicht.py"""
import inspect
import os
import re
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "mt5-copier"))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


E = "150KTC-SKU-V2-DLL-000000-00000000"
RK, RV, RT = [1640, 416, 120, 26], [1766, 416, 120, 26], [156, 746, 69, 28]
RR, RM, RC = [1000, 766, 200, 22], [1300, 766, 200, 22], [1850, 766, 60, 22]
GEO = {"innerWidth": 1920, "innerHeight": 760, "dpr": 1}


class Sitz:
    """TopstepX nach dem Klick: Fill-Meldung + Positionszeile; Risk/To Make per Doppelklick → Feld → tippen → Enter.
    zu_lesungen = so viele Lesungen NACH dem Order-Klick melden beide Zellen „Mitte außerhalb des Fensters" (None = nie, -1 = immer,
    "runden" = bis die Spur das SL-Nachsetzen meldet — also genau während der drei normalen Runden)."""

    def __init__(self, richtung="sell", menge=2, avg=27301.75, zu_lesungen=None, zu_felder=("risk", "to_make"), edit_geht=True):
        self.richtung, self.menge, self.avg, self.zu_lesungen = richtung, menge, avg, zu_lesungen
        self.zu_felder, self.edit_geht, self.rest_bei_klick = zu_felder, edit_geht, []
        self.pos, self.lesungen, self.t_klick, self.reiter = False, None, 0, False
        self.werte = {"risk": None, "to_make": None}
        self.edit, self.eingabe, self.markiert = None, "", False
        self.klicks, self.tasten, self.trail = [], [], None

    def _zu(self):
        if self.lesungen is None or self.zu_lesungen is None:
            return False
        if self.zu_lesungen == "runden":
            return not any("SL NACHSETZEN" in str(x) for x in (self.trail or []))
        return self.zu_lesungen < 0 or self.lesungen <= self.zu_lesungen

    def _feld(self, name, rect):
        if self.edit == name:
            return {"text": "", "wert": None, "rect": rect, "zu": {"disabled": False, "verdeckt": False},
                    "edit": {"offen": True, "wert": self.eingabe, "rect": rect, "fokus": True, "typ": "number"}}
        w = self.werte[name]
        zu = {"disabled": False, "verdeckt": True, "oben": "ausserhalb"} if (self._zu() and name in self.zu_felder) else {"disabled": False, "verdeckt": False}
        return {"text": "" if w is None else f"${w:,.2f}", "wert": w, "rect": rect, "zu": zu, "edit": {"offen": False}, "stift": None}

    def stand(self, opts=None):
        if self.lesungen is not None:
            self.lesungen += 1
            self.pos = True
        n = self.menge
        meld = []
        if self.pos:
            meld.append({"art": "fill", "status": "ausgefuehrt", "aktiv": True, "seite": self.richtung, "menge": n, "symbol": "NQZ26",
                         "typ": "market", "preis": self.avg, "erst_gesehen": self.t_klick + 300})
        zeile = {"symbol": "NQ", "menge": -n if self.richtung == "sell" else n, "seite": self.richtung, "avg": self.avg, "pl_text": "$0.00",
                 "risk": self._feld("risk", RR), "to_make": self._feld("to_make", RM), "close_rect": RC, "rect": [69, 766, 1930, 22]}
        return {"v": "tsx-0.6.4", "geo": GEO,
                "konto": {"aktiv": f"$150K Combine|{E}", "kontonr": E, "abgekuerzt": False, "liste_offen": False, "liste": []},
                "kopf": {"balance": {"text": "$157,087.32", "wert": 157087.32}, "mll": {"text": "$150,000.00", "wert": 150000.0},
                         "rpl": {"text": "$0.00", "wert": 0.0}, "upl": {"text": "$0.00", "wert": 0.0}, "balance_relativ": False},
                "positionen": [{"symbol": "NQZ26", "seite": self.richtung, "menge": n, "avg": self.avg, "pl_text": None}] if self.pos else [],
                "positionen_sichtbar": True, "flach": False if self.pos else True, "popups": [],
                "toasts": {"gruppen": [], "meldungen": meld},
                "ticket": {"k3": True, "k4": True, "ordertyp": {"text": "Market"},
                           "contract": {"wert": "NQZ26", "offen": False, "fokus": False, "rect": [1582, 92, 376, 28], "zu": {}},
                           "menge": {"wert": str(n), "rect": [1567, 188, 470, 40], "fokus": False, "zu": {}}, "vorschlaege": [],
                           "kauf": {"text": f"BUY +{n} @ MARKET", "rect": RK, "zu": {"disabled": False, "verdeckt": False}},
                           "verkauf": {"text": f"SELL -{n} @ MARKET", "rect": RV, "zu": {"disabled": False, "verdeckt": False}},
                           "reiter": {"positions": {"rect": RT, "aktiv": self.reiter, "text": "Positions", "zu": {"disabled": False, "verdeckt": False}}},
                           "gitter": {"da": bool(self.reiter), "spalten": ["symbol", "position", "entry price", "risk", "to make", "close"],
                                      "zeilen": [zeile] if (self.pos and self.reiter) else [],
                                      "grund": None if self.reiter else "keine Tabelle mit den Spalten Risk und To Make im Bild"}}}

    def klick(self, r, name, toast_ok=False, pruef=None, doppel=False):
        self.klicks.append(name)
        if name.startswith("ORDER-Knopf"):
            self.lesungen, self.t_klick = 0, int(time.time() * 1000)
        elif name == "Reiter Positions":
            self.reiter = True
        elif name.startswith("Risk-Zelle") or name.startswith("To Make-Zelle"):
            feld = "risk" if name.startswith("Risk") else "to_make"
            if self.trail is not None:
                import order_bot as ob_
                self.rest_bei_klick.append(ob_._tsx_frist(self.trail) - self.trail.sekunden())
            if doppel and self.edit_geht:
                w = self.werte[feld]
                self.edit, self.eingabe, self.markiert = feld, ("" if w is None else str(int(w))), False
        else:
            raise AssertionError("unerwarteter Klick " + name)
        return True

    def taste(self, k, modifiers=0):
        self.tasten.append(("Strg+" if modifiers == 2 else "") + k)
        if k == "a" and modifiers == 2:
            self.markiert = True
        elif k == "Backspace" and self.edit:
            self.eingabe, self.markiert = ("" if self.markiert else self.eingabe[:-1]), False
        elif k == "Escape":
            self.edit, self.eingabe = None, ""
        elif k == "Enter" and self.edit:
            tw = 5.0 * self.menge                              # NQ: ein Tick der ganzen Position in $
            self.werte[self.edit] = round(round(float(self.eingabe) / tw) * tw, 2)
            self.edit, self.eingabe = None, ""

    def tippen(self, t):
        self.tasten.append("tippe " + t)
        if self.edit:
            self.eingabe = (t if self.markiert else self.eingabe + t)
            self.markiert = False

    def lese_js(self, a, timeout=8):
        return None


def lauf(ob, seite, tp=1944, sl=1497, frist=None):
    res = {"ok": False, "code": "", "msg": "", "schritt": "lesen", "etappe": "K3", "gesendet": False, "retry_ok": True, "scharf": False}
    t = ob._StempelSpur()
    seite.trail = t
    if frist:
        t.frist_s = frist
    befehl = {"richtung": seite.richtung, "menge": seite.menge, "wurzel": "NQ", "ext": E, "scharf": True, "plan_id": "p-1"}
    cmd = {"ext_id": E, "symbol": "NQ", "richtung": seite.richtung, "volumen": seite.menge, "tp_usd": tp, "sl_usd": sl, "plan_id": "p-1", "scharf": True}

    def raus(code, msg, schritt, ok=False, **ex):
        res.update(ok=ok, code=code, msg=msg, schritt=schritt, **ex)
        return res
    st0 = seite.stand()
    ok_v, f_v, kn, _mz = ob.tsx_k3_vor_klick(st0, befehl, "NQZ26", E)
    if not ok_v:
        raise AssertionError(f"Vor-Klick-Blick der nachgebauten Seite fällt durch: {f_v}")
    ob._tsx_k4_senden(seite, st0, befehl, "NQZ26", kn, res, t, raus, cmd)
    return res, " > ".join(t)


def kern(warnung):
    """Nachbau der Warnungs-Regeln aus app.py _tsx_brackets_kern / prophos.html tsxWarnungBrackets (nur der Warnungs-Zweig)."""
    w = re.sub(r"^\s*Brackets in TopstepX prüfen:\s*", "", str(warnung or ""), flags=re.I)
    teile = [x.strip() for x in re.split(r";\s*", w) if x.strip()]
    if not teile:
        return None
    risk = any(re.match(r"^Risk\b[^;]*nicht gesetzt", x, re.I) for x in teile)
    tp = any(re.match(r"^To Make\b[^;]*nicht gesetzt", x, re.I) for x in teile)
    if (risk or tp) and all(re.search(r"nicht gesetzt", x, re.I) for x in teile):
        return {"risk": risk, "tp": tp}
    return {"risk": True, "tp": True}


def main():
    import order_bot as ob
    ob._warte = lambda *a, **k: None
    ob._tsx_pause = lambda *a, **k: None
    ob._puls_diagnose_senden = lambda *a, **k: None
    ob._puls_ergebnis_senden = lambda *a, **k: None
    R, N = ob.TSX_K4_BRACKET_RUNDEN, ob.TSX_K4_SL_NACHSETZ_RUNDEN

    # ── tsx_k4_zelle_zu_grund (rein rechnend) ──
    G = ob.tsx_k4_zelle_zu_grund
    ok_rect = [1000, 766, 200, 22]
    check(G({"rect": ok_rect, "zu": {"verdeckt": False}}, GEO) == "", "Grund: klickbare Zelle → leer")
    check(G({"rect": None, "zu": {}}) == "ohne Rechteck" and G({"rect": [1, 2], "zu": {}}) == "ohne Rechteck"
          and G({"rect": ["x", 1, 2, 3]}) == "ohne Rechteck", "Grund: ohne/kaputtes Rechteck")
    check(G({"rect": [1000, 766, 12, 22], "zu": {}}) == "zu schmal (12 px)", "Grund: zu schmal mit Breite")
    check(G({"rect": ok_rect, "zu": {"disabled": True, "verdeckt": True}}) == "gesperrt (disabled)", "Grund: gesperrt geht vor verdeckt")
    g_aus = G({"rect": [1000, 1745, 200, 30], "zu": {"verdeckt": True, "oben": "ausserhalb"}}, {"innerWidth": 1920, "innerHeight": 1750})
    check(g_aus == "Mitte außerhalb des Fensters (Zelle y 1745–1775, x 1000–1200, Fenster 1920×1750)", f"Grund: außerhalb mit Lage + Fenster ({g_aus})")
    g_ob = G({"rect": ok_rect, "zu": {"verdeckt": True, "oben": {"tag": "div", "role": "alert", "text": "Order Filled; Sell 2"}}}, GEO)
    check(g_ob.startswith("verdeckt von div alert 'Order Filled, Sell 2'") and ";" not in g_ob, f"Grund: verdeckt von … ohne Semikolon ({g_ob})")
    check(";" not in G({"rect": ok_rect, "zu": {"verdeckt": True}}, None) and "Fenster ?" in G({"rect": ok_rect, "zu": {"verdeckt": True}}, None),
          "Grund: verdeckt ohne oben/geo wirft nie")

    # ── a) Risk normal setzbar ──
    s = Sitz()
    r, sp = lauf(ob, s)
    check(r["ok"] is True and "warnung" not in r and "brackets_fehlen" not in r and s.werte == {"risk": 1500.0, "to_make": 1940.0}
          and "SL NACHSETZEN" not in sp and "ORDER OHNE SL" not in sp and s.klicks.count("ORDER-Knopf 'SELL -2 @ MARKET'") == 1,
          f"a) Risk setzbar → wie bisher, kein Nachsetzen ({r.get('warnung')}, {s.werte})")

    # ── b) drei Runden lang außerhalb, dann frei → Nachsetzen setzt Risk ──
    s = Sitz(zu_lesungen="runden")
    r, sp = lauf(ob, s)
    check(r["ok"] is True and s.werte["risk"] == 1500.0 and "SL NACHSETZEN: Risk 1497 $ steht nach" in sp and "SL nachsetzen: Versuch" in sp
          and "Mitte außerhalb des Fensters" in sp and "ORDER OHNE SL" not in sp
          and (r.get("brackets_fehlen") or {}).get("risk") is not True,
          f"b) Zelle erst unerreichbar, dann frei → SL nachgesetzt ({r.get('brackets_fehlen')}, {s.werte})")
    check(r.get("brackets_fehlen") == {"risk": False, "tp": True} and "To Make 1944 $ nicht gesetzt" in (r.get("warnung") or "")
          and "Risk 1497 $ nicht gesetzt" not in (r.get("warnung") or ""),
          f"b) To Make wird im Nachsetzen nicht versucht, bleibt Warnung + brackets_fehlen.tp ({r.get('warnung')})")
    check(not any(k.startswith("To Make") for k in s.klicks) and s.klicks.count("ORDER-Knopf 'SELL -2 @ MARKET'") == 1,
          "b) genau ein Order-Klick, kein Close, keine To-Make-Klicks während die Zelle unerreichbar war")

    # ── c) bleibt unerreichbar → ORDER OHNE SL, 🔴-Weg über brackets_fehlen ──
    s = Sitz(zu_lesungen=-1)
    r, sp = lauf(ob, s)
    w = r.get("warnung") or ""
    check(r["ok"] is True and r.get("gesendet") is True and r.get("brackets_fehlen") == {"risk": True, "tp": True}
          and "ORDER OHNE SL: Risk 1497 $" in sp and "Position bleibt offen" in sp,
          f"c) SL nie setzbar → ORDER OHNE SL in der Spur, brackets_fehlen risk+tp ({r.get('brackets_fehlen')})")
    check("Risk 1497 $ nicht gesetzt (Risk-Zelle verdeckt, gesperrt oder ohne Rechteck — Mitte außerhalb des Fensters (Zelle y 766–788" in w
          and kern(w) == {"risk": True, "tp": True}, f"c) Warnung: alter Anfang + EINE Ursache mit Wert, Parser liest risk+tp ({w[:160]})")
    check(sp.count("SL nachsetzen: Versuch") == N and sp.count("Risk-Zelle verdeckt, gesperrt oder ohne Rechteck — Mitte außerhalb") - 1 == R + N
          and sp.count("To Make-Zelle verdeckt, gesperrt oder ohne Rechteck — Mitte außerhalb") == R and sp.count("— kein Klick") == 2 * R + N,
          f"c) {R} Runden für beide + {N} Nachsetz-Runden nur für Risk, jede mit Ursache in der Spur")
    check(s.klicks == ["ORDER-Knopf 'SELL -2 @ MARKET'", "Reiter Positions"] and not any("close" in k.lower() for k in s.klicks),
          f"c) unerreichbare Zelle: kein Klick darauf, nie ein Close, genau ein Order-Klick ({s.klicks})")

    # ── e) Risk in Runde 1 gesetzt, nur To Make unerreichbar → kein Nachsetzen (gilt nur dem SL) ──
    s = Sitz(zu_lesungen=-1, zu_felder=("to_make",))
    r, sp = lauf(ob, s)
    check(r["ok"] is True and s.werte["risk"] == 1500.0 and "SL NACHSETZEN" not in sp and "SL nachsetzen" not in sp
          and r.get("brackets_fehlen") == {"risk": False, "tp": True} and sp.count("To Make-Zelle verdeckt") == R,
          f"e) Risk steht, To Make fehlt → {R} Runden wie bisher, kein Nachsetzen ({r.get('brackets_fehlen')})")

    # ── f) knappe Frist: jedes Warten kostet Zeit — nie ein Zellen-Klick mit < 30 s Rest, Ergebnis kommt (kein Hänger) ──
    alt_warte = ob._warte
    lauf_t = {}

    def warte_zeit(a, b):
        t_ = lauf_t.get("t")
        if t_ is not None:
            t_._t0 -= (a + b)                            # die Spur altert um die längste Streuung
    ob._warte = warte_zeit
    s = Sitz(edit_geht=False)
    orig_spur = ob._StempelSpur

    class Spur(orig_spur):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            lauf_t["t"] = self
    ob._StempelSpur = Spur
    try:
        r, sp = lauf(ob, s, frist=80.0)
    finally:
        ob._StempelSpur, ob._warte = orig_spur, alt_warte
    m = re.search(r"ORDER OHNE SL: Risk 1497 \$ nach \d+ Runden \+ (\d+) Nachsetz-Versuchen", sp)
    check(r["ok"] is True and r.get("brackets_fehlen", {}).get("risk") is True and m and int(m.group(1)) < N
          and s.rest_bei_klick and min(s.rest_bei_klick) >= 29.0,
          f"f) knappe Frist: Nachsetzen endet am Zeitlimit, kein Klick unter 30 s Rest, Ergebnis ok ({m.group(1) if m else '-'} Versuche, "
          f"Rest min {min(s.rest_bei_klick) if s.rest_bei_klick else '-'})")

    # ── d) kein Plan-SL → keine Nachsetz-Runden (wie heute) ──
    s = Sitz(zu_lesungen=-1)
    r, sp = lauf(ob, s, sl=None)
    check(r["ok"] is True and "SL NACHSETZEN" not in sp and "SL nachsetzen" not in sp and "ORDER OHNE SL" not in sp
          and r.get("brackets_fehlen") == {"risk": False, "tp": True} and sp.count("To Make-Zelle verdeckt") == R,
          f"d) ohne Plan-SL: nur die {R} Runden für To Make, kein Nachsetzen ({r.get('brackets_fehlen')})")
    s = Sitz()
    r, sp = lauf(ob, s, sl=None)
    check(r["ok"] is True and "warnung" not in r and s.werte == {"risk": None, "to_make": 1940.0}, "d) ohne Plan-SL, alles frei → nur To Make, wie heute")

    # ── tvv2: SL im Ticket VOR der Order — ohne bewiesenen SL wird nicht gesendet ──
    RL = ob.cdp_ticket_ruecklesung
    plan = {"richtung": "buy", "menge": 2, "tp": 1944.0, "sl": 1497.0, "spiel_usd": ob.cdp_feld_spiel("NQ", 2)}

    def tk(sl_an=True, sl_wert="1497", tp_an=True, einh="$"):
        return {"ticket": {"typen": [{"id": "market", "aria-selected": "true"}], "seite": "buy", "menge": {"wert": "2"},
                           "tp": {"wert": "1944", "an": tp_an, "einheit": einh, "beschriftung": {"text": "Take profit, $"}},
                           "sl": {"wert": sl_wert, "an": sl_an, "einheit": einh, "beschriftung": {"text": "Stop loss, $"}}},
                "kauf_knopf": {"seite": "buy"}}
    ok0, z0, f0 = RL(tk(), plan)
    check(ok0 and f0 == [], f"tvv2: SL AN + Wert → Rücklesung ok ({z0}, {f0})")
    _o, _z, f1 = RL(tk(sl_an=False), plan)
    check("SL-Schalter nicht AN" in f1, f"tvv2: SL-Schalter AUS bei Plan-SL → Rücklesung scheitert, nichts gesendet ({f1})")
    _o, _z, f2 = RL(tk(sl_an=None), plan)
    check("SL-Schalter nicht AN" in f2, f"tvv2: SL-Schalter unlesbar → scheitert ({f2})")
    _o, _z, f3 = RL(tk(sl_wert="900"), plan)
    check(any(x.startswith("SL '") for x in f3), f"tvv2: falscher SL-Wert → scheitert ({f3})")
    _o, _z, f4 = RL(tk(sl_wert=""), plan)
    check(any(x.startswith("SL '") for x in f4), f"tvv2: leeres SL-Feld → scheitert ({f4})")
    plan_ohne = dict(plan, sl=None)
    _o, _z, f5 = RL(tk(sl_an=False), plan_ohne)
    check(not any(x.startswith("SL") for x in f5), f"tvv2: kein Plan-SL, Schalter AUS → wie heute ok ({f5})")
    _o, _z, f6 = RL(tk(sl_an=True), plan_ohne)
    check("SL-Schalter AN, der Plan hat kein SL" in f6, f"tvv2: kein Plan-SL, Schalter AN → scheitert wie heute ({f6})")
    q = inspect.getsource(ob.modus_tvkette_cdp)
    i_rl = q.find("rl_ok, rl_text, rl_fehler = cdp_ticket_ruecklesung(st, plan)")
    i_raus = q.find('return raus("ruecklesung"')
    i_klick = q.find("ORDER-Knopf")
    i_klick = i_klick if i_klick >= 0 else q.find("s.klick(", i_rl)
    check(0 <= i_rl < i_raus and (i_klick < 0 or i_raus < q.find("s.klick(", i_raus)),
          "tvv2: Rücklesung (mit SL) + „nichts gesendet\" steht im Code vor dem Senden-Klick")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER")
        sys.exit(1)
    print("ALLE OK")


if __name__ == "__main__":
    main()
