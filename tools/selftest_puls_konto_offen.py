#!/usr/bin/env python3
"""Selbsttest KONTO OFFEN (mt5-copier/order_bot.py, 08.10.2026, Finn ~22:15 Dubai: eine offene Position am Konto blockiert jeden
Puls-Start, auch eine gewollte Hand-Position — „nichts gegen Hedge intern, sonst passt es"). Alles mit Attrappen: kein Chrome, kein
Netz, keine Order.

Aufruf:  python3 tools/selftest_puls_konto_offen.py
Prueft cdp_konto_offen (Positions-Bereich nur ueber den aktiven Reiter „positions" sicher erkannt; Orders-Reiter mit gefuellten
Orders und „Avg Fill Price"-Kopf sperrt nie; unklar = keine Sperre; Gegenseite sperrt; NQ sperrt MNQ; ES nie), den Orbit-Startweg
modus_tvkette_cdp (konto_offen ohne Senden-Klick, flach/unklar bis zum Klick, Reiter wird selbst gesichert, Probelauf), den
Neustart-Riegel und den Topstep-Weg (tsx_offene_positionen, Reiter „Positions" vor dem Klick, konto_offen statt vorpruefung)."""
import contextlib
import copy
import inspect
import io
import json
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

OK = True
EXT = "TDFYSL000000000000001"                 # Platzhalter (Repo öffentlich gewesen — nie echte Kontonummern)
E_TSX = "EXPRESS-V2-000000-00000000"


def check(bed, text):
    global OK
    print(("✓ " if bed else "✗ ") + text)
    OK = OK and bool(bed)


# ── Zeilen in der Form der echten puls_augen-Rohdaten (art stand, 08.10.2026; IDs ersetzt) ─────────────────────────────────────────
def pos_zeile(symbol="MNQZ6", side="Long", qty=4, sichtbar=True, avg="31,250.50"):
    seite = "buy" if side == "Long" else "sell" if side == "Short" else None
    return {"symbol": symbol, "seite": seite, "menge": qty, "avg": 31250.5, "pl_text": "−14.00USD", "sichtbar": sichtbar,
            "zeile_rect": [56, 772, 1199, 48] if sichtbar else None, "veraltet_moeglich": not sichtbar,
            "close": {"dn": "close-settings-cell-button", "aria": "Close", "rect": [1213, 785, 22, 22]},
            "spalten": {"": "", "Qty": str(qty), "Side": side, "Profit": "−14.00USD", "Symbol": symbol, "Position ID": "1000001",
                        "Update Time": "", "Avg Fill Price": avg}}


def order_zeile(symbol="MNQZ6", side="Buy", typ="Market", status="filled", sichtbar=True):
    return {"typ": typ, "menge": 4, "preis": None, "seite": side.lower(), "status": status, "symbol": symbol, "sichtbar": sichtbar,
            "zeile_rect": [56, 772, 1199, 48] if sichtbar else None, "veraltet_moeglich": not sichtbar, "cancel": None,
            "spalten": {"Qty": "4", "Side": side, "Type": typ, "Status": status, "Symbol": symbol, "Order ID": "2000001",
                        "Filled Qty": "4", "Avg Fill Price": "31,250.50", "Limit Price": "", "Stop Price": ""}}


def stand(reiter="positions", pos=(), orders=(), ps=True, summary=True):
    return {"v": "0.8.1", "konto": {"aktiv": EXT + "USD", "positionen_sichtbar": ps, "orders_sichtbar": False},
            "positionen": list(pos), "orders": list(orders), "popups": [], "toasts": {"gruppen": [], "meldungen": []},
            "konto_summary": ({"reiter": reiter, "texte": {"Equity": "153,286.65", "Profit": "+4.00", "Account Balance": "153,282.65"}}
                              if summary else None)}


def leiste(aktiv="positions"):
    return [{"id": i, "text": t, "role": "tab", "sel": "true" if i == aktiv else "false", "rect": [x, 554, 70, 28]}
            for i, t, x in (("positions", "Positions", 60), ("orders", "Orders", 140), ("summary", "Account Summary", 220))]


