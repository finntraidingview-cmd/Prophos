#!/usr/bin/env python3
"""Selbsttest TC1b (05.11.2026): offener Echo-Plan, Master + Hedge ≥ 60 min flach → 🟠 an die Master-IDs + Zeile in „Manuelle Arbeit“, nur Meldung.
Fälle: Chris Tradeify CFD 100k …7785 Phase 1 (70af3250, frisch, Balance 0, 0 Positionen, 0 Hedges) und drei Geist-Pläne der letzten Tage
(27cde17e Marco, c4db1e61 Mike, 114a10de Marco — Terminal von der Geist-Prüfung wieder geöffnet, frischer flacher Stand) lösen aus; ein normaler
offener Trade (1aaa8823 Marc, Position + Hedge), ein frischer Plan (< 60 min), eine alte Copier-Zeile (PC still), ein Plan nach 59 min und — S2-Stopp
zu 37ba5b49 — Zeilen MIT note („warte auf Snapshot“ bei Echo V2, „Snapshot eingefroren“) nicht: dort ist pos [] nur unbekannt, das meldet die Frost-Wache.
Dazu TC1c Weg A (Echo-Ende von Railway nach ≥ 10 min frisch flach, nur mit belegter Balance: af4f8ee8 Jacob, 70af3250 Chris). Läuft die echte echo_frost_tick mit Attrappen für Supabase und Versand. Ohne Netz. Aufruf: python3 tools/selftest_echo_flach.py"""
import ast
import os
import re
import sys
from datetime import datetime, timedelta, timezone

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "app.py"), encoding="utf-8").read()
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


baum = ast.parse(SRC)
FUNKS = ("echo_frost_urteil", "echo_gesehen_belegt", "echo_frost_stufe", "echo_frost_karenz", "echo_frost_faellig", "echo_terminal_zu", "_ts_iso", "echo_auto_ende_urteil", "_echo_auto_ende_schreiben", "_wd_num", "_liq_de",
         "lt_echo_live_wahl", "echo_flach_urteil", "echo_flach_n", "echo_flach_schritt", "echo_frost_tick", "hand_echo_flach", "admin_in_sicht")
ns = {"datetime": datetime, "timezone": timezone, "timedelta": timedelta, "time": __import__("time")}
exec(re.search(r"^MODELL_NAME = .*$", SRC, re.M).group(0), ns)
exec(re.search(r"^ECHO_FROST_ALT_S, ECHO_FROST_ERINNERN_S, ECHO_FROST_KARENZ_S = .*$", SRC, re.M).group(0), ns)
exec(re.search(r"^ECHO_FLACH_S, ECHO_FLACH_ERINNERN_S = .*$", SRC, re.M).group(0), ns)
exec(re.search(r'^ECHO_FLACH_TXT = .*$', SRC, re.M).group(0), ns)
exec(re.search(r'^ECHO_TERMINAL_ZU_TXT = .*$', SRC, re.M).group(0), ns)
exec(re.search(r"^ECHO_AUTO_ENDE_S = .*$", SRC, re.M).group(0), ns)
exec(re.search(r"^ECHO_AUTO_ERGEBNIS_ANTEIL = .*$", SRC, re.M).group(0), ns)
for f in FUNKS:
    knoten = next(k for k in baum.body if isinstance(k, ast.FunctionDef) and k.name == f)
    exec(compile(ast.Module(body=[knoten], type_ignores=[]), "app.py", "exec"), ns)

T0 = datetime(2026, 11, 5, 4, 0, tzinfo=timezone.utc).timestamp()   # 08:00 Dubai
iso = lambda ts: datetime.fromtimestamp(ts, timezone.utc).isoformat()   # noqa: E731

