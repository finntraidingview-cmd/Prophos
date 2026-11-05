"""Selbsttest HP1 (05.11.2026, Finn: „Bei jedem Modell, wo ich einen Trade sehe, der mit Hedgen zu tun hat, IMMER beide P&Ls“).

Teil 1 (Tab): tplDaten nimmt TP/SL in $ der Funded-Zeile als Rückfall (vorher „–“ bei fremden IDs), apIdsAusTrade trägt fusion/refund der
Delta-Zeile nach Wartet/Läuft. Teil 2 (HP1b): lt_fusion_paar (app.py, rein rechnend) liefert Fusion € an Master-TP/-SL aus den Werten am Plan —
Reihenfolge wie die Planer-Karten (funded_plan → hedge_vorschau → hedge_eur/slave_risk); die Radar-Spanne zeigt sie neben den Master-$.
Nur lesen. Aufruf: python3 tools/selftest_hedge_paare.py"""
import os
import re
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
fehler = 0


def check(ok, name):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    if not ok:
        fehler += 1


# --- lt_fusion_paar ausführen (nur diese Funktion + _wd_num) ---
def block(name):
    i = APP.index(f"\ndef {name}(") + 1
    return APP[i:APP.find("\n\n\n", i)]


ns = {}
exec(block("_wd_num") + "\n\n" + block("lt_fusion_paar"), ns)
f = ns["lt_fusion_paar"]
ECHO = {"route": "mt5", "slave_account_id": "s1"}
check(f(ECHO, {"funded_plan": {"hedge_tp_eur": -69.0, "hedge_sl_eur": 283.05}}) == (-69.0, 283.05), "Funded CFD (Echo mit Slave): funded_plan.hedge_tp/sl_eur")
check(f(dict(ECHO, slave_risk=1500), {"hedge_vorschau": {"pass_eur": -36, "blow_eur": 675}}) == (-36.0, 675.0), "Echo-Hedge: Vorschau pass/blow vor slave_risk")
check(f({"route": "tvv2", "slave_risk": 1500}, {"hedge_art": "apex", "apex_hedge": {"status": "mit"}, "hedge_vorschau": {"tp_eur": 50}}) == (-50.0, 1500.0),
      "Orbit Prio 2 mit Hedge (tp_eur positiv) → −50, ohne blow → slave_risk")
# STOPP S4 (05.11.2026): Vorschau ohne echten Hedge zählt nie
check(f({"route": "mt5v2"}, {"hedge_vorschau": {"pass_eur": -338.18, "blow_eur": 92.31}}) == (None, None), "Echo V2 mit Vorschau (ehv_tick), ohne Slave → nichts")
check(f({"route": "mt5"}, {"hedge_vorschau": {"pass_eur": -338.18, "blow_eur": 92.31}}) == (None, None), "Echo (mt5) ohne Slave → nichts")
check(f({"route": "tvv2", "slave_risk": 1500}, {"hedge_art": "apex", "apex_hedge": {"status": "ohne"}, "hedge_vorschau": {"tp_eur": 50, "blow_eur": 675}}) == (None, None),
      "Orbit Prio 2 ohne Hedge (auf Orbit V2 zurück) → nichts")
check(f({"route": "tvv2"}, {"hedge_art": "tradeify_final", "tradeify_hedge": {"status": "ohne"}, "hedge_vorschau": {"pass_eur": -40, "blow_eur": 500}}) == (None, None),
      "Tradeify-Final ohne Hedge → nichts")
check(f({"route": "tvv2", "orbit_v3": True}, {"hedge_art": "tradeify_final", "tradeify_hedge": {"status": "mit"}, "hedge_vorschau": {"pass_eur": -40, "blow_eur": 500}}) == (-40.0, 500.0),
      "Tradeify-Final mit Hedge → Vorschau")
check(f({"route": "tvv2", "slave_risk": 900}, {"hedge": {"ticket": 1, "status": "offen"}, "hedge_vorschau": {"pass_eur": -20, "blow_eur": 300}}) == (-20.0, 300.0),
      "laufender Hedge am Plan → Vorschau gilt")
