#!/usr/bin/env python3
"""Selbsttest MT5 „ORDER ÄNDERN" TRIFFT (Finn über Master 21.10.2026: „ob der Bot wirklich immer dieses Order bearbeiten trifft, da gab es
am Anfang Probleme" — Polar 21.10.: 6/7 bestätigt, Lauf 7f6adf45 04:59 „SL/TP gesetzt … nicht bestätigt"). Die ECHTEN Funktionen aus
mt5-copier/order_bot.py laufen gegen nachgebaute UIA-Elemente (Fenstertexte wie in den Spuren / selftest.py), Maus, Uhr und pywinauto
sind ersetzt — ohne Windows, ohne Netz.
 a) Dialog erkennen: Ändern-Dialog DE/EN (langer Knopf „#Ticket … Ändern" / „Modify #Ticket …"), F9-Dialog nie; Reiter „Position
    ändern" ist nie der Bestätigen-Knopf; Dialog fremder Position wird verworfen; Kontextmenü „Ändern oder Löschen"/„Modify or
    Delete" (ausgegraut / fehlt); Zeilen-Scan Rechtsklick → Doppelklick, richtige Ticket-Zeile bei mehreren Positionen.
 b) Preisfelder: Feld füllt „0.00" nach → über die Auswahl tippen; Komma-Anzeige; digits 1/2/3; Feld nimmt nicht → nie bestätigen.
 c) Rücklesen sltp_bestaetigt mit Toleranz; Fall 7f6adf45 nachgestellt (API zeigt weiter die Notfall-Level) → grobe Level bleiben, Grund.
 d) Wiederholung: höchstens NACHZIEHEN_VERSUCHE mit gewürfelter Pause, dann aufgeben; fehlt ein Level → ok False (nie still ohne SL/TP).
 e) Nur finale Trades: pass → nur TP, blow → nur SL, beide, null → kein Ändern-Klick.
Aufruf: python3 tools/selftest_mt5_aendern.py"""
import os
import re
import sys
import types

HIER = os.path.dirname(os.path.abspath(__file__))
BOT = os.path.join(os.path.dirname(HIER), "mt5-copier", "order_bot.py")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fn(src, name):
    i = src.index(f"\ndef {name}(") + 1
    return src[i:src.find("\n\n\n", i)]


class Uhr:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += max(0.0, float(s or 0))


