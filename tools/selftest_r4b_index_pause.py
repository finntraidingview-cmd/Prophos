#!/usr/bin/env python3
"""Selbsttest R4b (05.11.2026): CFD/NAS100 startet nie in der Index-Pause, der Gegenrichtungs-Riegel schiebt CFD-Challenges nie über das Startfenster.
Befund S7 R4: Chris …117785/…117783 und Marco …116895 (Tradeify CFD, Echo) wurden am 04.11. 34/30/16 × vom Riegel geschoben und kamen 02:00–02:32 Dubai
frei = CME-/NAS100-Pause → „Market closed", Review „nicht gelaufen 0,00" ohne Grund.
(A) echte cfdIndexPauseZiel/cfdIndexOffen aus prophos.html in JavaScriptCore: Vorfall-Zeiten, Puffer 15 min, Wochenende, Sommerzeit, Fensterende → aufgeben.
(B) gleiche Regel wie Railway: cfdIndexOffen(t) == (_cme_offen_seit_s(t) ≥ 15 min) für jede Minute einer Winter- und einer Sommerwoche.
(C) Verdrahtung im Start-Takt (vor rkVorStart, nur mt5/mt5v2), Anzeige, Endlesung mit Grund; (D) SQL: nur auto_plan-CFD, 90-s-Zweig unverändert.
Aufruf: python3 tools/selftest_r4b_index_pause.py"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
FEHLER = []


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def ms(iso):
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


def main():
    html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    app = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
    sql = open(os.path.join(WURZEL, "sql", "2026-11-05_gegenhedge_cfd_fensterende.sql"), encoding="utf-8").read()

    i = html.index("  function cmeMarktOffen(ms){")
    cme = html[i:html.index("\n  }\n", i) + 4]
    j = html.index("  const CFD_PAUSE_PUFFER_MS = ")
    cfd = html[j:html.index("  window._cfdIndexPauseZiel = cfdIndexPauseZiel", j)]
    k = html.index("  function deNichtGelaufenHinweis(r, grund){")
    dng = html[k:html.index("\n  }\n", k) + 4]

    # (B) Minuten-Raster für den Vergleich mit Railway
    raster = []
    for start in ("2026-11-02T00:00:00Z", "2026-07-06T00:00:00Z"):   # Mo Winter / Mo Sommer, je 8 Tage (inkl. Wochenende)
        t0 = ms(start)
        raster += [t0 + m * 60000 for m in range(0, 8 * 24 * 60, 7)]
    faelle = {
        "chris_0200": [ms("2026-11-04T22:00:40Z"), ms("2026-11-04T23:00:00Z"), 0.5],     # 02:00 Dubai, dt-Tagesgrenze 00:00 = 23:00 UTC
        "pause_3h":   [ms("2026-11-04T22:00:40Z"), ms("2026-11-05T01:00:40Z"), 0.5],
        "offen":      [ms("2026-11-04T12:00:00Z"), None, 0.5],
        "puffer":     [ms("2026-11-04T23:05:00Z"), None, 0.0],
        "puffer_rand": [ms("2026-11-04T23:15:00Z"), None, 0.0],
        "freitag":    [ms("2026-11-06T22:30:00Z"), ms("2026-11-07T01:30:00Z"), 0.5],
        "freitag_lang": [ms("2026-11-06T22:30:00Z"), None, 0.0],
        "sommer":     [ms("2026-07-01T21:00:00Z"), None, 0.0],
        "zufall_max": [ms("2026-11-04T22:30:00Z"), None, 0.999],
    }
    if not shutil.which("osascript"):
        check(False, "osascript fehlt — JS-Teil nicht prüfbar")
    else:
        js = ("function run(){ var window = {};\n" + cme + cfd + dng +
              "\nvar F = " + json.dumps(faelle) + ", R = " + json.dumps(raster) + ", out = {f: {}, raster: []};\n"
              "for(var k in F){ var a = F[k]; out.f[k] = cfdIndexPauseZiel(a[0], a[1], a[2]) }\n"
              "for(var i = 0; i < R.length; i++) out.raster.push(cfdIndexOffen(R[i]) ? 1 : 0)\n"
              "out.h1 = deNichtGelaufenHinweis({ mt5_baseline: { start_sperre: { art: 'richtung', status: 'aufgegeben', text: 'Riegel: Gegenrichtung Schwesterkonto — nicht gestartet (x)' } } }, 'kein Deal');\n"
              "out.h2 = deNichtGelaufenHinweis({ mt5_baseline: { start_sperre: { art: 'richtung', status: 'wartet', text: 'y' } } }, 'kein Deal');\n"
              "out.h3 = deNichtGelaufenHinweis({ mt5_baseline: {} }, 'kein Deal');\n"
              "return JSON.stringify(out) }")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as f:
            f.write(js)
        aus = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=60)
        os.unlink(f.name)
        check(aus.returncode == 0, f"JS läuft in JavaScriptCore ({aus.stderr.strip()[:160]})")
        if aus.returncode == 0:
            o = json.loads(aus.stdout)
            r = o["f"]
            check(r["chris_0200"] == {"aufgeben": True, "frei": ms("2026-11-04T23:15:00Z")},
                  f"Vorfall Chris 02:00:40 Dubai: frei erst 03:15 Dubai, hinter der dt-Tagesgrenze → nicht gestartet ({r['chris_0200']})")
            z = r["pause_3h"]
            check(z and "ziel" in z and ms("2026-11-04T23:15:00Z") <= z["ziel"] < ms("2026-11-04T23:18:00Z"), f"in der Pause mit Platz: Ziel 03:15–03:18 Dubai ({z})")
            check(r["offen"] is None, "Markt offen → nichts schieben")
            check(r["puffer"] and r["puffer"].get("ziel") == ms("2026-11-04T23:15:00Z"), f"erste 15 min nach der Öffnung zählen als Pause ({r['puffer']})")
            check(r["puffer_rand"] is None, "genau 15 min nach der Öffnung → frei")
            check(r["freitag"] and r["freitag"].get("aufgeben") is True, f"Freitag nach 16:00 CT: Montag-Öffnung liegt hinter 3 h → nicht gestartet ({r['freitag']})")
            check(r["freitag_lang"] and r["freitag_lang"].get("ziel") == ms("2026-11-08T23:15:00Z"), f"ohne Ende: Sonntag 17:15 CT ({r['freitag_lang']})")
            check(r["sommer"] and r["sommer"].get("ziel") == ms("2026-07-01T22:15:00Z"), f"Sommerzeit: Pause 21:00–22:00 UTC, Ziel 22:15 UTC ({r['sommer']})")
            check(r["zufall_max"]["ziel"] < ms("2026-11-04T23:18:00Z"), "Zufall höchstens + 3 min")
            # (B) gleiche Regel wie Railway
            ns = {"datetime": datetime, "timezone": timezone}
            a = app.index("\ndef _cme_offen_seit_s(") + 1
            exec(app[a:app.find("\n\n\n", a)], ns)
            pu = int(re.search(r"^FCP_PAUSE_PUFFER_MIN = (\d+)", app, re.M).group(1))
            py = [1 if (ns["_cme_offen_seit_s"](t / 1000) is not None and ns["_cme_offen_seit_s"](t / 1000) >= pu * 60) else 0 for t in raster]
            diff = [raster[n] for n in range(len(raster)) if py[n] != o["raster"][n]]
            check(not diff and pu == 15, f"Tab-Regel = Railway (_cme_offen_seit_s ≥ FCP_PAUSE_PUFFER_MIN {pu} min) für {len(raster)} Minuten Winter + Sommer (Abweichungen {diff[:3]})")
            check(o["h1"].startswith("nicht gestartet — Riegel: Gegenrichtung Schwesterkonto") and o["h2"] == "nicht gelaufen — kein Deal" and o["h3"] == "nicht gelaufen — kein Deal",
                  f"Endlesung: aufgegebener Riegel steht im Review ({o['h1'][:60]} …), sonst wie bisher")

    # (C) Verdrahtung im Tab
    t = html[html.index("  async function tpStartUmTick(){"):]
    t = t[:t.index("const { data, error: eClaim } = await suClaimSetzen(plan.id, verspaetet > fenster ? 'verbrauch' : 'start', true)")]
    i_hook, i_rk = t.find("if(cfdIndexRoute(plan)){"), t.find("const rk = await rkVorStart(plan)")
    check(0 < i_hook < i_rk and "if(verspaetet <= fenster && await cfdIndexPauseVerschieben(plan)) return" in t
          and "await suClaimSetzen(plan.id, 'verbrauch', false)   // Verbrauch: Riegel hat aufgegeben (R4b)" in t,
          "Start-Takt: vor rkVorStart — aufgegeben → nur Verbrauch mit Grund, Index-Pause → schieben")
    check("const cfdIndexRoute = p => !!p && (p.route === 'mt5' || p.route === 'mt5v2')" in html, "nur CFD/NAS100-Routen (Echo, Echo V2); Futures/Orbit/Topstep/Polar unberührt")
    check(".is('start_um_gestartet_at', null).eq('start_um', plan.startUm).select('*')" in html, "Schieben nur ungeclaimt und mit der alten Startzeit (Guard)")
    check("'index_pause'].includes(s.art)" in html and "if(s.art === 'richtung' && s.status === 'aufgegeben')" in html and "hinweis: deNichtGelaufenHinweis(r, u.grund)" in html,
          "Karte zeigt Index-Pause und aufgegebenen Riegel, Endlesung schreibt den Grund")

    # (D) SQL
    check("cfd := coalesce(new.auto_plan, false) and new.route in ('mt5', 'mt5v2');" in sql, "SQL: nur Challenge-Planer-CFD (auto_plan, mt5/mt5v2)")
    check("if coalesce(new.start_claim_art, '') = 'verbrauch' then" in sql and "return null;                           -- aufgegeben" in sql,
          "SQL: aufgegeben lässt nur den Verbrauchs-Claim durch")
    check("ende := public.prophos_cfd_fenster_ende(erst);" in sql and "public.prophos_waage_fenster_ende(p_erst)" in sql and "if ziel > ende then" in sql,
          "SQL: Fensterende = Planer-Fenster/dt-Tagesgrenze (wie Waage-Deckel) und cfd_bis")
    neunzig = sql[sql.index("  if old.start_um is not null and old.start_um < now() - interval '60 minutes' then"):sql.index("end $function$;")]
    check("prophos_gegenhedge_konflikt(new.id, new.user_id, new.master_firm, new.richtung, coalesce(old.start_um, now()))" in neunzig
          and "20 + floor(random() * 20)" in neunzig and "cfd" not in neunzig, "SQL: 90-s-Zweig unverändert")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
