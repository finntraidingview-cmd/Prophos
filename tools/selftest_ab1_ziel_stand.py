#!/usr/bin/env python3
"""Selbsttest AB1 (Finn 17.11.2026 ~15:05 Dubai, Marc FundedNext 100k On Demand …7821): Abhak-Popup „Trade erledigt“ schlug „Funded-CFD-Ziel erreicht“ /
⏳ Waiting vor, obwohl Consistency (48 % > 40 %) fehlte, und sprang erst nach der frischen Antwort von /konto-ziele auf „Nichts ändern“.
Prüft ohne Netz in JavaScriptCore (echte Funktionen aus prophos.html):
  1. wdlFcfdZielErreicht urteilt nur noch über /konto-ziele abhak.bereit (gemerkter Stand) — nie mehr Balance ≥ Radar-Ziel
  2. wpZielStand liefert die Ziel-Stand-Zeile mit Marcs Zahlen, ohne Consistency nur den Balance-Teil, am Ziel „Ziel erreicht → Waiting for Payout“
  3. Verdrahtung im Popup (Zeile sofort, frische Antwort ersetzt nur den Text)
Aufruf:  python3 tools/selftest_ab1_ziel_stand.py"""
import json
import os
import subprocess
import tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


def schnitt(von, bis):
    return html[html.index(von):html.index(bis)]


zs = schnitt("function wpZielStand(", "window._wpZielStand")
fz = schnitt("function wdlFcfdZielErreicht(", "function wdlFcfdZielAb(") + schnitt("function wdlFcfdZielAb(", "window._wdlFcfdZielMoeglich")

# /konto-ziele-Antwort wie Railway nach Marcs Trade (Werte aus dem FundedNext-Dashboard, Konto ohne Kennung)
MARC = {"typ": "funded_cfd", "groesse": 100000,
        "od_ziel": {"usd": 4901.4, "grund": "consistency", "bereit": False, "fehlt": 823.98, "p": 40},
        "abhak": {"bal": 104077.42, "ziel_bal": 102000, "rest": -2077.42, "erreicht": True, "bereit": False, "wartet": False,
                  "ok_text": "Ziel +4.077 $ / +2.000 $", "fehlt_text": "Consistency 48,1 % > 40 % (größter Tag 1.960,56 $ / Profit 4.077,42 $ · On-Demand-Ziel 4.901,4 $)",
                  "cons": {"p": 40, "b": 1960.56, "w": 4077.42, "anteil": 0.48083, "ok": False, "basis": "netto", "lesbar": True}, "gewinntage": None}}
OHNE_CONS = {"typ": "funded_cfd", "groesse": 100000,
             "abhak": {"bal": 101500, "ziel_bal": 102000, "rest": 500, "erreicht": False, "bereit": False, "wartet": False, "cons": None, "gewinntage": None}}
AM_ZIEL = {"typ": "funded_cfd", "groesse": 100000,
           "od_ziel": {"usd": 4901.4, "grund": "consistency", "bereit": True, "fehlt": 0, "p": 40},
           "abhak": {"bal": 104950, "ziel_bal": 102000, "rest": -2950, "erreicht": True, "bereit": True, "wartet": False,
                     "cons": {"p": 40, "b": 1960.56, "w": 4950, "anteil": 0.396, "ok": True, "basis": "netto", "lesbar": True}}}
CONS_SUMME = {"typ": "funded_cfd", "groesse": 100000,   # normale Firma, Consistency über Gewinn-Tage: Ziel erreicht, Consistency reißt → fehlen aus b ÷ p − w
              "abhak": {"bal": 102300, "ziel_bal": 102000, "rest": -300, "erreicht": True, "bereit": False, "wartet": False,
                        "cons": {"p": 50, "b": 1400, "w": 2500, "anteil": 0.56, "ok": False}, "gewinntage": [2, 3]}}
MIKE = {"typ": "funded", "groesse": 100000,   # Apex 100k …0004 nach dem Trade (kz_fdp_abhak): Ziel 112.000, Toleranz 0 → nicht erreicht
        "abhak": {"bal": 111957.10, "start": 100000, "ziel_bal": 112000, "rest": 42.9, "erreicht": False, "bereit": False, "wartet": False, "schritt": "winning_days",
                  "fehlt_text": "Ziel +11.957 $ von +12.000 $ — fehlen 43 $", "checks": [["nein", "Ziel bis Winning Days", "+11.957 $ / +12.000 $"]]}}
