#!/usr/bin/env python3
"""Selbsttest SKALA JE KONTO in Admin → Übersicht → Konten je Firma (20.10.2026, Finn 03:05 Dubai: „Diese blauen und grünen Balken
ersetzen … Wo steht der Account gerade bei der Balance? Gesamtwert? Wo auf dem Strahl befindet er sich?").
Aufruf:  python3 tools/selftest_admin_skala.py
Prueft: (1) app.py admin_skala_felder (rein rechnend, Helfer nachgebaut): Boden aus liq_regel_waehlen → liq_boden_kernwerte →
liq_konto_boden, Ziel aus accounts.ziel_usd vor Kernwerte-Regel (ap_regel_konto → zw_ziel) nur für challenge/phase1/phase2, Funded ohne
Ziel, Fehler → None; (2) prophos.html admSkalaInfo (echt per osascript/JXA): Lage auf dem Strahl in allen Zuständen — mittig, über Ziel,
nahe Boden (rot), Funded ohne Ziel (offen), ohne Balance (grau), ohne Boden (gespiegelt), ohne Größe; (3) Zeile/CSS/Mobil/Kopf-Summe im Text."""
import json
import os
import re
import shutil
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
APP = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# (1) Backend
def block(name):
    i = APP.index(f"\ndef {name}(") + 1
    return APP[i:APP.find("\n\n\n", i)]


ns = {"re": re}
exec(block("_wd_num"), ns)
AUFRUFE = []
ns.update({
    "_wd_konto_groesse": lambda a: a.get("_gr"),
    "liq_regel_waehlen": lambda regeln, firma, typ, gr: ({"firma": firma, "typ": typ}, ""),
    "liq_boden_kernwerte": lambda regel, a, typ, wd, kw: (regel, a, a.get("_gr")),
    "liq_konto_boden": lambda regel, a, gr, peak, start, rel: (AUFRUFE.append(("boden", start)) or (a.get("_boden"), a.get("_btext", "Größe − DD"), 4000, a.get("_bart", "statisch"))),
    "ap_regel_finden": lambda kw, firm: {"namen": [firm]} if firm != "Unbekannt" else None,
    "ap_regel_konto": lambda kr, a, bal: dict(kr, konto=a.get("ziel_pct_konto")),
    "zw_ziel": lambda regel, phase, bal: (AUFRUFE.append(("ziel", phase, regel.get("konto"))) or ((round(bal * 1.08, 2), 100000.0) if regel.get("konto") is None else (round(bal * 1.10, 2), 100000.0))),
})
exec(block("admin_skala_felder"), ns)
F = ns["admin_skala_felder"]
a = {"account_type": "phase2", "firm": "FundedNext", "starting_balance": 100000, "tv_balance": 103400, "_gr": 100000, "_boden": 94000}
z = F(a, [], [])
check(z == {"boden": 94000.0, "boden_art": "statisch", "boden_text": "Größe − DD", "ziel": 111672.0, "ziel_quelle": "regel"}, f"Phase 2: Boden aus Konto-Boden, Ziel aus Kernwerten (8 % auf die Balance) — {z}")
check(AUFRUFE[-1] == ("ziel", "phase2", None) and AUFRUFE[-2] == ("boden", 100000), "Ziel mit Phase des Kontos, Boden mit Start-Balance gerechnet")
z = F(dict(a, ziel_usd=108000), [], [])
check(z["ziel"] == 108000.0 and z["ziel_quelle"] == "konto", "accounts.ziel_usd geht vor der Regel")
z = F(dict(a, ziel_pct_konto={"phase2": 10}), [], [])
check(z["ziel"] == round(103400 * 1.10, 2) and AUFRUFE[-1][2] == {"phase2": 10}, "ziel_pct_konto läuft über ap_regel_konto in die Regel")
z = F(dict(a, account_type="funded", tv_balance=None), [], [])
check(z["ziel"] is None and z["ziel_quelle"] is None and z["boden"] == 94000.0, "Funded: kein $-Ziel, Boden bleibt")
z = F(dict(a, account_type="winning_days"), [], [])
check(z["ziel"] is None, "Winning Days: kein $-Ziel")
z = F(dict(a, firm="Unbekannt", _boden=None, _btext="kein Max Drawdown am Konto", _bart=None), [], [])
check(z["boden"] is None and z["boden_text"] == "kein Max Drawdown am Konto" and z["ziel"] is None, "ohne Regel/DD: Boden None mit Text, kein Ziel")
check(F({}, [], []) == {"boden": None, "boden_art": None, "boden_text": None, "ziel": None, "ziel_quelle": None} and F(None, [], []) == F({}, [], []), "leeres Konto → alles None")
ns["liq_konto_boden"] = lambda *x: (_ for _ in ()).throw(RuntimeError("kaputt"))
z = F(a, [], [])
check(z["boden"] is None and "RuntimeError" in z["boden_text"] and z["ziel"] == 111672.0, "Boden wirft → Boden None mit Grund, Ziel trotzdem")
check("r.update(admin_skala_felder(a_, _sk_regeln, _sk_kw))" in APP and "_sk_regeln, _sk_kw = _liq_regeln_laden(), _liq_kw_laden()" in APP, "admin_build_overview hängt die Felder je Zeile an (Regeln einmal je Abruf)")

