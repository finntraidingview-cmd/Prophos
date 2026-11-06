#!/usr/bin/env python3
"""Selbsttest DO2 · Stufen am MT5-Buy/Sell-Knopf ohne zweite Order (06.11.2026, Slave 4 — Doppel-Order The5%ers 200k/100k: Leertaste hatte
gesendet, Ausführung 6–23 s, nach 4 s drückte der Bot die nächste Stufe → zweite Order).

Ohne Netz, ohne Windows: mt5-copier/order_bot.py importiert, stufen_ausloesen mit virtueller Uhr und einem Fake-Terminal, das jede wirksame
Stufe als Order zählt, die Journal-Zeile beim Absenden schreibt und die Position erst nach der Ausführungszeit zeigt. Fälle: langsame
Ausführung 15 s / 23 s (EINE Order), Journal schreibt verzögert (EINE Order), Stufe 1 wirkungslos (nächste Stufe nach der Frist), Journal nicht
lesbar (keine 2. Stufe, unklar), Dialog „in progress“, Ablehnung „failed market … [Market closed]“, schnelle Ausführung. Dazu
order_anfrage_im_journal gegen die echten Journal-Zeilen von pc-xxxxxx (Kennungen erfunden) und die Rückgaben in run().
Aufruf: python3 tools/selftest_do2_stufen.py"""
import os
import random
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# ── order_anfrage_im_journal: echte Zeilen (Konto/Order-Nummern erfunden) ────────────────────────────────────
J = [
    "NP\t0\t11:06:27.498\tNetwork\t'1234567': terminal synchronized with Broker: 0 positions, 0 orders, 64 symbols, 0 spreads",
    "IE\t0\t11:08:13.128\tTrades\t'1234567': market sell 54 NAS100 sl: 27062.80 tp: 26784.95",
    "KR\t0\t11:08:21.800\tTrades\t'1234567': market sell 54 NAS100 sl: 27062.80 tp: 26784.95",
    "MM\t0\t11:08:28.053\tTrades\t'1234567': accepted market sell 54 NAS100 sl: 27062.80 tp: 26784.95",
    "LF\t0\t11:08:28.054\tTrades\t'1234567': deal #400000001 sell 54 NAS100 at 26975.09 done (based on order #600000001)",
    "FF\t0\t11:09:21.178\tTrades\t'1234567': modify #600000001 sell 54 NAS100 sl: 27062.80, tp: 26784.95 -> sl: 27049.13, tp: 26784.95",
]
s = lambda hms: sum(float(x) * f for x, f in zip(hms.split(":"), (3600, 60, 1)))  # noqa: E731
check(ob.order_anfrage_im_journal(J, 1234567, "NAS100", "sell", s("11:08:12")) is not None, "Journal: „market sell“ nach dem Klick → Anfrage")
check(ob.order_anfrage_im_journal(J[:2], 1234567, "NAS100", "sell", s("11:08:15")) is None, "Journal: Zeile ~2 s vor ab_s zählt nicht")
check(ob.order_anfrage_im_journal(J[:2], 1234567, "NAS100", "sell", s("11:08:14.0")) is not None, "Journal: < 1 s vor ab_s zählt (Uhr-Rundung)")
check(ob.order_anfrage_im_journal(J[:2], 7654321, "NAS100", "sell", s("11:08:12")) is None, "Journal: anderes Konto zählt nicht")
check(ob.order_anfrage_im_journal(J[:2], 1234567, "NAS100", "buy", s("11:08:12")) is None, "Journal: andere Richtung zählt nicht")
check(ob.order_anfrage_im_journal(J[:2], 1234567, "US30", "sell", s("11:08:12")) is None, "Journal: anderes Symbol zählt nicht")
check(ob.order_anfrage_im_journal([J[5]], 1234567, "NAS100", "sell", s("11:09:00")) is None, "Journal: „modify #…“ ist keine Anfrage")
check(ob.order_anfrage_im_journal([J[4]], 1234567, "NAS100", "sell", s("11:08:00")) is not None, "Journal: „deal #… sell“ ist ein Beleg")
check(ob.order_anfrage_im_journal(["XX\t0\t00:00:03.100\tTrades\t'1234567': market buy 2 NAS100"], 1234567, "NAS100", "buy", s("23:59:58")) is not None,
      "Journal: über Mitternacht")
