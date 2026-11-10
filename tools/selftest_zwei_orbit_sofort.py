#!/usr/bin/env python3
"""Selbsttest ZWEI ORBIT — Sofort-Start-Wächter + Texte je Grund (03.11.2026, Z4, Lücken 2 und 3 der Prüfung S3,
.claude/master/berichte/2026-11-03_zwei_orbit_pruefung.md). Ohne Netz.
  · panel.richtung_frei füllt zweit_aus aus der Railway-Antwort (zweit/zweit_art), Rückgabe bleibt (frei, msg, code), fail-closed unverändert
  · tv-order / tv-konto / tsxorder reichen zweit/zweit_art an den PC-Tab durch
  · prophos.html: Zweit-Wartezeile → /admin/zweit-frei im Takt aus puls_heim_regel (gestreut), frei → sofort neu einplanen; Texte je Grund
    (zweitGrund) in Toast, Karte, Grund-Zeile und Pille. Das Verhalten von zweitGrund prüft der Boot-Check im Browser (window._zweitGrund).
Aufruf: python3 tools/selftest_zwei_orbit_sofort.py"""
import io
import json
import os
import re
import sys
import types

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


# ── Panel: richtung_frei mit gestellter Railway-Antwort ──
code = PANEL[PANEL.index("RIEGEL_NETZ_WIEDERHOLEN = "):PANEL.index("def riegel_pflicht_fehlt(")]   # RD1 (10.11.2026): mit riegel_netzfehler
ANTWORT = {}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _urlopen(req, timeout=None):
    if ANTWORT.get("wirf"):
        raise OSError("netz weg")
    return _Resp(json.dumps(ANTWORT["d"]).encode("utf-8"))


fake_urllib = types.ModuleType("urllib")
fake_req = types.ModuleType("urllib.request")
fake_req.urlopen = _urlopen
fake_req.Request = lambda *a, **k: None
fake_urllib.request = fake_req
import urllib.error as _ue   # noqa: E402  RD1: riegel_netzfehler braucht die echten Fehlerklassen
fake_urllib.error = _ue
sys.modules["urllib"], sys.modules["urllib.request"], sys.modules["urllib.error"] = fake_urllib, fake_req, _ue
ns = {"re": re, "json": json, "code_token": lambda: "tok", "CODE_QUELLE": "http://x", "time": types.SimpleNamespace(sleep=lambda s: None),
      "random": __import__("random")}
exec(code, ns)
RF = ns["richtung_frei"]
PID = "12345678-1234-1234-1234-123456789012"

ANTWORT.update(d={"ok": True, "frei": False, "code": "big_trade_nah", "zweit": True, "zweit_art": "nah",
                  "grund": "1. Trade Apex …1234 (BUY 3 NQ) ist 1.200 $ vor dem TP (Grenze 2.500 $) — zweiter Start wartet (Spanne 2.500 $)"})
z = {}
r = RF(PID, "buy", zweit_aus=z)
check(len(r) == 3 and r[0] is False and r[2] == "big_trade_nah" and z == {"zweit": True, "zweit_art": "nah"},
      "Zweit-Sperre: (frei, msg, code) wie bisher, zweit_aus bekommt zweit + zweit_art")
ANTWORT.update(d={"ok": True, "frei": False, "code": "big_trade_nah", "zweit": True, "zweit_code": "markt_oeffnung", "bis": "2026-11-03T14:35:00Z",
                  "grund": "Markteröffnung 09:28–09:35 New York (bis 18:35 Dubai): kein weiterer Big Trade"})
z = {}
RF(PID, "buy", zweit_aus=z)
check(z == {"zweit": True, "zweit_code": "markt_oeffnung", "bis": "2026-11-03T14:35:00Z"}, "Codes von S6: zweit_code + bis gehen mit")
ANTWORT.update(d={"ok": True, "frei": False, "code": "big_trade_nah", "grund": "Big Trade auf diesem PC 900 $ vor dem TP"})
z = {}
RF(PID, "buy", zweit_aus=z)
check(z == {}, "Heim-Sperre des PCs (ohne zweit) → zweit_aus bleibt leer")
ANTWORT.update(d={"ok": True, "frei": False, "code": "gegenrichtung", "zweit": True, "grund": "läuft"})
z = {}
r = RF(PID, "buy", zweit_aus=z)
check(r[2] == "gegenrichtung" and z == {}, "Gegenrichtung → kein Zweit-Merker")
ANTWORT.update(d={"ok": True, "frei": False, "code": "big_trade_nah", "zweit": True})
check(RF(PID, "buy")[0] is False, "ohne zweit_aus (master-order, polar) unverändert")
ANTWORT.update(d={"ok": True, "frei": True})
check(RF(PID, "sell", zweit_aus={}) == (True, "", ""), "frei → (True, '', '')")
ANTWORT.update(wirf=True)
check(RF(PID, "sell", zweit_aus={})[2] == "riegel_unerreichbar", "Netz weg → fail-closed riegel_unerreichbar")
ANTWORT.update(wirf=False)
for pfad, muster in (("tv-order", 'richtung_frei(_pid, cmd["richtung"], zweit_aus=_zweit)'),
                     ("tv-konto", 'richtung_frei(_pid, cmd["richtung"], zweit_aus=_zweit)'),
                     ("tsxorder", 'richtung_frei(cmd.get("plan_id"), cmd.get("richtung"), zweit_aus=_zweit)')):
    i = PANEL.index(f"[panel] {pfad} RIEGEL {{_code}}")
    blk = PANEL[i - 400:i + 400]
    check(muster in blk and '"msg": _msg, **_zweit}' in blk, f"{pfad}: zweit/zweit_art gehen an den Tab")

