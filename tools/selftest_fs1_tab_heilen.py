#!/usr/bin/env python3
"""Selbsttest FS1 Tab (10.11.2026, Master nach FS1): „Prophos-Tab antwortet nicht“ beim Puls-Start.
(a) Puls schreibt den Tab-Zustand aus dem Panel in Spur und Meldung (order_bot tab_zustand_kurz, panel tab_zustand_ausgabe, Herzschlag vis/geladen);
(b) dieselbe Abfrage startet im Panel die VORHANDENE Stufen-Heilung sofort (tab_heil_sofort_lage), neu laden/öffnen dort nur ohne offenen Trade
(tab_heil_sofort_riegel, Railway tab_stand_offen_n), und der Tab startet den Plan beim ersten Mal einmal nach 2–4 min neu (prophos.html sfBehoben, tab_n).
Ohne Netz. Aufruf: python3 tools/selftest_fs1_tab_heilen.py"""
import os
import re
import subprocess
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, WURZEL)
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
os.environ.setdefault("PROPHOS_FRONTEND", "1")
os.environ["SUPABASE_SERVICE_KEY"] = ""
import panel  # noqa: E402
import order_bot as ob  # noqa: E402
import app  # noqa: E402

FEHLER = []


def check(ok, text):
    print(("  ✓ " if ok else "  ✗ ") + text)
    if not ok:
        FEHLER.append(text)


print("1) Panel: Sofort-Auslöser")
L = panel.tab_heil_sofort_lage
J = 1_000_000.0
check(L({"at": 0.0}, J) == (None, "") and L({"at": J - 30, "erledigt": True}, J)[0] is None and L({"at": J - 601}, J)[0] is None,
      "ohne Auslöser, erledigt oder älter als 10 min → nichts")
d, t = L({"at": J - 30, "plan": "abcdef12-0000"}, J)
check(d == 30 and "antwortete beim Puls-Start nicht" in t and "abcdef12" in t, "frischer Auslöser → Problem mit Plan-Kurzkennung")
R = panel.tab_heil_sofort_riegel
check(R(0, None) == "" and R(0, {"offen_n": 3}) == "", "Stufe 1 (wecken) immer frei")
check(R(1, {"offen_n": 0}) == "" and "Trade offen (2)" in R(1, {"offen_n": 2}) and "nicht lesbar" in R(2, {}) and "nicht lesbar" in R(1, None)
      and "nicht lesbar" in R(1, {"offen_n": None}) and "nicht lesbar" in R(1, {"offen_n": True}), "ab Stufe 2: nur bei offen_n == 0, sonst gesperrt (fail-closed)")
S = panel.tab_heil_stufe
a, g, ep = S(None, 30, "x", J, "", True, 999, J - 60)          # Abstand-Sperre greift im normalen Weg …
check(a == "" and "wartet: letzte Heil-Folge" in g, "normaler Weg: 10-min-Abstand bleibt")
a, g, ep = S(None, 30, "x", J, "", True, 999, 0.0)              # … im Sofort-Weg wird letzte=0 übergeben
check(a == "wecken" and ep["stufe"] == 1, "Sofort-Weg: Stufe 1 wecken ohne Abstand")
a, g, _ = S(ep, 100, "x", J + 61, R(1, {"offen_n": 1}), True, 999, 0.0)
check(a == "" and "Trade offen" in g, "Stufe 2 bei offenem Trade: wartet, kein Neuladen")
a, g, _ = S(ep, 100, "x", J + 61, R(1, {"offen_n": 0}), True, 999, 0.0)
check(a == "neuladen", "Stufe 2 ohne offenen Trade: neu laden")

print("2) Panel: Tab-Zustand")
Z = panel.tab_zustand_ausgabe
z = Z(J, {"zuletzt": J - 4.2, "login": True, "sb_s": 12, "rt_aus_s": 0, "vis": "h", "geladen": int(J - 300)}, {"ep": {"stufe": 1}, "grund": "g"},
      {"at": J - 5}, {"ergebnis": "neu geladen", "ergebnis_at": J - 900}, J - 75)
check(z["ok"] and z["still_s"] == 4.2 and z["vis"] == "h" and z["geladen_vor_s"] == 300 and z["puls_abfrage_vor_s"] == 75 and z["heil_stufe"] == 1
      and z["neuladen_vor_s"] == 900 and z["sofort_vor_s"] == 5, "Felder: Abfrage, Sichtbarkeit, Ladezeit, Puls-Abfrage, Heil-Stufe, Neuladen")
