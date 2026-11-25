#!/usr/bin/env python3
"""Selbsttest FK1 Frontend (Finn 25.11.2026: geblowte FTMO-Futures-Challenges verlängern sich alle 30 Tage weiter → „Abo kündigen" in „Braucht dich").
Echte Funktionen aus prophos.html in JavaScriptCore: tplBraucht-Zeile (art 'abo'), tplBdLabel (≤ 3 Tage rot, sonst gelb), tplBdGrau
(„verlängert sich am TT.MM."), tplBdAktion (Knopf „✓ gekündigt", data-tpl-abo), fk1Datum; dazu Quelltext-Checks (Klick → POST, Schreibsperre).
Backend (fk1_verlaengerung/fk1_faelle, Route): tools/selftest_fk1_ftmo_kuendigen.py.
Aufruf:  python3 tools/selftest_fk1_braucht_dich.py"""
import json
import os
import subprocess
import sys
import tempfile

HTML = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def stueck(start, ende):
    i = HTML.index(start)
    return HTML[i:HTML.index(ende, i + len(start))]


lab = stueck("  function tplBdLabel(z){", "  // Konto kurz wie in Geplant/Zu bestätigen")
akt = stueck("  function tplBdAktion(z){", "  // Eine Zeile Klartext, was zu tun ist")
grau = stueck("  function tplBdGrau(z, l, wer){", "  window._tplBraucht = ")
fd = stueck("  const fk1Datum = ", "\n")
js = ("const escapeHtml = s => String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/\"/g,'&quot;');\n"
      "const apBlowText = t => t; const TPL_GRUND_WORT = {}; const _tplNeu = new Map();\n" + fd + "\n" + lab + akt + grau +
      "\nconst Z = d => Object.assign({ art: 'abo', firma: 'FTMO Futures', konto: '50k FTMO110764 → Challenge', typ: 'challenge', ende4: '0764', abo: 'k1',"
      " text: 'Abo kündigen', tun: 'x' }, d);\n"
      "const a = Z({ aboRot: false, aboTage: 12, aboAm: '2026-12-07' }), b = Z({ aboRot: true, aboTage: 2, aboAm: '2026-11-27' }), c = Z({ aboRot: true, aboTage: 0, aboAm: '2026-11-25' });\n"
      "const la = tplBdLabel(a), lb = tplBdLabel(b);\n"
      "print(JSON.stringify({ la, lb, ga: tplBdGrau(a, la, 'Julian'), gb: tplBdGrau(b, lb, 'Julian'), gc: tplBdGrau(c, tplBdLabel(c), 'Julian'),"
      " ka: tplBdAktion(a), kl: tplBdAktion(Object.assign({}, a, { lauf: { laeuft: true } })), d1: fk1Datum('2026-12-07'), d2: fk1Datum('') }));\n")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
p = subprocess.run([JSC, d.name], capture_output=True, text=True)
os.unlink(d.name)
try:
    r = json.loads(p.stdout.strip().splitlines()[-1])
except Exception:
    r = {}
    print(p.stdout, p.stderr)
check(r.get("la") == {"w": "Abo kündigen", "ton": "gelb", "r": 9}, "Label „Abo kündigen“ gelb bei > 3 Tagen")
check(r.get("lb") == {"w": "Abo kündigen", "ton": "rot", "r": 0}, "Label rot und oben bei ≤ 3 Tagen")
check(r.get("ga") == "verlängert sich am 07.12. · im FTMO-Dashboard kündigen", f"Klartext „verlängert sich am TT.MM.“ → {r.get('ga')}")
check(r.get("gb", "").startswith("verlängert sich am 27.11. — in 2 Tagen") and r.get("gc", "").startswith("verlängert sich am 25.11. — heute"),
      "≤ 3 Tage: „in n Tagen“ / „heute“")
check('data-tpl-abo="k1"' in r.get("ka", "") and "✓ gekündigt" in r.get("ka", "") and "speichert" in r.get("kl", ""), "Knopf „✓ gekündigt“ (data-tpl-abo), während des Speicherns gesperrt")
check(r.get("d1") == "07.12." and r.get("d2") == "?", "fk1Datum")

# ── Quelltext ──
br = stueck("  function tplBraucht(D, ids){", "  // FK1: Fälle laden")
check("art: 'abo'" in br and "add(f.user_id, f.person," in br and "window._fk1" in br and "fk1Laden()" in br,
      "tplBraucht: je Fall eine Zeile bei SEINER ID (add → ID-Karte), lädt gedrosselt")
ld = stueck("  async function fk1Laden(erzwingen){", "  window._fk1 = _fk1")
check("/konto/abo-kuendigen?alle=1" in ld and "10 * 60000" in ld and "tplSpaeter()" in ld, "Laden: GET alle=1, höchstens alle 10 min, zeichnet bei Änderung neu")
kl = stueck("    const ab = e.target.closest('[data-tpl-abo]')", "    const ba = e.target.closest('[data-tpl-blowarch]')")
check("method: 'POST'" in kl and "/konto/abo-kuendigen" in kl and "konto_id: kid" in kl and "_fk1.faelle = (_fk1.faelle || []).filter" in kl,
      "Klick ✓ gekündigt → POST /konto/abo-kuendigen, Zeile sofort weg; Fehler → Knopf zurück + Toast")
check("'[data-tpl-abo]'" in stueck("    const PR_SCHREIB = [", "    ]"), "Schreibsperre für Nur-Lese-Logins kennt den Knopf")
check("generisch" not in kl and "openModal" not in kl, "kein Modal, eigener Zweig im bestehenden tplRoot-Handler")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)