# ── prophos.html ──
check(HTML.count("function zweitGrund(d){") == 1 and "window._zweitGrund = zweitGrund" in HTML, "zweitGrund einmal, Test-Haken da")
b = HTML[HTML.index("async function sfBehoben(plan, f){"):HTML.index("async function sfNeuEinplanen(plan, grund, hand){")]
check(0 < b.index("if(sfIstZweit(f)){") < b.index("if(f.schritt === 'big_trade_nah' && sfIstWdSperre(f))") < b.index("const warte = /Selbstheilung"),
      "sfBehoben: Zweit-Wartezeile vor WD- und 15-min-Weg")
check("if(z && z.frei) return 'zweiter Big Trade frei — sofort neu'" in b and "if(z === 'warten') return null" in b,
      "frei → sofort neu einplanen, Takt nicht um → warten")
zf = HTML[HTML.index("async function sfZweitFrei(plan){"):HTML.index("// Letzte Startminute des Tages")]
check("/admin/zweit-frei?plan=" in zf and "'sb-token': tok" in zf and "return null" in zf,
      "sfZweitFrei: GET /admin/zweit-frei mit Login, Fehler → null (15-min-Weg)")
tk = HTML[HTML.index("async function sfZweitTakt(){"):HTML.index("function sfIstZweit(f){")]
check("from('puls_heim_regel').select('zweit_takt_von_s,zweit_takt_bis_s')" in tk and "10 * 60000" in tk, "Takt aus puls_heim_regel, 10 min gemerkt")
check("const SF_ZWEIT_TAKT = { von: 20, bis: 40, at: 0 }" in HTML, "Standard-Takt 20–40 s")
check("Math.random() * Math.max(0, SF_ZWEIT_TAKT.bis - SF_ZWEIT_TAKT.von)" in HTML and "sfZweitPlanen()\n" in HTML, "Wächter-Takt gestreut, läuft an")
rd = HTML[HTML.index("async function sfZweitRunde(){"):HTML.index("const sfZweitPlanen =")]
check("_sfLaeuft" in rd and "window._tabNebenSofort" in rd and "!sfDeckelVoll(f)" in rd and "sfNeuEinplanen(p, grund, false)" in rd,
      "Wächter-Runde: Haupt-Tab, teilt _sfLaeuft mit sfTick, plant über sfNeuEinplanen (Backend-Nachholen mit Regeln)")
check("f.zweit === true || /zweiter Start wartet/.test(String(f.msg || ''))" in HTML, "Zweit am Flag, alter Stand/unklar am Railway-Satz")
check("zweit: !!(r && r.zweit === true), zweit_art: r && r.zweit_art" in HTML and "if(f.zweit === true){ flag.zweit = true;" in HTML,
      "Orbit-Start reicht zweit an sfMelden, Flag am Plan")
fv = HTML[HTML.index("async function faVorStart(plan){"):HTML.index("window._faVorStart =")]
check("const zg = bt && (d.zweit || d.zweit_art || d.code) ? zweitGrund(d) : null" in fv and "wartet: ${zg.kurz}" in fv, "faVorStart-Toast: Grund je Art bei Zweit-Sperren")
check("'echo_hedge', 'zweit', 'firma', 'markt'].includes(s.art)" in HTML and "if(s.art === 'zweit' || s.art === 'firma' || s.art === 'markt'){ const zg = zweitGrund(s)" in HTML,
      "Karte zeigt start_sperre art 'zweit' und die neuen Arten 'firma'/'markt' (S6)")
sf = HTML[HTML.index("function tplSfTun(sf, wer){"):HTML.index("function tplSfTun(sf, wer){") + 12000]
check("case 'big_trade_nah': case 'big_trade_unklar': if(sfIstZweit(sf))" in sf and sf.count("case 'big_trade_unklar'") == 1,
      "Grund-Zeile: eigener Satz für Zweit-Sperren, kein toter case")
check("if(z.zweit) return { w: z.zweit.pille, ton: 'gelb', r: 6 }" in HTML and "zweit: sfIstZweit(sf) ? (zweitGrund(sf) ||" in HTML,
      "Pille je Grund am Code, gelb statt Start-Fehler rot")
ve = HTML[HTML.index("function sfVersuchtErneut(sf, jetzt){"):HTML.index("window._sfVersuchtErneut =")]
check("if(sfIstZweit(sf)) return true" in ve and ve.index("if(sfDeckelVoll(sf)) return false") < ve.index("if(sfIstZweit(sf)) return true"),
      "Gegenprüfung: Zweit-Warten gilt als „versucht erneut“ (kein Hängen-Alarm, kein rotes Start-Fehler nach 30 min)")
check("function sfIstZweit(f){" in HTML and "const sfIstZweit" not in HTML, "sfIstZweit gehoben (sfVersuchtErneut steht weiter oben)")
check("? 'Startfenster zu Ende' : null }" in b, "gesperrt bis Fensterende → einmal nachholen, Backend setzt tagesende")
check("firma_laeuft: 'gleiche_firma', markt_oeffnung: 'markt'" in HTML and "zweit_code: r && r.zweit_code, bis: r && r.bis" in HTML, "Codes von S6 im Tab erkannt und am Flag")
print("ALLES GRÜN" if not FEHLER else f"{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
