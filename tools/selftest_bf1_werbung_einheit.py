#!/usr/bin/env python3
"""Selbsttest BF1 (24.11.2026, Finn: „Black-Friday-Banner konnten wir früher wegklicken, geht gerade nicht mehr — deswegen die ganzen
Fehler"). Kein Chrome, kein Netz, keine Order.

Aufruf:  python3 tools/selftest_bf1_werbung_einheit.py
Prüft:
 (1) CDP_WERBUNG_JS und CDP_EINHEIT_MENUE_JS sind gültiges JavaScript (macOS osascript, sonst übersprungen);
 (2) Werbe-Blick: benanntes X bis 96 px (quadratisch), namenlose X weiter ≤ 60 px, Hinweis-Karten (HintWizard) nur MIT Werbetext;
 (3) Einheiten-Regeln: „Reward $"/„Risk $" = Geld, „Reward % balance"/„% price" = andere Einheit, nie Geld;
 (4) cdp_einheit_wahl mit dem neuen Menü (Price · Ticks · % price · Reward $ · Reward % balance) → genau „Reward $";
 (5) _cdp_einheit_auf_dollar mit Attrappe: ein Klick auf den Wähler, ein Klick auf das TEXT-Rechteck von „Reward $", Beweis über die
     Beschriftung „Take profit $"; ohne Beweis kein zweiter Anlauf.
Die DOM-Seite (Modal 72-px-X, Copilot-Hinweis, Menü ohne Rolle, Gegenproben) wurde am 24.11.2026 im Browser-Nachbau geprüft und der
neue Werbe-Blick live auf pc-xc5c52 nur lesend ausgewertet (alt [], neu = Black-Friday-Modal mit X [1299,93,72,72])."""
import json
import os
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HIER), "mt5-copier"))
import order_bot as ob  # noqa: E402

FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# (1) Syntax
if shutil.which("osascript"):
    for n in ("CDP_WERBUNG_JS", "CDP_EINHEIT_MENUE_JS"):
        r = subprocess.run(["osascript", "-l", "JavaScript", "-e", "new Function(" + json.dumps("return " + getattr(ob, n)) + "); 'OK'"],
                           capture_output=True, text=True)
        check(r.stdout.strip() == "OK", f"{n} ist gültiges JavaScript ({(r.stderr or r.stdout).strip()[:100]})")
else:
    print("· Syntax-Prüfung übersprungen (kein osascript)")

# (2) Werbe-Blick: Regeln stehen im JS
W = ob.CDP_WERBUNG_JS
check("q.width > 96 || q.height > 96" in W and "Math.abs(q.width - q.height) > 16" in W and "if (!benanntKopf ||" in W,
      "benanntes X bis 96 px nur quadratisch, sonst nicht")
check("if (q.width > 60 || q.height > 60) {" in W and "if (!benanntKopf ||" in W, "über 60 px nur über den Benannt-Zweig (namenlose X bleiben ≤ 60 px)")
check("var benanntKopf = /\\bclose\\b|schlie(ß|ss)en|\\bdismiss\\b/i.test((e.getAttribute('aria-label') || '') + ' ' + (e.getAttribute('title') || ''))" in W,
      "großes X nur über aria-label/title mit Wortgrenze (nie Text wie „Offer closes in“, Prüfer)")
check(W.index("NIE.test(w) || XTABU.test(w)") < W.index("q.width > 60 || q.height > 60"),
      "Kauf-/Angebots-/Panel-Wörter werden vor der Größen-Ausnahme verworfen")
check("[data-role=\"hint\"],[data-qa-id*=\"HintWizard\"]" in W and "if (n >= 1 && k.b.matches && k.b.matches(HINT)) n += 1;" in W,
      "Hinweis-Karte zählt nur MIT einem Werbe-Merkmal (+1), ohne Werbetext bleibt sie stehen")
check("elementFromPoint" in W and W.index("var oben = document.elementFromPoint") > W.index("Math.abs(q.width - q.height)"),
      "verdecktes X weiter ausgeschlossen (oberstes Element am Mittelpunkt)")