PLAENE = [
    {"id": "70af3250-aaaa", "user_id": "u-chris", "status": "open", "route": "mt5", "master_account_id": "k7785", "master_firm": "Tradeify CFD",
     "master_name": "100k 117785 → Phase 1", "started_at": "2026-11-05T03:06:41.890+00:00", "eg": "2026-11-05T03:07:12+00:00"},
    {"id": "27cde17e-aaaa", "user_id": "u-marco", "status": "open", "route": "mt5", "master_account_id": "k4755", "master_firm": "FundedNext",
     "master_name": "100k 26774755 → Phase 1", "started_at": "2026-11-05T00:21:00+00:00", "eg": "2026-11-05T00:22:00+00:00"},
    {"id": "c4db1e61-aaaa", "user_id": "u-mike", "status": "open", "route": "mt5", "master_account_id": "k8534", "master_firm": "FundedNext",
     "master_name": "100k 21178534 → Funded", "started_at": "2026-11-05T02:52:00+00:00", "eg": "2026-11-05T02:53:00+00:00"},
    {"id": "114a10de-aaaa", "user_id": "u-marco", "status": "open", "route": "mt5", "master_account_id": "k3615", "master_firm": "FundedNext",
     "master_name": "100k 14353615 → Phase 1", "started_at": "2026-11-05T01:43:00+00:00", "eg": None},
    {"id": "1aaa8823-aaaa", "user_id": "u-marc", "status": "open", "route": "mt5", "master_account_id": "k7821", "master_firm": "FundedNext",
     "master_name": "100k 14367821 → Funded · On Demand", "started_at": "2026-11-05T02:00:00+00:00", "eg": "2026-11-05T02:01:00+00:00"},
    {"id": "frisch01-aaaa", "user_id": "u-ina", "status": "open", "route": "mt5v2", "master_account_id": "kneu1", "master_firm": "FTMO",
     "master_name": "100k 5550001 → Phase 1", "started_at": iso(T0 + 20 * 60), "eg": None},   # beim Prüfen nach 61 min erst 41 min alt
    {"id": "note0001-aaaa", "user_id": "u-ina", "status": "open", "route": "mt5v2", "master_account_id": "knot1", "master_firm": "FTMO",
     "master_name": "100k 5550003 → Funded", "started_at": "2026-11-05T01:00:00+00:00", "eg": "2026-11-05T01:01:00+00:00"},   # Echo V2, Terminal zu
    {"id": "note0002-aaaa", "user_id": "u-mike", "status": "open", "route": "mt5", "master_account_id": "knot2", "master_firm": "FundingPips",
     "master_name": "100k 5550004 → Phase 1", "started_at": "2026-11-05T01:00:00+00:00", "eg": "2026-11-05T01:01:00+00:00"},   # eingefroren
    {"id": "still001-aaaa", "user_id": "u-jacob", "status": "open", "route": "mt5", "master_account_id": "kstil", "master_firm": "FTMO",
     "master_name": "100k 5550002 → Phase 1", "started_at": "2026-11-05T01:00:00+00:00", "eg": "2026-11-05T01:01:00+00:00"},
]
ACCS = [{"id": "k7785", "external_id": "117785"}, {"id": "k4755", "external_id": "26774755"}, {"id": "k8534", "external_id": "21178534"},
        {"id": "k3615", "external_id": "14353615"}, {"id": "k7821", "external_id": "14367821"}, {"id": "kneu1", "external_id": "5550001"},
        {"id": "kstil", "external_id": "5550002"}, {"id": "knot1", "external_id": "5550003"}, {"id": "knot2", "external_id": "5550004"}]
EINGEFROREN = "Snapshot eingefroren — Lese-EA im Master-Terminal pruefen! (Chart mit ProphosHedgeReader offen? …)"


