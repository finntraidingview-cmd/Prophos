#!/usr/bin/env python3
"""Selbsttest KP3 (26.11.2026, Finn über den Master: „Kaufliste/Musterportfolio müssen HT-IDs und Emin-IDs unterscheiden, z. B. kauft Emin immer nur
50k-Konten“). Vorrat-Ziele + Kauf-Größe je Unternehmen (vorrat_ziele_gruppe), Variante (b): Emin 50k nur bei Futures (Lucid, FNF, FTMO Futures).
Ohne Netz: reine Funktionen per AST aus app.py (kompiliert die ganze Datei = Syntax-Check), kaufliste_app mit Stub für kapital_app, Frontend-Funktionen
(klVorlage, vrZieleListe, vrZielGruppeAktiv) in JavaScriptCore, SQL statisch. Aufruf: python3 tools/selftest_kp3_ziele_je_gruppe.py"""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import types

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(W, "sql", "2026-11-26_kp3_vorrat_ziele_gruppe.sql"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def zwischen(txt, a, b):
    i = txt.index(a)
    return txt[i:txt.index(b, i + len(a))]


# ── 1. reine Funktionen aus app.py ──
baum = ast.parse(SRC)
compile(baum, "app.py", "exec")
check(True, "app.py kompiliert")
ns = {"re": re}
for x in baum.body:
    if isinstance(x, ast.Assign) and any(getattr(t, "id", "") in ("VORRAT_ZG_FELDER", "VORRAT_TYPEN", "VORRAT_CFD_TYPEN", "VORRAT_STATUS",
                                                                    "VORRAT_STD_GROESSEN", "VORRAT2_RECHEN_STAND") for t in x.targets):
        exec(compile(ast.Module(body=[x], type_ignores=[]), "app.py", "exec"), ns)
for f in ("vorrat_ziele_fuer", "vorrat_uid_gruppe", "vorrat_groesse", "vorrat_bestand", "vorrat_rechnen", "_vr2_num", "vorrat_ziel_pruefen"):
    k = next((x for x in baum.body if isinstance(x, ast.FunctionDef) and x.name == f), None)
    check(k is not None, f"Funktion {f} in app.py")
    if k is not None:
        exec(compile(ast.Module(body=[k], type_ignores=[]), "app.py", "exec"), ns)
check(ns.get("VORRAT2_RECHEN_STAND", 0) >= 10, "RECHEN_STAND hochgezählt (neues Feld nachkauf.groesse, alte Läufe einmal neu)")

ZIELE = {
    "Lucid Trading": {"art": "plus_ueber_start", "typen": ["winning_days"], "von": 10000, "bis": 15000, "kauf_einheit": "150k", "kauf_groesse": 150000, "reihe": 8},
    "FundedNext": {"art": "groessen_summe", "typen": ["funded_cfd", "funded"], "von": 200000, "bis": 300000, "kauf_einheit": "100k", "kauf_groesse": 100000, "reihe": 5},
    "Tradeify": {"art": "plus_ueber_start", "typen": ["winning_days"], "von": 20000, "bis": 30000, "kauf_einheit": "150k Select", "kauf_groesse": 150000, "reihe": 1},
}
G_EMIN = "90c616f3-3ec1-49cb-b3ba-8a267d0a43df"
ZG = {G_EMIN: {"Lucid Trading": {"art": "plus_ueber_start", "typen": ["winning_days"], "von": 5000, "bis": 10000, "groessen": None, "kauf_einheit": "50k",
                                 "kauf_groesse": 50000}}}
DATEN = {"gruppen": [{"id": G_EMIN, "name": "Emin", "verwalter_id": "emin"}, {"id": "ht-g", "name": "Hermann Technologies", "verwalter_id": None}],
         "mitglieder": [{"user_id": "julian", "gruppe_id": G_EMIN}, {"user_id": "marc", "gruppe_id": "ht-g"}, {"user_id": "emin", "gruppe_id": G_EMIN}]}
fuer, ug_f = ns["vorrat_ziele_fuer"], ns["vorrat_uid_gruppe"]
UG = ug_f(DATEN, ZG)
check(UG == {"julian": G_EMIN, "emin": G_EMIN}, f"uid → Gruppe nur für Gruppen mit eigenen Zeilen (Mitglieder + Verwalter), HT nicht: {UG}")
check(ug_f({"gruppen": [{"id": "g2", "verwalter_id": "v2"}], "mitglieder": []}, ZG) == {}, "Gruppe ohne eigene Zeilen → keine Zuordnung (rechnet global)")
check(fuer(ZIELE, ZG, UG, "marc") is ZIELE and fuer(ZIELE, {}, {}, "julian") is ZIELE, "HT-ID / ohne Gruppen-Zeilen: genau die globalen Ziele (bitgleich)")
ej = fuer(ZIELE, ZG, UG, "julian")
check(ej["Lucid Trading"]["kauf_groesse"] == 50000 and ej["Lucid Trading"]["von"] == 5000 and ej["Lucid Trading"]["bis"] == 10000
      and ej["Lucid Trading"]["reihe"] == 8 and ej["Lucid Trading"]["kauf_einheit"] == "50k", "Emin-ID: Lucid mit eigener Zeile (50k, 5.000–10.000), reihe global")
check(ej["FundedNext"] is ZIELE["FundedNext"] and ej["Tradeify"]["kauf_groesse"] == 150000, "Emin-ID: Firmen ohne eigene Zeile wie HT (CFD 100k, Tradeify 150k)")
check(ZIELE["Lucid Trading"]["kauf_groesse"] == 150000, "globale Ziele bleiben unverändert (keine Vermischung)")

# vorrat_rechnen je ID (Stufe 1)
konten = [{"user_id": "julian", "firma": "Lucid Trading", "typ": "winning_days", "groesse": 50000, "balance": 56000},
          {"user_id": "marc", "firma": "Lucid Trading", "typ": "winning_days", "groesse": 150000, "balance": 156000}]
erg = ns["vorrat_rechnen"](konten, ZIELE, {}, ["marc", "julian"], ziele_fuer=lambda u: fuer(ZIELE, ZG, UG, u))
zl = {(z["user_id"], z["firma"]): z for z in erg["zellen"]}
check(zl[("julian", "Lucid Trading")]["von"] == 5000 and zl[("julian", "Lucid Trading")]["lage"] == "im_ziel"
      and zl[("marc", "Lucid Trading")]["von"] == 10000 and zl[("marc", "Lucid Trading")]["lage"] == "unter",
      "Stufe 1: +6.000 ist bei Emin (5.000–10.000) im Ziel, bei HT (10.000–15.000) darunter")
erg0 = ns["vorrat_rechnen"](konten, ZIELE, {}, ["marc", "julian"])
check(all(z["von"] == ZIELE[z["firma"]]["von"] for z in erg0["zellen"]), "ohne ziele_fuer: alle IDs global (wie vor KP3)")

# Ziel-Prüfung für Gruppen: Kauf-Größe
p = ns["vorrat_ziel_pruefen"]
check(p(ZIELE["Lucid Trading"], {"kauf_groesse": 50000})[0] == {"kauf_groesse": 50000.0} and p(ZIELE["Lucid Trading"], {"kauf_groesse": 0})[1],
      "Kauf-Größe änderbar, 0 abgelehnt (dieselbe Prüfung wie global)")

# ── 2. Lauf + Aktion statisch ──
lauf = zwischen(SRC, "def vorrat2_rechnen_lauf(", "\ndef vorrat2_lauf(")
check("zg, ug, _zg_ok = _vorrat_ziele_gruppen()" in lauf and "ziel_u = vorrat_ziele_fuer(ziele, zg, ug, uid)[f]" in lauf
      and "vorrat2_zelle(ziel_u," in lauf and "vorrat_fakten_text(z, name, f, ziel_u, status)" in lauf and "vorrat2_zelle(ziele[f]" not in lauf,
      "Lauf rechnet jede Zelle mit dem Ziel des Unternehmens der ID")
zelle = zwischen(SRC, "def vorrat2_zelle(", "\ndef ")
check('"groesse": (int(g_kauf) if (g_kauf and not stueck) else None)' in zelle, "nachkauf.groesse = Kauf-Größe (für die Vorlage in der Kaufliste)")
bv = zwischen(SRC, "def admin_build_vorrat(", "\ndef ")
check("ziele_fuer=(lambda u: vorrat_ziele_fuer(ziele, zg, ug, u)) if zg else None" in bv, "Vorrat-Seite (Stufe 1) ebenso je Unternehmen")
zgl = zwischen(SRC, "def _vorrat_ziele_gruppen(", "\ndef ")
check("== 404" in zgl and "return {}, {}, False" in zgl and "raise" in zgl and "admin_gruppen_daten()" in zgl,
      "Tabelle fehlt → global wie bisher; anderer Fehler fliegt (nie Emin still mit HT-Größen)")
ak = zwischen(SRC, "def _vorrat_ziel_gruppe_aendern(", "\ndef _vorrat2_aktion(")
check('if nur and str(g.get("verwalter_user_id")) != str(uid):' in ak and "if not nur and not _vorrat_zg_admin():" in ak,
      "Recht: Verwalter nur seine Gruppe, uneingeschränkt nur mit Admin-Gate (nicht jede HT-ID)")
check('if not g or not g.get("verwalter_user_id"):' in ak and "nur Unternehmen mit Verwalter" in ak, "nur Gruppen mit Verwalter haben eigene Ziele (HT = global)")
check('sb_insert("vorrat_ziele_gruppe", dict({k: basis.get(k) for k in VORRAT_ZG_FELDER}' in ak and "vorrat_ziel_pruefen(alt or basis, body, neu=False)" in ak,
      "fehlt die Gruppen-Zeile: aus der globalen angelegt, dieselbe Prüfung")
check("_mp_cache.clear()" in ak and 'vorrat2_lauf("hand")' in ak, "nach dem Speichern: Tachos frisch, Lauf neu")
va = zwischen(SRC, "def _vorrat2_aktion(", "\ndef ")
check('if aktion == "ziel" and body.get("gruppe_id"):' in va and va.index('body.get("gruppe_id")') < va.index('if aktion in ("ziel", "ziel_neu"):'),
      "aktion ziel mit gruppe_id → Gruppen-Weg; ohne → global wie bisher")
gs = zwischen(SRC, "def vorrat_ziele_gruppen_sicht(", "\ndef ")
check('q["verwalter_user_id"] = f"eq.{nur}"' in gs and "elif not _vorrat_zg_admin():\n        return []" in gs, "Karte: Verwalter sieht nur seine Gruppe, Nicht-Admin nichts")
ga = zwischen(SRC, "def _vorrat_zg_admin(", "\ndef ")
check("_K._gate()" in ga and "return gerr is None and erlaubt is None" in ga and "return False" in ga, "Admin-Gate = kapital_app._gate (Fehler = kein Admin)")

# ── 3. kaufliste_app: Größe je Zeile ──
stub = types.ModuleType("kapital_app")
stub._sb = lambda *a, **k: []
stub._gate = lambda: (None, None)
sys.modules["kapital_app"] = stub
sys.path.insert(0, W)
import kaufliste_app as KL  # noqa: E402
zeilen = KL.zeilen_aus_vorrat([{"user_id": "julian", "firma": "Lucid Trading", "status": "frei", "max_laufend": 3, "gruppe_id": G_EMIN,
                                "nachkauf": {"n": 2, "einheit": "50k", "groesse": 50000, "dringlichkeit": "jetzt"}},
                               {"user_id": "marc", "firma": "FTMO", "status": "frei", "max_laufend": 2,
                                "nachkauf": {"n": 1, "einheit": "200k", "groesse": 200000, "dringlichkeit": "jetzt"}}])
zj = next((z for z in zeilen if z["user_id"] == "julian"), {})
zm = next((z for z in zeilen if z["user_id"] == "marc"), {})
check(zj.get("groesse") == 50000 and zj.get("einheit") == "50k" and zj.get("gruppe_ziel") is True and zm.get("gruppe_ziel") is False,
      "Kaufliste: Zeile trägt Kauf-Größe + ob sie mit Gruppen-Zielen rechnet (Emin ja, HT nein)")

# ── 4. Frontend in jsc ──
kl = zwischen(HTML, "  function klVorlage(firma, einheit, liste, groesse, streng){", "\n  }\n") + "\n  }\n"
vz = zwischen(HTML, "  function vrZielGruppen(d){", "  function vrZielKlartext(z){")
js = ("const klNorm = f => String(f || '').toLowerCase().replace(/[^a-z0-9]/g, '')\nconst KL_TYP_RANG = { challenge: 0, phase1: 1, phase2: 2 }\n"
      "const _vr = { zielGruppe: '' }\n" + kl + vz + """
const L = [{ id: 1, firm: 'Lucid Trading', account_type: 'challenge', account_size: 150000 }, { id: 2, firm: 'Lucid Trading', account_type: 'challenge', account_size: 50000 },
           { id: 3, firm: 'FundedNext Futures', account_type: 'challenge', account_size: 150000 }, { id: 4, firm: 'Tradeify', account_type: 'challenge', account_size: 150000 },
           { id: 5, firm: 'FTMO', account_type: 'phase1', account_size: 100000 }]
const out = {}
out.lucid50 = (klVorlage('Lucid Trading', '50k', L, 50000, true) || {}).id
out.fnf50 = klVorlage('FundedNext Futures', '50k', L, 50000, true)
out.alt = (klVorlage('FundedNext Futures', '50k', L, null) || {}).id
out.tr150 = (klVorlage('Tradeify', '150k Select', L, 150000, false) || {}).id
out.ftmo200 = (klVorlage('FTMO', '200k', L, 200000, false) || {}).id
const D = { ziele: [{ firma: 'Lucid Trading', art: 'plus_ueber_start', von: 10000, bis: 15000, kauf_groesse: 150000, reihe: 8 }, { firma: 'FundedNext', art: 'groessen_summe', von: 200000, bis: 300000, reihe: 5 }],
            ziele_gruppen: [{ gruppe_id: 'g-emin', name: 'Emin', ziele: [{ firma: 'Lucid Trading', art: 'plus_ueber_start', von: 5000, bis: 10000, kauf_groesse: 50000, reihe: 99 }] }] }
out.ht = vrZieleListe(D).map(z => z.firma + ':' + z.von + ':' + (z.kauf_groesse || '') + ':' + !!z.eigen)
_vr.zielGruppe = 'g-emin'
out.emin = vrZieleListe(D).map(z => z.firma + ':' + z.von + ':' + (z.kauf_groesse || '') + ':' + !!z.eigen + ':' + z.reihe)
_vr.zielGruppe = ''
out.verwalter = vrZielGruppeAktiv(Object.assign({}, D, { ziele_global_darf: false }))
out.ohne = vrZielGruppeAktiv({ ziele: D.ziele })
print(JSON.stringify(out))
""")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
    f.write(js)
r = subprocess.run([JSC, f.name], capture_output=True, text=True, timeout=60)
os.unlink(f.name)
check(r.returncode == 0, f"jsc läuft ({(r.stderr or r.stdout)[:200]})")
e = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}
check(e.get("lucid50") == 2 and e.get("tr150") == 4, "Vorlage genau der Kauf-Größe (Lucid 50k Flex, Tradeify 150k)")
check(e.get("fnf50") is None, "Gruppen-Zeile FNF 50k ohne passende Vorlage → keine (Chip „Vorlage fehlt“), nie still die 150k-Vorlage")
check(e.get("ftmo200") == 5, "HT-Zeile (ohne Gruppen-Ziele) FTMO 200k: wie vor KP3 Rückfall auf die 100k-Vorlage (Review: bitgleich)")
check(e.get("alt") == 3, "alter Lauf ohne groesse: wie bisher (Rückfall auf die Firma)")
check(e.get("ht") == ["Lucid Trading:10000:150000:false", "FundedNext:200000::false"], f"Karte HT: globale Ziele {e.get('ht')}")
check(e.get("emin") == ["Lucid Trading:5000:50000:true:8", "FundedNext:200000::false:5"], f"Karte Emin: eigene Zeile überschreibt, Rest wie HT {e.get('emin')}")
check(e.get("verwalter") == "g-emin" and e.get("ohne") == "", "Verwalter landet direkt in seiner Gruppe; ohne Gruppen-Daten wie bisher")
check("Vorlage fehlt" in HTML and "klVorlage(z.firma, z.einheit, liste, z.groesse, z.gruppe_ziel)" in HTML, "Kaufliste: Chip „Vorlage fehlt“ und Größe aus dem Lauf")
check("body.gruppe_id = gid" in HTML and "data-vr-zg=" in HTML and "zahl('kauf_groesse', z.kauf_groesse, 'Kauf-Größe ($)')" in HTML,
      "Ziele-Karte: Umschalter je Unternehmen, Kauf-Größe, Speichern mit gruppe_id")