# (3) Einheiten-Regeln
for t in ("$", "USD", "Reward $", "Risk $", "reward $"):
    check(bool(ob.CDP_RX_EINHEIT_GELD.search(t)) and not ob.CDP_RX_EINHEIT_ANDERE.search(t), f"„{t}“ ist Geld")
for t in ("Reward % balance", "Risk % balance", "% price", "Price", "Ticks", "%"):
    check(not ob.CDP_RX_EINHEIT_GELD.search(t) and bool(ob.CDP_RX_EINHEIT_ANDERE.search(t)), f"„{t}“ ist andere Einheit, nie Geld")
for t in ("PAAPEX000000000001USD", "5.00 USD", "Get 60% off"):
    check(not ob.CDP_RX_EINHEIT_GELD.search(t), f"„{t}“ ist kein Geld-Eintrag")

# (4) Auswahl im neuen Menü
NEU = [{"text": "Price", "rect": [1059, 435, 32, 16]}, {"text": "Ticks", "rect": [1059, 469, 32, 16]},
       {"text": "% price", "rect": [1059, 501, 47, 16]}, {"text": "Reward $", "rect": [1059, 533, 60, 16]},
       {"text": "Reward % balance", "rect": [1059, 565, 118, 16]}]
e, grund, _t = ob.cdp_einheit_wahl(NEU)
check(e is not None and e["text"] == "Reward $" and not grund, f"neues TP-Menü → genau „Reward $“ ({grund!r})")
SL = [dict(x, text=x["text"].replace("Reward", "Risk")) for x in NEU]
e2, g2, _t = ob.cdp_einheit_wahl(SL)
check(e2 is not None and e2["text"] == "Risk $", f"neues SL-Menü → genau „Risk $“ ({g2!r})")
e3, g3, _t = ob.cdp_einheit_wahl([x for x in NEU if x["text"] != "Reward $"])
check(e3 is None and "0×" in g3, f"ohne Geld-Eintrag nichts gewählt ({g3!r})")
e4, g4, _t = ob.cdp_einheit_wahl(NEU + [{"text": "USD", "rect": [1200, 600, 30, 16]}])
check(e4 is None and "2×" in g4, f"zwei Geld-Einträge → nichts gewählt ({g4!r})")
M = ob.CDP_EINHEIT_MENUE_JS
check("var weg='rolle';if(!out.length){weg='text';" in M and "g.z.length<2" in M and "r.width>500||r.height>500" in M,
      "Text-Weg nur ohne Rollen-Treffer, mindestens zwei Zeilen, Menü höchstens 500×500 px")
check("sb2(e)" in M and "opacity==='0'" in M and "r.right<=innerWidth" in M, "Text-Weg: Deckkraft 0 / außerhalb des Bilds zählen nicht (Prüfer)")
check("var q=x.b.getBoundingClientRect()" in M, "Text-Weg meldet das Rechteck des TEXTES (nicht die Zeilenmitte mit dem ⓘ-Knopf)")

# (4b) Gruppen-Filter des Text-Wegs (Prüfer BF1): nur neu, nahe am Wähler, Geld + andere Einheit je Gruppe
WAEHLER = [1059, 417, 124, 18]
NEU_G = [dict(x, g=1, gr=[1059, 435, 164, 172]) for x in NEU]
UMSCH = [{"text": "$", "rect": [1300, 460, 10, 16], "g": 2, "gr": [1290, 455, 60, 26]},
         {"text": "%", "rect": [1320, 460, 10, 16], "g": 2, "gr": [1290, 455, 60, 26]}]