def live(jetzt):
    return [
        {"master_login": "117785", "pc_name": "pc-c19p2l", "updated_at": iso(jetzt - 2), "note": None, "pos": [], "hd": {}},           # frisch, Balance 0
        {"master_login": "26774755", "pc_name": "pc-t8wg97", "updated_at": iso(jetzt - 5), "note": None, "pos": [], "hd": {}},   # Geist: wieder offen, flach
        {"master_login": "21178534", "pc_name": "pc-l5o8bv", "updated_at": iso(jetzt - 3), "note": None, "pos": [], "hd": {}},
        {"master_login": "14353615", "pc_name": "pc-t8wg97", "updated_at": iso(jetzt - 4), "note": None, "pos": [], "hd": {}},
        {"master_login": "5550003", "pc_name": "pc-xc5c52", "updated_at": iso(jetzt - 2), "note": "warte auf Snapshot des Master-Terminals", "pos": [], "hd": {}},
        {"master_login": "5550004", "pc_name": "pc-l5o8bv", "updated_at": iso(jetzt - 2), "note": EINGEFROREN, "pos": [], "hd": {}},
        {"master_login": "14367821", "pc_name": "pc-7ftp5l", "updated_at": iso(jetzt - 1), "note": None,
         "pos": [{"ident": 290266974, "volume": 0.22}], "hd": {"290266974": [{"ticket": 246120936, "volume": 1.29}]}},             # normaler Trade
        {"master_login": "5550001", "pc_name": "pc-xc5c52", "updated_at": iso(jetzt - 2), "note": None, "pos": [], "hd": {}},          # Plan erst 10 min alt
        {"master_login": "5550002", "pc_name": "pc-auzre5", "updated_at": iso(jetzt - 3600), "note": None, "pos": [], "hd": {}},       # PC still (alt)
    ]


GESENDET, LOG = [], set()
STATE = {"jetzt": T0}


def sb_select(tab, q):
    if tab == "accounts":
        return ACCS
    if tab == "mt5_live":
        return live(STATE["jetzt"])
    if tab == "alarm_log":
        return []
    if tab == "trade_plans":
        return [dict(PLAN_DB)] if PLAN_DB else []
    return []


PLAN_DB = {}   # Plan-Zeile für _echo_auto_ende_schreiben (TC1c-Nachzug)


def alarm_senden(prio, art, titel, text, **kw):
    GESENDET.append({"prio": prio, "art": art, "titel": titel, "text": text, **kw})
    LOG.add(kw.get("schluessel"))


ns.update(sb_select=sb_select, alarm_senden=alarm_senden, alarm_im_log=lambda keys, s: {k for k in keys if k in LOG},
          _pc_namen_daten=lambda: {"pc-c19p2l": {"name": "Chris"}, "pc-t8wg97": {"name": "Marco"}, "pc-l5o8bv": {"name": "Mike"},
                                   "pc-7ftp5l": {"name": "Marc"}, "pc-xc5c52": {"name": "Ina"}, "pc-auzre5": {"name": "Jacob"}},
          panel_lage=lambda *a: "aus", _panel_herz={}, _PANEL_HERZ_START=0, _sb_anfrage=lambda *a, **k: None, _sb_pruefen=lambda r: None,
          SUPABASE_URL="x", _sb_headers=lambda *a: {}, _echo_frost={}, _echo_frost_seit={}, _echo_gesehen=set(),
          _echo_flach_seit={}, _echo_flach_stand={}, _alarm={"gemeldet": {}})
NAMEN = {"u-chris": "Chris", "u-marco": "Marco", "u-mike": "Mike", "u-marc": "Marc", "u-ina": "Ina", "u-jacob": "Jacob"}
tick = ns["echo_frost_tick"]
flach = lambda: [g for g in GESENDET if g["art"] == "echo_offen_flach"]   # noqa: E731

tick(PLAENE, NAMEN, T0)
check(not flach(), "erster Takt: Flach-Uhr startet, noch keine Meldung")
STATE["jetzt"] = T0 + 59 * 60
tick(PLAENE, NAMEN, STATE["jetzt"])
check(not flach(), "nach 59 min flach: noch keine Meldung")
STATE["jetzt"] = T0 + 61 * 60
tick(PLAENE, NAMEN, STATE["jetzt"])
ids = sorted(g["plan_id"][:8] for g in flach())
check(ids == ["114a10de", "27cde17e", "70af3250", "c4db1e61"], f"nach 61 min: 117785 + die drei Geist-Pläne melden ({ids})")
check(all(g["prio"] == 2 and g["schluessel"].endswith("|0") and "abhaken" in g["titel"] for g in flach()), "🟠 (Stufe 2), Schlüssel …|0, Titel „abhaken“")
c = next(g for g in flach() if g["plan_id"].startswith("70af3250"))
check("Chris · Tradeify CFD …7785 (Echo)" in c["text"] and "PC von Chris (pc-c19p2l)" in c["text"] and "61 min" in c["text"], f"Text 117785: {c['text'][:120]}")
check(not any(g["plan_id"].startswith(("1aaa8823", "frisch01", "still001")) for g in flach()),
      "kein Alarm: normaler Trade mit Position + Hedge, Plan < 60 min, PC still (alte Zeile → echo_blind-Weg)")
