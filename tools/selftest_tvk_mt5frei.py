#!/usr/bin/env python3
"""Selbsttest: TV-Konten lesen trotz offener Echo-/Echo-V2-Pläne (Master 29.10.2026, Befund Chris: drei mt5v2-Trades sperrten das Lesen den
ganzen Tag). PC-Tab: tvkFrei lässt nur mt5/mt5v2 als „offener Plan" aus; Panel /api/tv-konten-liste: bei laufender MT5-Order/Polar oder Arbeit
am PC (< 120 s) → 409 belegt, kein Bot-Start. Panel-Handler mit nachgebauter Anfrage, ohne Netz/Bot.  Aufruf: python3 tools/selftest_tvk_mt5frei.py"""
import io
import json
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(WURZEL, "mt5-copier"))
import panel  # noqa: E402


class _Kopf(dict):
    def get(self, k, d=None):
        return super().get(k.lower(), d)


def aufruf(body):
    h = panel.Handler.__new__(panel.Handler)
    raw = json.dumps(body).encode()
    h.path = "/api/tv-konten-liste"
    h.headers = _Kopf({"content-length": str(len(raw)), "content-type": "application/json", "host": "127.0.0.1:8770"})
    h.rfile = io.BytesIO(raw)
    gesendet = {}
    h._send = lambda code, b, ctype=None: gesendet.update(code=code, body=json.loads(b))
    h._local_ok = lambda: True
    h.do_POST()
    return gesendet