check(ob.order_anfrage_im_journal(J[:2], 0, "NAS100", "sell", s("11:08:12")) is not None, "Journal: ohne Login nur Symbol + Richtung")

# ── stufe_urteil ─────────────────────────────────────────────────────────────────────────────────────────────
U = ob.stufe_urteil
check(U(True, False, None, "", True, False) == "bestaetigt" and U(False, True, None, "", True, False) == "bestaetigt", "Urteil: Position / Dialog zu")
check(U(False, False, J[1], "", True, False) == "gesendet", "Urteil: Journal-Anfrage → gesendet (vor Fristende)")
check(U(False, False, None, "Request in progress", True, False) == "gesendet", "Urteil: Dialog „in progress“ → gesendet")
check(U(False, False, "'1': failed market sell 1 NAS100 [Market closed]", "", True, False) == "antwort", "Urteil: „failed market …“ → antwort")
check(U(False, False, None, "Invalid stops", True, False) == "antwort", "Urteil: Server-Antwort im Dialog")
check(U(False, False, None, "", True, False) == "warten", "Urteil: Frist läuft → warten")
check(U(False, False, None, "", True, True) == "nichts", "Urteil: Frist um, Journal lesbar, keine Anfrage → nichts")
check(U(False, False, None, "", False, True) == "kein_beweis", "Urteil: Frist um, Journal nicht lesbar → kein_beweis")


# ── Fake-Terminal mit virtueller Uhr ─────────────────────────────────────────────────────────────────────────
class Terminal:
    """wirksam = Stufen-Namen, die wirklich senden; ausf_s = Ausführungszeit; journal_verz_s = Journal-Zeile erst so spät lesbar;
    journal_lesbar = False → leeres Journal; dialog_text = was der Dialog nach dem Senden zeigt; abgelehnt = Server lehnt ab."""

    def __init__(self, wirksam, ausf_s=15.0, journal_verz_s=0.0, journal_lesbar=True, dialog_text="", abgelehnt=None, schliesst_dialog=False):
        self.t = 0.0
        self.wirksam, self.ausf_s, self.jv, self.jl = set(wirksam), ausf_s, journal_verz_s, journal_lesbar
        self.dialog_text, self.abgelehnt, self.schliesst = dialog_text, abgelehnt, schliesst_dialog
        self.orders = []          # Sendezeitpunkte
        self.klicks = []

    def uhr(self):
        return self.t

    def jetzt_s(self):
        return 36000 + self.t     # 10:00:00 + t (Journal-Uhr = Ortszeit)

    def schlafen(self):
        self.t += 0.3

    def weg(self, name, wirft=None, wirft_vorher=False):
        def tu():
            self.klicks.append((name, self.t))
            self.t += 0.2
            if wirft_vorher:
                raise ob.StufeNichtGesendet("Knopf nimmt keinen Tastatur-Fokus an")
            if name in self.wirksam:
                self.orders.append(self.t)
            if wirft and name in wirft:
                raise TimeoutError("COM-Timeout nach dem Klick")
        return tu

    def lesen(self, ab_s, mit_journal):
        self.t += 0.05
        pos = any(self.t >= o + self.ausf_s for o in self.orders) and not self.abgelehnt
        weg = self.schliesst and bool(self.orders)
        dtext = self.dialog_text if self.orders else ""
        zeile, lesbar = None, False
        if mit_journal:
            zeilen = []
            for o in self.orders:
                if self.t >= o + self.jv:
                    hh = 36000 + o
                    ts = f"{int(hh // 3600):02d}:{int(hh % 3600 // 60):02d}:{int(hh % 60):02d}.{int((hh % 1) * 1000):03d}"
                    zeilen.append(f"XX\t0\t{ts}\tTrades\t'1234567': " + (f"failed market sell 54 NAS100 [{self.abgelehnt}]" if self.abgelehnt
                                                                         else "market sell 54 NAS100 sl: 1 tp: 2"))
            if self.jl:
                zeilen = ["NP\t0\t09:59:00.000\tNetwork\t'1234567': authorized"] + zeilen
            else:
                zeilen = []
            lesbar = bool(zeilen)
            zeile = ob.order_anfrage_im_journal(zeilen, 1234567, "NAS100", "sell", ab_s)
        return pos, weg, zeile, dtext, lesbar


