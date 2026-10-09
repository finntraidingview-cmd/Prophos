#!/usr/bin/env python3
"""Selbsttest KONTO WEG NACH SEITEN-NEULADEN (09.10.2026, Terminal 2 — Finn über Master, Fall Mike Tradeify …1443: „Balance lesen“ endete mit
„Konto-Liste steht ohne eigenen Klick offen und bleibt es nach Esc“; nach dem eigenen Formular-Login stand das Ziel 0× in der Liste, der
zweite Blick fand die hängende Liste und brach ab). Geprüft mit nachgebauter Sitzung: hängende Liste → EINMAL Seite neu laden, dann
normal; Neuladen nicht möglich → wie bisher ehrlich raus; Ziel 0× → extra.liste_zu (Liste nach Esc wirklich zu?); _cdp_seite_neu_laden
ruft Page.reload und wartet auf ein aktives Konto; Frontend kontoWegFolge (archiveAccount 'blown', laufende → Überprüfen, Push) und die
Backend-Route /konto-weg/melden (Besitz-Prüfung, Text aus der DB). Alle Kennungen erfunden. Aufruf: python3 tools/selftest_konto_weg_neuladen.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HIER, "..", "mt5-copier"))
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


T1, T2, T3, ZIEL = "TDFYSL150100000001", "TDFYSL150100000002", "TDFYSL150100000003", "TDFYSL150100000009"
MAX = {"leiste": [56, 0, 1194, 38], "unter_leiste": 735, "max_knopf": {"rect": [1212, 0, 38, 38], "aria": "Restore panel"}}


class Sitz:
    """Puls-Chrome-Attrappe. haengt=True: eine Liste ist schon offen und Esc schließt sie nicht (Mike 09.10.2026). neu_laden() schließt sie."""
    ws = None

    def __init__(self, zeilen, haengt=False, esc_schliesst=True, ladbar=True):
        self.zeilen, self.offen, self.haengt, self.esc_schliesst, self.ladbar, self.spur = zeilen, haengt, haengt, esc_schliesst, ladbar, []
        self.neu = 0

    def stand(self, opts=None):
        e = [{"text": z + "USD", "rect": [78, 90 + 32 * i, 228, 32], "aktiv": i == 0} for i, z in enumerate(self.zeilen)]
        return {"konto": {"panel": "offen", "panel_lage": "maximiert", "schalter": {"rect": [72, 59, 199, 28]}, "aktiv": self.zeilen[0] + "USD",
                          "liste_offen": self.offen, "liste_voll": self.offen, "eintraege": e if self.offen else []}}

    def lese_js(self, a, timeout=8):
        if "innerText" in a:
            return False
        return {"frei": True, "was": ""} if "elementFromPoint" in a else dict(MAX)

    def werbung_weg(self, zwang=False):
        return 0

    def taste(self, k, modifiers=0):
        self.spur.append("Taste " + k)
        if not self.haengt and self.esc_schliesst:
            self.offen = False

    def klick(self, r, n, toast_ok=False, pruef=None, doppel=False):
        self.spur.append(n)
        if n == "Konto-Umschalter":
            self.offen = True
        elif n.startswith("Konto "):
            z = n.split(" ", 1)[1]
            self.zeilen, self.offen = [z] + [x for x in self.zeilen if x != z], False
        return True

    def neu_laden(self):
        if not self.ladbar:
            raise RuntimeError("weg")
        self.neu += 1
        self.spur.append("NEU")
        self.offen, self.haengt = False, False


def main():
    import order_bot as ob
    ob._warte = lambda *a, **k: None

    # 1) hängende Liste, Ziel steht im Login → einmal neu laden, dann normal gewählt
    s = Sitz([T1, ZIEL, T2], haengt=True)
    r = ob._cdp_konto_sichern(s, ZIEL, {}, [])
    check(r[0] is True and s.neu == 1 and s.spur.index("NEU") < s.spur.index("Konto-Umschalter"),
          f"hängende Liste → einmal Seite neu laden, dann eigener Umschalter-Klick und Wahl ({r[:3]}, {s.spur})")

    # 2) hängende Liste, Neuladen nicht möglich → wie bisher ehrlich raus, nichts gewählt
    s = Sitz([T1, ZIEL], haengt=True, ladbar=False)
    r = ob._cdp_konto_sichern(s, ZIEL, {}, [])
    check(r[0] is False and r[1] == "konto_nicht_erreicht" and "ohne eigenen Klick offen" in r[2] and not any(x.startswith("Konto T") for x in s.spur),
          f"Neuladen nicht möglich → alte Meldung, kein Eintrag gedrückt ({r[2][:80]})")

    # 3) hängt auch nach dem Neuladen → genau EIN Neuladen, dann raus
    class Klebt(Sitz):
        def neu_laden(self):
            self.neu += 1
            self.spur.append("NEU")
    s = Klebt([T1, T2], haengt=True)
    r = ob._cdp_konto_sichern(s, ZIEL, {}, [])
    check(r[0] is False and r[1] == "konto_nicht_erreicht" and s.neu == 1, f"hängt auch nach dem Neuladen → genau ein Neuladen, dann ehrlich raus ({s.neu})")

    # 4) eigene Liste, Ziel 0×, Esc schließt → liste_zu True; Esc schließt nicht → liste_zu False
    s = Sitz([T1, T2, T3])
    r = ob._cdp_konto_sichern(s, ZIEL, {}, [])
    check(r[4].get("liste_zu") is True and r[4].get("konto_treffer") in (0, None), f"Ziel 0×, Liste geht mit Esc zu → liste_zu True ({r[4]})")
    s = Sitz([T1, T2, T3], esc_schliesst=False)
    tr = []
    r = ob._cdp_konto_sichern(s, ZIEL, {}, tr)
    check(r[4].get("liste_zu") is False and any("kein Beleg für ein fehlendes Konto" in x for x in tr),
          f"Ziel 0×, Liste bleibt nach Esc offen → liste_zu False, Spur sagt es ({r[4].get('liste_zu')})")
    check(not ob.cdp_konto_weg(dict(r[4], konto_treffer=0, liste_aktiv=T1 + "USD", ziel_im_text=False), True, ZIEL)[0],
          "Befund aus einer Liste, die nach Esc offen bleibt → nie konto_weg")

    # 5) _cdp_seite_neu_laden mit CDP-Attrappe: Page.reload, wartet bis ein aktives Konto lesbar ist
    class WS:
        def __init__(self):
            self.rufe_n = []

        def rufe(self, m, p=None, timeout=5):
            self.rufe_n.append(m)
            return {}

    class C:
        def __init__(self):
            self.ws, self.n = WS(), 0

        def _seite_abwarten(self, sek):
            return True

        def _augen_laden(self):
            pass

        def lese_js(self, a, timeout=8):
            return None

        def stand(self, opts=None):
            self.n += 1
            return {"konto": {"aktiv": (T1 + "USD") if self.n >= 3 else ""}}
    c = C()
    orig_kachel = ob._cdp_kachel_weg
    ob._cdp_kachel_weg = lambda s_, t_: None
    try:
        st = ob._cdp_seite_neu_laden(c, {}, [], "Test")
    finally:
        ob._cdp_kachel_weg = orig_kachel
    check(c.ws.rufe_n[:1] == ["Page.reload"] and st["konto"]["aktiv"] == T1 + "USD" and c.n == 3,
          f"Neuladen: Page.reload, wartet auf aktives Konto ({c.ws.rufe_n}, {c.n})")

    class Kaputt(C):
        def __init__(self):
            super().__init__()

            class W2:
                def rufe(self, m, p=None, timeout=5):
                    raise RuntimeError("zu")
            self.ws = W2()
    check(ob._cdp_seite_neu_laden(Kaputt(), {}, [], "Test") is None, "Neuladen scheitert → None (zählt nie als Beleg)")

    # 6) Frontend + Backend am Quelltext
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    i = html.index("async function kontoWegFolge(")
    f = html[i:html.index("window._kontoWegFolge", i)]
    check("archiveAccount(id, 'blown')" in f and "isAccountArchived(id)" in f, "kontoWegFolge: vorhandener Archiv-Weg mit Grund blown, nicht doppelt")
    check(".update({ status: 'review', ended_at: nowIso }).eq('id', p.id).eq('status', 'open')" in f and "konto_weg: true" in f,
          "laufende Pläne des Kontos → Überprüfen mit final.konto_weg (Status-Guard open)")
    check("/konto-weg/melden" in f and "(accounts || []).find(a => String(a.id) === id); if(!acc) return false" in f,
          "nur eigene Konten, Push über die Backend-Route")
    check("if(r && !r.ok && tvV2KontoWegAntwort(r)){\n        await kontoWegFolge(acc.id, r, 'balance')" in html, "Balance lesen: konto_weg → kontoWegFolge")
    check("kontoWegFolge(p0.masterAccountId, r, 'endlesung')" in html and "kontoWegFolge(plan.masterAccountId, r, 'start')" in html,
          "Endlesung und Start: konto_weg → kontoWegFolge")
    app = open(os.path.join(HIER, "..", "app.py"), encoding="utf-8").read()
    j = app.index("def konto_weg_melden():")
    g = app[j:app.index("\n\n\n", j)]
    check('str(acc.get("user_id")) != uid' in g and "403" in g and "KONTO_WEG_PUSH_SPERRE_S" in g and 'd.get("text")' not in g,
          "Backend: nur eigenes Konto, Text aus der DB, je Konto höchstens einmal je Stunde")

    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 0 if not FEHLER else 1


if __name__ == "__main__":
    sys.exit(main())