def test_urteil():
    K = ob.cdp_konto_offen
    # 1) Positionsliste mit NQ-Familie-Position → konto_offen
    u = K(stand(pos=[pos_zeile()]), leiste(), "MNQ")
    check(u["urteil"] == "offen" and u["text"] == "Konto hat schon eine offene Position (BUY 4 MNQ) — nichts gesendet"
          and u["offen"][0]["seite"] == "buy" and "augen.js + Leiste" in u["grund"], f"Positions-Reiter + MNQ-Zeile → offen ({u['text']})")
    # 2) Leere Positionsliste → normal
    u = K(stand(pos=[]), leiste(), "MNQ")
    check(u["urteil"] == "flach" and not u["text"] and u["spur"].startswith("Positionen vor dem Senden: flach"), f"leere Positionsliste → flach ({u['spur']})")
    # 3) Orders-Reiter mit gefüllten Orders (Kopf „Avg Fill Price" → positionen_sichtbar true) → KEINE Sperre
    st_o = stand(reiter="orders", pos=[pos_zeile(sichtbar=False)], orders=[order_zeile(), order_zeile(typ="Take Profit", status="filled")], ps=True)
    u = K(st_o, leiste("orders"), "MNQ")
    check(u["urteil"] == "unklar" and "orders" in u["grund"] and u["spur"].startswith("positionen_unklar:"), f"Orders-Reiter + gefüllte Orders → unklar, keine Sperre ({u['spur']})")
    st_o2 = stand(reiter="orders", pos=[dict(pos_zeile(), spalten={"Symbol": "MNQZ6", "Avg Fill Price": "31,250.50", "Qty": "4"})], ps=True)
    check(K(st_o2, leiste("orders"), "MNQ")["urteil"] == "unklar", "Orders-Reiter, sogar mit einer als Position gelesenen Zeile → nie gesperrt")
    check(K(stand(reiter="orders", ps=True), [], "MNQ")["urteil"] == "unklar"
          and K(dict(stand(pos=[pos_zeile()], ps=True), konto_summary=None), leiste("orders"), "MNQ")["urteil"] == "unklar",
          "Orders-Reiter nur aus augen.js oder nur aus der Leiste → unklar")
    # 4) Unklarer Bereich → keine Sperre + Diagnose
    u = K(dict(stand(pos=[pos_zeile()]), konto_summary=None), [], "MNQ")
    check(u["urteil"] == "unklar" and "nicht lesbar" in u["grund"] and "1 sichtbare MNQ/NQ-Zeile(n)" in u["spur"],
          f"Reiter weder aus augen.js noch aus der Leiste → unklar, Zeile nur in der Diagnose ({u['spur']})")
    u = K(stand(reiter="summary", ps=False), leiste("summary"), "MNQ")
    check(u["urteil"] == "unklar" and "summary" in u["grund"], "Reiter Account Summary (wie pc-xxxxxx in puls_augen) → unklar")
    u = K(stand(pos=[pos_zeile()], ps=False), leiste(), "MNQ")
    check(u["urteil"] == "unklar" and "keine Positions-Tabelle" in u["grund"], "Reiter Positions, aber Tabelle nicht sichtbar → unklar")
    u = K(stand(pos=[pos_zeile()]), leiste("orders"), "MNQ")
    check(u["urteil"] == "unklar" and "Reiterleiste" in u["grund"], "Widerspruch augen.js positions / Leiste orders → unklar")
    u = K(stand(pos=[dict(pos_zeile(), menge=None)]), leiste(), "MNQ")
    check(u["urteil"] == "unklar" and "ohne lesbare Menge" in u["grund"], "Zeile ohne lesbare Menge → unklar, keine Sperre")
    # 5) Gegenseite → Sperre (Plan buy, Short NQ — NQ sperrt auch einen MNQ-Plan)
    u = K(stand(pos=[pos_zeile("NQZ6", "Short", 2)]), leiste(), "MNQ")
    check(u["urteil"] == "offen" and u["text"] == "Konto hat schon eine offene Position (SELL 2 NQ) — nichts gesendet", f"Gegenseite + NQ bei MNQ-Plan → offen ({u['text']})")
    check(K(stand(pos=[pos_zeile("MNQZ6", "Long", 1)]), leiste(), "NQ")["urteil"] == "offen", "MNQ-Hand-Position sperrt einen NQ-Plan")
    # 6) Anderes Symbol → keine Sperre
    u = K(stand(pos=[pos_zeile("ESZ6", "Long", 1), pos_zeile("MESZ6", "Short", 3)]), leiste(), "MNQ")
    check(u["urteil"] == "flach", f"ES/MES offen, Plan MNQ → keine Sperre ({u['spur']})")
    # 7) Grenzfälle der Zeilen
    check(K(stand(pos=[pos_zeile(sichtbar=False)]), leiste(), "MNQ")["urteil"] == "flach", "unsichtbare (womöglich veraltete) Zeile zählt nie")
    check(K(stand(pos=[dict(pos_zeile(), spalten=dict(pos_zeile()["spalten"], **{"Order ID": "2000001", "Status": "filled"}))]), leiste(), "MNQ")["urteil"] == "flach",
          "Zeile mit Order-ID/Status ist eine Order, nie eine Position")
    check(K(stand(pos=[dict(pos_zeile(), menge=0)]), leiste(), "MNQ")["urteil"] == "flach", "Menge 0 = flach")
    check(K(stand(pos=[dict(pos_zeile(), spalten=None)]), [], "MNQ")["urteil"] == "offen", "spalten vom Größendeckel entfernt + nur augen.js-Reiter → trotzdem offen")
    check(K(stand(pos=[pos_zeile()], summary=False), leiste(), "MNQ")["urteil"] == "offen", "konto_summary fehlt, Leiste beweist Positions → offen")
    u = K(stand(pos=[pos_zeile(), pos_zeile("NQZ6", "Short", 1)]), leiste(), "MNQ")
    check(u["text"] == "Konto hat schon eine offene Position (BUY 4 MNQ, SELL 1 NQ) — nichts gesendet", f"mehrere Zeilen im Text ({u['text']})")
    check(K(None, None, "MNQ")["urteil"] == "unklar" and K(stand(), leiste(), "")["urteil"] == "flach", "kaputte Eingaben → nie offen")
    check(ob.puls_wurzel_familie("MNQ") == ob.puls_wurzel_familie("NQ") == "NQ" and ob.puls_wurzel_familie("ES") != "NQ", "Familie MNQ = NQ, ES eigene")


