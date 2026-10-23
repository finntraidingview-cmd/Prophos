#!/usr/bin/env python3
"""Selbsttest WAAGE-DECKEL (Finn 23.10.2026 ~13:50/13:55 Dubai, live 1 Long : 7 Short: „4:1 ist too much, 7:1 sowieso. Dann lieber gar keinen
Trade starten. Verschieben geht" — „Mach die Regel mit ‚würde‘" — ~14:05: „Nie mehr als 2 darf der Abstand sein. 3:1 okay, 4:1 nicht okay.
2:0 okay, 3:0 nicht mehr."). Regel: Seite des Starts − andere Seite > regeln.ausgleich.waage_max_abstand (2) → gesperrt. Ohne Netz. Geprüft:
(A) app.py ap_waage_deckel rein rechnend — 3 : 1 frei, 4 : 1 gesperrt, beide Seiten; Start in die leichte Seite nie gesperrt; leere andere
    Seite = 1 (3 : 0 frei, 4 : 0 gesperrt); CFD nie; Deckel aus regeln.ausgleich.waage_deckel (ap_ausgleich_param: Standard 3, geklemmt 1–20).
(B) ap_waage_start_lage (Startweg PC-Tab → /admin/auto-plan/waage-start → rkVorStart) mit den Zeiten vom 23.10. (Dubai):
    13:30 Aurel Tradeify S bei 2 L : 4 S → 2 : 5 frei; 13:30 Simon Topstep S (tsv2) → 2 : 6 frei (= 3 : 1); der nächste Short → 2 : 7
    gesperrt, auch über tsv2; 1 : 3 + Short gesperrt TROTZ „Gegentrade folgt" (Paar-Partner in 5 min); Drehen in die schwere Seite (Konflikt-
    fall, nachher = gedrehte Richtung) gesperrt; Long bei 1 : 5 frei; Apex zählt nicht (ohne Waage, kein Deckel); WD/gehedgt zählen nicht.
(C) Startweg DB-Claim: sql/2026-10-23_waage_deckel.sql — Trigger genau auf dem Claim, nur Auto-Pläne ohne hand_werte_at, gleiche Klassen-
    Definition wie app.py (AP_CFD_ROUTEN, WD_BALANCE_FUTURES, Tradeify CFD), gleiche Kontoarten (AP_TYPEN), gleiche Regel (seite > deckel ×
    max(andere, 1)), Wert aus regeln.ausgleich.waage_deckel (Standard 3), nur open + Claim ≤ 15 min (review für beide Seiten gleich nicht),
    10–20 min gewürfelt, nach 120 min aufgeben, Protokoll „[Waage-Deckel]"; die Futures-Erkennung aus dem SQL-Text = ap_klasse.
(D) Startweg Railway: app.py setzt den Claim (start_um_gestartet_at) nie selbst → jeder automatische Start läuft über (C).
(E) PC-Tab (prophos.html): rkVorStart prüft deckel_sperrt VOR Drehen/„folgt", dreht nur in die leichte Seite, sonst rkVerschieben mit
    „[Waage-Deckel]"; Hand-Starts (hand_werte_at, Knopf) nur Hinweis (rkDeckelHinweis).
(F) VERBRAUCH NIE BREMSEN (Master 23.10.2026): sql/2026-10-23_start_claim_art.sql (Spalte + Leeren beim Zurücknehmen des Claims), der Trigger
    lässt 'verbrauch' immer und einen Claim ohne Art > 25 min nach der Startzeit (alter Tab, „verpasst") durch; der Tab claimt Archiv/Manuell/
    Ziel/verpasst als 'verbrauch', den echten Start als 'start'. Entscheidungsmodell des Triggers mit allen Fällen, auch dem Übergang: ein
    verschobener Verbrauch wird beim nächsten Tick wieder Verbrauch (planKontoSperre VOR jedem Start), ein Plan rutscht nie als Start durch.
Aufruf: python3 tools/selftest_waage_deckel.py"""
import os
import re
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
sys.path.insert(0, HIER)
import selftest_zwei_waagen as zw  # noqa: E402

