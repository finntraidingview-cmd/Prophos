#!/usr/bin/env python3
"""Selbsttest Radar „ein Konto nur einmal“ + Vorgänger eines Rest-Trades still abhaken (Finn 02.11.2026 ~19:45, Jacob Apex 100k …0016, f5f27ede / e6fadf3b).

Verdrahtung im Quelltext. Die Fälle liefen am 02.11.2026 im Stub (window._wdlStub + window._wdlRestVorgaengerTick): nur der rest_hedge-Plan derselben ID,
angelegt nach dem Ende des Vorgängers, hakt still ab; Auto-Planer, Hand-Plan ohne rest_hedge, vor dem Ende angelegt, andere ID, Vorgänger schon completed → nichts.
Live belegt: e6fadf3b rest_hedge true, auto_plan false, created_at 15:26:12 UTC nach f5f27ede ended_at 15:21:21 UTC, gleiche user_id.

Aufruf:  python3 tools/selftest_radar_konto_einmal.py"""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


check('"rest_hedge": p.get("rest_hedge") is True, "auto_plan": p.get("auto_plan"), "created_at": p.get("created_at")' in app, "Radar-Zeile trägt rest_hedge, auto_plan, created_at")
check('polar_slave_user_id,multiplier,auto_plan,rest_hedge"' in app, "/admin/live-trades lädt auto_plan und rest_hedge")
check("const wdlAktiveKonten = () =>" in html and "if(t.konto_id && aktiv.has(String(t.konto_id))) continue" in html, "Rest von Hand lässt Konten mit aktivem Plan weg")
check(".filter(x => x.fehlt || !x.kid || !aktiv.has(String(x.kid)))" in html, "Review lässt Konten mit aktivem Plan weg, Tage sammeln bleibt")
check("x.rest_hedge !== true || x.auto_plan === true" in html, "Tick nur bei rest_hedge-Plänen, nie Auto-Planer")
check("n.uid === wdlUid(t) && n.at > ende" in html, "Tick nur gleiche ID und nach dem Ende des Vorgängers angelegt")
check("if(!_wdlRestRecht.ok) return" in html and "(_wdlRestN.get(pid) || 0) >= 3" in html, "Tick nur mit Planer-Schreibrecht, höchstens 3 Versuche")
check("wdlVormerken(pid, t, grund, true)" in html and "if(!still && typeof atToast === 'function') atToast(" in html, "Vormerken aus dem Tick ohne Toast")
check("if(still && e && e.status === 409)" in html and "_mwdErlStill = !!opts.nurStill" in html, "stiller Ein Klick schluckt 409 (schon abgehakt)")
check("try{ wdlRestVorgaengerTick() }catch(_){}" in html, "Tick läuft im Lade-Takt")
check("x.planer_plan === true" in html and '"planer_plan": bool(re.search(r"Funded-(CFD-)?Planer"' in app, "Funded-Planer-Pläne zählen nie als „Trade planen“")
check("if(!/nicht mehr in Überprüfen/.test(String(e.message || ''))) wdlLokalVergessen(pid)" in html, "stiller 409: nur „nicht mehr in Überprüfen“ bleibt still, sonst kommt die Zeile zurück")
print("\nALLES GRÜN" if not fehler else f"\n{len(fehler)} FEHLER")
sys.exit(1 if fehler else 0)
