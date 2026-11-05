#!/usr/bin/env python3
"""Selbsttest UNTERNEHMEN GETRENNT (UNT2, 05.11.2026, Finn-Grundsatz „Unternehmen haben nichts gegeneinander"; Bericht G2 A1–A5/A8/A11,
G2b Schritt 2). Ohne Netz, Platzhalter-IDs (U1/U2 = HT, U3 = Verwalter einer Gruppe „Emin"):
A  reine Helfer: ap_unternehmen_filter (HT = alles außer Verwalter-Gruppen, auch neue IDs), ap_unternehmen_ids, ap_unternehmen_karte,
   ap_ppl_firma_je_unternehmen / ap_ppl_firma_wahl / ap_cfd_ppl (Punktwert-Rückfall nur aus dem eigenen Unternehmen)
B  _ap_stand_laden VORHER (app.py aus `git show <basis>:app.py`) gegen NACHHER mit derselben gestellten DB:
   - HT im Hintergrund-Takt (ausgeblendet = Verwalter-Gruppe): offen/geplant/folgetag/hinweise/id_fest/basis_* BITGLEICH; anders nur
     die WD-Blöcke von U3 (starts_heute) und der Firmen-Rückfall, wo U3 die Mehrheit stellte — genau Emins Anteile
   - HT im Request mit Gruppen-Chip (ausgeblendet leer): vorher Emins Pläne im HT-Stand, nachher nicht
   - Gruppen-Stand (eigene = {U3}): nur U3 — Pläne, WD-Blöcke, Rückfall
   - _ap_stand_fuer_uid: HT-Plan → HT-Stand, Gruppen-Plan → Gruppen-Stand
C  Quelltext-Verträge: Gruppen-Aufrufer geben eigene mit, Hand-Eingriffe je Plan nehmen _ap_stand_fuer_uid, HT-Lauf ohne Gruppen-IDs,
   POST user_ids sperrt Gruppen-IDs, heute_beendet je Unternehmen gemerkt, A11 bricht ab statt eines Topfs, Hedge-Takte mit
   ap_ppl_ctx_unternehmen, prophos.html würfelt nur das eigene Unternehmen (prophos_gruppe_von), Fehler → nicht würfeln
Aufruf: python3 tools/selftest_unternehmen_getrennt.py [basis-commit, Standard: Stand vor dem UNT2-Commit]"""
import copy
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
sys.path.insert(0, HIER)
import selftest_auto_delta as sd  # noqa: E402

FEHLER = []
U1, U2, U3 = sd.U1, sd.U2, sd.U3
DATEN = {"gruppen": [{"id": "g-emin", "name": "Emin", "verwalter_id": U3}, {"id": "g-ht", "name": "Hermann Technologies", "verwalter_id": None}],
         "mitglieder": [{"user_id": U1, "gruppe_id": "g-ht"}, {"user_id": U2, "gruppe_id": "g-ht"}]}


def check(ok, text):
    print(("✓ " if ok else "✗ ") + text)
    if not ok:
        FEHLER.append(text)