check(not any(g["plan_id"].startswith(("note0001", "note0002")) for g in flach()) and not any(k.startswith("note") for k in ns["_echo_flach_seit"]),
      "S2: Zeile mit note (Echo V2 „warte auf Snapshot“, „Snapshot eingefroren“) + pos [] → kein „wohl zu“, keine Flach-Uhr")
fz = [g for g in GESENDET if g["plan_id"].startswith("note0002") and g["art"] in ("echo_terminal_zu", "echo_blind")]
check(len(fz) == 1 and fz[0]["art"] == "echo_terminal_zu", "eingefroren + Position gesehen → meldet die Frost-Wache (⚪ Terminal zu), wie bisher")
check(not [g for g in GESENDET if g["art"] in ("echo_blind", "echo_terminal_zu") and g["plan_id"].startswith(("70af3250", "1aaa8823"))],
      "frischer flacher Stand (117785) und normaler Trade lösen keinen echo_blind aus")
st = ns["_echo_flach_stand"]
check(sorted(k[:8] for k in st) == ids and st["70af3250-aaaa"]["text"] == ns["ECHO_FLACH_TXT"] and st["70af3250-aaaa"]["konto_id"] == "k7785",
      "„Manuelle Arbeit“-Zeilen für genau die vier Pläne")
n_vor = len(flach())
STATE["jetzt"] = T0 + 62 * 60
tick(PLAENE, NAMEN, STATE["jetzt"])
check(len(flach()) == n_vor, "nächster Takt: keine zweite Meldung (Entprellung)")
ns["_alarm"]["gemeldet"].clear()
tick(PLAENE, NAMEN, STATE["jetzt"])
check(len(flach()) == n_vor, "Railway-Neustart (Speicher leer): alarm_log verhindert die Doppelmeldung")
STATE["jetzt"] = T0 + (60 + 181) * 60
tick(PLAENE, NAMEN, STATE["jetzt"])
er = [g for g in flach() if g["schluessel"].endswith("|1")]
check(len(er) == 4 and all(g["titel"].startswith("Erinnerung:") for g in er), "Erinnerung nach weiteren 3 h, einmal je Plan")
# Position taucht wieder auf → Uhr und Zeile weg
alt_live = live
live = lambda j: [dict(z, pos=[{"ident": 1}]) if z["master_login"] == "117785" else z for z in alt_live(j)]   # noqa: E731
tick(PLAENE, NAMEN, STATE["jetzt"] + 60)
check("70af3250-aaaa" not in st and "70af3250-aaaa" not in ns["_echo_flach_seit"], "Position wieder da → Flach-Uhr und Zeile weg")
live = alt_live
tick([p for p in PLAENE if not p["id"].startswith("c4db1e61")], NAMEN, STATE["jetzt"] + 120)
check("c4db1e61-aaaa" not in st, "Plan abgehakt (nicht mehr open) → Zeile weg")

# Reine Regeln
U = ns["echo_flach_urteil"]
j = T0
check(U({"updated_at": iso(j), "pos": [], "hd": {}}, j) and U({"updated_at": iso(j), "pos": [], "hd": {"1": []}}, j), "flach: keine Position, Hedge-Liste leer")
check(not U({"updated_at": iso(j), "pos": [], "hd": {"1": [{"t": 1}]}}, j) and not U({"updated_at": iso(j), "pos": [{"x": 1}], "hd": {}}, j),
      "nicht flach: Hedge offen oder Master-Position")