# ── 5. SQL ──
code = "\n".join(z for z in SQL.splitlines() if not z.lstrip().startswith("--"))
check("primary key (gruppe_id, firma)" in code and "references public.id_gruppen(id) on delete cascade" in code, "Tabelle: eine Zeile je Gruppe × Firma")
check("enable row level security" in code and "revoke all on public.vorrat_ziele_gruppe from anon, authenticated;" in code
      and "to anon" not in code and "to authenticated" not in code, "RLS an, anon/authenticated ohne Rechte (nur Service-Key)")
check("(values ('Lucid Trading', 5000::numeric, 10000::numeric), ('FundedNext Futures', 5000, 10000))" in code
      and "w.von, w.bis, null, '50k', 50000, z.reihe" in code,
      "Seed = Finns Werte: Emin Lucid + FNF +5.000–10.000 $ Winning Days, Kauf 50k")
check("FTMO Futures', 5" not in code and "Tradeify'," not in code and "The5" not in code,
      "keine eigenen Zeilen für CFD, Tradeify/Topstep/Apex, FTMO Futures (wie HT)")
check("g.verwalter_user_id is not null" in code and "auto_plan_gruppe apg where apg.gruppe_id = g.id" in code and "on conflict (gruppe_id, firma) do nothing" in code,
      "Seed nur für Gruppen mit Verwalter + Gruppen-Planer (Emin), wiederholbar, überschreibt nie")
check(code.strip().startswith("begin;") and "commit;" in code, "eine Transaktion")

print()
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