# ── Orbit-Startweg mit Attrappe (modus_tvkette_cdp) ─────────────────────────────────────────────────────────────────────────────────
class _Seite:
    """Puls-Chrome-Attrappe: Reiter Positions/Orders/Summary, Positions- und Order-Zeilen; klick zeichnet auf, der Senden-Knopf wird
    NIE gedrückt (Rückgabe False = „Maus nicht bewiesen") — kommt der Lauf bis dorthin, steht das als Klick in der Liste."""

    def __init__(self, aktiv="positions", pos=(), orders=(), reiter_klick_wirkt=True):
        self.aktiv, self.pos, self.orders, self.wirkt = aktiv, list(pos), list(orders), reiter_klick_wirkt
        self.klicks = []

    def stand(self, opts=None):
        pos = [dict(p, sichtbar=p["sichtbar"] and self.aktiv == "positions") for p in self.pos]
        ords = [dict(o, sichtbar=self.aktiv == "orders") for o in self.orders]
        st = stand(reiter=self.aktiv, pos=pos, orders=ords, ps=self.aktiv in ("positions", "orders"))
        st["kauf_knopf"] = {"text": "Buy 2 MNQZ6 MARKET", "symbol": "MNQZ6", "rect": [900, 600, 220, 32], "disabled": False}
        st["ticket"] = {"senden": st["kauf_knopf"]}
        return copy.deepcopy(st)

    def lese_js(self, js, timeout=8):
        return leiste(self.aktiv) if js is ob.CDP_REITER_JS else None

    def klick(self, rect, name, toast_ok=False, **kw):
        self.klicks.append(name)
        if name.startswith("Reiter positions") and self.wirkt:
            self.aktiv = "positions"
        return not name.startswith("SENDEN")

    def werbung_weg(self, zwang=False):
        return False

    def hin(self, *a, **k):
        return True

    def zu(self):
        pass