check(not U({"updated_at": iso(j), "note": "warte auf Snapshot des Master-Terminals", "pos": [], "hd": {}}, j)
      and not U({"updated_at": iso(j), "note": EINGEFROREN, "pos": [], "hd": {}}, j), "S2: mit note nie flach (pos [] ist dann unbekannt)")
check(not U({"updated_at": iso(j - 10 * 60), "pos": [], "hd": {}}, j) and not U(None, j) and not U({"updated_at": "kaputt", "pos": []}, j)
      and not U({"updated_at": iso(j), "pos": None, "hd": {}}, j), "nicht flach: Zeile älter als 9 min, fehlt, kaputt oder ohne Positionsliste")
N = ns["echo_flach_n"]
check(N(None, None, j) is None and N(j - 3500, None, j) is None and N(j - 3700, j - 3000, j) is None and N(j - 3700, None, j) == 0
      and N(j - 3600 - 3 * 3600, None, j) == 1 and N(j - 5 * 3600, j - 3700, j) == 0,
      "Fälligkeit: ab 60 min flach (und Plan ≥ 60 min), Erinnerung ab +3 h — gezählt ab dem späteren Zeitpunkt (nie Erinnerung ohne erste Meldung)")
fr = [g for g in flach() if g["plan_id"].startswith("frisch01")]
check([g["schluessel"][-2:] for g in fr] == ["|0"], "später gestarteter Plan: zuerst die normale Meldung, keine Erinnerung vorweg")

# Handarbeit
H = ns["hand_echo_flach"]
z = {"plan_id": "p1", "user_id": "u1", "seit": "2026-11-05T05:00:00+00:00", "art": "offen_flach"}
check(len(H([], [z], None, set(), set())) == 1 and H([], [z], frozenset({"u2"}), set(), set()) == [] and H([], [z], None, {"u1"}, set()) == []
      and H([], [z], None, set(), {"u1"}) == [] and len(H([{"plan_id": "p1"}], [z], None, set(), set())) == 1,
      "„Manuelle Arbeit“: nur in der Sicht, ohne ausgeblendete/Verwalter-IDs, kein Plan doppelt")
a = SRC[SRC.index("def admin_handarbeit("):]
check('gr["manuell"] = hand_echo_flach(gr.get("manuell"), list(_echo_flach_stand.values()), sicht, std_aus, ausgeblendet)' in a[:a.index("antwort = {")],
      "admin_handarbeit hängt die Zeilen vor dem Zählen an (n zählt mit)")
check("if(z.art === 'offen_flach') return zeile(z," in HTML, "Handarbeit-Popup zeigt den Text der neuen Zeile")
t = SRC[SRC.index("def echo_flach_schritt("):SRC.index("# ECHO-ENDE VON RAILWAY")]
check("sb_update" not in t and "_sb_anfrage" not in t and "baselinePatch" not in t and "rpc/" not in t, "kein Schreibweg in den Plan")

# ── TC1c Weg A: Echo-Ende von Railway nach ≥ 10 min frisch flach, nur mit belegter Balance ──
E = ns["echo_auto_ende_urteil"]
J = T0
chris = {"id": "70af3250-aaaa", "status": "open", "route": "mt5", "started_at": "2026-11-05T03:06:41.890+00:00", "final_at": None, "bal0": "103576.8",
         "master_pl": None, "master_tp": "1465.00", "master_sl": "1806.00"}
jacob = {"id": "af4f8ee8-aaaa", "status": "open", "route": "mt5", "started_at": "2026-11-05T15:47:00+00:00", "final_at": None, "bal0": "95643",
         "master_pl": None, "master_tp": "2850.00", "master_sl": "713.00"}