z0 = Z(J, {}, {}, {}, {}, None)
check(z0["still_s"] is None and z0["geladen_vor_s"] is None and z0["puls_abfrage_vor_s"] is None and z0["vis"] == "", "alter Tab ohne Angaben → leer, kein Fehler")
check(Z(J, {"geladen": int(J + 50)}, {}, {}, {}, None)["geladen_vor_s"] is None, "Ladezeit in der Zukunft (Uhr) → unbekannt")

print("3) Bot: Meldung")
K = ob.tab_zustand_kurz
k = K(z)
check(k.startswith("Tab: ") and "letzte Abfrage vor 4 s" in k and "im Hintergrund" in k and "geladen vor 5 min" in k and "Puls-Abfrage vor 75 s" in k
      and "Heil-Stufe 1" in k, f"kurzer Beleg ({k})")
check(K({"ok": False}) == "" and K(None) == "" and "Sichtbarkeit unbekannt" in K({"ok": True}) and "nicht angemeldet" in K({"ok": True, "login": False}),
      "ohne Panel-Antwort nichts, alter Tab: Sichtbarkeit unbekannt")
src = open(os.path.join(WURZEL, "mt5-copier", "order_bot.py"), encoding="utf-8").read()
i = src.index("    def tab_abbruch(text):")
blk = src[i:src.index("        return raus(res[\"code\"], res[\"msg\"], res[\"schritt\"])", i)]
check('_tab_zustand_lesen(cmd.get("plan_id"), "tab_nicht_erreichbar")' in blk and 'msg=f"{text} — nichts gesendet, Plan bleibt Geplant."' in blk
      and blk.index("_tab_zustand_lesen") < blk.index("res.update(code=\"tab_nicht_erreichbar\""), "tab_abbruch: Zustand lesen (startet Heilung), Schlüssel-Text vorne gleich")
check("timeout=1.5" in src[src.index("def _tab_zustand_lesen"):src.index("def modus_tvkette_cdp")], "Panel-Abfrage höchstens 1,5 s")

print("4) Panel: Einbau")
q = open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8").read()
h = q[q.index("def _tab_heil_schritt(pc, still0):"):q.index("# ══ EA-SELBSTHEILUNG OHNE KNOPF")]
check("tab_heil_sofort_lage(TAB_HEIL_SOFORT, jetzt)" in h and "tab_heil_sofort_riegel(" in h
      and h.count('TAB_HEIL_SOFORT["erledigt"] = True') == 1 and 'TAB_HEIL_SOFORT.update(erledigt=True, geheilt=True)' in h, "Heil-Schritt: Sofort-Lage, Riegel, kein Abstand vor Stufe 1, erledigt nach Erfolg/Meldung")
check('0.0 if sofort and int((TAB_HEIL["ep"] or {}).get("stufe") or 0) == 0 else TAB_HEIL["letzte"]' in h
      and h.index("if sofort and not aktion:") < h.index("if aktion:\n") and "        return False\n" in h[h.index("if sofort and not aktion:"):h.index("if aktion:\n")],
      "Prüfer: Abstand nur vor Stufe 1 umgangen (auch nach Warte-Runden); wartet der Sofort-Weg, läuft der übrige Wächter weiter")
check(Z(J, {}, {}, {"at": J - 5, "erledigt": True, "geheilt": True}, {}, None)["sofort_geheilt"] is True and Z(J, {}, {}, {}, {}, None)["sofort_geheilt"] is False
      and Z(J, {}, {}, {"at": J - 5, "erledigt": True}, {}, None)["sofort_geheilt"] is False
      and Z(J, {}, {}, {"at": J - 700, "erledigt": True, "geheilt": True}, {}, None)["sofort_geheilt"] is False,
      "Runde 2 (S2): „geheilt“ nur nach gelungener Stufe der jüngsten Folge (≤ 10 min), nie nach „nur gemeldet“")
check(h.index("tab_heil_lage(still0") < h.index("tab_heil_sofort_lage"), "echtes Tab-Problem geht vor (normaler Weg bitgleich)")
r = q[q.index('if path == "/api/tab-zustand":'):q.index('if path == "/api/tsx-stand":')]
check('== "tab_nicht_erreichbar"' in r and "TAB_HEIL_SOFORT.update(" in r and 're.sub(r"[^0-9a-f-]", ""' in r, "Route: nur anlass=tab_nicht_erreichbar löst aus, Plan-ID gesäubert")
check('_TAB_OEFFNEN["klick_at"] = time.time()' in q and '_TAB_OEFFNEN["vis"] = w("vis") if w("vis") in ("v", "h") else ""' in q, "Puls-Abfrage und Sichtbarkeit gemerkt")