check(f({"hedge_eur": 400, "slave_risk": 750}, {}) == (-400.0, 750.0), "Winning Day: hedge_eur am TP, slave_risk am Liq (wie wdPlanFusion)")
check(f({"route": "mt5v2", "slave_risk": 900}, {}) == (None, None), "ohne Hedge (Echo V2 mit slave_risk): nichts")
check(f({}, None) == (None, None) and f(None, {}) == (None, None), "leere Eingaben → (None, None)")
check(f({"hedge_eur": 0}, {"funded_plan": {"hedge_tp_eur": 0}}) == (None, None), "0 € zählt nicht als Wert")
check('**dict(zip(("fusion_tp_eur", "fusion_sl_eur"), lt_fusion_paar(p, base))),' in block("_wd_heute_zeile"), "_wd_heute_zeile gibt fusion_tp_eur/fusion_sl_eur mit")
check(",rest_hedge,slave_risk\")" in APP, "/admin/live-trades liest slave_risk")
# HP1c (Hinweis S4): auch /admin/wd-heute liest slave_risk — sonst fehlt WD-Zeilen im Radar-Heute der Fusion-€ am Liq
_wh = APP[APP.index("\ndef admin_wd_heute("):]
_wh = _wh[:_wh.index("\n\n\n")]
check('"slave_pl,pl_quelle,slave_risk")' in _wh, "/admin/wd-heute liest slave_risk")
check(f({"route": "tvv2", "hedge_eur": 400, "slave_risk": 750}, {"hedge": {"ticket": 7}}) == (-400.0, 750.0), "WD-Zeile mit slave_risk: Fusion € an TP und Liq")

# --- Tab ---
check("?? (tplNum(x.tp) > 0 ? Number(x.tp) : null) ?? tplNum(g && g.tp)," in HTML and "?? (tplNum(x.sl) > 0 ? Number(x.sl) : null) ?? tplNum(g && g.sl)," in HTML,
      "tplDaten: TP/SL in $ der Delta-Zeile vor dem Lauf-Rückfall")
check("...(rd.fusion ? { fusion: rd.fusion } : {}), ...(rd.refund != null ? { refund: rd.refund } : {}) } }" in HTML, "apIdsAusTrade: fusion/refund aus der Delta-Zeile")
w0 = HTML.index("  function wdlSpanne(t){")
sp = HTML[w0:HTML.index("\n  }\n", w0)]
check(sp.count("return fus(") == 1 and "return (l == null || r == null || l === r) ? null : fus({" in sp and "fusLinks: d0(t.fusion_sl_eur), fusRechts: d0(t.fusion_tp_eur)" in sp,
      "wdlSpanne: beide Rückgaben tragen fusLinks/fusRechts")
h0 = HTML.index("  function wdlSpanneHtml(")
sh = HTML[h0:HTML.index("\n  }\n", h0)]
check("${betrag(sp.plLinks)}${fusB(sp.fusLinks)}</small>" in sh and "${betrag(sp.plRechts)}${fusB(sp.fusRechts)}</small>" in sh, "wdlSpanneHtml: Fusion € an beiden Enden")

# fusB per jsc: Format und „nichts ohne Wert“
JSC = "/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc"
m = re.search(r"    const fusB = (v => .*?: '')\n", sh)
if m and os.path.exists(JSC):
    import subprocess
    import tempfile
    js = f"var fusB = {m.group(1)};\nprint(JSON.stringify([fusB(-69), fusB(283.05), fusB(null), fusB(undefined)]))"
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
        d.write(js)
    r = subprocess.run([JSC, d.name], capture_output=True, text=True)
    os.unlink(d.name)
    out = r.stdout.strip()
    check('rot' in out and '−69 €' in out and '+283 €' in out and out.endswith(',"",""]'), f"fusB: „↔ −69 €“ rot, „↔ +283 €“ grün, ohne Wert leer ({out[:120]} {r.stderr[:80]})")
else:
    check(False, "fusB nicht gefunden oder jsc fehlt")

print("ALLES GRÜN" if not fehler else f"{fehler} FEHLER")
sys.exit(1 if fehler else 0)