WEGE = ("Fokus+Leertaste", "SendInput-Klick", ".click()", "click_input")


def lauf(term, frist=None, wirft=None, vorher=(), zeit_ok=None):
    trail = []
    frist = frist if frist is not None else random.uniform(24.0, 30.0)
    erg = ob.stufen_ausloesen([(n, term.weg(n, wirft, n in vorher)) for n in WEGE], term.lesen, frist, trail, "sell", term.jetzt_s,
                              uhr=term.uhr, schlafen=term.schlafen, zeit_ok=zeit_ok)
    return erg, trail


random.seed(6112026)
for ausf in (6.0, 15.0, 23.0, 35.0):
    t = Terminal(wirksam=WEGE, ausf_s=ausf)        # jede Stufe würde senden (Fall 06.11.)
    (aus, anfr), tr = lauf(t)
    check(len(t.orders) == 1 and len(t.klicks) == 1 and aus == "Fokus+Leertaste" and anfr,
          f"langsame Ausführung {ausf:.0f} s, jede Stufe wirksam → EINE Order, eine Stufe ({len(t.orders)} Order, Spur: {tr[-1][:60]})")
t = Terminal(wirksam=WEGE, ausf_s=23.0, journal_verz_s=8.0)
(aus, anfr), tr = lauf(t)
check(len(t.orders) == 1 and anfr, f"Journal schreibt 8 s verzögert → trotzdem EINE Order ({len(t.orders)})")
t = Terminal(wirksam=WEGE, ausf_s=23.0, journal_verz_s=40.0)
(aus, anfr), tr = lauf(t)
check(len(t.orders) == 1, f"Journal 40 s verzögert, Ausführung 23 s → Position vor Fristende, EINE Order ({len(t.orders)})")
t = Terminal(wirksam={"SendInput-Klick", ".click()", "click_input"}, ausf_s=0.5)   # Leertaste verpufft
(aus, anfr), tr = lauf(t, frist=25.0)
check(len(t.orders) == 1 and aus == "SendInput-Klick" and t.klicks[1][1] >= 25.0 and any("naechste Stufe" in x for x in tr),
      f"Stufe 1 wirkungslos → Stufe 2 erst nach der Frist ({t.klicks[1][1]:.1f} s), EINE Order")
