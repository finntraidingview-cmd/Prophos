#!/usr/bin/env python3
"""Selbsttest CF1 (23.11.2026, Master nach NV3: Marco Topstep …7245, Plan 28789882 — Versuch 1 „Contract-Feld nicht gedrückt (Klick ohne Beweis)",
danach Puls-Chrome-Neustart, Prophos-Tab samt Antwort weg, Trade ohne Hedge). Geprüft ohne Chrome/Netz/Order:
  * neustart_entscheid: Code 'contract' startet das Puls-Chrome NIE neu (wie ticket/konto)
  * _tsx_k3_contract: erster Klick ohne Beweis → neu lesen, Überlagerungen wegräumen, zweiter Klick mit Beweis → weiter wie immer;
    zweimal ohne Beweis → derselbe Abbruchtext wie bisher; Überlagerung ohne Schließ-Weg → Abbruch mit Grund, kein zweiter Klick
Aufruf: python3 tools/selftest_cf1_contract_feld.py   Kennungen erfunden."""
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def erg(**k):
    d = {"ok": False, "code": "", "msg": "", "schritt": "", "trail": "x", "gesendet": False, "retry_ok": True}
    d.update(k)
    return d


E = ob.neustart_entscheid
a, g, _ = E(erg(code="contract", schritt="ticket", msg="Contract-Feld nicht gedrückt (Klick ohne Beweis) — nichts getan."), "tsv2", 20.0)
check(a == "nein" and "contract" in g, f"Code 'contract' → kein Chrome-Neustart ({a}, {g})")
check(E(erg(code="knopf", schritt="knopf"), "tsv2", 20.0)[0] == "direkt", "andere Fehler vor dem Klick (knopf) bleiben wie bisher → direkt")
check("contract" in ob.PULS_NEUSTART_NIE_VOR_KLICK and {"ticket", "konto", "konto_nicht_erreicht"} <= ob.PULS_NEUSTART_NIE_VOR_KLICK,
      "PULS_NEUSTART_NIE_VOR_KLICK: contract dazu, alte Codes bleiben")

FELD = [400, 150, 220, 30]


class Sitzung:
    """TopstepX-Attrappe: Klick aufs Contract-Feld gelingt erst ab dem n-ten Versuch (vorher: am Punkt liegt nicht das Feld)."""

    def __init__(self, ok_ab=2):
        self.ok_ab, self.klicks, self.feld_klicks, self.getippt, self.wert = ok_ab, [], 0, [], "MNQZ26"

    def stand(self, opts=None):
        return {"ticket": {"contract": {"rect": list(FELD), "zu": {}, "fokus": True, "wert": self.wert, "offen": bool(self.getippt) and self.wert != "NQZ26"},
                           "vorschlaege": [{"code": "NQZ26", "rect": [400, 190, 220, 28], "code_rect": [430, 194, 60, 20], "zu": {}}]},
                "titel": "NQZ26", "popups": []}

    def klick(self, r, n, toast_ok=False, pruef=None):
        self.klicks.append((n, bool(pruef)))
        if n == "Contract-Feld":
            self.feld_klicks += 1
            return self.feld_klicks >= self.ok_ab
        if n.startswith("Contract "):
            self.wert = "NQZ26"
            return True
        return True

    def fokus_im(self, r, n, versuche=3):
        return True

    def taste(self, k, modifiers=0):
        pass

    def tippen(self, t):
        self.getippt.append(t)


def lauf(sitz, ueber=None):
    alt = {n: getattr(ob, n) for n in ("_warte", "_tsx_pause", "_tsx_fokus_exakt", "_cdp_esc", "_tsx_ueberlagerung_weg")}
    aufrufe = []
    ob._warte = lambda *a, **k: None
    ob._tsx_pause = lambda *a, **k: None
    ob._tsx_fokus_exakt = lambda *a, **k: True
    ob._cdp_esc = lambda s, st, trail, grund: trail.append("Esc: " + grund)
    ob._tsx_ueberlagerung_weg = lambda s, st, trail: (aufrufe.append(1) or (st, ueber))
    trail = []
    try:
        r = ob._tsx_k3_contract(sitz, sitz.stand(), "nq", trail)
    finally:
        for n, f in alt.items():
            setattr(ob, n, f)
    return r, trail, aufrufe


s1 = Sitzung(ok_ab=2)
r1, t1, u1 = lauf(s1)
check(r1[0] is True and r1[4] == "NQZ26" and s1.feld_klicks == 2 and u1 == [1] and s1.getippt == ["nq"]
      and any("zweiter Versuch" in x for x in t1) and all(p for n, p in s1.klicks if n == "Contract-Feld"),
      f"1. Klick ohne Beweis → Überlagerungen weg, 2. Klick mit Beweis → Contract gewählt ({r1[:3]}, {t1})")
s2 = Sitzung(ok_ab=9)
r2, t2, u2 = lauf(s2)
check(r2[0] is False and r2[1] == "contract" and r2[2] == "Contract-Feld nicht gedrückt (Klick ohne Beweis) — nichts getan." and s2.feld_klicks == 2
      and not s2.getippt, f"zweimal ohne Beweis → Abbruch mit dem bisherigen Text, nichts getippt ({r2[2]})")
s3 = Sitzung(ok_ab=9)
r3, t3, u3 = lauf(s3, ueber="Dialog ohne Text offen (…) — kein eindeutiger Schließen-Knopf, nichts geklickt")
check(r3[0] is False and r3[1] == "contract" and r3[2].startswith("Contract-Feld nicht gedrückt (Klick ohne Beweis) — nichts getan.")
      and "kein eindeutiger Schließen-Knopf" in r3[2] and s3.feld_klicks == 1, f"Überlagerung ohne Schließ-Weg → Abbruch mit Grund, kein 2. Klick ({r3[2]})")
s4 = Sitzung(ok_ab=1)
r4, t4, u4 = lauf(s4)
check(r4[0] is True and s4.feld_klicks == 1 and u4 == [], "erster Klick mit Beweis → wie bisher, keine Überlagerungs-Prüfung")
print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
