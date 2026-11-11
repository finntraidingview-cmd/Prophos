#!/usr/bin/env python3
"""Selbsttest MT1 Punkt 1+1b (11.11.2026): Ändern-Klick wird BEWIESEN (API trägt SL/TP bzw. Terminal-Journal), keine blinden Zusatzklicks.
Anlass MT1-Abfrage A: in 61 von 61 Läufen galt der Ändern-Dialog nie als zu („Aendern-Knopf ausgeloest“ 0×), alle vier Klick-Wege gingen jedes Mal ab;
31 von 57 Nachzügen saßen erst im 2. Versuch. Prüft: aendern_journal_urteil (rein: modify-Zeilen des Tickets seit dem Klick, failed → Grund,
Close/Order-Zeilen und fremde Tickets zählen nicht, Mitternacht), aendern_kaskade mit Stub-Uhr in 50 gewürfelten Abläufen (nach Beweis/Ablehnung/
gesendeter Anfrage NIE ein weiterer Klick, Ergebnis-Seite zu; nur „weder API noch Journal“ → nächster Weg; ohne Beweis wie bisher „Dialog zu“),
Einbau in _sltp_klicken / _sltp_nachziehen / Erst-Setzen, kein order_send. Ohne Netz, ohne MetaTrader. Aufruf: python3 tools/selftest_mt1_aendern.py"""
import os
import random
import re
import sys
import time

