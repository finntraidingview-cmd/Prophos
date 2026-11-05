"""Selbsttest MK1 (05.11.2026, Master: „Ein Modell = ein Name überall“, Variante A): die zentrale modellName()-Tabelle in prophos.html
liefert genau die beschlossenen Namen, wegLabel/wdlWeg holen ihre Namen daraus, und die alten Abweichler („WD-Weg + Hedge“, „Echo mit Hedge“,
„Echo · mit Hedge“, „Orbit + Hedge“, „Orbit V2 · Fusion-Gegenhedge“, „Orbit V3“ als Anzeige) stehen nicht mehr in Anzeige-Texten.
Radar-Filter/-Gruppen (WDL_MODELLE, WDL_HEDGE_GRUPPEN) bleiben unverändert — ihre Schlüssel = die Namen der Tabelle.
Nur lesen, nichts live. Aufruf: python3 tools/selftest_modell_namen.py"""
import os
import re
import subprocess
import tempfile

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
fehler = 0


def check(ok, name):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    if not ok:
        fehler += 1


# 1) Funktion herauslösen und mit jsc ausführen (wegLabel/wdlWeg als Stubs: sie markieren nur, dass ein Objekt dorthin geht)
a = HTML.index("  function modellName(x){")
b = HTML.index("\n  }\n", a) + 4
fn = HTML[a:b]
js = fn + """
var wegLabel = function(p){ return 'PLAN:' + (p.route || '') }
var wdlWeg = function(t){ return 'RADAR:' + (t.route || '') }
var faelle = [
  ['echo', 'Echo'], ['echo_v2', 'Echo V2'], ['orbit', 'Orbit'], ['orbit_v2', 'Orbit V2'], ['orbit_prio2', 'Orbit Prio 2'], ['nova', 'Nova'],
  ['topstep_v2', 'Topstep V2'], ['winning_day', 'Winning Day'], ['polar', 'Polar'], ['duplikum', 'Duplikum'],
  ['mt5', 'Echo'], ['mt5v2', 'Echo V2'], ['tvv2', 'Orbit V2'], ['tvv3', 'Orbit'], ['orbit_v3', 'Orbit'], ['apex_hedge', 'Orbit Prio 2'],
  ['tsv2', 'Topstep V2'], ['wd', 'Winning Day'], ['tvplus', 'Duplikum'], ['Orbit', 'Orbit'], ['ORBIT_PRIO2', 'Orbit Prio 2'], ['Winning Day', 'Winning Day'],
  ['irgendwas', 'irgendwas'], [null, ''], [undefined, '']
]
var out = []
for(var i = 0; i < faelle.length; i++){ var r = modellName(faelle[i][0]); if(r !== faelle[i][1]) out.push(String(faelle[i][0]) + ' -> ' + r) }
if(modellName({ masterAccountId: 1, route: 'tvv2' }) !== 'PLAN:tvv2') out.push('Plan-Objekt geht nicht an wegLabel')
if(modellName({ orbitV3: true, route: 'tvv2' }) !== 'PLAN:tvv2') out.push('Plan mit orbitV3 geht nicht an wegLabel')
if(modellName({ route: 'mt5', orbit_v3: false }) !== 'RADAR:mt5') out.push('Radar-Zeile geht nicht an wdlWeg')
print(out.length ? 'FALSCH ' + out.join(' | ') : 'GLEICH')
"""
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
r = subprocess.run([JSC, d.name], capture_output=True, text=True)
os.unlink(d.name)
check(r.returncode == 0 and r.stdout.strip() == "GLEICH", f"modellName: Tabelle, Routen, Namen, Objekte ({(r.stdout + r.stderr).strip()[:300]})")

# 2) wegLabel/wdlWeg holen die Namen aus der Tabelle
wl = HTML[HTML.index("  const wegLabel = p =>"):]
wl = wl[:wl.index("\n")]
check("'" not in wl.split("=>", 1)[1].split("//")[0].replace("modellName('", "").replace("')", "").replace("'mt5v2'", "").replace("'tsv2'", ""),
      "wegLabel: keine eigenen Namens-Literale mehr")