def lade(src):
    """wie sd.lade, aber aus einem gegebenen Quelltext; Namen, die es dort (noch) nicht gibt, fallen weg (Basis vor UNT2)."""
    ns = {"ap_deaktiviert_anwenden": lambda k, ids=None: k, "re": re, "random": __import__("random"), "datetime": datetime, "timezone": timezone,
          "timedelta": timedelta, "json": json, "hashlib": __import__("hashlib"), "time": __import__("time"),
          "eh_stand": lambda regeln=None: {"an": False}, "ah_stand": lambda regeln=None: {"an": False}, "tfh_stand": lambda regeln=None: {"an": False},
          "ap_echo_hedge_anlegen": lambda z, k, r: {"echo": 0, "weg": []}, "ap_echo_kandidat": lambda z, k: False,
          "ap_echo_ohne_melden": lambda *a, **k: None, "lots_deckel_lots": lambda p: None, "admin_gruppen_daten": lambda: DATEN,
          "_firm_norm": lambda x: str(x or "")}
    __import__("_unt_stub").unt_stub(ns)   # UNT3: Regel je Unternehmen im Namensraum = Standard (wie die anderen Lader)

    def block(name):
        i = src.index(f"\ndef {name}(") + 1
        return src[i:src.find("\n\n\n", i)]
    for m in re.finditer(r"^AP_[A-Z0-9_]+ = .*$", src, re.M):
        try:
            exec(m.group(0), ns)
        except Exception:
            pass
    for k in ("WD_HEUTE_PPL", "LT_ECHO_ROUTEN", "LT_ECHO_MAX_ALTER_S", "ZW_CONS_FIRMEN", "TFH_STANDARD", "EH_STANDARD", "_KETTE_DLL_CACHE", "_ap_bot", "_ap_info",
              "WD_FUTURES_FIRMEN", "WD_BALANCE_FUTURES", "WD_KONTO_ABSTAND_S", "WD_ERLEDIGT_ROUTEN", "WD_FUSION_AM_PLAN", "_ap_kette", "LIQ_VERLAUF_CACHE_S",
              "_liq_verlauf_cache", "PC_STAND_LEBT_S"):
        m = re.search(rf"^{k} = .*$", src, re.M)
        try:
            exec(m.group(0), ns)
        except Exception:
            pass
    teile = [re.search(r"^AP_KW_TYP_NAME = \{.*?\}$", src, re.M | re.S).group(0)]
    namen = [n for n in sd.REIN + sd.IO + ("ap_gruppe_ausgeblendet",) if f"\ndef {n}(" in src]
    exec("\n".join(teile + [block(f) for f in namen]), ns)
    return ns