def main():
    f = []
    ok = lambda b, t: f.append(t) if not b else print("✓", t)   # noqa: E731
    alt = {k: getattr(panel, k) for k in ("_browser_und_mt5_frei", "_win_leerlauf_s", "subprocess", "polar_panel")}
    gestartet = []

    class _Sub:
        TimeoutExpired = panel.subprocess.TimeoutExpired

        @staticmethod
        def run(*a, **k):
            # nachgezogen 11.11.2026 (ST1, Slave 2): 39596cc7 SW1b — der Bot startet über bot_argv() = [python, -c, BOT_STARTER_CODE, bot, modus, …]
            # (mit bot_ohne_cache.flag wie früher [python, bot, modus, …]); der Modus steht direkt hinter dem Bot-Pfad
            cmd = list(a[0]) if a else []
            i = 4 if len(cmd) > 1 and cmd[1] == "-c" else 2
            gestartet.append(cmd[i] if len(cmd) > i else "?")
            return type("R", (), {"stdout": json.dumps({"ok": True, "konten": ["APEX-1"], "trail": "x"}), "stderr": ""})()
    try:
        panel.subprocess = _Sub
        panel.polar_panel = None
        b = {"konto": "APEX0000000000001", "firma": "Apex Trader"}
        panel._browser_und_mt5_frei, panel._win_leerlauf_s = (lambda tv_eigen=False: False), (lambda: 999)
        r = aufruf(b)
        ok(r["code"] == 409 and r["body"]["code"] == "puls_beschaeftigt" and "MT5" in r["body"]["msg"] and not gestartet
           and not panel.TV_ORDER_LOCK.locked(), f"MT5-Order läuft → 409 belegt, kein Bot-Start, Lock wieder frei ({r['body'].get('msg')})")
        panel._browser_und_mt5_frei, panel._win_leerlauf_s = (lambda tv_eigen=False: True), (lambda: 30)
        r = aufruf(b)
        ok(r["code"] == 409 and "gearbeitet" in r["body"]["msg"] and not gestartet, "am PC wird gearbeitet (30 s) → 409 belegt")
        panel._win_leerlauf_s = lambda: 300
        r = aufruf(b)
        ok(r["code"] == 200 and r["body"].get("ok") is True and gestartet == ["tvkontenliste"], f"frei + Leerlauf 300 s → Bot liest ({gestartet})")
        panel._win_leerlauf_s = lambda: None     # Mac/ohne Windows: Leerlauf unbekannt → wie bisher
        gestartet.clear()
        r = aufruf(b)
        ok(r["code"] == 200 and gestartet == ["tvkontenliste"], "Leerlauf unbekannt (kein Windows) → wie bisher lesen")
    finally:
        for k, v in alt.items():
            setattr(panel, k, v)
    ph = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    # ── PA1f (Finn 25.11.2026: „Er darf immer dann lesen, wenn Puls ganz normal raus darf. Wenn z. B. ein Orbit-Trade kurz vor TP oder SL
    # steht, dann nicht."): keine Pauschal-Sperre „offener Plan"/„Big Trade läuft" mehr, stattdessen der echte Puls-heim-Riegel (pulsHeimFrei)
    i = ph.index("  function tvkFrei(){")
    blk = ph[i:ph.index("  async function tvkTick(){", i)]
    frei_fn = blk[:blk.index("  async function tvkPulsDarfRaus(")]
    raus_fn = blk[blk.index("  async function tvkPulsDarfRaus("):]
    j0 = ph.index("  async function pulsHeimFrei(konto, fenster){")
    heim_fn = ph[j0:ph.index("  // External ID des Master-Kontos", j0)]
    ok("offener Plan (nicht Echo)" not in frei_fn and "bigTradePlan()" not in frei_fn and "sofort" not in frei_fn.split("{", 1)[0],
       "PC-Tab: Pauschal-Sperren „offener Plan (nicht Echo)“ und „Big Trade/Winning Day läuft“ sind raus (auch die Einmal-Marke sofort)")
    ok("TVK_START_ABSTAND_MS" in frei_fn and "hedgePulsUnterwegs()" in frei_fn and "polarLaeuft()" in frei_fn and "_osBusy || _osActive || _rsAktiv" in frei_fn
       and "_hwWiederTimer" in frei_fn, "PC-Tab: Start < 45 min, Puls unterwegs, Polar, Signal/Fern-Lauf, Heimweg/Endlesung bleiben")
    ok("await pulsHeimFrei('', 'tv')" in raus_fn, "PC-Tab: derselbe Riegel wie jeder Kontowechsel (pulsHeimFrei, TradingView-Fenster, ohne Konto-Abkürzung)")
    tk = ph[ph.index("  async function tvkTick(){"):ph.index("  window._tvKonten = {")]
    ok("nur_sofort" not in tk and "tvkFrei(true)" not in tk and "await tvkPulsDarfRaus()" in tk and "bigTradeHeimPlanen(a.ext || '', 'TV-Konten lesen', true, 'tv')" in tk,
       "PC-Tab: Riegel nach dem Holen, gesperrt → „belegt“ (kein Fehlversuch), danach Heimweg wie nach jedem Start")
    ok("&verschieben=${encodeURIComponent(String(sperre).slice(0, 160))}" in tk and "/^kein (PC-Tab|Puls-Chrome)/.test(sperre)" in tk
       and tk.index("&verschieben=") < tk.index("/pc/tv-konten-auftrag?pc=${pcq}`"),
       "PC-Tab (PA1f-Zusatz): darf gerade nicht raus → fällige Kauf-Aufträge sichtbar verschieben (Grund mit), nichts holen; ohne Puls-Chrome nie")
    # echte Funktionen in JavaScriptCore: tvkFrei + tvkPulsDarfRaus + pulsHeimFrei, Railway /admin/puls-heim nachgestellt
    js = r"""
const window = { mtcApi: () => 0, _epLokal: null }; let MT5_LOCAL = true, _bthSelbst = false;
let tradePlans = [], _BT = null, _ANTWORT = null, _FRAGEN = 0, _UNTERWEGS = '';
const TVK_START_ABSTAND_MS = 45 * 60000, WATCHER_HOME = 'https://railway.invalid';
let _osBusy = false, _osActive = false, _rsAktiv = false, _hwWiederTimer = null, _hwEndHalt = null;
const polarLaeuft = () => false, polarStartSperre = () => false, hedgePulsUnterwegs = () => _UNTERWEGS;
const bigTradePlan = f => (f === 'tv' ? _BT : null), tvV2Konto = p => p.ext, hedgePcId = () => 'pc-test1';
const pulsStehtImKonto = async k => !!k;   // wie das Original: ohne Konto nie „steht schon im Konto"
const supabase = { auth: { getSession: async () => ({ data: { session: { access_token: 'tok' } } }) } };
class AbortController { constructor(){ this.signal = {} } abort(){} }
const setTimeout = () => 0, clearTimeout = () => 0, console = { info(){}, warn(){} };
const fetch = async url => { _FRAGEN++; if(_ANTWORT === 'weg') throw new Error('netz'); return { ok: true, status: 200, json: async () => _ANTWORT } };
""" + frei_fn + heim_fn + raus_fn + r"""
const fall = async (name, bt, antwort, plaene) => { _BT = bt; _ANTWORT = antwort; _FRAGEN = 0; tradePlans = plaene || [];
  window._epLokal = { ab: Date.now(), stand: { positionen_tab: 'puls-1' } };
  return { name, frei: tvkFrei(), raus: await tvkPulsDarfRaus(), fragen: _FRAGEN } };
(async () => {
  const offen = [{ status: 'open', route: 'tvv2' }, { status: 'open', route: 'tsv2' }, { status: 'open', route: 'tvplus' }];
  const r = [];
  r.push(await fall('ohne', null, null, offen));
  r.push(await fall('wd_weit', { ext: 'LFE1' }, { ok: true, frei: true }, offen));
  r.push(await fall('orbit_tp', { ext: 'TDFYSL1' }, { ok: true, frei: false, code: 'big_trade_nah', grund: 'Tradeify …0431 ist 83 $ vor dem TP — Puls bleibt im Konto' }, offen));
  r.push(await fall('wd_sl', { ext: 'LFE2' }, { ok: true, frei: false, code: 'big_trade_nah', grund: 'Winning Day Lucid …0002 ist 40 $ vor der Liq — Puls bleibt im Konto' }, offen));
  r.push(await fall('weg', { ext: 'LFE1' }, 'weg', offen));
  r.push(await fall('kaputt', { ext: 'LFE1' }, { ok: false }, offen));
  const bald = [{ status: 'planned', startUm: new Date(Date.now() + 30 * 60000).toISOString() }];
  r.push(await fall('start30', null, null, bald));
  _UNTERWEGS = 'Puls-Order'; r.push(await fall('unterwegs', null, null, [])); _UNTERWEGS = '';
  print(JSON.stringify(r));
})();
"""
    import subprocess
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
        d.write(js)
    p = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
    os.unlink(d.name)
    try:
        r = {x["name"]: x for x in json.loads(p.stdout.strip().splitlines()[-1])}
    except Exception:
        r = {}
        print(p.stdout[-2000:], p.stderr[-2000:])
    g = lambda n: r.get(n) or {}   # noqa: E731
    ok(g("ohne").get("frei") == "" and g("ohne").get("raus") == "" and g("ohne").get("fragen") == 0,
       "offene Trades (tvv2/tsv2/tvplus) ohne Big Trade/WD im TV-Fenster → frei, keine Anfrage")
    ok(g("wd_weit").get("frei") == "" and g("wd_weit").get("raus") == "" and g("wd_weit").get("fragen") == 1,
       "offener Winning Day weit weg vom TP → Railway frei → lesen")
    ok(g("orbit_tp").get("raus", "").startswith("Tradeify …0431 ist 83 $ vor dem TP") and g("orbit_tp").get("fragen") == 1,
       f"Orbit nahe TP → gesperrt mit Grund ({g('orbit_tp').get('raus')})")
    ok("vor der Liq" in g("wd_sl").get("raus", ""), "Winning Day nahe SL/Liq → gesperrt")
    ok(g("weg").get("raus") and g("kaputt").get("raus"), "Railway weg / Antwort kaputt → gesperrt (fail-closed)")
    ok(g("start30").get("frei", "").startswith("Start in"), "Start in < 45 min sperrt weiter")
    ok(g("unterwegs").get("frei") == "Puls-Order", "Puls unterwegs sperrt weiter")
    j = ph.index("  function tvnRuhe(")
    ok("p.status === 'open' && !echo(p))) return 'offener Plan'" in ph[ph.index("  function tvnPlanSperre("):j],
       "TV-Neuladen/Tampermonkey (tvnPlanSperre): offene Pläne außer mt5/mt5v2 sperren")
    for t in f:
        print("✗", t)
    print("alle Tests bestanden" if not f else f"FEHLER ({len(f)})")
    return 1 if f else 0


if __name__ == "__main__":
    sys.exit(main())