# (2) Frontend admSkalaInfo
m = re.search(r"    function admSkalaInfo\(r\)\{\n.*?\n    \}", HTML, re.S)
check(bool(m), "admSkalaInfo gefunden")
FAELLE = [
    ("mittig", {"balance": 107654, "start": 100000, "boden": 94000, "ziel": 108000}),
    ("über Ziel", {"balance": 109500, "start": 100000, "boden": 94000, "ziel": 108000}),
    ("nahe Boden", {"balance": 95000, "start": 100000, "boden": 94000, "ziel": 108000}),
    ("unter Start, nicht nah", {"balance": 98500, "start": 100000, "boden": 94000, "ziel": 108000}),
    ("Funded ohne Ziel", {"balance": 151889, "start": 150000, "boden": 146000, "ziel": None, "type": "funded"}),
    ("ohne Balance", {"balance": None, "start": 100000, "boden": 94000, "ziel": 108000}),
    ("ohne Boden", {"balance": 101000, "start": 100000, "boden": None, "ziel": 108000}),
    ("ohne Größe", {"balance": 1000, "start": None, "size": None}),
    ("Funded unter Start", {"balance": 147000, "start": 150000, "boden": 146000, "ziel": None}),
]
if m and shutil.which("osascript"):
    js = (m.group(0) + "\nvar F = " + json.dumps([f[1] for f in FAELLE]) + ";\n"
          "JSON.stringify(F.map(function(r){ var i = admSkalaInfo(r); return [i.grau, i.grund, i.startPos, i.zielPos, i.pos, i.farbe, i.zahl, i.diff, i.diffFarbe, i.links, i.rechts] }))")
    r = subprocess.run(["osascript", "-l", "JavaScript", "-e", js], capture_output=True, text=True)
    try:
        v = json.loads(r.stdout.strip())
    except ValueError:
        v = None
    check(isinstance(v, list) and len(v) == len(FAELLE), f"admSkalaInfo läuft ({(r.stderr or '').strip()[:120]})")
    if isinstance(v, list) and len(v) == len(FAELLE):
        mi, ue, nb, us, fu, ob, obo, og, fus = v
        check(mi[0] is False and mi[3] == 100 and abs(mi[2] - 42.9) < 0.2 and abs(mi[4] - 97.5) < 0.2 and mi[5] == "gruen" and mi[6] == "107.654 → 108.000 $" and mi[7] == "fehlen 346 $",
              f'mittig: Start bei 42,9 %, Marke 97,5 % grün, „107.654 → 108.000 $" · „fehlen 346 $" — {mi}')
        check(ue[4] == 99 and ue[5] == "gruen" and ue[7] == "Ziel erreicht · +1.500 $" and ue[8] == "gruen", f"über Ziel: Marke geklemmt bei 99 %, grün, Ziel erreicht — {ue}")
        check(nb[5] == "rot" and nb[7] == "fehlen 13.000 $ · 5.000 $ unter Start" and nb[8] == "rot", f"nahe Boden (≤ Boden + ¼ der Spanne): rot — {nb}")
        check(us[5] == "amber" and us[7] == "fehlen 9.500 $ · 1.500 $ unter Start" and us[8] == "", f"unter Start, nicht nah am Boden: amber — {us}")
        check(fu[3] is None and fu[10] == 154000 and abs(fu[2] - 50) < 0.2 and fu[5] == "gruen" and fu[6] == "151.889 $" and fu[7] == "+1.889 $ über Start" and fu[8] == "gruen",
              f'Funded ohne Ziel: Spanne zum Boden nach rechts gespiegelt (offen bis 154.000), Start mittig, grün „+1.889 $ über Start" — {fu}')
        check(ob[0] is True and ob[1] == "keine Lesung" and ob[4] is None and ob[6] == "– → 108.000 $" and abs(ob[2] - 42.9) < 0.2, f"ohne Balance: grau, keine Marke, Start-Tick bleibt — {ob}")
        check(obo[0] is False and obo[9] == 92000 and abs(obo[2] - 50) < 0.2 and obo[5] == "gruen", f"ohne Boden: Spanne zum Ziel nach links gespiegelt (92.000), Start mittig — {obo}")
        check(og[0] is True and og[1] == "Kontogröße unbekannt", f"ohne Größe: grau mit Grund — {og}")
        check(fus[5] == "rot" and fus[7] == "−3.000 $ unter Start · Boden in 1.000 $" and fus[8] == "rot", f"Funded unter Start, im letzten Viertel über dem Boden: rot, Abstand zum Boden — {fus}")