J2 = datetime(2026, 11, 5, 19, 48, tzinfo=timezone.utc).timestamp()
z_jacob = {"updated_at": iso(J2 - 1), "note": None, "pos": [], "hd": {}, "mbal": "98266.71"}
z_chris = {"updated_at": iso(J2 - 2), "note": None, "pos": [], "hd": {}, "mbal": "0"}
acc_chris = {"tv_balance": "105144.8", "tv_balance_at": "2026-11-05T03:46:51.496+00:00"}
u, g = E(jacob, z_jacob, {}, J2 - 11 * 60, True, J2)
check(u is not None and u[0]["master_balance"] == 98266.71 and u[0]["beleg"] == "mt5_live" and u[1]["master_pl"] == 2623.71 and u[1]["status"] == "review"
      and u[1]["pl_quelle"] == "echo" and u[0]["quelle"] == "railway_flach", f"af4f8ee8 Jacob: 11 min flach, Balance 98.266,71 aus MT5 → review, P&L +2.623,71 ({g})")
u, g = E(chris, z_chris, acc_chris, J2 - 11 * 60, True, J2)
check(u is not None and u[0]["master_balance"] == 105144.8 and u[0]["beleg"] == "konto" and u[1]["master_pl"] == 1568.0
      and u[1]["ended_at"].startswith("2026-11-05T03:46:51"), f"70af3250 Chris: Balance 0 → letzte Konto-Lesung 105.144,80 nach dem Start, P&L +1.568, Ende 03:46 ({g})")
check(E(jacob, z_jacob, {}, J2 - 9 * 60, True, J2)[0] is None, "erst 9 min flach → nichts")
check(E(jacob, z_jacob, {}, J2 - 11 * 60, False, J2)[0] is None, "nie eine Position belegt → nichts")
check(E(dict(jacob, final_at="2026-11-05T19:00:00Z"), z_jacob, {}, J2 - 11 * 60, True, J2)[0] is None, "final schon am Plan (Tab) → nichts")
check(E(jacob, dict(z_jacob, note="Snapshot eingefroren …"), {}, J2 - 11 * 60, True, J2)[0] is None, "Zeile mit note → nichts (Frost-Wache)")
check(E(jacob, dict(z_jacob, hd={"1": [{"ticket": 9}]}), {}, J2 - 11 * 60, True, J2)[0] is None, "Hedge noch offen → nichts")
z_aus = dict(z_chris)
check(E(chris, z_aus, {"tv_balance": "103576.8", "tv_balance_at": "2026-11-05T05:00:00+00:00"}, J2 - 11 * 60, True, J2)[0] is None,
      "Balance 0 + Konto-Lesung = Start-Balance (Terminal evtl. nicht eingeloggt, Trade läuft) → nichts")
check(E(chris, z_aus, {"tv_balance": "105144.8", "tv_balance_at": "2026-11-05T02:00:00+00:00"}, J2 - 11 * 60, True, J2)[0] is None,
      "Konto-Lesung VOR dem Start → kein Beleg, nichts")
check(E(dict(chris, bal0=None), z_aus, acc_chris, J2 - 11 * 60, True, J2)[0] is None, "Balance 0 ohne Start-Balance → kein Ergebnis-Beleg, nichts")
u, _ = E(dict(jacob, bal0=None), z_jacob, {}, J2 - 11 * 60, True, J2)
check(u is not None and "master_pl" not in u[1], "MT5-Balance ohne Start-Balance: beenden, aber kein P&L geschätzt (Finn trägt ein)")
check(E(dict(jacob, master_pl=12.0), z_jacob, {}, J2 - 11 * 60, True, J2)[0][1].get("master_pl") is None, "vorhandener P&L wird nie überschrieben")
check(E(dict(jacob, route="tvv2"), z_jacob, {}, J2 - 11 * 60, True, J2)[0] is None, "nur Echo-Routen")
# Ablauf im Takt (Attrappe Supabase): schreibt final (Guard open) + review (Guard open), ⚪-Meldung, Uhr/Zeile weg
GESENDET.clear(); LOG.clear(); ns["_alarm"]["gemeldet"].clear(); ns["_echo_flach_seit"].clear(); ns["_echo_flach_stand"].clear()
GESCHRIEBEN = []


class _R:
    def __init__(self, d):
        self.d = d

    def json(self):
        return self.d