f1 = ob.cdp_einheit_text_gruppen(NEU_G + UMSCH, UMSCH, WAEHLER)
check([x["text"] for x in f1] == [x["text"] for x in NEU], "vorher schon sichtbare Gruppe („$ | %“-Umschalter) fällt raus, das neue Menü bleibt")
e5, g5, _t = ob.cdp_einheit_wahl(ob.cdp_einheit_text_gruppen(UMSCH, UMSCH, WAEHLER))
check(e5 is None and "kein Menü offen" in g5, f"Menü nicht aufgegangen, nur der alte Umschalter → nichts gewählt ({g5!r})")
WEIT = [dict(x, gr=[100, 100, 164, 172]) for x in NEU_G]
check(ob.cdp_einheit_text_gruppen(WEIT, [], WAEHLER) == [], "Gruppe weit weg vom Wähler zählt nicht")
OHNE = [dict(x) for x in NEU_G if x["text"] in ("Reward $", "Reward % balance")][:1] + [dict(NEU_G[3], text="USD", rect=[1059, 560, 30, 16])]
check(ob.cdp_einheit_text_gruppen(OHNE, [], WAEHLER) == [], "Gruppe ohne zweite (andere) Einheit zählt nicht")
ROLLE = [{"text": "Ticks", "rect": [10, 10, 80, 30]}, {"text": "$", "rect": [10, 40, 80, 30]}]
check(ob.cdp_einheit_text_gruppen(ROLLE, ROLLE, WAEHLER) == ROLLE, "Rollen-Weg (ohne Gruppe) bleibt unverändert")

# (5) _cdp_einheit_auf_dollar mit Attrappe
alt_w = ob._warte
ob._warte = lambda *a, **k: None
try:
    def lauf(menue, beschriftung_danach):
        klicks, esc = [], []

        class S:
            def klick(self, rect, name, **k):
                klicks.append((list(rect), name))
                return True

            def lese_js(self, js, timeout=8):
                if js is not ob.CDP_EINHEIT_MENUE_JS:
                    return None
                return {"menues": 1, "eintraege": menue if klicks else UMSCH, "weg": "text"}   # vor dem Klick nur der Umschalter

            def stand(self, opts=None):
                if len(klicks) >= 2:
                    return {"ticket": {"tp": {"beschriftung": {"text": beschriftung_danach}, "einheit": None}}}
                return {"ticket": {"tp": {"beschriftung": {"text": "Take profit price", "rect": [1059, 417, 124, 18]}, "einheit": "price"}}}
        alt_esc = ob._cdp_esc
        ob._cdp_esc = lambda s, st, trail, grund: esc.append(grund)
        try:
            trail = []
            st0 = S().stand()
            s = S()
            st, ok, zusatz = ob._cdp_einheit_auf_dollar(s, st0, "tp", "Take profit", {}, trail)
        finally:
            ob._cdp_esc = alt_esc
        return ok, zusatz, klicks, esc, trail
    ok, zusatz, klicks, esc, trail = lauf(NEU_G + UMSCH, "Take profit $")
    check(ok and len(klicks) == 2 and klicks[1][0] == [1059, 533, 60, 16] and "Reward $" in klicks[1][1],
          f"Wähler + „Reward $“ (Text-Rechteck) geklickt, Beweis „Take profit $“ ({klicks}, {zusatz!r})")
    check(any("Einheit auf $ gestellt (bewiesen" in z for z in trail), "Spur „Einheit auf $ gestellt (bewiesen …)“")
    ok2, zusatz2, klicks2, esc2, trail2 = lauf(NEU_G + UMSCH, "Take profit price")
    check(not ok2 and len(klicks2) == 2 and "Beschriftung danach 'Take profit price'" in zusatz2,
          f"ohne Beweis kein zweiter Anlauf, ehrlicher Zusatz ({zusatz2!r})")
    ok3, zusatz3, klicks3, esc3, _tr = lauf(UMSCH, "Take profit price")
    check(not ok3 and len(klicks3) == 1 and "kein Menü offen" in zusatz3 and not esc3,
          "Menü geht nicht auf (nur der alte Umschalter sichtbar) → nur der Wähler-Klick, kein Klick aufs Ticket-„$“, kein Esc")
finally:
    ob._warte = alt_w

print()
print("ALLES OK" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