def stelle_db(ns, jetzt):
    """sd.db_stubs + Emins Zeilen: offener Trade und geplanter Plan von U3, WD-Blöcke für U1 (HT) und U3 (Emin), firm_specs von U3
    mit anderem FundedNext-Punktwert in der Mehrheit (U2 hat keine FundedNext-Zeile → Rückfall)."""
    reg, _g = sd.db_stubs(ns, jetzt)
    mitt = datetime(jetzt.year, jetzt.month, jetzt.day, tzinfo=timezone.utc)
    alt_all, alt_sel = ns["_sb_all"], ns["sb_select"]
    emin_offen = {"id": "p-e1", "user_id": U3, "master_account_id": "k-e1", "status": "open", "richtung": "sell", "started_at": (mitt + timedelta(minutes=30)).isoformat(),
                  "master_firm": "Tradeify", "master_tp": 500, "master_sl": 500, "master_contracts": 2, "master_symbol": "MNQZ6", "route": "tvv2", "mt5_baseline": {}}
    emin_plan = {"id": "p-e2", "user_id": U3, "master_account_id": "k-e2", "status": "planned", "richtung": "buy", "auto_plan": True,
                 "start_um": (mitt + timedelta(hours=20)).isoformat(), "created_at": mitt.isoformat(), "master_firm": "FundedNext",
                 "master_tp": 3000, "master_sl": 3000, "master_contracts": 2.0, "route": "mt5v2", "mt5_baseline": {}}
    ht_plan = {"id": "p-h1", "user_id": U2, "master_account_id": "k-2", "status": "planned", "richtung": "sell", "auto_plan": True,
               "start_um": (mitt + timedelta(hours=21)).isoformat(), "created_at": mitt.isoformat(), "master_firm": "FundedNext",
               "master_tp": 3000, "master_sl": 3000, "master_contracts": 2.0, "route": "mt5v2", "mt5_baseline": {}}
    konten_e = [{"id": "k-e1", "user_id": U3, "name": "TDFY E", "firm": "Tradeify", "account_type": "challenge", "external_id": "TDFY-000091"},
                {"id": "k-e2", "user_id": U3, "name": "FN E", "firm": "FundedNext", "account_type": "phase1", "external_id": "000092"}]
    wd = [{"tag": mitt.date().isoformat(), "user_id": U1, "name": "Eins", "status": "geplant", "start_um": (mitt + timedelta(hours=22)).isoformat(),
           "richtung": "buy", "konten": [{"id": "w-1", "firm": "Tradeify", "aktiv": True}]},
          {"tag": mitt.date().isoformat(), "user_id": U3, "name": "Drei", "status": "geplant", "start_um": (mitt + timedelta(hours=22, minutes=2)).isoformat(),
           "richtung": "sell", "konten": [{"id": "w-3", "firm": "Tradeify", "aktiv": True}]}]
    fs_e = [{"user_id": U3, "name": "FundedNext", "ppl": "99.0000", "symbol": None, "unit": "Lots"},
            {"user_id": U3, "name": "FundedNext", "ppl": "99.0000", "symbol": None, "unit": "Lots"}]

    def _sb_all(table, params):
        if table == "trade_plans" and params.get("status") == "eq.open":
            return alt_all(table, params) + [dict(emin_offen)]
        if table == "trade_plans" and params.get("status") == "eq.planned":
            return [dict(ht_plan), dict(emin_plan)]
        if table == "accounts":
            ids = re.findall(r"[\w-]+", params.get("id", "")[4:-1]) if params.get("id") else None
            return alt_all(table, params) + [dict(k) for k in konten_e if ids is None or k["id"] in ids]
        if table == "firm_specs":
            return [r for r in alt_all(table, params) if not (r["user_id"] == U2 and r["name"] == "FundedNext")] + [dict(r) for r in fs_e]
        return alt_all(table, params)

    def sb_select(table, params):
        if table == "wd_tagesplan":
            return copy.deepcopy(wd)
        if table == "trade_plans":
            return [{"user_id": U3}] if "p-e2" in str(params.get("id")) else [{"user_id": U2}]
        return alt_sel(table, params)
    ns.update(_sb_all=_sb_all, sb_select=sb_select, _ap_namen=lambda: ({U1: "Eins", U2: "Zwei", U3: "Drei"}, {U3}),
              _ap_plaene_mit_hand=lambda q: _sb_all("trade_plans", q), _ap_konten_mit_trade=lambda ids: set(), _ap_peaks=lambda ks: {},
              ap_startwert_kandidat=lambda a, e, d: False)
    return reg


def kurz(stand):
    """vergleichbarer Auszug (ohne Zeitstempel-Objekte)."""
    return json.loads(json.dumps({k: stand.get(k) for k in ("offen", "geplant", "folgetag", "hinweise", "id_fest", "basis_netto", "basis_brutto",
                                                           "basis_einsatz", "brutto_einsatz")}, default=str, sort_keys=True))


def uids(stand, *schl):
    return sorted({str(z.get("user_id")) for k in schl for z in stand.get(k) or ()})