print("5) Railway: offene Trades je PC")
N = app.tab_stand_offen_n
check(N([{"id": "a", "status": "open"}, {"id": "b", "status": "planned"}], []) == 1 and N([{"id": "a", "status": "open"}], [{"id": "a"}, {"id": "h"}]) == 2
      and N([], []) == 0 and N(None, None) == 0, "offene Pläne der IDs + Hedges dieses PCs, je Plan einmal")
asrc = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
c = asrc[asrc.index('@app.route("/code/tab-stand/<pc>"'):asrc.index('@app.route("/reader-kurs"')]
check('"offen_n": offen_n' in c and "offen_n = None" in c and '"select": "id,status", "status": "eq.open", "user_id": "in.("' in c
      and c.index("offen_n = None") < c.index("try:   # Prüfer FS1 (SOLLTE 2/3)") and '"select": "status,start_um,start_um_gestartet_at' in c,
      "Tab-Stand liefert offen_n aus eigener Abfrage im eigenen try (ohne IDs/Fehler None), bestehende Abfrage unverändert")

print("6) Tab (prophos.html)")
h5 = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
check("vis: document.visibilityState === 'visible' ? 'v' : 'h', geladen:" in h5, "Herzschlag meldet Sichtbarkeit + Ladezeit")
check("tab_n: ((alt && Number(alt.tab_n)) || 0) + (f.schritt === 'tab_nicht_erreichbar' ? 1 : 0)" in h5, "sfMelden zählt tab_nicht_erreichbar je Plan")
b = h5[h5.index("  async function sfBehoben(plan, f){"):]
b = b[:b.index("    // EA-Selbstheilung lief noch (08.10.2026")]
check("f.schritt === 'tab_nicht_erreichbar' && Number(f.tab_n) === 1" in b and "return null" not in b[b.index("FS1 (10.11.2026, Master nach FS1"):],
      "schneller Neustart nur beim 1. Mal, sonst weiter zum 15-min-Weg (kein return null)")
m = re.search(r"  const sfTabSchnellMs = (.*?)\n  // REIN.*?\n  const sfTabLebt = (.*?)\n", h5, re.S)
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
if m and os.path.exists(JSC):
    js = (f"const S = {m.group(1)}; const L = {m.group(2)};\n"
          "const ids = ['00000000-0000', 'ffffffff-0000', 'abc', '', null, '8f3e21aa-1'];\n"
          "const ok1 = ids.every(i => { const v = S(i); return v >= 120000 && v < 240000 }) && S('8f3e21aa-1') === S('8f3e21aa-1');\n"
          "const ok2 = L({ ok: true, still_s: 3, vis: 'v' }) && L({ ok: true, still_s: 15, login: true, vis: 'v' }) && !L({ ok: true, still_s: 16, vis: 'v' })"
          " && !L({ ok: true, still_s: 2, login: false, vis: 'v' }) && !L({ ok: false, still_s: 1, vis: 'v' }) && !L(null) && !L({ ok: true, still_s: null, vis: 'v' })"
          " && !L({ _httpFail: true }) && !L({ ok: true, still_s: 3, vis: 'h' }) && !L({ ok: true, still_s: 3 })"
          " && L({ ok: true, still_s: 3, vis: 'h', sofort_geheilt: true }) && !L({ ok: true, still_s: 3, vis: 'h', sofort_erledigt: true });\n"
          "print(ok1 && ok2 ? 'JA' : 'NEIN ' + ok1 + ' ' + ok2);\n")
    f = os.path.join(os.environ.get("TMPDIR", "/tmp"), "fs1_tab.js")
    open(f, "w").write(js)
    out = subprocess.run([JSC, f], capture_output=True, text=True).stdout.strip()
    check(out == "JA", f"JS: Wartezeit gestreut 2–4 min je Plan fest, „Tab lebt“ nur bei Abfrage ≤ 15 s und sichtbar oder Heilung gegriffen ({out})")
else:
    check(bool(m), "JS-Funktionen gefunden (jsc fehlt: nur Quelltext geprüft)")
check(h5.count("${tabZ}") == 3 and "const tabZ = sfTabZustandText(claim, hier)" in h5, "m5still/puls_still-Texte ohne Antwort: Tab-Zustand hinten an")

print()
print("FEHLER: " + "; ".join(FEHLER) if FEHLER else "ALLES GRÜN")
sys.exit(1 if FEHLER else 0)