def lauf_tv(seite, scharf=True, richtung="buy"):
    diag = []
    cmd = {"ext_id": EXT, "symbol": "MNQZ6", "richtung": richtung, "volumen": 2, "tp_usd": 30, "sl_usd": None, "plan_id": "p-1"}
    if scharf:
        cmd["scharf"] = True
    namen = ("_cdp_sitzung_holen", "_cdp_konto_mit_login", "_cdp_today_aus_reiter", "_cdp_ticket_fuellen", "cdp_ticket_ruecklesung",
             "_handlauf_aktiv", "_puls_diagnose_senden", "_puls_ergebnis_senden", "_cdp_panel_zurueck", "_warte")
    alt = {n: getattr(ob, n) for n in namen}
    try:
        ob._cdp_sitzung_holen = lambda c, t: seite
        ob._cdp_konto_mit_login = lambda sitz, ext, opts, c, t, r: (True, "", "", sitz[0].stand(opts), {"konto_aktiv": ext})
        ob._cdp_today_aus_reiter = lambda s, opts, t: (None, None, None, None)
        ob._cdp_ticket_fuellen = lambda s, st, plan, sym, opts, t: (True, "", "", "ticket", s.stand(opts), s.stand(opts)["kauf_knopf"])
        ob.cdp_ticket_ruecklesung = lambda st, plan: (True, "passt", [])
        ob._handlauf_aktiv = lambda: False
        ob._puls_diagnose_senden = lambda spur=None, schritt="": diag.append((schritt, " > ".join(list(spur or []))))
        ob._puls_ergebnis_senden = lambda *a, **k: None
        ob._cdp_panel_zurueck = lambda s, t: None
        ob._warte = lambda *a, **k: None
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            ob.modus_tvkette_cdp(cmd)
        import time as _t
        _t.sleep(0.05)                                 # der cdp-senden-Thread schreibt seine Diagnose
        return json.loads(out.getvalue().strip().splitlines()[-1]), diag
    finally:
        for n, v in alt.items():
            setattr(ob, n, v)


