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

    def __init__(self, ok_ab=2, fremd_beim_klick="", fremd_alt="", spur_zeile=True):
        self.ok_ab, self.klicks, self.feld_klicks, self.getippt, self.wert = ok_ab, [], 0, [], "MNQZ26"
        self.fremd_beim_klick, self._fremd_fenster, self.spur_zeile, self.vorn, self._klick_grund = fremd_beim_klick, fremd_alt, spur_zeile, 0, ""

    def fremd_hinweis(self):
        # wie _AugenSitzung.fremd_hinweis: aus _fremd_fenster
        return f" Fenster '{self._fremd_fenster}' liegt über dem Puls-Chrome — immer im Vordergrund?" if self._fremd_fenster else ""

    def _win_vorn(self):
        self.vorn += 1
        return 1, ""

    def stand(self, opts=None):
        return {"ticket": {"contract": {"rect": list(FELD), "zu": {}, "fokus": True, "wert": self.wert, "offen": bool(self.getippt) and self.wert != "NQZ26"},
                           "vorschlaege": [{"code": "NQZ26", "rect": [400, 190, 220, 28], "code_rect": [430, 194, 60, 20], "zu": {}}]},
                "titel": "NQZ26", "popups": []}

    def klick(self, r, n, toast_ok=False, pruef=None):
        self.klicks.append((n, bool(pruef)))
        if n == "Contract-Feld":
            self.feld_klicks += 1
            if self.feld_klicks < self.ok_ab:
                if self.fremd_beim_klick:
                    self._fremd_fenster = self.fremd_beim_klick
                if self.spur_zeile:
                    self.spur.append("Contract-Feld: am Zielpunkt @3272,322 liegt nicht das Ziel ('span') [drin ja, klein NEIN] — kein Druck")
                return False
            return True
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
    ob._tsx_ueberlagerung_weg = lambda s, st, trail: (aufrufe.append(1) or (st, ueber))
    trail = ob._StempelSpur()                     # CF1c: wie im echten Lauf — jede Zeile mit „12.3s·" vorn
    sitz.spur = trail
    esc = []
    ob._cdp_esc = lambda s, st, trail, grund: (esc.append(grund), trail.append("Esc: " + grund))
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
check(r2[0] is False and r2[1] == "contract" and r2[2].startswith("Contract-Feld nicht gedrückt (Klick ohne Beweis) — nichts getan. Grund: ")
      and "liegt nicht das Ziel ('span')" in r2[2] and "[drin" not in r2[2] and s2.feld_klicks == 2 and not s2.getippt,
      f"zweimal ohne Beweis → bisheriger Text vorn + wahrer Grund aus der Spur, nichts getippt ({r2[2]})")
check(s1.vorn == 1 and any("leichter Weg" in x for x in t1) and any(str(x).endswith("Esc: Contract-Feld ohne Beweis") for x in t1),
      "CF1b leichter Weg: Esc, Puls-Chrome nach vorn, neu lesen, ein Klick")
s5 = Sitzung(ok_ab=9, fremd_beim_klick="Administrator: Windows PowerShell", spur_zeile=False)
r5, t5, u5 = lauf(s5)
check("Grund: Fenster 'Administrator: Windows PowerShell'" in r5[2], f"fremdes Fenster beim Klick, keine Spur-Zeile → Fenster in der Meldung ({r5[2]})")
s6 = Sitzung(ok_ab=9, fremd_alt="Altes Fenster eines früheren Klicks", spur_zeile=False)
r6, t6, u6 = lauf(s6)
check("Altes Fenster" not in r6[2] and "Grund:" not in r6[2], f"CF1c: veraltetes Fremdfenster aus einem älteren Klick → nie als Grund ({r6[2]})")
check("liegt nicht das Ziel ('span')" in r2[2], "CF1c: Grund aus der echten _StempelSpur (Zeitstempel vorn) kommt in die Meldung")
G = ob.klick_grund_kurz
check(G("Puls-Chrome kommt nicht in den Vordergrund (vorn: 'Explorer' 7, Klasse 'CabinetWClass', …)", "", [], "X") == "vorn 'Explorer', CabinetWClass"
      and G("", "", ["Y: weg", "X: am Punkt 'a' [b] — kein Druck"], "X") == "am Punkt 'a' — kein Druck" and G("", "", [], "X") == ""
      and G("", "", ["12.3s·X: am Punkt 'c' — kein Druck"], "X") == "am Punkt 'c' — kein Druck"
      and G("", " Fenster 'F' liegt über …", ["4.0s·X: Spur zuerst"], "X") == "Spur zuerst" and G("", " Fenster 'F' liegt über …", [], "X") == "Fenster 'F' liegt über …",
      "klick_grund_kurz: Vordergrund-Fenster zuerst, sonst die Spur-Zeile ohne [..], sonst leer")