HIER = os.path.dirname(os.path.abspath(__file__))
W = os.path.dirname(HIER)
BOT = open(os.path.join(W, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def block(name):
    i = BOT.index(f"\ndef {name}(") + 1
    return BOT[i:BOT.index("\n\n\n", i)]


ns = {"re": re, "time": time, "_warte": lambda a, b: None}
for k in ("AENDERN_BEWEIS_S", "AENDERN_SERVER_S"):
    exec(re.search(rf"^{k} = .*$", BOT, re.M).group(0), ns)
for n in ("lokal_sek", "aendern_journal_urteil", "aendern_kaskade", "_aendern_beweis", "sltp_bestaetigt"):
    exec(block(n), ns)
J, K = ns["aendern_journal_urteil"], ns["aendern_kaskade"]

# 1) Journal-Urteil
Z = ["LL\t0\t10:00:05.120\tTrades\t'1234': modify #1179274 buy 3.4 NAS100 sl: 0.00, tp: 0.00 -> sl: 26950.66, tp: 27134.81",
     "LL\t0\t10:00:05.410\tTrades\t'1234': accepted modify #1179274 buy 3.4 NAS100 -> sl: 26950.66, tp: 27134.81"]
ab = 10 * 3600 + 4
check(J(Z, 1179274, ab)[0] == "gesendet", "modify-Zeile des Tickets nach dem Klick → gesendet")
F = ["LL\t0\t10:00:05.120\tTrades\t'1234': failed modify #1179274 buy 3.4 NAS100 sl: 0.00, tp: 0.00 -> sl: 26950.66, tp: 27134.81 [Invalid stops]"]
check(J(F, 1179274, ab) == ("abgelehnt", "Invalid stops"), "failed modify → abgelehnt mit Grund aus der eckigen Klammer")
check(J(Z + F, 1179274, ab)[0] == "abgelehnt" and J(F + Z, 1179274, ab)[0] == "gesendet", "die JÜNGSTE modify-Zeile entscheidet")
check(J(Z, 1179274, ab + 400) == (None, ""), "Zeilen vor dem Klick zählen nicht")
check(J(Z, 11792740, ab) == (None, "") and J(Z, 117927, ab) == (None, ""), "fremdes Ticket (Präfix/Teil) zählt nicht")
C = ["LL\t0\t10:00:05.120\tTrades\t'1234': market sell 3.4 NAS100, close #1179274 buy 3.4 NAS100 27007.10"]
check(J(C, 1179274, ab) == (None, ""), "Close-/Order-Zeilen des Tickets zählen nicht als Ändern")
M = ["LL\t0\t00:00:01.050\tTrades\t'1234': modify #77 buy 1 NAS100 -> sl: 1, tp: 2"]
check(J(M, 77, 23 * 3600 + 59 * 60 + 58)[0] == "gesendet", "über Mitternacht (Ortszeit) erkannt")
check(J([], 77, 0) == (None, "") and J(Z, None, ab) == (None, ""), "leer / ohne Ticket → nichts")


# 2) Kaskade mit Stub-Uhr
class Uhr:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def warte(self, a, b):
        self.t += a


def lauf(szen, mit_beweis=True, sichtbar_ab_klick=None):
    """szen: je Weg (klick_wirft, ab_wann_beweis s, art, text) — art None = nichts sichtbar."""
    u = Uhr()
    trail, klicks, zu = [], [], {"n": 0}
    ab_gesehen = set()
    akt = {"i": -1, "t0": 0.0}

    def weg_f(i):
        def f():
            if szen[i][0]:
                raise RuntimeError("Fokus fehlt")
            klicks.append(i)
            akt.update(i=i, t0=u.t)
        return f

    def beweis(ab_s):
        ab_gesehen.add(ab_s)
        i = akt["i"]
        if i < 0:
            return None, ""
        _wirft, ab_w, art, txt = szen[i]
        return (art, txt) if (art and u.t - akt["t0"] >= ab_w) else (None, "")
    wege = tuple((f"w{i}", weg_f(i)) for i in range(len(szen)))
    noch_offen = None if sichtbar_ab_klick is None else (lambda: len(klicks) < sichtbar_ab_klick)
    r = K(wege, beweis if mit_beweis else None, lambda: False, lambda: zu.__setitem__("n", zu["n"] + 1), lambda: zu.__setitem__("n", zu["n"] + 10), trail,
          uhr=u, warte=u.warte, noch_offen=noch_offen)
    lauf.ab = ab_gesehen
    return r, klicks, zu["n"], trail, u.t


r, kl, zu, tr, t = lauf([(False, 0.5, "api_ok", "Position trägt SL"), (False, 0, None, ""), (False, 0, None, ""), (False, 0, None, "")])
check(r["ok"] and r["beleg"] == "api_ok" and kl == [0] and zu == 1, "Weg 1 wirkt (API) → bestätigt, KEIN zweiter Klick, Ergebnis-Seite zu")
r, kl, zu, tr, t = lauf([(False, 1.0, "gesendet", "modify #1"), (False, 0, None, ""), (False, 0, None, ""), (False, 0, None, "")])
check(not r["ok"] and r.get("gesendet") and kl == [0] and zu == 1 and t >= 10.0, "Journal zeigt die Anfrage, keine Bestätigung → bis 10 s warten, kein weiterer Klick")
r, kl, zu, tr, t = lauf([(False, 0.5, "abgelehnt", "Invalid stops"), (False, 0, None, ""), (False, 0, None, ""), (False, 0, None, "")])
check(r.get("abgelehnt") == "Invalid stops" and kl == [0] and zu == 1, "Server lehnt ab → kein weiterer Weg in diesem Versuch, Grund in der Antwort")
r, kl, zu, tr, t = lauf([(False, 0, None, ""), (False, 0.3, "api_ok", "ok"), (False, 0, None, ""), (False, 0, None, "")])
check(r["ok"] and kl == [0, 1] and any("weder API noch Journal" in x for x in tr), "Weg 1 ohne jede Spur → Weg 2, der wirkt → Ende")
r, kl, zu, tr, t = lauf([(True, 0, None, ""), (False, 0.2, "api_ok", "ok"), (False, 0, None, ""), (False, 0, None, "")])
check(r["ok"] and kl == [1], "Weg 1 wirft (kein Fokus) → kein Klick gezählt, Weg 2")
r, kl, zu, tr, t = lauf([(False, 0, None, "")] * 4)
check(not r["ok"] and kl == [0, 1, 2, 3] and zu == 10 and r["msg"] == "Aendern-Knopf reagiert auf keinen Weg", "nichts wirkt → alle vier Wege, dann ESC")
r, kl, zu, tr, t = lauf([(False, 0.5, "weg", "Position nicht mehr offen"), (False, 0, None, ""), (False, 0, None, ""), (False, 0, None, "")])
check(r["ok"] and r["beleg"] == "weg" and kl == [0], "Position inzwischen zu → Ende ohne weiteren Klick")
r, kl, zu, tr, t = lauf([(False, 0, None, "")] * 4, mit_beweis=False)
check(not r["ok"] and kl == [0, 1, 2, 3] and any("ohne Wirkung" in x for x in tr), "ohne Beweis (Polar) wie bisher: Dialog-Kriterium")

r, kl, zu, tr, t = lauf([(False, 0, None, "")] * 4)
check(len(lauf.ab) == 1, "Prüfer SOLLTE: das Journal-Fenster beginnt EINMAL vor dem ersten Weg (spät geschriebene Zeile von Weg 1 zählt nach Weg 2 noch)")
r, kl, zu, tr, t = lauf([(False, 0, None, "")] * 4, sichtbar_ab_klick=1)
check(kl == [0] and r.get("dialog_weg") and not r["ok"] and any("nicht mehr sichtbar" in x for x in tr),
      "Prüfer SOLLTE: Dialog nach Weg 1 nicht mehr sichtbar (Win32) → KEIN weiterer Weg (SendInput träfe das alte Rechteck)")
r, kl, zu, tr, t = lauf([(False, 0, None, "")] * 4, mit_beweis=False, sichtbar_ab_klick=1)
check(kl == [0, 1, 2, 3], "ohne Beweis (Polar) bleibt noch_offen ohne Wirkung — Verhalten wie vor MT1")

# _aendern_beweis wirklich ausführen (Prüfer HINWEIS: bisher nur Textsuche)
ns["_api_lesen"] = lambda path, exp: {"positionen": [{"ticket": 77, "sl": 100.0, "tp": 200.0}]}
ns["_mt5_journal_zeilen_tag"] = lambda dp, tage, n: []
b = ns["_aendern_beweis"]("p", 1, 77, 100.0, 200.0, 2, "C:/daten")
check(b(0)[0] == "api_ok", "_aendern_beweis: Position trägt SL/TP → api_ok")
ns["_api_lesen"] = lambda path, exp: {"positionen": []}
check(b(0)[0] == "weg", "_aendern_beweis: Position nicht mehr offen → weg")
ns["_api_lesen"] = lambda path, exp: {"positionen": [{"ticket": 77, "sl": 0.0, "tp": 0.0}]}
ns["_mt5_journal_zeilen_tag"] = lambda dp, tage, n: ["LL\t0\t10:00:05.120\tTrades\t'1': failed modify #77 buy 1 NAS100 -> sl: 100, tp: 200 [Invalid stops]"]
check(b(10 * 3600 + 4) == ("abgelehnt", "Invalid stops"), "_aendern_beweis: API ohne Werte, Journal lehnt ab → abgelehnt mit Grund")
ns["_api_lesen"] = lambda path, exp: {"fehler": "IPC"}
check(b(10 * 3600 + 400)[0] is None, "_aendern_beweis: API-Fehler, Journal-Zeile vor dem Klick → nichts")
b2 = ns["_aendern_beweis"]("p", 1, 77, 100.0, 200.0, 2, "")
check(b2(0) == (None, ""), "_aendern_beweis: ohne Journal-Ordner und ohne API → nichts (nie werfen)")

# 50 gewürfelte Abläufe: nach dem ersten Beleg (api_ok/weg/abgelehnt/gesendet) nie ein weiterer Klick
rnd = random.Random(11)
fehl = 0
for _ in range(50):
    szen = [(rnd.random() < 0.15, rnd.uniform(0, 6), rnd.choice([None, None, "api_ok", "gesendet", "abgelehnt", "weg"]), "x") for _i in range(4)]
    r, kl, zu, tr, t = lauf(szen)
    # sichtbar ist ein Beleg nur, wenn er vor dem letzten Blick im Fenster liegt (Takt 0,25 s → bis AENDERN_BEWEIS_S − 0,25)
    erster = next((i for i in kl if szen[i][2] and szen[i][1] <= ns["AENDERN_BEWEIS_S"] - 0.25), None)
    if erster is not None and kl[-1] != erster:
        fehl += 1
    if r.get("ok") and r.get("beleg") not in ("api_ok", "weg"):
        fehl += 1
check(fehl == 0, f"50 gewürfelte Abläufe: nach einem Beleg kein weiterer Klick ({fehl} Verstöße)")

# 3) Einbau
sk = block("_sltp_klicken")
check("def _sltp_klicken(w, ticket, symbol, sl_text, tp_text, trail, anker_pfad=None, beweis=None):" in BOT and "return aendern_kaskade((" in sk
      and "beweis, _dialog_zu, _ergebnis_zu, _esc, trail, noch_offen=lambda: _fenster_sichtbar(dlg))" in sk, "_sltp_klicken nutzt die Kaskade mit Beweis")
check("if _fenster_sichtbar(dlg):" in sk, "Ergebnis-Seite nur schließen, wenn Win32 sie sichtbar meldet")
nz = block("_sltp_nachziehen")
check("beweis = _aendern_beweis(path, expected, p[\"ticket\"], sl, tp, digits, _dp)" in nz and ", beweis=beweis)" in nz
      and 'if k and k.get("abgelehnt"):' in nz, "Nachziehen: Beweis + längere Pause nach einer Ablehnung")
check("beweis=_aendern_beweis(path, expected, p[\"ticket\"], sl, tp, digits, _dp))" in BOT, "Erst-Setzen (F9-SL/TP fehlte) ebenfalls mit Beweis")
check("mt5.order_send" not in BOT.split("def _aendern_beweis(")[1].split("\n\n\ndef ")[0], "Beweis nur lesend (kein order_send)")
check(re.search(r"^\s*[^#\n]*mt5\.order_send\(", BOT, re.M) is None, "order_bot.py ruft nirgends mt5.order_send auf (Finn: am Master nur Klicks)")
print()
print("FEHLER: " + ", ".join(FEHLER) if FEHLER else "alles grün")
sys.exit(1 if FEHLER else 0)