def test_orbit_weg():
    # A) offene Hand-Position → nichts gesendet, kein Senden-Klick, start_fehler-tauglich, Diagnose
    s = _Seite(pos=[pos_zeile("MNQZ6", "Long", 2)])
    r, diag = lauf_tv(s)
    check(r["code"] == "konto_offen" and r["schritt"] == "konto_offen" and r["gesendet"] is False and r["retry_ok"] is True and r["ok"] is False
          and r["msg"] == "Konto hat schon eine offene Position (BUY 2 MNQ) — nichts gesendet" and not any(k.startswith("SENDEN") for k in s.klicks),
          f"offene Position → konto_offen, kein Senden-Klick ({r['msg']}; Klicks {s.klicks})")
    check(any(d[0] == "konto_offen" and "Positionen vor dem Senden: OFFEN" in d[1] for d in diag) and r["positionen_pruefung"]["urteil"] == "offen"
          and r["positionen_offen"][0]["menge"] == 2.0, "Spur geht als puls_diagnose (schritt konto_offen) raus, Befund im Ergebnis")
    # B) flach → bis zum Senden-Klick (Attrappe drückt nie)
    s = _Seite()
    r, diag = lauf_tv(s)
    check(r["code"] == "knopf" and "SENDEN-Knopf" in s.klicks and r["positionen_pruefung"]["urteil"] == "flach"
          and any(d[0] == "cdp-senden" for d in diag), f"leere Positionsliste → normal bis zum Senden-Klick ({s.klicks})")
    # C) Orders-Reiter bleibt aktiv (Reiter-Klick ohne Wirkung) + gefüllte Orders → KEINE Sperre, positionen_unklar in der Diagnose
    s = _Seite(aktiv="orders", pos=[pos_zeile()], orders=[order_zeile()], reiter_klick_wirkt=False)
    r, diag = lauf_tv(s)
    check(r["code"] == "knopf" and "SENDEN-Knopf" in s.klicks and r["positionen_pruefung"]["urteil"] == "unklar"
          and any(d[0] == "cdp-senden" and "positionen_unklar:" in d[1] for d in diag),
          "Orders-Reiter aktiv → keine Sperre, Start wie bisher, „positionen_unklar“ in der cdp-senden-Diagnose")
    # D) Orders-Reiter aktiv, Puls holt „Positions" selbst nach vorn → die versteckte Hand-Position wird sichtbar → gesperrt
    s = _Seite(aktiv="orders", pos=[pos_zeile("NQZ6", "Short", 1)], orders=[order_zeile()])
    r, _ = lauf_tv(s)
    check(r["code"] == "konto_offen" and any(k.startswith("Reiter positions") for k in s.klicks) and "SENDEN-Knopf" not in s.klicks
          and "SELL 1 NQ" in r["msg"], f"Reiter Positions selbst gesichert → Gegen-/NQ-Position erkannt, nichts gesendet ({s.klicks})")
    # E) anderes Symbol → normal
    s = _Seite(pos=[pos_zeile("ESZ6", "Long", 1)])
    r, _ = lauf_tv(s)
    check(r["code"] == "knopf" and "SENDEN-Knopf" in s.klicks, "ES-Position, MNQ-Plan → keine Sperre")
    # F) Probelauf zeigt dasselbe Urteil, ohne je zu senden
    s = _Seite(pos=[pos_zeile("MNQZ6", "Short", 3)])
    r, _ = lauf_tv(s, scharf=False)
    check(r["code"] == "konto_offen" and r["msg"].endswith("(Probelauf)") and "SENDEN-Knopf" not in s.klicks, f"Probelauf: konto_offen ({r['msg']})")
    s = _Seite()
    r, _ = lauf_tv(s, scharf=False)
    check(r["ok"] is True and r["schritt"] == "probe" and "SENDEN-Knopf" not in s.klicks, "Probelauf flach: Probe wie bisher")
    # G) Neustart-Riegel: eine offene Position ist kein Chrome-Problem
    art, grund, _ = ob.neustart_entscheid({"ok": False, "code": "konto_offen", "gesendet": False, "retry_ok": True}, "tvv2", 30.0)
    art2, _, _ = ob.neustart_entscheid({"ok": False, "code": "konto_offen", "gesendet": False, "retry_ok": True}, "tsv2", 30.0)
    check(art == art2 == "nein" and "konto_offen" in ob.PULS_NEUSTART_NIE, f"konto_offen → nie Chrome-Neustart/zweiter Versuch ({grund})")
    # H) Quelltext-Riegel: Prüfung NACH dem Konto-Beweis und VOR dem einen Senden-Klick, nur im Startweg
    q = inspect.getsource(ob.modus_tvkette_cdp)
    check(q.index("cdp_konto_passt(") < q.index("_cdp_konto_offen_blick(s, st, root") < q.index('s.klick(cdp_rect(kk), "SENDEN-Knopf")')
          and q.index("_cdp_positions_reiter_sichern(s, trail)") < q.index("# ═══ K4")
          and q.count("_cdp_konto_offen_blick(") == 2, "Prüfung nach Konto-Beweis, vor dem Senden-Klick; Reiter vor dem frischen Blick gesichert")
    rest = "".join(inspect.getsource(f) for f in (ob.modus_tvlesen_cdp, ob._neustart_lesung_tvv2, ob._cdp_endpruefung))
    check("cdp_konto_offen" not in rest and "konto_offen" not in inspect.getsource(ob.modus_tvclose)
          if hasattr(ob, "modus_tvclose") else "cdp_konto_offen" not in rest, "Endlesung/Nachlesung/Endprüfung/Schließen bleiben ungesperrt")


# ── Topstep-Weg (tsv2) ──────────────────────────────────────────────────────────────────────────────────────────────────────────────
RK, RV, RT = [1640, 416, 120, 26], [1766, 416, 120, 26], [156, 746, 69, 28]