def main():
    # Basis = Stand vor UNT2: Elternteil des Commits, der ap_unternehmen_filter einführt (git log -S); noch nicht committet → HEAD
    basis = sys.argv[1] if len(sys.argv) > 1 else None
    if not basis:
        ein = subprocess.run(["git", "-C", WURZEL, "log", "-1", "--format=%H", "-S", "def ap_unternehmen_filter(", "--", "app.py"],
                             capture_output=True, text=True).stdout.strip()
        basis = (ein + "^") if ein else "HEAD"
    neu_src = open(os.path.join(WURZEL, "app.py"), encoding="utf-8").read()
    alt_src = subprocess.run(["git", "-C", WURZEL, "show", f"{basis}:app.py"], capture_output=True, text=True).stdout
    n = lade(neu_src)

    # ── A reine Helfer ──
    F = n["ap_unternehmen_filter"]
    ht, gr = F(None, DATEN), F({U3}, DATEN)
    check(ht(U1) and ht(U2) and not ht(U3) and not ht("neu-ohne-zeile"), "A1 HT = Mitglieder der Gruppe ohne Verwalter; Verwalter-Gruppe und ID ohne Unternehmen (UNT0) nicht")
    check(F(None, {"gruppen": [], "mitglieder": []})("neu-ohne-zeile"), "A1b ohne Gruppen-Tabellen: alles HT wie vor den Gruppen")
    check(gr(U3) and not gr(U1) and not gr("neu-ohne-zeile"), "A2 Gruppe = genau ihre IDs")
    check(n["ap_unternehmen_ids"](U3, DATEN) == frozenset({U3}) and n["ap_unternehmen_ids"](U1, DATEN) is None
          and n["ap_unternehmen_ids"]("neu", DATEN) == frozenset({"neu"}), "A3 ap_unternehmen_ids: Gruppe · None = HT · ohne Unternehmen = nur sie selbst")
    K = n["ap_unternehmen_karte"](DATEN)
    S = n["ap_unternehmen_schluessel"]
    check(K == {U1: "ht", U2: "ht", U3: "g-emin"} and S(U1, K) == "ht" and S(U3, K) == "g-emin" and S("neu", K) == "solo:neu" and S("neu", {}) == "ht",
          "A4 Schlüssel: HT · Gruppe · ohne Unternehmen = solo:<uid> (keine Kopplung) · ohne Gruppen alles HT")
    rows = [{"user_id": U1, "name": "FTMO", "ppl": "1.0", "unit": "Lots"}, {"user_id": U3, "name": "FTMO", "ppl": "0.85", "unit": "Lots"},
            {"user_id": U3, "name": "FTMO", "ppl": "0.85", "unit": "Lots"}]
    je = n["ap_ppl_firma_je_unternehmen"](rows + [{"user_id": "neu", "name": "FTMO", "ppl": "7.0", "unit": "Lots"}], K)
    check(je["ht"]["ftmo"][0] == 1.0 and je["g-emin"]["ftmo"][0] == 0.85, "A5 Rückfall je Unternehmen getrennt (HT 1,0 / Emin 0,85 statt Mehrheit 0,85 für alle)")
    ppl, pf = n["ap_ppl_karte"](rows)
    ctx = {"ppl": {}, "ppl_firma": pf, "ppl_firma_je": je, "unternehmen_von": K}
    check(je.get("solo:neu", {}).get("ftmo", (0,))[0] == 7.0 and n["ap_cfd_ppl"](ctx, {"user_id": "neu2", "firm": "FTMO"}) is None,
          "A5b ohne Unternehmen: eigener Rückfall, eine andere ID ohne Unternehmen erbt nichts")
    check(n["ap_cfd_ppl"](ctx, {"user_id": U2, "firm": "FTMO"}) == 1.0 and n["ap_cfd_ppl"](ctx, {"user_id": U3, "firm": "FTMO"}) == 0.85,
          "A6 ap_cfd_ppl: HT-ID ohne eigene Zeile nimmt den HT-Wert, Emin-ID den Emin-Wert")
    check(n["ap_cfd_ppl"]({"ppl": {}, "ppl_firma": pf}, {"user_id": U2, "firm": "FTMO"}) == 0.85, "A7 ohne ppl_firma_je wie bisher (ein Unternehmen im ctx)")

    # ── B Stand vorher/nachher ──
    jetzt = datetime(2026, 11, 5, 9, 0, tzinfo=timezone.utc)
    if not alt_src:
        check(False, f"B Basis {basis}:app.py nicht lesbar")
    else:
        a = lade(alt_src)
        reg_a, reg_n = stelle_db(a, jetzt), stelle_db(n, jetzt)
        s_alt = a["_ap_stand_laden"](reg_a, jetzt)
        s_neu = n["_ap_stand_laden"](reg_n, jetzt)
        check(kurz(s_alt) == kurz(s_neu), "B1 HT-Takt (ausgeblendet = Emin): offen/geplant/folgetag/hinweise/id_fest/basis_* bitgleich")
        wd_alt = sorted(z["user_id"] for z in s_alt["starts_heute"] if z.get("wd"))
        wd_neu = sorted(z["user_id"] for z in s_neu["starts_heute"] if z.get("wd"))
        check(wd_alt == sorted([U1, U3]) and wd_neu == [U1], f"B2 WD-Blöcke im HT-Stand: vorher {len(wd_alt)} (mit Emin), nachher nur HT ({len(wd_neu)})")
        check([z for z in s_alt["starts_heute"] if not z.get("wd")] == [z for z in s_neu["starts_heute"] if not z.get("wd")], "B3 übrige Starts bitgleich")
        fa, fn = s_alt["ctx"]["ppl_firma"].get("fundednext"), s_neu["ctx"]["ppl_firma"].get("fundednext")
        check(fa and fa[0] == 99.0 and fn and fn[0] == 10.0, f"B4 FundedNext-Rückfall: vorher Emins Mehrheit {fa and fa[0]}, nachher HT {fn and fn[0]}")
        check(all(s_alt["ctx"]["ppl"].get(k) == v for k, v in s_neu["ctx"]["ppl"].items()) and not any(k[0] == U3 for k in s_neu["ctx"]["ppl"]),
              "B5 eigene firm_specs-Zeilen der HT-IDs bitgleich, Emins fehlen")
        # Request mit Gruppen-Chip / eingeschränktem Login: _admin_standard_aus leer → ausgeblendet ohne Emin
        for ns in (a, n):
            ns["_ap_namen"] = lambda: ({U1: "Eins", U2: "Zwei", U3: "Drei"}, set())
        c_alt, c_neu = a["_ap_stand_laden"](reg_a, jetzt), n["_ap_stand_laden"](reg_n, jetzt)
        check(U3 in uids(c_alt, "offen", "geplant"), "B6 vorher: HT-Stand im Request mit Gruppen-Chip enthielt Emins Pläne (Lücke belegt)")
        check(kurz(c_neu) == kurz(s_neu), "B7 nachher: HT-Stand gleich, egal aus welcher Sicht er geladen wird")
        g = n["_ap_stand_laden"](reg_n, jetzt, namen={U1: "Eins", U2: "Zwei", U3: "Drei"}, ausgeblendet={U1, U2}, eigene={U3})
        check(uids(g, "offen", "geplant") == [U3] and sorted(z["user_id"] for z in g["starts_heute"] if z.get("wd")) == [U3],
              "B8 Gruppen-Stand: nur U3 (Pläne + WD-Blöcke)")
        check((g["ctx"]["ppl_firma"].get("fundednext") or (0,))[0] == 99.0 and not any(k[0] != U3 for k in g["ctx"]["ppl"]), "B9 Gruppen-Stand: Rückfall nur aus der Gruppe")
        st_e = n["_ap_stand_fuer_uid"](reg_n, U3, jetzt)
        st_h = n["_ap_stand_fuer_uid"](reg_n, U2, jetzt)
        check(uids(st_e, "offen", "geplant") == [U3] and U3 not in uids(st_h, "offen", "geplant"), "B10 _ap_stand_fuer_uid: Gruppen-Plan → Gruppen-Stand, HT-Plan → HT-Stand")
        n["admin_gruppen_daten"] = lambda: (_ for _ in ()).throw(RuntimeError("Gruppen weg"))
        try:
            n["_ap_stand_laden"](reg_n, jetzt)
            check(False, "B11 Gruppen nicht lesbar → Stand scheitert (nie still über beide Unternehmen)")
        except RuntimeError:
            check(True, "B11 Gruppen nicht lesbar → Stand scheitert (nie still über beide Unternehmen)")
        n["admin_gruppen_daten"] = lambda: DATEN

    # ── C Quelltext-Verträge ──
    def fn(name):
        i = neu_src.index(f"\ndef {name}(") + 1
        m = re.search(r"\n(def |@app\.route)", neu_src[i:])
        return neu_src[i:i + m.start()] if m else neu_src[i:]
    plan = fn("ap_planen")
    check("eigene=uids if gruppe else None" in plan, "C1 ap_planen: Gruppen-Lauf lädt den Stand mit eigene = Gruppen-IDs")
    check("uids = [u for u in uids if _ht(u)]" in plan and "HT nicht geplant" in plan, "C2 HT-Lauf ohne IDs der Verwalter-Gruppen, Gruppen nicht lesbar → nicht geplant")
    check('unternehmen=frozenset(uids) if gruppe else "ht"' in plan, "C3 Tages-Saldo im Planer je Unternehmen")
    check(neu_src.count('ausgeblendet=ap_gruppe_ausgeblendet(namen, gr["ids"]), eigene=gr["ids"])') == 2
          and "ausgeblendet=ap_gruppe_ausgeblendet(namen, sicht_d), eigene=sicht_d)" in neu_src, "C4 Waage-Takt, Waage-Start, Delta-Sicht: Gruppen-Stand mit eigene")
    check(fn("_ap_nachholen_kern").count("_ap_stand_fuer_uid(reg, plan.get(\"user_id\"), jetzt)") == 1
          and "_ap_stand_fuer_uid(reg, plan.get(\"user_id\"), jetzt, tag=" in fn("_ap_werte_setzen")
          and "stand = _ap_stand_fuer_uid(reg, _puid)" in neu_src, "C5 Hand-Eingriffe je Plan (Nachholen, Startzeit, Bot-Eingriff) gegen den Stand des eigenen Unternehmens")
    check("Diese ID gehört nicht zu Hermann Technologies (Verwalter-Gruppe oder noch ohne Unternehmen)" in neu_src, "C6 POST user_ids nimmt keine Gruppen-ID und keine ID ohne Unternehmen in den HT-Planer")
    hb = fn("ap_heute_beendet_gemerkt")
    check("_ap_hb_cache_je" in hb and "unternehmen=unternehmen" in hb, "C7 heute_beendet je Unternehmen gemerkt (vorher ein Merker mit der Sicht des ersten Aufrufers)")
    check("return None" in fn("_fcp_gruppe_je_uid") and "if gruppe_je is None:" in fn("fcp_planen")
          and "return dict(erg, ok=False" in fn("fdp_planen"), "C8 A11: Gruppen nicht lesbar → Funded-Läufe brechen ab statt eines Topfs")
    check(all("ctx_ppl = ap_ppl_ctx_unternehmen(" in fn(f) for f in ("ap_echo_hedge_anlegen", "_eh_tick_lauf", "ehv_tick", "fcp_planen")),
          "C9 Hedge-/Funded-Takte: Punktwert-Rückfall je Unternehmen")
    check("elif isinstance(sicht_d, str) and ap_unternehmen_ids(sicht_d, admin_gruppen_daten()):" in neu_src and "_hb_u = _eig" in neu_src,
          "C12 Delta ohne sicht für ein Gruppen-Mitglied: Stand + heute beendet seines Unternehmens (Prüfung)")
    kt = fn("ap_kette_tick")
    check("stand_je[_uk] = _ap_stand_fuer_uid(reg, t1.get(\"user_id\"), jetzt)" in kt and "_ap_stand_laden(" not in kt, "C13 Topstep-Kette: Trade 2 gegen den Stand des Unternehmens der ID")
    check("stand = _ap_stand_fuer_uid(reg, plan.get(\"user_id\"))" in neu_src, "C14 Waage-Startprüfung ohne Planer-Gruppe: Stand des Unternehmens statt HT")
    check('"msg": f"Gruppen nicht lesbar ({type(e).__name__}) — nichts geändert"}), 502' in neu_src, "C15 POST user_ids: Gruppen nicht lesbar → 502 JSON")
    html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    check("rows = await wdNurEigenesUnternehmen(await wdRowsLaden(j.tag), uid)" in html and "if(await wdWuerfelnSchreiben(j.tag, false)) _wd.eigeneAt = 0" in html,
          "C16 wdTick: nur ungewürfelte Zeilen des eigenen Unternehmens lösen das Würfeln aus (kein 30-s-Dauertakt)")
    i = html.index("async function wdWuerfelnSchreiben(")
    ws = html[i:html.index("\n  }\n", i)]
    check("wdNurEigenesUnternehmen(await wdRowsLaden(tag), ich)" in ws and "return 0" in ws.split("const r = _wd.regeln")[0],
          "C10 prophos.html: gewürfelt wird nur über das eigene Unternehmen, Fehler → nicht würfeln")
    check("supabase.rpc('prophos_gruppe_von', { uid: k })" in html, "C11 Unternehmen aus prophos_gruppe_von (derselbe Schlüssel wie die DB-Riegel)")
    # D wdNurEigenesUnternehmen funktional (JavaScriptCore über osascript): HT-Tab sieht nur HT-Zeilen, Emin-Tab nur Emin, Fehler fliegt
    if shutil.which("osascript"):
        j0 = html.index("  const _wdUnt = new Map()")
        j1 = html.index("window._wdNurEigenesUnternehmen = wdNurEigenesUnternehmen", j0)
        js = ("var window = {}, FEHLT = false, AUFRUFE = 0;\n"
              "var supabase = { rpc: function(n, a){ AUFRUFE++; if(FEHLT) return Promise.resolve({ data: null, error: { message: 'weg' } });"
              " var g = { u1: 'g-ht', u2: 'g-ht', u3: 'g-emin', u4: null, u5: null }[a.uid]; return Promise.resolve({ data: g === undefined ? null : g, error: null }) } };\n"
              + html[j0:j1] + "\nvar ERG = {};\n"
              "var rows = [{user_id:'u1'},{user_id:'u2'},{user_id:'u3'},{user_id:'u4'},{user_id:'u5'}];\n"
              "(async function(){\n"
              " ERG.ht = (await wdNurEigenesUnternehmen(rows, 'u1')).map(function(x){return x.user_id}).join(',');\n"
              " ERG.emin = (await wdNurEigenesUnternehmen(rows, 'u3')).map(function(x){return x.user_id}).join(',');\n"
              " ERG.ohne = (await wdNurEigenesUnternehmen(rows, 'u4')).map(function(x){return x.user_id}).join(',');\n"
              " ERG.aufrufe = AUFRUFE;\n"
              " _wdUnt.clear(); FEHLT = true; try{ await wdNurEigenesUnternehmen(rows, 'u1'); ERG.fehler = 'kein Fehler' }catch(e){ ERG.fehler = 'fliegt' }\n"
              " try{ await wdNurEigenesUnternehmen(rows, ''); ERG.login = 'kein Fehler' }catch(e){ ERG.login = 'fliegt' }\n"
              "})();\nfunction run(){ return JSON.stringify(ERG) }\n")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
            f.write(js)
        r = subprocess.run(["osascript", "-l", "JavaScript", f.name], capture_output=True, text=True, timeout=30)
        os.unlink(f.name)
        try:
            e = json.loads(r.stdout.strip())
        except ValueError:
            e = {"roh": (r.stdout + r.stderr)[:300]}
        check(e.get("ht") == "u1,u2" and e.get("emin") == "u3" and e.get("ohne") == "u4", f"D1 Würfel-Zeilen je Unternehmen: HT u1,u2 · Emin u3 · ohne Unternehmen nur sich, nicht mit u5 ({e})")
        check(e.get("aufrufe") == 5, f"D2 je ID einmal gefragt, dann gemerkt ({e.get('aufrufe')} RPCs für 3 Tabs × 5 IDs)")
        check(e.get("fehler") == "fliegt" and e.get("login") == "fliegt", "D3 RPC-Fehler oder ohne Login → Fehler fliegt (wdWuerfelnSchreiben würfelt dann nicht)")
    else:
        print("  (D übersprungen: kein osascript)")
    print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
    return 1 if FEHLER else 0


if __name__ == "__main__":
    sys.exit(main())