SQL = os.path.join(WURZEL, "sql", "2026-10-23_waage_deckel.sql")
HTML = os.path.join(WURZEL, "prophos.html")
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def main():
    src = open(zw.APP, encoding="utf-8").read()
    ns = zw.lade()
    D, S = ns["ap_waage_deckel"], ns["ap_waage_start_lage"]

    # ── (A) Regel: Abstand (Finn ~14:05: „3:1 okay, 4:1 nicht okay. 2:0 okay, 3:0 nicht mehr. Immer 2 darf der Abstand sein.") ──────────
    def w(nl, ns_):
        return {"n_long": nl, "n_short": ns_}
    finn = [((3, 1), "buy", False), ((4, 1), "buy", True), ((2, 0), "buy", False), ((3, 0), "buy", True), ((6, 4), "buy", False), ((7, 4), "buy", True),
            ((1, 3), "sell", False), ((1, 4), "sell", True), ((0, 2), "sell", False), ((0, 3), "sell", True), ((4, 6), "sell", False), ((4, 7), "sell", True)]
    falsch = [(lage, r, soll) for lage, r, soll in finn if D("futures", w(*lage), r)[0] != soll]
    check(not falsch, f"Finns Beispiele, beide Seiten: 3:1 frei, 4:1 gesperrt, 2:0 frei, 3:0 gesperrt, 6:4 frei, 7:4 gesperrt (falsch {falsch})")
    check(not D("futures", w(1, 7), "buy")[0] and not D("futures", w(0, 5), "buy")[0], "Start in die leichte Seite nie gesperrt (Long bei 1 : 7, 0 : 5)")
    check(not D("cfd", w(0, 9), "sell")[0], "CFD nie (dort die €-Waage)")
    check(D("futures", w(2, 4), "sell", 1.0)[0] and not D("futures", w(1, 4), "sell", 3.0)[0] and not D("futures", w(1, 3), "sell", "kaputt")[0]
          and D("futures", w(0, 3), "sell", "kaputt")[0], "Abstand aus dem Wert (1 → 2 : 4 gesperrt; 3 → 1 : 4 frei; kaputt → 2)")
    sperrt, grund = D("futures", w(1, 4), "sell")
    check(sperrt and "1 Long : 4 Short" in grund and "Abstand höchstens 2" in grund, f"Grund nennt Lage und Abstand: {grund}")
    a = {}
    exec("\n".join([re.search(r"^AP_AUSGLEICH_STANDARD = .*$", src, re.M).group(0), re.search(r"^AP_WAAGE_OHNE_FIRMEN = .*$", src, re.M).group(0),
                    src[src.index("\ndef ap_ausgleich_param(") + 1:src.find("\n\n\n", src.index("\ndef ap_ausgleich_param("))]]), a)
    P = a["ap_ausgleich_param"]
    check(P({})["waage_max_abstand"] == 2.0 and P({"ausgleich": {"waage_max_abstand": 3}})["waage_max_abstand"] == 3.0
          and P({"ausgleich": {"waage_max_abstand": 0}})["waage_max_abstand"] == 1.0 and P({"ausgleich": {"waage_max_abstand": 99}})["waage_max_abstand"] == 20.0
          and P({"ausgleich": {"waage_max_abstand": "x"}})["waage_max_abstand"] == 2.0 and "waage_deckel" not in P({}),
          "regeln.ausgleich.waage_max_abstand: Standard 2, eigener Wert, geklemmt 1–20, Unsinn → 2")

    # ── (B) Start-Lage mit den Fällen vom 23.10. (Startweg PC-Tab) ───────────────────────────────────────────────────────────
    TF, TS, AP = ("Tradeify", "tradeify", "tvv2"), ("Topstep", "topstep", "tsv2"), ("Apex Trader", "apex", "tvv2")
    jm = 13 * 60 + 30.0
    lauf, plan = zw.lauf, zw.plan
    basis = [lauf("ina", "ina", *TF, "buy", 215), lauf("l2", "chris", *TF, "buy", 215),
             lauf("ez", "ezpoker", *TF, "sell", 215), lauf("mo", "moritz", *TF, "sell", 215),
             lauf("m1", "marco", *TS, "sell", 150), lauf("m2", "marco2", *TS, "sell", 150)]          # 2 L : 4 S nach 13:27

    def stand(offen, geplant, **param):
        return {"jetzt_min": jm, "offen": offen, "geplant": geplant, "id_fest": {}, "starts_heute": [], "param": dict({"waage_max_abstand": 2.0}, **param)}
    st0 = stand(basis[:5], [plan("m2", "marco2", *TS, "sell", 150, jm)])
    L = S(st0, "m2", "sell")
    check(not L["nachher"]["deckel_sperrt"] and (L["nachher"]["n_long"], L["nachher"]["n_short"]) == (2, 4), "13:27 Marco Topstep: 2 : 3 → 2 : 4 — frei (Abstand 2)")
    st = stand(basis, [plan("aurel", "aurel", *TF, "sell", 215, jm), plan("simon", "simon", *TS, "sell", 150, jm + 5)])   # Simon erst später (≤ 2 min zählte mit)
    L = S(st, "aurel", "sell")
    check(L["zaehlt"] and L["nachher"]["deckel_sperrt"] and (L["nachher"]["n_long"], L["nachher"]["n_short"]) == (2, 5),
          "13:30 Aurel Tradeify S: 2 : 4 → 2 : 5 — jetzt GESPERRT (Abstand 3), wäre verschoben worden")
    st2 = stand(basis, [plan("simon", "simon", *TS, "sell", 150, jm)])
    L = S(st2, "simon", "sell")
    check(L["zaehlt"] and L["klasse"] == "futures" and L["nachher"]["deckel_sperrt"] and "2 Long : 5 Short" in (L["nachher"]["deckel_grund"] or ""),
          "13:30 Simon Topstep S (tsv2): 2 : 4 → 2 : 5 gesperrt — tsv2 zählt als Futures, gleicher Riegel")
    st3 = stand(basis[:4] + [lauf("aurel", "aurel", *TF, "sell", 215)], [plan("neu", "jacob", *TS, "sell", 150, jm)])
    L = S(st3, "neu", "sell")
    check(not L["nachher"]["deckel_sperrt"] and (L["nachher"]["n_long"], L["nachher"]["n_short"]) == (2, 4), "2 : 3 + Short → 2 : 4 frei (genau Abstand 2)")
    # nach Inas Ende 1 : 3 + Short, Gegentrade (EzPoker-Long) folgt in 5 min → bleibt gesperrt
    st4 = stand([lauf("l2", "chris", *TF, "buy", 215), lauf("ez", "ezpoker", *TF, "sell", 215), lauf("mo", "moritz", *TF, "sell", 215),
                 lauf("m1", "marco", *TS, "sell", 150)],
                [plan("aurel", "aurel", *TF, "sell", 215, jm), plan("ezl", "ezpoker", *TF, "buy", 215, jm + 5)])
    L = S(st4, "aurel", "sell")
    check(L["nachher"]["deckel_sperrt"] and not L["nachher"]["passt"] and "folgt" not in L["nachher"],
          "1 : 3 + Short = 1 : 4 gesperrt TROTZ „Gegentrade folgt in 5 min\" — kein Paar-Freibrief über den Deckel")
    st6 = stand([lauf("l2", "chris", *TF, "buy", 215), lauf("ez", "ezpoker", *TF, "sell", 215), lauf("mo", "moritz", *TF, "sell", 215),
                 lauf("m1", "marco", *TS, "sell", 150)], [plan("m3", "marco", *TS, "buy", 150, jm)])
    L = S(st6, "m3", "sell")   # Konfliktfall 13:27: geplant BUY, rkVorStart fragt die gedrehte Richtung SELL ab
    check(L["nachher"]["deckel_sperrt"] and not L["gegen"]["deckel_sperrt"],
          "Drehen in die schwere Seite gesperrt (Marco Topstep BUY → SELL bei 1 : 3 wäre 1 : 4), die Gegenrichtung BUY nicht")
    st7 = stand([lauf("l2", "chris", *TF, "buy", 215)] + [lauf(f"s{i}", f"u{i}", *TF, "sell", 215) for i in range(5)],
                [plan("lg", "aurel", *TF, "buy", 215, jm)])
    check(not S(st7, "lg", "buy")["nachher"]["deckel_sperrt"], "Long bei 1 : 5 frei (macht die Waage leichter)")
    st8 = stand([lauf("l2", "chris", *TF, "buy", 215)] + [lauf(f"s{i}", f"u{i}", *TF, "sell", 215) for i in range(4)],
                [plan("ap", "aurel", *AP, "sell", 200, jm)])
    L = S(st8, "ap", "sell")
    check(L.get("ohne_waage") and not L["nachher"].get("deckel_sperrt"), "Apex zählt nicht in der Waage → kein Deckel")
    st9 = stand([lauf("l2", "chris", *TF, "buy", 215)] + [lauf(f"s{i}", f"u{i}", *TF, "sell", 215) for i in range(3)]
                + [dict(lauf("wd", "mike", *TF, "sell", 215), typ="winning_days"), dict(lauf("g", "jacob", *TF, "sell", 215), gehedgt=True)],
                [plan("p", "aurel", *TF, "sell", 215, jm)])
    L = S(st9, "p", "sell")
    check(L["nachher"]["deckel_sperrt"] and (L["nachher"]["n_long"], L["nachher"]["n_short"]) == (1, 4), "WD und gehedgt zählen nicht (1 : 3 + Short = 1 : 4)")
    st10 = stand(st9["offen"], st9["geplant"], waage_max_abstand=3.0)
    check(not S(st10, "p", "sell")["nachher"]["deckel_sperrt"], "Abstand 3 aus regeln.ausgleich: 1 : 4 frei")

    # ── (C) DB-Claim (SQL-Datei) ───────────────────────────────────────────────────────────────────────────────────────────
    sql = open(SQL, encoding="utf-8").read()
    check(re.search(r"create trigger trade_plans_waage_deckel\s+before update of start_um_gestartet_at on public\.trade_plans\s+for each row "
                    r"when \(old\.start_um_gestartet_at is null and new\.start_um_gestartet_at is not null\)", sql) is not None,
          "Trigger sitzt genau auf dem Claim (start_um_gestartet_at NULL → gesetzt)")
    check("new.auto_plan is not true or new.hand_werte_at is not null" in sql, "nur automatische Starts ohne Hand-Werte (Hand nur Hinweis)")
    typen = re.findall(r"[\"'](\w+)[\"']", re.search(r"^AP_TYPEN = (.*)$", src, re.M).group(1))
    check(sql.count("in ('" + "', '".join(typen) + "')") >= 2, f"Kontoarten = AP_TYPEN {typen}")
    cfd = re.findall(r'"(\w+)"', re.search(r"^AP_CFD_ROUTEN = (.*)$", src, re.M).group(1))
    check(re.search(r"if r in \(" + ", ".join(f"'{x}'" for x in sorted(cfd, key=lambda x: -len(x))) + r"\) then return false", sql) is not None
          or re.search(r"if r in \(" + ", ".join(f"'{x}'" for x in cfd) + r"\) then return false", sql) is not None, f"CFD-Routen = AP_CFD_ROUTEN {cfd}")
    fut = re.findall(r'"([^"]+)"', re.search(r"^WD_FUTURES_FIRMEN = (.*)$", src, re.M).group(1)) + \
        re.findall(r'"([^"]+)"', re.search(r"^WD_BALANCE_FUTURES = .*$", src, re.M).group(0))
    rumpf = sql[sql.index("function public.prophos_waage_futures"):sql.index("function public.prophos_waage_deckel_lage")]
    check(sorted(set(fut)) == sorted(set(re.findall(r"strpos\(f, '([^']+)'\)", rumpf))), f"Futures-Firmen = WD_BALANCE_FUTURES {sorted(set(fut))}")

    def sql_futures(route, firm):          # Mini-Auswertung des SQL-Rumpfs (gleiche Reihenfolge)
        r, f = str(route or "").strip().lower(), str(firm or "").strip().lower()
        n = re.sub(r"[^a-z0-9]", "", f)
        if r in cfd:
            return False
        if r.startswith("tv") or r.startswith("ts"):
            return True
        if not f or ("tradeify" in n and "cfd" in n):
            return False
        return any(k in f for k in re.findall(r"strpos\(f, '([^']+)'\)", rumpf))
    a2 = {"re": re}
    exec("\n".join([re.search(rf"^{k} = .*$", src, re.M).group(0) for k in ("WD_FUTURES_FIRMEN", "WD_BALANCE_FUTURES", "AP_CFD_ROUTEN")]
                   + [src[src.index(f"\ndef {n}(") + 1:src.find("\n\n\n", src.index(f"\ndef {n}("))] for n in ("_ist_tradeify_cfd", "ap_klasse")]), a2)
    faelle = [("tvv2", "Tradeify"), ("tsv2", "Topstep"), ("mt5v2", "Tradeify CFD"), (None, "Tradeify CFD"), (None, "Apex Trader"), ("mt5", "FundedNext"),
              (None, "Lucid Trading"), (None, "FundedNext Futures"), (None, "Blue Guardian"), (None, "Alpha Futures"), ("tvplus", "Tradeify")]
    abw = [(r, f) for r, f in faelle if sql_futures(r, f) != (a2["ap_klasse"](r, f) == "futures")]
    check(not abw, f"SQL-Futures-Erkennung = app.py ap_klasse für {len(faelle)} Fälle (Abweichungen {abw})")
    check("seite - andere > max_abstand" in sql and "* greatest(andere" not in sql, "Regel wie ap_waage_deckel: Seite − andere > Abstand (kein Verhältnis mehr)")
    check("m numeric := 2" in sql and "a->>'waage_max_abstand'" in sql and "greatest(1, least(20, v::numeric))" in sql
          and "->>'waage_deckel'" not in sql and "(Abstand höchstens " in sql,
          "Wert aus regeln.ausgleich.waage_max_abstand, Standard 2, geklemmt 1–20 (wie ap_ausgleich_param), Grund „Abstand höchstens …\"")
    lage_sql = sql[sql.index("function public.prophos_waage_deckel_lage"):sql.index("function public.prophos_waage_fenster_ende")]
    check("(p.status = 'open'" in lage_sql and "'review'" not in lage_sql and f"interval '{int(ns['AP_WAAGE_CLAIM_MAX_MIN'])} minutes'" in lage_sql,
          f"gezählt: open + Claim ≤ {int(ns['AP_WAAGE_CLAIM_MAX_MIN'])} min (AP_WAAGE_CLAIM_MAX_MIN), review für beide Seiten gleich nicht")
    check("least(20, rest) - 10" in sql and "random()" in sql and sql.count("'[Waage-Deckel] '") >= 2
          and "pg_advisory_xact_lock(hashtext('prophos_waage_deckel'))" in sql,
          "verschoben 10–20 min gewürfelt (oben aufs Fensterende gedeckelt), Protokoll „[Waage-Deckel]\", Advisory-Lock")
    check("waage_ohne" in sql and "array['apex']" in sql, "Firmen ohne Waage aus regeln.ausgleich.waage_ohne, Standard Apex")

    # ── (D) Railway claimt nie selbst ──────────────────────────────────────────────────────────────────────────────────────
    setzt = [m.group(0) for m in re.finditer(r'"start_um_gestartet_at":\s*([^,}\n]+)', src)
             if not re.match(r'(?:f?"(?:is|eq)\.|None\b)', m.group(1).strip())]   # nur Filter (is./eq.) und Zurücksetzen (None)
    check(not setzt, f"app.py setzt den Claim nie selbst — jeder automatische Start geht über den DB-Riegel ({setzt})")

    # ── (E) PC-Tab ─────────────────────────────────────────────────────────────────────────────────────────────────────────
    html = open(HTML, encoding="utf-8").read()
    rk = html[html.index("  async function rkVorStart(plan){"):html.index("  window._rk = { vorStart: rkVorStart")]
    i_deckel, i_konflikt = rk.find("L.nachher.deckel_sperrt"), rk.find("        if(konflikt){")
    check(0 < i_deckel < i_konflikt, "rkVorStart prüft den Deckel vor Drehen und „Gegentrade folgt\"")
    block = rk[i_deckel:i_konflikt]
    check("!konflikt && L.gegen && rkWaageOk(L.gegen) && !L.gegen.deckel_sperrt" in block and "rkVerschieben(" in block and "[Waage-Deckel]" in block,
          "gesperrt: nur Drehen in die leichte Seite, sonst verschieben mit „[Waage-Deckel]\"")
    check("plan.autoPlan && plan.handWerteAt && !tpIstWdPlan(plan)) rkDeckelHinweis(plan)" in rk
          and "if(!plan.startUmGestartetAt && typeof rkDeckelHinweis === 'function') rkDeckelHinweis(plan)" in html,
          "Hand-Werte und Start per Knopf: nur Hinweis (rkDeckelHinweis), kein Riegel")
    # ── (F) Verbrauch nie bremsen ──────────────────────────────────────────────────────────────────────────────────────────
    ca = open(os.path.join(WURZEL, "sql", "2026-10-23_start_claim_art.sql"), encoding="utf-8").read()
    check("add column if not exists start_claim_art text" in ca
          and re.search(r"before update of start_um_gestartet_at on public\.trade_plans\s+for each row when \(old\.start_um_gestartet_at is not null "
                        r"and new\.start_um_gestartet_at is null\)", ca) is not None and "new.start_claim_art := null" in ca,
          "start_claim_art: Spalte (idempotent) + Leeren, wenn der Claim zurückgenommen wird (kein alter 'verbrauch' klebt am nächsten Start)")
    check(sorted(["2026-10-23_start_claim_art.sql", "2026-10-23_waage_deckel.sql"])[0] == "2026-10-23_start_claim_art.sql"
          and "Die Spalte start_claim_art legt auch sql/2026-10-23_start_claim_art.sql an" in sql, "eigene SQL-Datei, sortiert VOR dem Trigger (der sichert die Spalte zusätzlich selbst ab)")
    trig = sql[sql.index("function public.trade_plans_waage_deckel()"):]
    i_v, i_u, i_lock, i_lage = (trig.find("coalesce(new.start_claim_art, '') = 'verbrauch'"),
                                trig.find("new.start_claim_art is null and old.start_um is not null and old.start_um < now() - interval '25 minutes'"),
                                trig.find("pg_advisory_xact_lock"), trig.find("prophos_waage_deckel_lage(new.id"))
    check(0 < i_v < i_u < i_lock < i_lage, "Trigger: 'verbrauch' und Übergang (ohne Art, > 25 min) VOR Lock und Lage → return new")

    def trigger(art, start_vor_min, sperrt, auto=True, hand=False):
        """Modell der SQL-Entscheidung (Reihenfolge wie oben geprüft) → 'durch' | 'gebremst'."""
        if not auto or hand:
            return "durch"
        if (art or "") == "verbrauch":
            return "durch"
        if art is None and start_vor_min is not None and start_vor_min > 25:
            return "durch"
        return "gebremst" if sperrt else "durch"
    faelle = [("Ziel erreicht (neuer Tab)", trigger("verbrauch", 5, True), "durch"),
              ("Manuelle Arbeit (neuer Tab)", trigger("verbrauch", 2, True), "durch"),
              ("Archiv (neuer Tab)", trigger("verbrauch", 0, True), "durch"),
              ("verpasst (neuer Tab)", trigger("verbrauch", 40, True), "durch"),
              ("verpasst (alter Tab ohne Art, 31 min, PC-Uhr 10 s vor)", trigger(None, 30.9 - 10 / 60, True), "durch"),
              ("echter Start, Deckel sperrt", trigger("start", 1, True), "gebremst"),
              ("echter Start (alter Tab ohne Art), Deckel sperrt", trigger(None, 1, True), "gebremst"),
              ("echter Start, Deckel frei", trigger("start", 1, False), "durch"),
              ("Hand-Werte", trigger("start", 1, True, hand=True), "durch")]
    falsch = [(n, ist) for n, ist, soll in faelle if ist != soll]
    check(not falsch, f"Trigger-Modell: Verbrauch immer durch, echter Start gebremst — {len(faelle)} Fälle (falsch {falsch})")
    # Übergang: alter Tab claimt „Ziel erreicht" ohne Art → gebremst und verschoben; nächster Tick (Tab neu geladen) prüft planKontoSperre VOR
    # Richtung/Claim → claimt 'verbrauch' → durch. Kein Weg führt dabei zum echten Start (der läge erst NACH den Sperre-Zweigen).
    erst = trigger(None, 3, True)
    html2 = open(HTML, encoding="utf-8").read()
    tick = html2[html2.index("      const sperre = await planKontoSperre(plan)\n      const zielOk"):html2.index("      if(eClaim || !data || !data.length){ await suClaimFehlgriff(plan, eClaim); return }")]
    i_sp, i_rk, i_claim = tick.find("planKontoSperre(plan)"), tick.find("await rkVorStart(plan)"), tick.find("suClaimSetzen(plan.id, verspaetet > fenster ? 'verbrauch' : 'start', true)")
    zweige = [tick.find("suClaimSetzen(plan.id, 'verbrauch', false)   // Verbrauch: nie starten"), tick.find("suClaimSetzen(plan.id, 'verbrauch', false)   // Verbrauch: Manuelle Arbeit"),
              tick.find("suClaimSetzen(plan.id, 'verbrauch', false)   // Verbrauch: Ziel erreicht")]
    check(erst == "gebremst" and 0 <= i_sp < min(zweige) and all(0 < z < i_rk < i_claim for z in zweige)
          and trigger("verbrauch", 15, True) == "durch",
          "Übergang: verschobener Verbrauch → nächster Tick erkennt Archiv/Manuell/Ziel VOR Richtung und Start-Claim, claimt 'verbrauch', geht durch")
    check(tick.count("return\n") >= 3 and tick.find("suClaimSetzen(plan.id, 'verbrauch', true)   // Verbrauch: verpasst") > 0
          and tick.count("supabase.from('trade_plans').update({ start_um_gestartet_at") == 0,
          "alle Claims im Start-Takt über suClaimSetzen mit Art (verpasst nach Vorprüfung = 'verbrauch'), keiner mehr ohne")
    hilf = html2[html2.index("  async function suClaimSetzen(planId, art, guard){"):html2.index("  async function suClaimSetzen(planId, art, guard){") + 1200]
    check("start_claim_art: art" in hilf and "/start_claim_art/i.test(" in hilf and "mach({ start_um_gestartet_at: new Date().toISOString() })" in hilf,
          "suClaimSetzen: Art im selben Update; fehlt die Spalte, derselbe Claim ohne Art (Riegel bremst dann wie vorher)")
    # ── (G) Auflagen der Prüfung 23.10.2026 (A1–D) ─────────────────────────────────────────────────────────────────────────
    i_alter, i_trig = sql.find("alter table public.trade_plans add column if not exists start_claim_art text;"), sql.find("create or replace function public.trade_plans_waage_deckel()")
    check(0 <= i_alter < i_trig and "notify pgrst, 'reload schema'" in ca and "notify pgrst, 'reload schema'" in sql,
          "A1: Trigger-Datei legt die Spalte selbst an (vertauschte Reihenfolge bricht keinen Claim), beide Dateien laden das PostgREST-Schema neu")
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo
    fe_sql = sql[sql.index("function public.prophos_waage_fenster_ende"):sql.index("-- nur der Trigger")]
    check("coalesce(nullif(z->>'fenster_tz', ''), nullif(z->>'tz', ''), 'Europe/Berlin')" in fe_sql and "p_erst + interval '60 minutes'" in fe_sql
          and "least(ende, tag_ende)" in fe_sql and "at time zone 'Europe/Berlin') + interval '1 day'" in fe_sql and "if b = 0 then b := 1440" in fe_sql,
          "A2: Fensterende wie rkFensterEnde (zeiten.fenster in fenster_tz, außerhalb +60 min), höchstens bis zur deutschen Tagesgrenze")

    def fenster_ende(erst, fenster=(("02:00", "20:00", 100),), tz="Asia/Dubai"):     # Nachbau der SQL-Funktion, Live-Stand zeiten 23.10.2026
        lok = erst.astimezone(ZoneInfo(tz))
        m = lok.hour * 60 + lok.minute
        ende = erst + timedelta(minutes=60)
        for f in fenster:
            a_ = int(f[0][:2]) * 60 + int(f[0][3:]); b_ = int(f[1][:2]) * 60 + int(f[1][3:]) or 1440
            if a_ <= m < b_:
                ende = (lok.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=b_)).astimezone(timezone.utc)
                break
        bl = erst.astimezone(ZoneInfo("Europe/Berlin"))
        tag_ende = (bl.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).astimezone(timezone.utc)
        return min(ende, tag_ende)
    dub = ZoneInfo("Asia/Dubai")
    e1 = fenster_ende(datetime(2026, 10, 23, 13, 30, tzinfo=dub))
    e2 = fenster_ende(datetime(2026, 10, 23, 21, 0, tzinfo=dub))
    e3 = fenster_ende(datetime(2026, 10, 24, 1, 30, tzinfo=dub))
    check(e1.astimezone(dub).strftime("%H:%M") == "20:00" and e2 == datetime(2026, 10, 23, 22, 0, tzinfo=dub) and e3.astimezone(dub).strftime("%H:%M") == "02:00",
          f"A2: 13:30 Dubai → Ende 20:00 · 21:00 (außerhalb) → +60 · 01:30 Dubai → Tagesgrenze dt 02:00 Dubai ({e1.astimezone(dub):%H:%M}, {e2.astimezone(dub):%H:%M}, {e3.astimezone(dub):%H:%M})")
    trig2 = sql[sql.index("create or replace function public.trade_plans_waage_deckel()"):]
    i_rest, i_auf, i_ziel = trig2.find("if rest < 10 then"), trig2.find("'status', 'aufgegeben'"), trig2.find("ziel := now() + make_interval")
    check(0 < i_rest < i_auf < i_ziel and "start_um = null" not in sql and "120 minutes" not in sql,
          "A2/A3: kein neues Ziel nach dem Fensterende (Rest < 10 min wie rkVerschieben) → aufgegeben; start_um bleibt (kein NULL, keine 120-min-Uhr)")
    rk_js = html[html.index("  const rkAufgegeben = p =>"):html.index("\n", html.index("  const rkAufgegeben = p =>"))]
    check("'richtung_konflikt', jsonb_build_object('quelle', 'start', 'status', 'aufgegeben'" in trig2 and "'start', old.start_um" in trig2
          and "f.status === 'aufgegeben'" in rk_js and "Date.parse(f.start) === Date.parse(p.startUm)" in rk_js,
          "A3: aufgegeben = richtung_konflikt {status aufgegeben, start = start_um} wie der Tab — Start-Takt lässt ihn aus (rkAufgegeben), Aufräumen sieht start_um")
    check(trig2.count("public.prophos_waage_ausgeblendet(new.user_id)") == 1 and "not public.prophos_waage_ausgeblendet(p.user_id)" in sql
          and "g.verwalter_user_id is not null" in sql,
          "B1: wie Python ohne Gruppen MIT Verwalter (Plan selbst zählt nicht, Zeilen dieser IDs zählen nicht)")
    check("coalesce(a->'waage_deckel_an', 'true'::jsonb) <> 'false'::jsonb" in sql and "if not coalesce((pa->>'an')::boolean, true) then" in trig2
          and P({})["waage_deckel_an"] is True and P({"ausgleich": {"waage_deckel_an": False}})["waage_deckel_an"] is False
          and P({"ausgleich": {"waage_deckel_an": "nein"}})["waage_deckel_an"] is True,
          "B3: Not-Aus regeln.ausgleich.waage_deckel_an — Standard an, nur echtes false; SQL und Python lesen denselben Schalter")
    st_aus = stand(st9["offen"], st9["geplant"], waage_deckel_an=False)
    check(not S(st_aus, "p", "sell")["nachher"]["deckel_sperrt"] and S(st9, "p", "sell")["nachher"]["deckel_sperrt"], "B3: Schalter aus → Python sperrt nicht (an → sperrt)")
    i_cfd, i_an, i_typ, i_lock2 = (trig2.find("lower(coalesce(new.route, '')) in ('mt5', 'mt5v2')"), trig2.find("if not coalesce((pa->>'an')::boolean, true)"),
                                   trig2.find("coalesce(typ, '') not in ('challenge', 'phase1', 'phase2')"), trig2.find("pg_advisory_xact_lock"))
    check(0 < i_cfd < i_an < i_typ < i_lock2, "C: erst ohne Zählung entscheiden (CFD-Route, Hedge, Schalter, Kontoart, Futures, ohne Waage, Verwalter), DANN Lock und Lage")
    check("'waage_deckel', jsonb_build_object('status', 'wartet', 'erst', erst" in trig2 and "(wd->>'erst')::timestamptz" in trig2
          and "alt->>'erst'" not in trig2, "D: eigene Uhr in mt5_baseline.waage_deckel (erst/versuche), nicht in start_sperre")
    check(all(f"revoke all on function public.{f} from public, anon, authenticated" in sql for f in
              ("prophos_waage_deckel_param()", "prophos_waage_ausgeblendet(uuid)", "prophos_waage_deckel_lage(uuid, text)", "prophos_waage_fenster_ende(timestamptz)"))
          and "to authenticated" not in sql, "Info: Lage/Hilfen nicht für authenticated, nur Trigger + service_role")
    # D′ (Nachprüfung 23.10.2026): durchgelassen → Uhr weg; erst nur, wenn der Plan genau auf dem Riegel-Termin wartet (naechster = start_um)
    i_lage2 = trig2.find("lage := public.prophos_waage_deckel_lage(new.id, new.richtung);")
    i_weg = trig2.find("new.mt5_baseline := new.mt5_baseline - 'waage_deckel';")
    i_sperr_ret = trig2.find("return new;", i_weg)
    check(0 < i_lage2 < i_weg < i_sperr_ret < trig2.find("ende := public.prophos_waage_fenster_ende(erst);")
          and "if new.mt5_baseline ? 'waage_deckel' then" in trig2 and "(wd->>'naechster')::timestamptz = old.start_um" in trig2,
          "D′: durchgelassener Start löscht mt5_baseline.waage_deckel; erst nur bei naechster = start_um")

    def uhr(wd, alt_start, jetzt):        # Modell der SQL-Wahl → (erst, versuche)
        if (wd or {}).get("status") == "wartet" and wd.get("erst") and wd["erst"] > jetzt - timedelta(hours=24) \
                and wd.get("naechster") is not None and alt_start is not None and wd["naechster"] == alt_start:
            return wd["erst"], int(wd.get("versuche") or 0) + 1
        return alt_start or jetzt, 1
    t0 = datetime(2026, 10, 23, 13, 30, tzinfo=dub)
    wd1 = {"status": "wartet", "erst": t0, "versuche": 1, "naechster": t0 + timedelta(minutes=14)}
    e_a = uhr(wd1, t0 + timedelta(minutes=14), t0 + timedelta(minutes=14))                     # zweiter Riegel auf dem Riegel-Termin
    morgen = datetime(2026, 10, 24, 9, 5, tzinfo=dub)                                         # Start-Fehler → nachgeholt am nächsten Tag (< 24 h)
    e_b = uhr(wd1, morgen, morgen)
    check(e_a == (t0, 2) and e_b == (morgen, 1) and fenster_ende(e_b[0]).astimezone(dub).strftime("%H:%M") == "20:00",
          "D′: zweiter Riegel behält die Uhr (Versuch 2); nachgeholt am nächsten Tag → neue Uhr, Fensterende 20:00 desselben Tages statt sofort aufgegeben")
    sp = html[html.index("  function tpStartSperre(p){"):html.index("  function rkFensterEnde(")]
    check("'waage_deckel'" in sp and "Waage-Deckel" in sp, "Info: Chip „Waage-Deckel\" in tpStartSperre (wartet / aufgegeben)")
    print("\n" + ("✓ alles grün" if not FEHLER else f"✗ {len(FEHLER)} Fehler"))
    sys.exit(1 if FEHLER else 0)


if __name__ == "__main__":
    main()
