#!/usr/bin/env python3
"""Selbsttest TS-D2 „Topstep DLL = Tagesstopp“ (Finn 20.11.2026 auf die Frage zur Regel vom 14.10. „DLL-Treffer → konto_geblowt/Archiv?“: „Nein, nur
Tagesstopp.“). Daily-Loss-Limit-Treffer (Dropdown „DAILY_LOSS Violation“, Meldung „You Hit YourDaily Loss Limit“) → NICHT geblowt, NICHT archiviert
(weder konto_geblowt noch konto_verletzungen, die der PC-Tab archiviert), Code konto_tagesstopp mit Text „Topstep DLL erreicht – Tagesstopp …“;
Maximum Loss / Ineligible / Violation bleiben konto_geblowt (TS-D1). Teile: A Regeln · B K2 mit nachgebauter Sitzung · C Order-Weg (Quelltext-Vertrag)
· D PC-Tab-Vertrag (Text-Anfang = Schlüssel von sfIstTagesstopp). Alle Kennungen erfunden. Aufruf: python3 tools/selftest_tsd2_dll_tagesstopp.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


ob._warte = lambda *a, **k: None
ob._tsx_pause = lambda *a, **k: None
ob._puls_diagnose_senden = lambda spur=None, schritt="": None

EXT = "150KTC-SKU-V2-DLL-000000-00000002"
ALT = "150KTC-SKU-V2-DLL-000000-00000001"
R_OK, R_KASTEN = [700, 520, 120, 36], [440, 250, 720, 340]
DLL_TEXT = "You Hit YourDaily Loss Limit.Take a break and come back tomorrow."
MLL_TEXT = "You Hit YourMaximum Loss Limit.Setbacks are part of every trader's journey."

# ── A) Regeln ───────────────────────────────────────────────────────────────────────────────────────────────────────────────
print("── A) Regeln")
check(ob.tsx_konto_verletzung("DAILY_LOSS Violation") == "daily_loss", "Dropdown „DAILY_LOSS Violation“ → daily_loss (Erkennung unverändert)")
liste = [{"id": EXT, "hinweis": "DAILY_LOSS Violation"}, {"id": ALT, "hinweis": "MAXIMUM_LOSS Violation"},
         {"id": "150KTC-SKU-V2-DLL-000000-00000003", "ineligible": True}]
v = ob.tsx_verletzungen_aus_liste(liste)
check(EXT not in v and v.get(ALT, {}).get("art") == "maximum_loss" and "150KTC-SKU-V2-DLL-000000-00000003" in v,
      f"konto_verletzungen (→ Archiv im PC-Tab): DLL fehlt, MLL + Ineligible bleiben ({sorted(v)})")
check(ob.tsx_blow_dialog_verletzung({"art": "daily_loss", "konto": EXT, "text": "x"}) == {}, "DLL-Meldung mit voller Kennung → keine Verletzung (kein Archiv)")
check(EXT in ob.tsx_blow_dialog_verletzung({"art": "maximum_loss", "konto": EXT, "text": "x"}), "MLL-Meldung mit voller Kennung → Verletzung wie bisher")

for res, aktiv, soll_g, soll_t, name in (
        ({"konto_hinweis": "DAILY_LOSS Violation"}, "", None, "liste", "Listen-Hinweis DLL am Ziel → Tagesstopp, nicht geblowt"),
        ({"konto_hinweis": "MAXIMUM_LOSS Violation"}, "", "liste", None, "Listen-Hinweis MLL am Ziel → geblowt"),
        ({"blow_dialog": {"art": "daily_loss", "konto": "", "text": DLL_TEXT}}, EXT, None, "dialog", "DLL-Meldung ohne Kennung, Ziel aktiv → Tagesstopp"),
        ({"blow_dialog": {"art": "maximum_loss", "konto": "", "text": MLL_TEXT}}, EXT, "dialog", None, "MLL-Meldung ohne Kennung, Ziel aktiv → geblowt"),
        ({"blow_dialog": {"art": "daily_loss", "konto": "", "text": DLL_TEXT}}, ALT, None, None, "DLL-Meldung ohne Kennung, anderes Konto aktiv → nichts"),
        ({"konto_hinweis": "DAILY_LOSS Violation", "blow_dialog": {"art": "maximum_loss", "konto": EXT, "text": MLL_TEXT}}, "", "dialog", None,
         "DLL-Hinweis + MLL-Meldung → MLL gewinnt (geblowt), kein Tagesstopp"),
        ({"ineligible": True, "konto_hinweis": "Ineligible"}, "", "liste", None, "Ineligible → geblowt wie bisher")):
    g = ob.tsx_geblowt_urteil(res, EXT, aktiv)
    t = ob.tsx_tagesstopp_urteil(res, EXT, aktiv)
    check(((g or {}).get("quelle") == soll_g if soll_g else g is None) and ((t or {}).get("quelle") == soll_t if soll_t else t is None),
          f"{name} (geblowt {g and g['quelle']}, tagesstopp {t and t['quelle']})")

res = {"konto_hinweis": "DAILY_LOSS Violation"}
g = ob._tsx_geblowt_merken(res, EXT, {"konto": {"aktiv": EXT}})
check(g is None and "konto_geblowt" not in res and res.get("konto_tagesstopp", {}).get("art") == "daily_loss",
      "_tsx_geblowt_merken: DLL → konto_tagesstopp gesetzt, konto_geblowt NICHT")
res = {"konto_hinweis": "MAXIMUM_LOSS Violation"}
ob._tsx_geblowt_merken(res, EXT, {"konto": {"aktiv": EXT}})
check(res.get("konto_geblowt", {}).get("art") == "maximum_loss" and "konto_tagesstopp" not in res, "_tsx_geblowt_merken: MLL → konto_geblowt wie bisher")
txt = ob.tsx_tagesstopp_text({"quelle": "dialog", "text": DLL_TEXT}, EXT)
check(txt.startswith(ob.TSX_TAGESSTOPP_TEXT) and ob.TSX_TAGESSTOPP_TEXT == "Topstep DLL erreicht – Tagesstopp" and "nicht archiviert" in txt,
      f"Text beginnt mit dem Schlüssel „Topstep DLL erreicht – Tagesstopp“ ({txt[:70]}…)")

# Prüfer 20.11.2026: zwei Meldungen offen (DLL + MLL) → MLL gewinnt, egal in welcher Reihenfolge
def _pp(t):
    return {"titel": t[:30], "text": t, "knoepfe": []}
check(ob.tsx_blow_dialog([_pp(DLL_TEXT), _pp(MLL_TEXT)])["art"] == "maximum_loss" and ob.tsx_blow_dialog([_pp(MLL_TEXT), _pp(DLL_TEXT)])["art"] == "maximum_loss"
      and ob.tsx_blow_dialog([_pp(DLL_TEXT)])["art"] == "daily_loss", "DLL- + MLL-Meldung zugleich → maximum_loss (beide Reihenfolgen), DLL allein → daily_loss")
# Prüfer 20.11.2026: kein Chrome-Neustart + 2. Versuch nach dem Tagesstopp (der Beweis wäre nach dem Schließen weg)
art_n = ob.neustart_entscheid({"code": "konto_tagesstopp", "gesendet": False, "retry_ok": True}, "tsv2", 10)
art_n = art_n[0]
check(art_n != "direkt" and "konto_tagesstopp" in ob.PULS_NEUSTART_NIE, f"neustart_entscheid(konto_tagesstopp) → kein Neustart ({art_n})")

# ── B) K2 mit nachgebauter Sitzung ──────────────────────────────────────────────────────────────────────────────────────────
print("── B) K2 mit nachgebauter Sitzung")
R_AUSL = [68, 4, 194, 34]


def popup(text):
    return {"role": "dialog", "titel": text[:30], "text": text[:160], "text_voll": text[:400], "rect": R_KASTEN, "cls": "box",
            "knoepfe": [{"text": "RESET ACCOUNT", "rect": [480, 520, 200, 36]}, {"text": "OK", "rect": R_OK}]}


def konto(nr, popups=None, verdeckt=None):
    zu = {"verdeckt": True, "oben": {"tag": "div", "text": verdeckt}} if verdeckt else {}
    return {"konto": {"aktiv": f"150K DLL Combine|{nr}", "kontonr": nr, "abgekuerzt": False, "rect": R_AUSL, "liste_offen": False, "zu": zu},
            "popups": popups or []}


class Sitz:
    def __init__(self, staende, antworten):
        self.staende, self.i, self.antworten, self.klicks = staende, 1, list(antworten), []

    def stand(self, opts=None):
        x = self.staende[min(self.i, len(self.staende) - 1)]
        self.i += 1
        return x

    def klick(self, rect, name, pruef=None, doppel=False):
        self.klicks.append((name, list(rect)))
        return self.antworten.pop(0) if self.antworten else False

    def taste(self, *a, **k):
        pass


def lauf(staende, antworten):
    s = Sitz(staende, antworten)
    trail = ob._StempelSpur()
    ok, code, msg, st, ex = ob._tsx_konto_sichern(s, EXT, staende[0], trail)
    return ok, code, msg, ex, s


# B1 anderes Konto aktiv, DLL-Meldung nennt das ZIEL → konto_tagesstopp (nicht geblowt, kein Archiv-Beweis in ex)
ok, code, msg, ex, s = lauf([konto(ALT, [popup(DLL_TEXT + f" Account: {EXT}")], "You Hit YourDaily Loss"), konto(ALT), konto(ALT)], [True])
check(not ok and code == "konto_tagesstopp" and msg.startswith(ob.TSX_TAGESSTOPP_TEXT) and not ex.get("blow_dialog")
      and EXT not in (ex.get("konto_verletzungen") or {}) and ex.get("konto_tagesstopp", {}).get("art") == "daily_loss",
      f"DLL-Meldung nennt das Ziel → konto_tagesstopp, kein blow_dialog/keine Verletzung ({code}: {msg[:60]})")
# B2 dasselbe mit MLL → konto_geblowt wie TS-D1
ok, code, msg, ex, s = lauf([konto(ALT, [popup(MLL_TEXT + f" Account: {EXT}")], "You Hit YourMaximum Loss"), konto(ALT), konto(ALT)], [True])
check(not ok and code == "konto_geblowt" and "Konto hat MLL erreicht (TopstepX-Dialog)" in msg, f"MLL-Meldung nennt das Ziel → konto_geblowt ({code})")
# B3 Ziel aktiv (Einstieg wie nach Lade-Schirm) + DLL-Meldung ohne Kennung → konto_tagesstopp
ok, code, msg, ex, s = lauf([konto(EXT, [popup(DLL_TEXT)]), konto(EXT), konto(EXT)], [True])
check(not ok and code == "konto_tagesstopp" and msg.startswith(ob.TSX_TAGESSTOPP_TEXT) and not ex.get("blow_dialog") and len(s.klicks) == 1,
      f"Ziel aktiv + DLL-Meldung → geschlossen, konto_tagesstopp ({code})")
# B4 Ziel aktiv + MLL-Meldung ohne Kennung → konto_geblowt (TS-D1 unverändert)
ok, code, msg, ex, s = lauf([konto(EXT, [popup(MLL_TEXT)]), konto(EXT), konto(EXT)], [True])
check(not ok and code == "konto_geblowt" and "MLL" in msg, f"Ziel aktiv + MLL-Meldung → konto_geblowt ({code})")
# B4b Ziel aktiv, offene Liste dieses Laufs führt es als MAXIMUM_LOSS, dazu eine DLL-Meldung ohne Kennung → geblowt (nicht nur Tagesstopp)
st_l = konto(EXT, [popup(DLL_TEXT)])
st_l["konto"].update(liste_offen=True, liste=[{"id": EXT, "hinweis": "MAXIMUM_LOSS Violation"}])
ok, code, msg, ex, s = lauf([st_l, st_l, konto(EXT), konto(EXT)], [True])
check(not ok and code == "konto_geblowt" and EXT in (ex.get("konto_verletzungen") or {}), f"Liste MLL am Ziel + DLL-Meldung → konto_geblowt ({code}: {msg[:60]})")
# B5 DLL-Meldung für ein ANDERES (vorgewähltes) Konto → schließen, normal zum Ziel wechseln
ok, code, msg, ex, s = lauf([konto(ALT, [popup(DLL_TEXT)], "You Hit YourDaily Loss"), konto(ALT), konto(ALT), konto(ALT), konto(EXT), konto(EXT)],
                            [True, True])
check(ok and len(s.klicks) == 2 and not ex.get("blow_dialog") and not ex.get("konto_tagesstopp"),
      f"DLL-Meldung des vorgewählten Kontos → schließen, Ziel wechseln, Ziel unberührt ({code})")

# ── C) Order-Weg + Aufrufer (Quelltext-Vertrag) ─────────────────────────────────────────────────────────────────────────────
print("── C) Order-Weg")
src = open(ob.__file__, encoding="utf-8").read()
i_t = src.index('if order and isinstance(res.get("konto_tagesstopp"), dict):')
check(i_t < src.index("return _tsx_k3_probe(s, st, order, res, trail, raus, order_cmd)", i_t)
      and 'raus("konto_tagesstopp", tsx_tagesstopp_text(res["konto_tagesstopp"], ext, "nichts platziert"), "konto_tagesstopp")' in src[i_t:i_t + 900],
      "Order-Weg: Tagesstopp beendet VOR der Ticket-Probe mit Code + Schritt konto_tagesstopp")
check('"konto_tagesstopp" if c2 == "konto_tagesstopp" else "konto"' in src and '"blow_dialog", "konto_tagesstopp")' in src,
      "K2-Aufrufer: konto_tagesstopp als eigener Schritt + Feld weitergereicht")

# ── D) PC-Tab-Vertrag ───────────────────────────────────────────────────────────────────────────────────────────────────────
print("── D) PC-Tab-Vertrag (sfIstTagesstopp)")
js_rx = re.compile(r"Topstep DLL erreicht – Tagesstopp")   # = prophos.html sfIstTagesstopp (gleiche Form wie dort)
im_tab = "Nichts platziert · " + txt                       # Prüfer 20.11.2026: fehler() im Tab setzt das davor
gekuerzt = im_tab[:120] + " … " + im_tab[-60:]              # sfMelden kürzt auf Anfang + Ende
html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("/Topstep DLL erreicht – Tagesstopp/.test(String(sf.msg || '') + ' ' + String(sf.grund || ''))" in html, "prophos.html nutzt dieselbe Regex")
check(js_rx.search(txt) and js_rx.search(gekuerzt) and not js_rx.search("Konto-Auslöser verdeckt ('You Hit YourDaily Loss') — Dialog offen?"),
      "der Text (auch gekürzt) trifft den Schlüssel des PC-Tabs, ein normaler Konto-Fehler nicht")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER: {FEHLER}")
sys.exit(1 if FEHLER else 0)