class R:
    def __init__(self, l, t, r, b):
        self.left, self.top, self.right, self.bottom = l, t, r, b

    def mid_point(self):
        return types.SimpleNamespace(x=(self.left + self.right) // 2, y=(self.top + self.bottom) // 2)


class El:
    """Nachgebautes UIA-Element: Text, Typ, Kinder, Rechteck, aktiv."""
    def __init__(self, text="", ct=None, kinder=(), rect=(0, 0, 10, 10), enabled=True, cls="", on_invoke=None):
        self.text, self.ct, self.kinder, self.rect, self.enabled = text, ct, list(kinder), rect, enabled
        self.element_info = types.SimpleNamespace(class_name=cls, control_type=ct, process_id=1)
        self.on_invoke, self.tasten, self.sichtbar = on_invoke, [], True

    def window_text(self):
        return self.text

    def descendants(self, control_type=None):
        out = []
        for k in self.kinder:
            if control_type is None or k.ct == control_type:
                out.append(k)
            out.extend(k.descendants(control_type))
        return out

    def rectangle(self):
        return R(*self.rect)

    def is_enabled(self):
        return self.enabled

    def is_visible(self):
        return self.sichtbar

    def invoke(self):
        if self.on_invoke:
            self.on_invoke(self)

    def type_keys(self, keys, **_kw):
        self.tasten.append(keys)


class Feld(El):
    """Edit-Feld: Leeren füllt optional „0.00" nach (MT5-Auto-Format), Auswahl wird beim Tippen ersetzt, Anzeige optional mit Komma."""
    def __init__(self, rect, text="0.00", nachfuellen="0.00", komma=False, taub=False):
        super().__init__("", "Edit", (), rect)
        self.inhalt, self.nachfuellen, self.komma, self.taub, self.auswahl = text, nachfuellen, komma, taub, False

    def set_focus(self):
        pass

    def get_value(self):
        return self.inhalt.replace(".", ",") if self.komma else self.inhalt

    def type_keys(self, keys, **_kw):
        self.tasten.append(keys)
        if keys in ("^a{DELETE}", "{HOME}+{END}{DELETE}"):
            self.inhalt, self.auswahl = (self.nachfuellen or ""), False
        elif keys in ("^a", "{HOME}+{END}"):
            self.auswahl = True
        elif not self.taub:
            self.inhalt = keys if self.auswahl else self.inhalt + keys
            self.auswahl = False


class Knopf(El):
    def __init__(self, text, rect, dlg_ref):
        super().__init__(text, "Button", (), rect)
        self.dlg_ref = dlg_ref

    def set_focus(self):
        pass

    def has_keyboard_focus(self):
        return True

    def type_keys(self, keys, **_kw):
        self.tasten.append(keys)
        if keys == "{SPACE}":
            self.dlg_ref["gedrueckt"] = self.text
            self.dlg_ref["dlg"].sichtbar = False


def aendern_dialog(ticket, sprache="de", sl_feld=None, tp_feld=None):
    """Ändern-Dialog wie MT5: links der Reiter, Felder nach Beschriftung, unten der breite Bestätigen-Knopf mit Order-Daten."""
    st = {}
    sl_feld = sl_feld or Feld((200, 100, 300, 120))
    tp_feld = tp_feld or Feld((200, 130, 300, 150))
    if sprache == "de":
        reiter, lang = "Position ändern", f"#{ticket} sell 0.04 NAS100 sl: 29758.50 tp: 29705.13 Ändern"
        sl_t, tp_t = "Stop Loss:", "Take Profit:"
    else:
        reiter, lang = "Modify Position", f"Modify #{ticket} sell 0.04 NAS100 sl: 29758.50 tp: 29705.13"
        sl_t, tp_t = "Stop Loss:", "Take Profit:"
    dlg = El("Position #" + str(ticket), "Window", [], (0, 0, 600, 400))
    k_reiter, k_lang = Knopf(reiter, (10, 10, 110, 30), st), Knopf(lang, (150, 300, 550, 330), st)
    dlg.kinder = [El(sl_t, "Text", (), (100, 100, 180, 120)), sl_feld, El(tp_t, "Text", (), (100, 130, 180, 150)), tp_feld,
                  k_reiter, k_lang]
    st["dlg"] = dlg
    return dlg, st, sl_feld, tp_feld


def lade():
    src = open(BOT, encoding="utf-8").read()
    uhr = Uhr()
    ns = {"re": re, "time": uhr, "os": os}
    for k in ("NACHZIEHEN_AB_USD", "NACHZIEHEN_VERSUCHE", "MT5_KLASSE"):
        exec(re.search(rf"^{k} = .*$", src, re.M).group(0), ns)
    for name in ("fmt_preis", "berechne_sl_tp", "sltp_vom_fill", "sltp_abweichung_usd", "kommission_runde", "nachzieh_seiten",
                 "sltp_bestaetigt", "zahl_gleich", "ist_aendern_knopf", "ist_bestaetigen_knopf", "zeile_nennt_ticket", "ist_handelszeile",
                 "_feld_lesen", "_feld_tippen", "_ist_aendern_dialog", "_dialog_gehoert_zu", "_menuepunkt_ausloesen",
                 "_kontextmenue_aendern_klicken", "_reihen_scan", "_map_felder", "_sltp_klicken", "_sltp_nachziehen"):
        exec(fn(src, name), ns)
    ns.update(_warte=lambda a=0, b=0: uhr.sleep(a), tipp_takt=lambda n, **_k: [0.01] * n, _echo_klick=lambda r, schritte=0: True,
              _echo_klickziel=lambda r: (r.left + 1, r.top + 1), _maus_fahren=lambda *a, **k: None, is_paused=lambda: False,
              _fremde_dialoge_schliessen=lambda w: None, _anker_lesen=lambda p: (_ for _ in ()).throw(OSError("kein Anker")),
              _anker_schreiben=lambda p, **f: None, _dialog_struktur=lambda d: "?", _handel_tab_aktivieren=lambda *a, **k: "suche")
    return ns, uhr, src


def main():
    ns, uhr, src = lade()
    T = 619040989          # Ticket aus Lauf 7f6adf45 (Polar-Slave The5ers)

    # ── a) Dialog erkennen ───────────────────────────────────────────────────────────────────────────
    for sp in ("de", "en"):
        d, _st, _s, _t = aendern_dialog(T, sp)
        check(ns["_ist_aendern_dialog"](d), f"Ändern-Dialog {sp.upper()} erkannt (langer Knopf)")
        check(ns["_dialog_gehoert_zu"](d, T) and not ns["_dialog_gehoert_zu"](d, T + 1), f"{sp.upper()}: Ticket-Gegenprobe eigene/fremde Position")
    f9 = El("Order", "Window", [Knopf("Sell by Market", (0, 0, 200, 30), {}), Knopf("Buy by Market", (0, 40, 200, 70), {})])
    check(not ns["_ist_aendern_dialog"](f9), "F9-Neu-Order-Dialog ist NIE der Ändern-Dialog (kein Buy/Sell drücken)")
    zu = El("Close", "Window", [Knopf(f"Close #{T} sell 0.04 NAS100 by Market", (0, 0, 300, 30), {})])
    check(not ns["_ist_aendern_dialog"](zu), "Schließen-Dialog ist nicht der Ändern-Dialog")
    B = ns["ist_bestaetigen_knopf"]
    check(not B("Position ändern") and not B("Modify Position") and B(f"#{T} sell 0.04 NAS100 sl: 29758.50 tp: 29705.13 Ändern")
          and B(f"Modify #{T} sell 0.04 NAS100 sl: 29758.50 tp: 29705.13"), "Reiter nie Bestätigen-Knopf, langer Knopf DE/EN ja")
    ohne = El("x", "Window", [El("Kurs 29989.33", "Text")])
    check(ns["_dialog_gehoert_zu"](ohne, T), "Dialog ohne Ticket-Nummer (nur Kurse) → kein Widerspruch")
    Z = ns["zeile_nennt_ticket"]
    zeilen = [f"{T + 1} NAS100 sell 0.04 29713.40", f"{T} NAS100 sell 0.04 29713.38", f"9{T} NAS100 buy 1.00"]
    check([z for z in zeilen if Z(z, T)] == [zeilen[1]], "mehrere Positionen: genau die Zeile mit unserem Ticket")

    # Kontextmenü: fake pywinauto.Desktop
    menue = {"offen": True, "fenster": []}
    pw = types.ModuleType("pywinauto")
    pw.Desktop = lambda backend=None: types.SimpleNamespace(windows=lambda: menue["fenster"])
    sys.modules["pywinauto"] = pw
    ns["_menue_offen"] = lambda: menue["offen"]

    def menue_mit(text, aktiv=True):
        menue["offen"] = True
        it = El(text, "MenuItem", (), (0, 0, 100, 20), aktiv, on_invoke=lambda _e: menue.update(offen=False))
        menue["fenster"] = [El("", "Menu", [El("Position schließen", "MenuItem"), it], cls="#32768")]
        return it
    K = ns["_kontextmenue_aendern_klicken"]
    menue_mit("Ändern oder Löschen")
    check(K(timeout=0.5) == "geklickt", "Kontextmenü DE „Ändern oder Löschen“ → geklickt (Menü zu = Beweis)")
    menue_mit("Modify or Delete")
    check(K(timeout=0.5) == "geklickt", "Kontextmenü EN „Modify or Delete“ → geklickt")
    menue_mit("Ändern oder Löschen", aktiv=False)
    check(K(timeout=0.5) == "ausgegraut", "Punkt ausgegraut (Klick neben der Zeile) → ausgegraut, nichts geklickt")
    menue["fenster"] = []
    check(K(timeout=0.5) == "kein_menue", "kein Menü → kein_menue")
    menue["fenster"] = [El("", "Menu", [El("Position schließen", "MenuItem")], cls="#32768")]
    check(K(timeout=0.5) == "kein_menue", "nur „Position schließen“ im Menü → nie geklickt")

    # Zeilen-Scan: Rechtsklick-Runde, dann Doppelklick-Runde; fremde Dialoge verwerfen
    w = El("12345678 - Konto", "Window", [], (0, 0, 1600, 900), cls=ns["MT5_KLASSE"])
    klicks = []
    ns["_klick_absolut"] = lambda x, y, taste="links", doppel=False: klicks.append((x, y, taste, doppel)) or True
    eigen, _st, _s, _t = aendern_dialog(T)
    fremd, _st2, _s2, _t2 = aendern_dialog(T + 1)
    folge = iter(["ausgegraut", "geklickt", "geklickt"] + ["kein_menue"] * 200)
    dlgs = iter([fremd, eigen])
    ns["_kontextmenue_aendern_klicken"] = lambda timeout=2.0: next(folge)
    ns["_finde_aendern_dialog"] = lambda w_, timeout=3.0: next(dlgs, None)
    spur = []
    d = ns["_reihen_scan"](w, T, spur, 450)
    check(d is eigen and any("Rechtsklick-Menue-Scan" in s for s in spur) and "{ESC}" in fremd.tasten,
          "Zeilen-Scan: ausgegraut → fremder Dialog verworfen (ESC) → eigener Dialog per Rechtsklick")
    check(all(y >= 450 for _x, y, _t_, _d in klicks), "Zeilen-Scan klickt nur in der unteren Fensterhälfte (nie Chart/Ein-Klick-Panel)")
    klicks.clear()
    ns["_kontextmenue_aendern_klicken"] = lambda timeout=2.0: "kein_menue"
    ns["_finde_aendern_dialog"] = lambda w_, timeout=3.0: eigen if klicks and klicks[-1][3] else None
    spur = []
    d = ns["_reihen_scan"](w, T, spur, 450)
    check(d is eigen and any("Doppelklick-Scan" in s for s in spur), "Kontextmenü nie lesbar → zweite Runde per Doppelklick")
    ns["_finde_aendern_dialog"] = lambda w_, timeout=3.0: None
    spur = []
    check(ns["_reihen_scan"](w, T, spur, 450) is None and "Zeilen-Scan ohne Treffer" in spur[-1], "kein Treffer → None + Diagnose in der Spur")

    # ── b) Preisfelder ───────────────────────────────────────────────────────────────────────────────
    P, FT = ns["fmt_preis"], ns["_feld_tippen"]
    check(P(29746.18, 1) == "29746.2" and P(29746.18, 2) == "29746.18" and P(1.234567, 3) == "1.235" and "," not in P(29746.18, 2),
          "fmt_preis: digits 1/2/3, immer Punkt (MT5-Felder unabhängig von der Windows-Sprache)")
    for dg, wert in ((1, 29746.2), (2, 29746.18), (3, 1.235)):
        f, spur = Feld((0, 0, 10, 10)), []
        check(FT(f, P(wert, dg), "TP", spur) and f.inhalt == P(wert, dg) and any("leert nicht ('0.00')" in s for s in spur),
              f"Feld füllt „0.00“ nach → über die Auswahl getippt, digits {dg}: {f.inhalt}")
    f, spur = Feld((0, 0, 10, 10), komma=True), []
    check(FT(f, "29746.18", "SL", spur) and any("SL getippt: 29746.18" in s for s in spur), "Feld zeigt Komma (29746,18) → als Zahl gleich")
    f, spur = Feld((0, 0, 10, 10), taub=True), []
    check(not FT(f, "29746.18", "SL", spur) and "SL NICHT uebernommen: 29746.18" in spur[-1], "Feld nimmt nichts an → False nach 3 Versuchen, Spur sagt es")

    # _sltp_klicken bis zum Knopf: Anker-Schnellweg trifft den Dialog
    for sp in ("de", "en"):
        d, st, slf, tpf = aendern_dialog(T, sp)
        ns["_reihen_scan"] = lambda *a, **k: d
        spur = []
        k = ns["_sltp_klicken"](w, T, "NAS100", "29746.18", "29696.32", spur)
        check(k == {"ok": True, "msg": "geklickt"} and slf.inhalt == "29746.18" and tpf.inhalt == "29696.32"
              and st.get("gedrueckt", "").endswith(("Ändern", "29705.13")) and st["gedrueckt"] not in ("Position ändern", "Modify Position"),
              f"_sltp_klicken {sp.upper()}: Felder nach Beschriftung, langer Knopf gedrückt (nicht der Reiter)")
    d, st, slf, tpf = aendern_dialog(T, "de", tp_feld=Feld((200, 130, 300, 150), taub=True))
    ns["_reihen_scan"] = lambda *a, **k: d
    k = ns["_sltp_klicken"](w, T, "NAS100", "29746.18", "29696.32", [])
    check(not k["ok"] and "Felder nicht befuellbar" in k["msg"] and "gedrueckt" not in st and "{ESC}" in d.tasten,
          "TP-Feld nimmt nicht → ESC, Bestätigen NIE gedrückt (keine halb gesetzte Änderung)")
    ns["is_paused"] = lambda: True
    check(ns["_sltp_klicken"](w, T, "NAS100", "1", "2", []) is None, "Echo pausiert → kein einziger Klick (None)")
    ns["is_paused"] = lambda: False

    # ── c/d/e) Nachziehen mit Rücklesen, Wiederholung, nur finale Seite ───────────────────────────────
    S = ns["sltp_bestaetigt"]
    check(S(29746.18, 29696.32, 29746.17, 29696.33, 2) and not S(29746.18, 29696.32, 29746.15, 29696.32, 2)
          and S(29746.2, 29696.3, 29746.3, 29696.2, 1) and S(1.2345, 1.3, 1.2355, 1.3, 3) and not S(0.0, 29696.32, 29746.18, 29696.32, 2),
          "sltp_bestaetigt: 1,5 Ticks Toleranz je digits, 0 = nicht gesetzt")

    # Fall 7f6adf45 nachgestellt: sell, Fill 29.713,38, Notfall-F9 SL 29.758,50 / TP 29.705,13 — die API zeigt nach dem Ändern weiter die
    # Notfall-Level. (4 Lot statt 0,04, damit die Abweichung über der 3-$-Schwelle liegt; The5ers 1 $/Pkt/Lot.)
    FILL, SL_F9, TP_F9, VOL, CS = 29713.38, 29758.50, 29705.13, 4.0, 1.0
    p = {"ticket": T}
    cmd = {"richtung": "sell", "sl_usd": 4 * 32.8, "tp_usd": 4 * 16.57}

    def lauf(final, api_folge, klick_erg=({"ok": True, "msg": "geklickt"},), grund="test"):
        klick_args, pausen, stand = [], [], {"i": 0}
        ergebnisse = list(klick_erg)
        ns["_sltp_klicken"] = lambda w_, t, sym, sl_t, tp_t, tr, anker_pfad=None: klick_args.append((sl_t, tp_t)) or \
            ergebnisse[min(len(klick_args), len(ergebnisse)) - 1]
        ns["_api_lesen"] = lambda path, exp, symbol=None, timeout_ms=None: api_folge(len(klick_args))
        ns["_kommission_lesen"] = lambda path, exp, t: 0.0
        alt_warte = ns["_warte"]
        ns["_warte"] = lambda a=0, b=0: (pausen.append((a, b)) if a >= 1.0 else None, uhr.sleep(a))
        ns["_EchoUnruhe"] = lambda: types.SimpleNamespace(__enter__=lambda s=None: None, __exit__=lambda *x: False)
        class _U:
            def __enter__(self): return self
            def __exit__(self, *a): return False
        ns["_EchoUnruhe"] = _U
        spur = []
        e = ns["_sltp_nachziehen"](w, "pfad", 1, p, dict(cmd, final=final, final_grund=grund), "NAS100", FILL, VOL, CS, 2, SL_F9, TP_F9, spur, None)
        ns["_warte"] = alt_warte
        return e, klick_args, pausen, spur

    pos = lambda sl, tp: {"positionen": [{"ticket": T, "sl": sl, "tp": tp}]}
    sl_ex, tp_ex = ns["sltp_vom_fill"]("sell", FILL, VOL, CS, cmd["sl_usd"], cmd["tp_usd"], 0.0, 2)

    e, ka, pz, spur = lauf("beide", lambda n: pos(SL_F9, TP_F9))
    check(e["ok"] and not e["nachgezogen"] and (e["sl"], e["tp"]) == (SL_F9, TP_F9) and "nicht bestätigt" in e["grund"]
          and "grobe F9-Level bleiben" in e["grund"] and spur[-1].startswith("Nachziehen: "),
          f"7f6adf45: API zeigt weiter die Notfall-Level → grobe Level bleiben, Grund in der Spur ({e['grund'][:60]}…)")
    check(len(ka) == ns["NACHZIEHEN_VERSUCHE"] == e["versuche"] and len(pz) == ns["NACHZIEHEN_VERSUCHE"] - 1 and all(a >= 1.0 and b > 0 for a, b in pz),
          f"höchstens {ns['NACHZIEHEN_VERSUCHE']} Anläufe, dazwischen gewürfelte Pause {pz}")
    e, ka, pz, spur = lauf("beide", lambda n: pos(sl_ex, tp_ex) if n >= 2 else pos(SL_F9, TP_F9))
    check(e["nachgezogen"] and len(ka) == 2 and (e["sl"], e["tp"]) == (sl_ex, tp_ex) and "Versuch 2" in spur[-1], "erst der 2. Anlauf greift → nachgezogen")
    e, ka, _pz, _s = lauf("beide", lambda n: pos(sl_ex, tp_ex))
    check(e["nachgezogen"] and len(ka) == 1, "1. Anlauf bestätigt → kein zweiter Klick")
    e, ka, _pz, _s = lauf("beide", lambda n: pos(0.0, TP_F9))
    check(not e["ok"] and "ein Level fehlt" in e["grund"] and len(ka) == 1, "Position ohne SL nach dem Ändern → ok False (SOFORT von Hand), kein Weiterklicken")
    e, ka, _pz, _s = lauf("beide", lambda n: {"positionen": []})
    check(e["ok"] and "Position schon zu" in e["grund"] and len(ka) == 1, "Position schon zu → nichts mehr, kein zweiter Anlauf")
    e, ka, _pz, _s = lauf("beide", lambda n: pos(SL_F9, TP_F9), klick_erg=(None,))
    check(e["ok"] and "pausiert" in e["grund"] and len(ka) == 1, "Echo pausiert → kein zweiter Anlauf, grobe Level bleiben")
    e, ka, _pz, _s = lauf("beide", lambda n: {"fehler": "IPC timeout"})
    check(e["ok"] and "nicht bestätigt" in e["grund"] and len(ka) == 2, "API nicht lesbar → nicht bestätigt, grobe Level bleiben (nie geraten)")

    # e) nur die finale Seite
    e, ka, _pz, spur = lauf("pass", lambda n: pos(SL_F9, tp_ex), grund="TP 3.006 $ ≥ Rest 2.964 $ bis Ziel 108.000")
    check(ka == [(P(SL_F9, 2), P(tp_ex, 2))] and e["nachgezogen"] and e["seiten"] == "TP" and any("Final: pass (TP 3.006" in s for s in spur),
          f"final pass → NUR TP exakt ({P(tp_ex, 2)}), SL bleibt {P(SL_F9, 2)}, Urteil + Grund in der Spur")
    e, ka, _pz, _s = lauf("blow", lambda n: pos(sl_ex, TP_F9))
    check(ka == [(P(sl_ex, 2), P(TP_F9, 2))] and e["nachgezogen"] and e["seiten"] == "SL", f"final blow → NUR SL exakt ({P(sl_ex, 2)}), TP bleibt")
    for fin in (None, "", "etappe", "PASSIV"):
        e, ka, _pz, spur = lauf(fin, lambda n: pos(SL_F9, TP_F9), grund="TP 4.000 $ < Rest 8.000 $ bis Ziel · SL nicht am Boden")
        check(ka == [] and not e["nachgezogen"] and e["seiten"] is None and "Final: keins" in spur[-1] and "kein Ändern-Klick" in spur[-1],
              f"final {fin!r} → kein Ändern-Klick, grobe F9-Level wie bisher")
    check(ns["nachzieh_seiten"]("Pass") == (True, False) and ns["nachzieh_seiten"]("blow") == (False, True)
          and ns["nachzieh_seiten"]("beide") == (True, True) and ns["nachzieh_seiten"](None) == (False, False), "nachzieh_seiten")

    print()
    if FEHLER:
        print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
        sys.exit(1)
    print("ALLES GRÜN")


if __name__ == "__main__":
    main()