MIKE_OK = {"typ": "funded", "abhak": dict(MIKE["abhak"], bal=112010, rest=-10, erreicht=True, bereit=True)}
OD_OHNE_G = dict(MARC, groesse=None)
WARTET = {"typ": "funded_cfd", "groesse": 100000, "abhak": {"bal": 104950, "ziel_bal": 102000, "bereit": True, "wartet": True}}

js = f"""
let GEM = null; const window = {{ _wpGemerkt: (id, nach) => GEM }};
{zs}
{fz}
const wdlBlowStand = t => t._bs || null;
const T = {{ konto_typ: 'funded_cfd', konto_id: 'k1', ended_at: '2026-11-17T11:00:00Z', ziel_usd: 102000, _bs: {{ bal: 104077.42, geblowt: false }} }};
const R = {{}};
R.marc = wpZielStand({json.dumps(MARC)});
R.ohne = wpZielStand({json.dumps(OHNE_CONS)});
R.ziel = wpZielStand({json.dumps(AM_ZIEL)});
R.summe = wpZielStand({json.dumps(CONS_SUMME)});
R.wartet = wpZielStand({json.dumps(WARTET)});
R.mike = wpZielStand({json.dumps(MIKE)});
R.mike_ok = wpZielStand({json.dumps(MIKE_OK)});
R.od_ohne_g = wpZielStand({json.dumps(OD_OHNE_G)});
R.mike_c = wpZielStand({json.dumps(dict(MIKE, abhak=dict(MIKE["abhak"], cons={"p": 50, "b": 7000, "w": 11957.1, "anteil": 0.5854, "ok": False, "nur_anzeige": True})))});
R.unplaus = wpZielStand({json.dumps(dict(MIKE, abhak=dict(MIKE["abhak"], bal=115000, rest=-3000, fehlt_text="Balance 115.000 $ unplausibel (Ziel 112.000 $) — Balance neu lesen")))});
R.leer = wpZielStand({{ typ: 'funded_cfd' }});
GEM = null; R.fz_ohne = wdlFcfdZielErreicht(T);
GEM = {{ art: 'cfd', bereit: false, wartet: false }}; R.fz_nein = wdlFcfdZielErreicht(T);
GEM = {{ art: 'cfd', bereit: true, wartet: false }}; R.fz_ja = wdlFcfdZielErreicht(T);
GEM = {{ art: 'cfd', bereit: true, wartet: true }}; R.fz_wartet = wdlFcfdZielErreicht(T);
GEM = {{ art: 'cfd', bereit: true, wartet: false }}; R.fz_blow = wdlFcfdZielErreicht(Object.assign({{}}, T, {{ _bs: {{ bal: 89000, geblowt: true }} }}));
R.fz_challenge = wdlFcfdZielErreicht(Object.assign({{}}, T, {{ konto_typ: 'challenge' }}));
GEM = null; R.so_ohne = wdlFcfdStandOffen(T);
GEM = {{ art: 'cfd', bereit: false, wartet: false }}; R.so_mit = wdlFcfdStandOffen(T);
GEM = null; R.so_unter = wdlFcfdStandOffen(Object.assign({{}}, T, {{ _bs: {{ bal: 100800, geblowt: false }} }}));
print(JSON.stringify(R));
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run([JSC, d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0, f"jsc läuft ({r.stderr[:300]}{r.stdout[-300:] if r.returncode else ''})")
R = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 else {}

print("1) Vorauswahl nur aus /konto-ziele abhak.bereit")
check(R.get("fz_ohne") is False, "Marc, Balance 104.077 ≥ Radar-Ziel 102.000, kein Stand → NICHT „Ziel erreicht“ (Popup öffnet auf „Nichts ändern“)")
check(R.get("fz_nein") is False, "Stand sagt nicht bereit (Consistency) → nicht erreicht")
check(R.get("fz_ja") is True, "Stand sagt bereit → erreicht (⏳ vorgewählt)")
check(R.get("fz_wartet") is False and R.get("fz_blow") is False and R.get("fz_challenge") is False, "wartet schon / geblowt / keine Funded CFD → nie")

check(R.get("so_ohne") is True and R.get("so_mit") is False and R.get("so_unter") is False,
      f"AB1b: Ziel möglich + kein Stand → „Ziel-Stand lädt noch“ (nie Ein Klick); mit Stand oder klar unter dem Ziel nicht ({R.get('so_ohne')}, {R.get('so_mit')}, {R.get('so_unter')})")
eg = schnitt("function wdlEinKlickGrund(", "window._wdlEinKlickGrund")
check("return wdlFcfdStandOffen(t) ? WDL_FCFD_STAND_OFFEN : ''" in eg and eg.index("wdlFcfdStandOffen(t)") > eg.index("'Ergebnis unplausibel (falsches Konto?)'"),
      "AB1b: letzte Prüfung — alle Schutz-Gründe (Hedge offen, ohne Lesung, unplausibel) bleiben vorrangig, Sammel bucht nur, was sonst Ein Klick wäre")
check("grund !== WDL_FCFD_STAND_OFFEN" in html, "AB1b: Sammel-Abhaken hält bei „Ziel-Stand lädt noch“ nicht an (wartet aufs Urteil)")

print("2) Ziel-Stand-Zeile")
m = R.get("marc") or {}
check(m.get("ok") is False and m.get("text") == "Ziel 104.901 $ · erreicht 4.077 / 4.901 $ (83 %) · Consistency 48 % (max 40 %) → fehlen 824 $", f"Marc: {m.get('text')}")
o = R.get("ohne") or {}
check(o.get("text") == "Ziel 102.000 $ · erreicht 1.500 / 2.000 $ (75 %) → fehlen 500 $", f"ohne Consistency nur der Balance-Teil: {o.get('text')}")
z = R.get("ziel") or {}
check(z.get("ok") is True and z.get("text", "").startswith("Ziel erreicht → Waiting for Payout"), f"am Ziel: {z.get('text')}")
s = R.get("summe") or {}
check(s.get("text") == "Ziel 102.000 $ · erreicht 2.300 / 2.000 $ (100 %) · Consistency 56 % (max 50 %) · Gewinntage 2/3 → fehlen 300 $", f"Gewinn-Tage-Basis + Gewinntage: {s.get('text')}")
check((R.get("wartet") or {}).get("text") == "Konto wartet schon auf Payout" and R.get("leer") is None, "wartet schon / ohne abhak")

mk = R.get("mike") or {}
check(mk.get("ok") is False and mk.get("text") == "Ziel 112.000 $ · erreicht 11.957 / 12.000 $ (99,6 %) → fehlen 43 $", f"Funded Futures Mike: {mk.get('text')}")
check((R.get("mike_ok") or {}).get("text", "").startswith("Ziel erreicht → Winning Days"), f"Futures am Ziel: {(R.get('mike_ok') or {}).get('text')}")
up = (R.get("unplaus") or {}).get("text", "")
check(up.endswith("→ noch nicht: Balance 115.000 $ unplausibel (Ziel 112.000 $) — Balance neu lesen"), f"nicht bereit ohne $-Rest → Grund aus Railway: {up}")
mc = R.get("mike_c") or {}
check(mc.get("text") == "Ziel 112.000 $ · erreicht 11.957 / 12.000 $ (99,6 %) · Consistency 59 % (max 50 %, fehlen 2.043 $) → fehlen 43 $", f"Futures-Consistency nur Anzeige, eigener Fehlbetrag: {mc.get('text')}")
check("102.000" not in (R.get("od_ohne_g") or {}).get("text", "x"), f"On Demand ohne Größe: nie das Radar-Ziel ({(R.get('od_ohne_g') or {}).get('text')})")

print("3) Verdrahtung")
oe = schnitt("function mklWdErledigtOeffnen(", "function mwdErlStatusUI(")
check("mwdErlZielZeile(_zsAn ? (typeof window._wpGemerkt === 'function'" in oe, "Zeile sofort beim Öffnen (gemerkter Stand oder „wird geladen …“)")
check("if(_zsAn) mwdErlZielZeile(u, true)" in oe and "_wpS.art === 'fd'" in oe, "frische Antwort ersetzt nur den Text — derselbe Abruf wie die Vorauswahl")
check("wdlFcfdZielErreicht(pw)) ? 'waiting' : 'none'" in oe, "Vorbelegung weiter über wdlFcfdZielErreicht (jetzt = abhak.bereit)")
check('id="mwd-erl-ziel"' in html and "stand: wpZielStand(d)" in html, "Element + wpAusD.stand")
wa = schnitt("function mwdErlWpAnwenden(", "function mklWdErledigtOeffnen(")
check("_mwdErlStatusAngefasst) return" in wa, "Finns eigener Klick wird nie überschrieben")

print("4) Backend kz_fdp_abhak: Consistency der Firma nur als Anzeige (Mike Apex 100k …0004)")
import hashlib
import re
from datetime import datetime, timezone, timedelta
BE = open(os.path.join(W, "app" + ".py"), encoding="utf-8").read()
ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "hashlib": hashlib}
for nm in ("_wd_num", "_liq_de", "kz_usd", "_wd_konto_groesse", "fdp_je_groesse", "fdp_ziel_gewinn", "fdp_zyklus", "fdp_tage", "fdp_konto_anzeige", "kz_fdp_abhak",
           "FDP_PUMP_TP_TOL_USD", "_fdp_pump_u", "_fdp_pump_spanne", "fdp_pump_tag_wurf", "ist_topstep_express", "fdp_express_basis", "fdp_ziel_schwelle",
           "fdp_ziel_tol_erreicht", "fdp_bal_start_abs"):
    m = re.search(r"^def " + re.escape(nm) + r"\(.*?(?=^[A-Za-z_@#])", BE, re.S | re.M) or re.search(r"^" + re.escape(nm) + r"\s*=.*?(?=^[A-Za-z_@#])", BE, re.S | re.M)
    exec(m.group(0), ns)
ns["_cme_handelstag"] = lambda st: str(st)[:10]
REG = {"name": "Apex Trader", "consistency_pct": 50, "je_groesse": {"100000": {"ziel_gewinn": 12000, "dd": 3000, "max_trade": 6000}}}
A = {"id": "aaaaaaaa-0000-0000-0000-000000000004", "name": "100k APEX0004 → Funded", "firm": "Apex Trader", "account_type": "funded"}
PL = [{"status": "completed", "started_at": "2026-11-12T14:00:00Z", "master_pl": 3000.0, "tv": {"balance_start": 100000}},
      {"status": "completed", "started_at": "2026-11-14T14:00:00Z", "master_pl": 3008.30, "tv": {"balance_start": 103000}},
      {"status": "review", "started_at": "2026-11-17T14:00:00Z", "master_pl": None, "tv": {"balance_start": 106008.30}}]
k = ns["kz_fdp_abhak"](A, {"regel": REG, "pay": []}, 111957.10, PL)
c = (k or {}).get("cons") or {}
check(k and k["ziel_bal"] == 112000 and k["bereit"] is False and abs(k["rest"] - 42.9) < 0.01, f"Ziel 112.000, Toleranz 0 → bei 43 $ Rest nicht erreicht, wie der Planer ({k and (k['ziel_bal'], k['bereit'], k['rest'])})")
check(c.get("nur_anzeige") is True and c.get("p") == 50 and abs(c.get("b", 0) - 5948.8) < 0.01 and c.get("ok") is True,
      f"Consistency nur Anzeige: größter Tag = ungebuchter Trade 5.948,80 von 11.957,10 ≈ 49,8 % ≤ 50 % ({c})")
k2 = ns["kz_fdp_abhak"](A, {"regel": dict(REG, consistency_pct=None), "pay": []}, 111957.10, PL)
check(k2 and k2.get("cons") is None, "ohne consistency_pct an der Firma → kein cons (Zeile nur Ziel)")
k3 = ns["kz_fdp_abhak"](A, {"regel": REG, "pay": []}, 112050.0, PL)
check(k3 and k3["bereit"] is True, "am Ziel bereit — Consistency ändert bereit nie")

print()
print("FEHLER: " + "; ".join(fehler) if fehler else "ALLES OK")
raise SystemExit(1 if fehler else 0)