else:
    print("… osascript fehlt — admSkalaInfo nur per Text geprüft")

# (3) Zeile, CSS, Mobil, Kopf
check("row.className = 'adm-row adm-sk' + (r.gp_plus ? ' is-plus' : '')" in HTML and "admSkalaHtml(r) +" in HTML and '<div class="adm-sk-zahlen"><b>${escapeHtml(i.zahl)}</b>' in HTML, "Zeile: Name/ID links, Skala Mitte, Zahlen rechts")
check("<small>Wert ${escapeHtml(admEur.format(wert))} · gezahlt ${escapeHtml(admEur.format(gez))}" in HTML, "Kettenwerte Wert · gezahlt bleiben als Kleintext")
check("adm-gp-spur\"><span style=\"width:${gezPct" not in HTML, "die alten Wert/gezahlt-Balken je Konto sind weg")
check("#dashboard-view .adm-sk-spur > b.is-gruen{background:var(--good)}" in HTML and ".adm-sk-spur > b.is-amber{" in HTML and ".adm-sk-spur > b.is-rot{" in HTML and ".adm-sk-spur.is-grau{" in HTML, "CSS: Marke grün/amber/rot, Spur grau ohne Lesung")
check("#dashboard-view .adm-gp-konten .adm-sk-skala{grid-column:1 / -1;order:3" in HTML, "Mobil: Skala volle Breite unter der Zeile, Zahlen rechts")
check("` · Balance ${balSum.toLocaleString('de-DE', { maximumFractionDigits: 0 })} $" in HTML, "Block-Kopf: Summe der gelesenen Balances")
check("if(i.start == null) return `<div class=\"adm-sk-skala\" title=\"${escapeHtml(i.grund)}\">" in HTML and "'keine Lesung' : 'offen'" in HTML, "Skala grau mit Grund, rechtes Ende offen ohne Ziel")

print()
if FEHLER:
    print(f"FEHLER ({len(FEHLER)}):")
    for f in FEHLER:
        print("  - " + f)
    sys.exit(1)
print("ALLES GRÜN")