t = Terminal(wirksam=set(), journal_lesbar=True)
(aus, anfr), tr = lauf(t, frist=25.0)
check(len(t.klicks) == 4 and not t.orders and aus == "click_input" and not anfr, "nichts wirkt, Journal lesbar → alle 4 Stufen, je nach Frist, keine Order")
t = Terminal(wirksam=WEGE, ausf_s=40.0, journal_lesbar=False)
(aus, anfr), tr = lauf(t, frist=25.0)
check(len(t.orders) == 1 and len(t.klicks) == 1 and anfr and "kein Beweis" in tr[-1], "Journal nicht lesbar, Ausführung 40 s → keine 2. Stufe, unklar")
t = Terminal(wirksam=set(), journal_lesbar=False)
(aus, anfr), tr = lauf(t, frist=25.0)
check(len(t.klicks) == 1 and anfr, "Journal nicht lesbar, nichts gesendet → trotzdem keine 2. Stufe (lieber unklar)")
t = Terminal(wirksam=WEGE, ausf_s=40.0, journal_lesbar=False, dialog_text="Request in progress")
(aus, anfr), tr = lauf(t, frist=25.0)
check(len(t.orders) == 1 and anfr and "Anfrage unterwegs" in tr[-1], "Dialog „in progress“ → keine 2. Stufe")
t = Terminal(wirksam=WEGE, abgelehnt="Market closed")
(aus, anfr), tr = lauf(t, frist=25.0)
check(len(t.orders) == 1 and not anfr and "Antwort des Servers" in tr[-1], "„failed market … [Market closed]“ → keine 2. Stufe, nicht unterwegs")
t = Terminal(wirksam=WEGE, ausf_s=0.3)
(aus, anfr), tr = lauf(t)
check(len(t.orders) == 1 and t.t < 3.0, f"schnelle Ausführung → sofort bestätigt ({t.t:.1f} s)")
t = Terminal(wirksam=WEGE, ausf_s=15.0, schliesst_dialog=True)
(aus, anfr), tr = lauf(t)
check(len(t.orders) == 1 and anfr, "Dialog zu, Position noch nicht da, Journal-Anfrage → Schritt 5 wartet länger (anfrage_gesehen)")

# ── run(): Einbau und Rückgaben (Quelltext) ─────────────────────────────────────────────────────────────────
src = open(os.path.join(HIER, "..", "mt5-copier", "order_bot.py"), encoding="utf-8").read()
i = src.index("def run(cfg_path, cmd):")
run_src = src[i:src.index("\ndef ", i + 10)]
check("_stufe_frist = random.uniform(24.0, 30.0)" in run_src and "ausgeloest, anfrage_gesehen = stufen_ausloesen(" in run_src, "run: Frist 24–30 s gestreut, Stufen über stufen_ausloesen")
check("_schnell_bestaetigt" not in src, "alter 4-s-Check weg")
check("_bestaetig_s = 40 if anfrage_gesehen else 12" in run_src, "Schritt 5: 40 s, wenn eine Anfrage unterwegs ist")
check("if markt_zu and not anfrage_gesehen:" in run_src, "Markt zu: retry_ok nur, wenn nichts unterwegs ist")
m = re.search(r"if anfrage_gesehen and not grund:\n.*?return \{(.*?)\}\n", run_src, re.S)
check(bool(m) and '"retry_ok": False' in m.group(1) and '"unklar": True' in m.group(1) and "NICHT erneut starten" in m.group(1),
      "keine Position trotz Anfrage → UNKLAR, retry_ok False")
check(run_src.count('"KEINE Bestaetigung binnen 12 s') == 2, "Schlüssel-Texte „KEINE Bestaetigung binnen 12 s“ unverändert")

# ── Nachträge aus der Gegenprüfung ───────────────────────────────────────────────────────────────────────────
t = Terminal(wirksam=WEGE, ausf_s=15.0)
(aus, anfr), tr = lauf(t, wirft={"Fokus+Leertaste"})
check(len(t.orders) == 1 and len(t.klicks) == 1 and anfr and aus == "Fokus+Leertaste", "Stufe wirft NACH dem Senden → gilt als gedrückt, keine 2. Order")
t = Terminal(wirksam={"SendInput-Klick"}, ausf_s=0.5)
(aus, anfr), tr = lauf(t, frist=25.0, vorher={"Fokus+Leertaste"})
check(len(t.orders) == 1 and aus == "SendInput-Klick" and t.klicks[1][1] < 1.0, "StufeNichtGesendet (kein Fokus) → sofort nächste Stufe")
t = Terminal(wirksam=set())
(aus, anfr), tr = lauf(t, frist=25.0, zeit_ok=lambda f: t.t + f < 40)
check(len(t.klicks) == 1 and "Zeitbudget" in tr[-1], "Zeitbudget knapp → keine weitere Stufe")
check(ob.order_anfrage_im_journal(["XX\t0\t11:08:13.128\tTrades\t'1234567': instant sell 2 NAS100 at 26975.0"], 1234567, "NAS100", "sell", s("11:08:12")) is not None,
      "Journal: Instant-Execution „instant sell“ zählt")