def _anfrage(meth, url, **kw):
    GESCHRIEBEN.append(("rpc", kw["json"]["p_plan"], kw["json"]["p_status"], sorted(kw["json"]["p_patch"])))
    return _R({"final": kw["json"]["p_patch"]["final"]})


def _update(tab, filt, upd):
    GESCHRIEBEN.append(("update", filt.get("id"), filt.get("status"), filt.get("mt5_baseline->final"), filt.get("updated_at"), upd.get("status"),
                        sorted((upd.get("mt5_baseline") or {}).keys())))
    return [{"id": filt["id"]}]


PL = [dict(jacob, user_id="u-jacob", master_account_id="k7924", master_firm="FundedNext", master_name="100k 14197924 → Funded", eg="2026-11-05T15:48:18+00:00")]
ACCS[:] = [{"id": "k7924", "external_id": "14197924", "tv_balance": "98266.71", "tv_balance_at": iso(J2 - 240)}]
live = lambda j: [{"master_login": "14197924", "pc_name": "pc-auzre5", "updated_at": iso(j - 1), "note": None, "pos": [], "hd": {}, "mbal": "98266.71"}]   # noqa: E731
ns.update(_sb_anfrage=_anfrage, sb_update=_update, _sb_pruefen=lambda r: None)
PLAN_DB.update(status="open", updated_at="2026-11-05T15:48:19.193241+00:00", mt5_baseline={"master_balance": 95643, "echo_pos_gesehen_at": "x", "puls_spur": {"ok": True}})
STATE["jetzt"] = J2 - 11 * 60
tick(PL, {"u-jacob": "Jacob"}, J2 - 11 * 60)
check(not GESCHRIEBEN, "erster flacher Takt: nichts geschrieben")
STATE["jetzt"] = J2
tick(PL, {"u-jacob": "Jacob"}, J2)
check(GESCHRIEBEN == [("update", "eq.af4f8ee8-aaaa", "eq.open", "is.null", "eq.2026-11-05T15:48:19.193241+00:00", "review",
                        ["echo_pos_gesehen_at", "final", "master_balance", "puls_spur"])],
      f"nach 11 min: EIN Update — Guard open + final fehlt + updated_at, Baseline behalten + final — {GESCHRIEBEN}")
W = ns["_echo_auto_ende_schreiben"]
GESCHRIEBEN.clear()
PLAN_DB.update(status="open", mt5_baseline={"master_balance": 95643, "final": {"closed_sum": -14.2, "at": "jetzt"}})
check(W("af4f8ee8-aaaa", {"master_balance": 1}, {"status": "review"}) is False and not GESCHRIEBEN, "Tab hat schon final geschrieben → Railway schreibt nichts (Tab-final mit closed_sum bleibt)")
PLAN_DB.update(status="review", mt5_baseline={"master_balance": 95643})
check(W("af4f8ee8-aaaa", {"master_balance": 1}, {"status": "review"}) is False and not GESCHRIEBEN, "Plan nicht mehr open → nichts")
PLAN_DB.clear()
check(W("af4f8ee8-aaaa", {"master_balance": 1}, {"status": "review"}) is False and not GESCHRIEBEN, "Plan nicht lesbar → nichts")
src_w = SRC[SRC.index("def _echo_auto_ende_schreiben("):SRC.index("def echo_frost_tick(")]
check("rpc/mt5_baseline_patch" not in src_w and src_w.count("sb_update(") == 1, "kein zweischrittiges Schreiben mehr (kein RPC, genau ein Update)")
ae = [g for g in GESENDET if g["art"] == "echo_auto_ende"]
check(len(ae) == 1 and ae[0]["prio"] == 3 and "98.266,71" in ae[0]["text"] and "+2623.71" in ae[0]["text"], f"⚪-Meldung „Echo-Plan beendet“ ({ae[0]['text'][:110] if ae else '-'})")
check("af4f8ee8-aaaa" not in ns["_echo_flach_seit"] and "af4f8ee8-aaaa" not in ns["_echo_flach_stand"], "Flach-Uhr und „Manuelle Arbeit“-Zeile weg")

print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