class _TS:
    """TopstepX-Attrappe: Order-Karte für MNQZ26 (flach oder nicht), Reiter „Positions" unten, Positions-Tabelle mit Zeilen."""

    def __init__(self, reiter=False, reiter_da=True, zeilen=(), k1=(), flach=True):
        self.reiter, self.reiter_da, self.zeilen, self.k1, self.flach = reiter, reiter_da, list(zeilen), list(k1), flach
        self.klicks = []

    def stand(self, opts=None):
        offen = self.reiter and self.reiter_da
        return copy.deepcopy({
            "v": "tsx-0.6.1", "titel": "MNQZ26 $31,000.00", "popups": [], "toasts": {"gruppen": [], "meldungen": []},
            "konto": {"aktiv": f"$150K Express|{E_TSX}", "kontonr": E_TSX, "abgekuerzt": False, "liste_offen": False, "liste": []},
            "kopf": {"balance": {"text": "$0.00", "wert": 0.0}}, "positionen": self.k1, "positionen_sichtbar": True, "flach": self.flach,
            "ticket": {"k3": True, "k4": True, "ordertyp": {"text": "Market"}, "contract": {"wert": "MNQZ26", "offen": False},
                       "menge": {"wert": "2"}, "kauf": {"text": "BUY +2 @ MARKET", "rect": RK, "zu": {"disabled": False, "verdeckt": False}},
                       "verkauf": {"text": "SELL -2 @ MARKET", "rect": RV, "zu": {"disabled": False, "verdeckt": False}},
                       "reiter": ({"positions": {"rect": RT, "aktiv": self.reiter, "text": "Positions", "zu": {"disabled": False, "verdeckt": False}}}
                                  if self.reiter_da else {}),
                       "gitter": {"da": offen, "zeilen": self.zeilen if offen else [], "grund": None if offen else "keine Tabelle"}}})

    def klick(self, r, name, toast_ok=False, pruef=None, doppel=False):
        self.klicks.append(name)
        if name == "Reiter Positions":
            self.reiter = True
        return True


def lauf_tsx(seite, scharf=True):
    gesendet = []
    res = {"ok": False, "code": "", "msg": "", "schritt": "lesen", "gesendet": False, "retry_ok": True, "balance": 0.0}
    t = ob._StempelSpur()
    befehl = {"richtung": "buy", "menge": 2, "wurzel": "MNQ", "ext": E_TSX, "scharf": scharf, "plan_id": "p-1"}

    def raus(code, msg, schritt, ok=False, **ex):
        res.update(ok=ok, code=code, msg=msg, schritt=schritt, **ex)
        return res
    alt = {n: getattr(ob, n) for n in ("_tsx_k3_ticket", "_tsx_k4_senden", "_tsx_pause", "_warte", "_puls_diagnose_senden")}
    try:
        ob._tsx_k3_ticket = lambda s_, st_, b_, t_: (True, "", "", st_, "MNQZ26")
        ob._tsx_k4_senden = lambda s_, st_, b_, z_, kn_, r_, t_, raus_, c_: (gesendet.append(st_), raus_("", "K4-Attrappe", "fertig", ok=True))[1]
        ob._tsx_pause = lambda: None
        ob._warte = lambda *a, **k: None
        ob._puls_diagnose_senden = lambda *a, **k: None
        ob._tsx_k3_probe(seite, seite.stand(), befehl, res, t, raus, {"plan_id": "p-1"})
        return res, gesendet, list(t)
    finally:
        for n, v in alt.items():
            setattr(ob, n, v)