check(ob.order_anfrage_im_journal(["XX\t0\t11:08:13.128\tTrades\t'1234567': market sell 1.26 NAS100, close #246819892 buy 1.26 NAS100 26823.01"],
                                  1234567, "NAS100", "sell", s("11:08:12")) is None, "Journal: Schließen einer anderen Position („close #“) zählt nicht")
check(ob.stufe_urteil(False, False, "'1': failed instant sell 1 NAS100 [Off quotes]", "", True, False) == "antwort", "Urteil: „failed instant …“ → antwort")
check(ob.stufe_urteil(False, False, None, "Order #1 sell 54 NAS100 done", True, False) == "gesendet", "Urteil: Dialog „done“ → gesendet")
check("zeit_ok=lambda f: trail.sekunden() + f + 40 + 30 < 270" in run_src, "run: Zeitbudget unter dem Panel-Timeout (300 s)")
check('raise StufeNichtGesendet("Knopf nimmt keinen Tastatur-Fokus an")' in run_src and 'raise StufeNichtGesendet("SendInput abgelehnt")' in run_src,
      "nur die zwei Vor-dem-Senden-Fälle springen sofort weiter")

# ── (b) Doppel-Hedge: Notfall-Halt im Copier ────────────────────────────────────────────────────────────────
import copier as cp  # noqa: E402
check(cp.notfall_halt_aktiv({1110312: 107.0}, 1110312, 100.0) and not cp.notfall_halt_aktiv({1110312: 107.0}, 1110312, 108.0)
      and not cp.notfall_halt_aktiv({}, 1110312, 100.0) and not cp.notfall_halt_aktiv(None, 1, 0), "Notfall-Halt: bis-Zeit, sonst frei")
check(cp.NOTFALL_HALT_S[0] >= 5 and cp.NOTFALL_HALT_S[1] > cp.NOTFALL_HALT_S[0], "Notfall-Halt gestreut 6–9 s")
csrc = open(os.path.join(HIER, "..", "mt5-copier", "copier.py"), encoding="utf-8").read()
i = csrc.index('"note": "notfall_close"')
check("m.notfall_halt[ident_i] = time.monotonic() + random.uniform(*NOTFALL_HALT_S)" in csrc[i:i + 2600], "Notfall-Close setzt den Halt (kein m.blocked)")
j = csrc.index('if a["kind"] == "open":')
check(csrc.index("notfall_halt_aktiv(m.notfall_halt, ident, time.monotonic())", j) < csrc.index("is_paused()", j), "Open-Gate: Halt vor dem Senden")
# Ablauf 06.11. nachgespielt: Hedge-SL 26.723, Master-TP 27.060 → mit Halt kein Open; Master läuft 10 s weiter → Wiederaufbau nach dem Halt
halt = {1110312: 26.723 + 6.0}
opens = [tk for tk in (27.217, 27.5, 32.0) if not cp.notfall_halt_aktiv(halt, 1110312, tk) and tk < 27.060]
check(not opens, "06.11.: Master 0,34 s nach dem Hedge zu → kein zweiter Hedge")
check(cp.notfall_halt_aktiv(halt, 1110312, 30.0) and not cp.notfall_halt_aktiv(halt, 1110312, 36.8), "Master läuft weiter → Wiederaufbau nach dem Halt")

print()
if FEHLER:
    print(f"{len(FEHLER)} FEHLER:", *FEHLER, sep="\n  ")
    sys.exit(1)
print("alle Prüfungen bestanden")