w0 = HTML.index("  function wdlWeg(t){")
ww = HTML[w0:HTML.index("\n  }\n", w0)]
for alt in ["'Orbit V2'", "'Echo'", "'Echo V2'", "'Orbit Prio 2'", "'Nova'", "'Winning Day'", "'Topstep V2'", "'Orbit'", "'Polar'"]:
    check(re.search(r"return[^\n]*" + re.escape(alt), ww) is None, f"wdlWeg: {alt} kommt aus modellName")

# 3) Radar-Filter/-Gruppen unverändert (Schlüssel = Tabellen-Namen)
check("const WDL_MODELLE = [['Mit Hedge', ['Echo', 'Orbit', 'Nova', 'Winning Day', 'Orbit Prio 2', 'Polar']], ['Ohne Hedge', ['Echo V2', 'Orbit V2', 'Topstep V2']]]" in HTML,
      "WDL_MODELLE: Namen der Tabelle, seit MK1b mit „Orbit Prio 2“ (Filter-Knopf)")
check("const WDL_HEDGE_GRUPPEN = [['Mit Hedge', ['Orbit', 'Nova', 'Echo', 'Winning Day', 'Orbit Prio 2', 'Polar']], ['Ohne Hedge', ['Orbit V2', 'Echo V2', 'Topstep V2']]]" in HTML,
      "WDL_HEDGE_GRUPPEN unverändert")

# 4) Abweichler weg (nur Anzeige-Strings, Kommentare dürfen die alten Namen nennen)
for alt in ["['WD-Weg + Hedge'", "'Orbit + Hedge'", "'Orbit + Hedge · Final'", "'Echo · mit Hedge'", "`Echo · mit Hedge", "'Echo mit Hedge'",
            "'<b>Echo mit Hedge</b>'", "slider('Echo mit Fusion-Hedge'", "'Orbit V2 · Fusion-Gegenhedge'", "'Orbit V3' :", "(E2_MODELL)} · Fusion-Gegenhedge</span>",
            "Plan auf Echo mit Fusion-Hedge um", "Auto-Pläne vor dem Start auf Echo mit Fusion-Hedge um", "'Orbit Prio 2 (Fusion-Hedge, WD-Weg)'", "Final mit Gegenhedge"]:
    check(alt not in HTML, f"Abweichler weg: {alt}")
check("return [modellName('orbit_prio2'), 'hedge']" in HTML, "Planer-Chip Prio-2-Plan = „Orbit Prio 2“")
check("wc.textContent = hedgeAn ? modellName('winning_day')" in HTML, "WD-Farmer-Kopf = „Winning Day“")

# 5) MK1b: app.py hat dieselbe Tabelle (gleiche Schlüssel, gleiche Namen) und keine alten Abweichler mehr in Texten
import ast
APP = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
py = ast.literal_eval(re.search(r"^MODELL_NAME = (\{.*\})\s*$", APP, re.M).group(1))
js = dict(re.findall(r"(\w+): '([^']+)'", fn[fn.index("Object.freeze({"):fn.index("}))")]))
check(py == js, f"app.py MODELL_NAME = JS-Tabelle ({sorted(set(py.items()) ^ set(js.items()))})")
for alt in ["'Echo mit Hedge' if mit_hedge", "fährt immer Echo mit Hedge\"", "(f\"Echo mit Hedge: {h['lots']", "(f\"Orbit V3 (finaler Tradeify",
            "Orbit V3 mit Gegenhedge {h", "Orbit Prio 2 (Fusion-Hedge, WD-Weg): {h", '"Apex-Challenge", {"apex_hedge": True}']:
    check(alt not in APP, f"app.py-Abweichler weg: {alt}")
US = open(os.path.join(WURZEL, "tv-reader", "tv-reader.user.js"), encoding="utf-8").read()
check("'Puls-Chrome (Orbit) — einschalten'" in US and "● Orbit · Puls-Chrome" in US and "`● Orbit V3 ·" not in US and "'Puls-Chrome (Orbit V3)" not in US,
      "Userscript: Menü und Abzeichen „Orbit“ (Version bewusst nicht angehoben)")

print("ALLES GRÜN" if not fehler else f"{fehler} FEHLER")
raise SystemExit(1 if fehler else 0)