# ── CF1b: Spur + Foto des 1. Versuchs vor dem Neustart ───────────────────────────────────────────────────────────────────────────
aus, fotos = [], []
r1 = erg(code="knopf", schritt="knopf", trail="0.1s·Start > 8.5s·Knopf nicht gedrückt (am Punkt 'div.hs-cta')")
ob._puls_mit_neustart("tsv2", lambda: ("", dict(r1)), lambda frist: ("", erg(ok=True, gesendet=True, bestaetigt=True, trail="2. ok")), None, "https://x/",
                      neustart=lambda spur, url: True, jetzt=lambda: 20.0, t0=0.0, ausgeben=aus.append, diagnose=lambda **k: None,
                      foto=lambda r: (fotos.append(r.get("code")) or ("pc-xxxxxx/2026-11-23/20261123-000000-abcdef", "")))
tr = str((aus[-1] if aus else {}).get("trail") or "")
check(fotos == ["knopf"] and "1. Versuch, Spur-Ende: 0.1s·Start > 8.5s·Knopf nicht gedrückt (am Punkt 'div.hs-cta')" in tr
      and "Fehlerfoto 1. Versuch → pc-xxxxxx/2026-11-23/20261123-000000-abcdef" in tr and tr.index("Fehlerfoto 1. Versuch") < tr.index("2. Versuch:"),
      f"Spur-Ende + Fehlerfoto des 1. Versuchs stehen in der Antwort, vor dem 2. Versuch ({tr[:300]})")
aus2 = []
ob._puls_mit_neustart("tsv2", lambda: ("", erg(ok=True)), lambda f: ("", {}), None, "https://x/", neustart=lambda s_, u: True, jetzt=lambda: 1.0, t0=0.0,
                      ausgeben=aus2.append, diagnose=lambda **k: None, foto=lambda r: (_ for _ in ()).throw(AssertionError("Foto ohne Neustart")))
check(len(aus2) == 1, "kein Neustart (ok) → kein Foto, Ausgabe wie bisher")
src = open(os.path.join(WURZEL, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
check(src.count('foto=lambda r: _fehlerfoto_sofort_begrenzt(') == 2, "beide Wege (Orbit, Topstep) fotografieren vor dem Neustart, mit Zeitgrenze")
# CF1c: knapp an der Frist → kein Foto, der 2. Versuch geht vor
aus3, fotos3 = [], []
ob._puls_mit_neustart("tsv2", lambda: ("", dict(r1)), lambda frist: ("", erg(ok=True, gesendet=True, bestaetigt=True, trail="2. ok")), None, "https://x/",
                      neustart=lambda spur, url: True, jetzt=lambda: 35.0, t0=0.0, ausgeben=aus3.append, diagnose=lambda **k: None,
                      foto=lambda r: (fotos3.append(1) or ("x", "")))
check(not fotos3 and "kein Fehlerfoto 1. Versuch: zu wenig Zeit" in str((aus3[-1] if aus3 else {}).get("trail") or ""),
      "CF1c: zu wenig Rest für Foto + 2. Versuch → kein Foto, Grund in der Spur")
# CF1c: Foto mit harter Zeitgrenze und eigenem Deckel-Schlüssel
import time as _t
alt_sf = ob._fehlerfoto_sofort
gerufen = []
ob._fehlerfoto_sofort = lambda weg, tab, code: (gerufen.append(weg), _t.sleep(2.0), ("spät", ""))[2]
try:
    t0_ = _t.time()
    b_, g_ = ob._fehlerfoto_sofort_begrenzt("tsxorder", "tsx", "contract", max_s=0.6)
    dauer_ = _t.time() - t0_
finally:
    ob._fehlerfoto_sofort = alt_sf
check(b_ is None and "nicht fertig" in g_ and dauer_ < 1.5 and gerufen == ["tsxorder_v1"],
      f"CF1c: hängendes Foto → nach der Grenze weiter, Deckel-Schlüssel tsxorder_v1 (≠ Endantwort) ({b_}, {g_}, {dauer_:.1f} s, {gerufen})")
s3 = Sitzung(ok_ab=9)
r3, t3, u3 = lauf(s3, ueber="Dialog ohne Text offen (…) — kein eindeutiger Schließen-Knopf, nichts geklickt")
check(r3[0] is False and r3[1] == "contract" and r3[2].startswith("Contract-Feld nicht gedrückt (Klick ohne Beweis) — nichts getan.")
      and "kein eindeutiger Schließen-Knopf" in r3[2] and s3.feld_klicks == 1, f"Überlagerung ohne Schließ-Weg → Abbruch mit Grund, kein 2. Klick ({r3[2]})")
s4 = Sitzung(ok_ab=1)
r4, t4, u4 = lauf(s4)
check(r4[0] is True and s4.feld_klicks == 1 and u4 == [], "erster Klick mit Beweis → wie bisher, keine Überlagerungs-Prüfung")
print("\n" + ("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER"))
sys.exit(1 if FEHLER else 0)