def test_topstep():
    O = ob.tsx_offene_positionen
    st = {"positionen": [{"symbol": "MNQZ26", "seite": "sell", "menge": 6, "avg": 1.0}],
          "ticket": {"gitter": {"da": True, "zeilen": [{"symbol": "MNQ", "menge": -6, "seite": "sell"}, {"symbol": "NQ", "menge": 1, "seite": "buy"},
                                                     {"symbol": "ES", "menge": 0, "seite": None}]}}}
    o = O(st)
    check([(x["wurzel"], x["seite"], x["menge"]) for x in o] == [("MNQ", "sell", 6.0), ("NQ", "buy", 1.0)]
          and ob.puls_konto_offen_text(o) == "Konto hat schon eine offene Position (SELL 6 MNQ, BUY 1 NQ) — nichts gesendet",
          f"tsx_offene_positionen: K1 + Tabelle entdoppelt, 0-Zeile keine Position ({ob.puls_konto_offen_text(o)})")
    check(O({"ticket": {"gitter": {"da": False, "zeilen": [{"symbol": "NQ", "menge": 1}]}}}) == [] and O(None) == [], "Tabelle nicht im Bild → keine Zeilen daraus")
    # A) Reiter zu, NQ-Hand-Position in anderem Contract (Order-Karte MNQ flach) → nach dem Reiter-Klick gesehen → konto_offen
    s = _TS(zeilen=[{"symbol": "NQ", "menge": 1, "seite": "buy"}])
    r, g, t = lauf_tsx(s)
    check(r["code"] == "konto_offen" and r["msg"] == "Konto hat schon eine offene Position (BUY 1 NQ) — nichts gesendet" and not g
          and s.klicks == ["Reiter Positions"] and r["gesendet"] is False and r["retry_ok"] is True,
          f"Topstep: Reiter Positions vor dem Klick, Position im anderen Contract → konto_offen, kein Order-Klick ({r['msg']}; {s.klicks})")
    # B) Reiter zu, flach → Reiter geöffnet, K4 mit dem frischen Blick
    s = _TS()
    r, g, t = lauf_tsx(s)
    check(r["ok"] and len(g) == 1 and g[0]["ticket"]["gitter"]["da"] is True and s.klicks == ["Reiter Positions"],
          "Topstep flach: Reiter geöffnet, K4 bekommt den frischen Blick mit Positions-Tabelle")
    # C) Reiter fehlt → positionen_unklar, wie bisher weiter (Order-Karte flach bewiesen)
    s = _TS(reiter_da=False)
    r, g, t = lauf_tsx(s)
    check(r["ok"] and len(g) == 1 and not s.klicks and any("positionen_unklar:" in x for x in t), "Topstep: Reiter fehlt → keine Sperre, Diagnose")
    # D) Reiter schon offen + flach → kein Klick
    s = _TS(reiter=True)
    r, g, t = lauf_tsx(s)
    check(r["ok"] and len(g) == 1 and not s.klicks, "Topstep: Tabelle schon im Bild → kein Reiter-Klick")
    # E) Position schon im ersten Blick (Order-Karte/Tabelle) → konto_offen statt vorpruefung, kein Klick
    s = _TS(reiter=True, zeilen=[{"symbol": "MNQ", "menge": -2, "seite": "sell"}], k1=[{"symbol": "MNQZ26", "seite": "sell", "menge": 2}], flach=False)
    r, g, t = lauf_tsx(s)
    check(r["code"] == "konto_offen" and "SELL 2 MNQ" in r["msg"] and not g and not s.klicks, f"Topstep: offene Position im ersten Blick → konto_offen ({r['msg']})")
    # F) Probe (scharf false) → kein Reiter-Klick, Probe wie bisher
    s = _TS()
    r, g, t = lauf_tsx(s, scharf=False)
    check(r["ok"] and r["schritt"] == "probe" and not s.klicks and not g, "Topstep-Probe: kein Reiter-Klick, kein K4")
    q = inspect.getsource(ob.modus_tsxlesen_cdp)
    check('raus("konto_offen", puls_konto_offen_text(offen), "konto_offen"' in q and "tabelle_unklar\", f\"Konto {ext} hat eine offene" not in q,
          "Topstep K1: offene Position endet mit konto_offen (vorher tabelle_unklar), Ticket unberührt")


def main():
    test_urteil()
    test_orbit_weg()
    test_topstep()
    print("\nALLES OK" if OK else "\nFEHLER")
    return 0 if OK else 1


if __name__ == "__main__":
    sys.exit(main())
