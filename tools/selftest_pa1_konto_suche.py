#!/usr/bin/env python3
"""Selbsttest PA1 (Finn 25.11.2026: „Wenn ich bei Futures gekauft habe, drücke ich nur auf ‚Gekauft'. Dann soll der Knopf grün werden und dort
die Zeit stehen, wann überprüft wird.") — Klick „Gekauft" → Auftrag art 'gekauft' (fällig 1 min–5 h gestreut) → Puls liest die Konto-Liste
(bestehender Weg) → Railway: neu = Eval-Kennungen der Firma − alle Konten aller IDs → anlegen mit Vorlage, Überzahl → 🟠 ohne Anlage.
Rein rechnende Teile echt (per AST aus app.py gezogen), Wege/Routen/Frontend als Quelltext-Prüfung.
Aufruf:  python3 tools/selftest_pa1_konto_suche.py [pfad/zu/app.py]"""
import ast
import os
import random
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HIER = os.path.dirname(os.path.abspath(__file__))
APP = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HIER, "..", "app.py")
SRC = open(APP, encoding="utf-8").read()
HTML = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
SQL = open(os.path.join(HIER, "..", "sql", "2026-11-25_pa1_konto_suche.sql"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


NAMEN = {"_wd_num", "tv_konto_normal", "admin_konto_ext_norm", "admin_konto_doppel", "TV_KONTEN_NAME_RE", "ADMIN_KONTO_APEX_RE", "ADMIN_MAIL_UID_RE",
         "PA1_MUSTER", "PA1_FIRMEN", "PA1_TYPEN", "PA1_BESTANDEN_TYPEN", "PA1_VERZUG_MIN_S", "PA1_VERZUG_MAX_S", "PA1_VERZUG_WE_MAX_S",
         "PA1_NACH_MIN_S", "PA1_NACH_MAX_S", "PA1_NACH_WE_MIN_S", "PA1_NACH_WE_MAX_S", "PA1_FRIST_S", "PA1_FRIST_WE_S", "PA1_VORHER_S",
         "PA1_MAX_ANZAHL", "PA1_MAX_FEHLVERSUCHE", "PA1_PHASE", "pa1_verzug_s", "pa1_iso", "pa1_wochenende", "pa1_klick_zeiten", "pa1_naechste",
         "pa1_art", "PA1_GROESSE_PRAEFIX", "pa1_groesse_passt", "pa1_name", "pa1_konto_zeile", "pa1_neue", "pa1_urteil", "pa1_offen_bestanden", "pa1_weiter", "pa1_nach_fehler", "pa1_hm",
         "pa1_knopf", "pa1_klick_lesen", "pa1_posten", "pa1_posten_plus", "pa1_nachgekauft", "pa1_posten_rest", "pa1_zuordnen", "pa1_bezug",
         "pa1_posten_minus", "PA1_SCHIEB_MIN_S", "PA1_SCHIEB_MAX_S", "PA1_UEBERFAELLIG_S", "pa1_verschieben_body"}
baum = ast.parse(SRC)
teile = []
for n in baum.body:
    if isinstance(n, ast.FunctionDef) and n.name in NAMEN:
        teile.append(ast.get_source_segment(SRC, n))
    elif isinstance(n, ast.Assign) and any(isinstance(t, ast.Tuple) and any(isinstance(e, ast.Name) and e.id in NAMEN for e in t.elts)
                                           or isinstance(t, ast.Name) and t.id in NAMEN for t in n.targets):
        teile.append(ast.get_source_segment(SRC, n))
ns = {"re": re, "random": random, "time": time, "datetime": datetime, "timedelta": timedelta, "timezone": timezone, "ZoneInfo": ZoneInfo}
exec("\n\n".join(teile), ns)
fehlend = sorted(x for x in NAMEN if x not in ns)
check(not fehlend, f"alle PA1-Bausteine in app.py gefunden {fehlend or ''}")
g = type("G", (), ns)

# ── pa1_neue: Abgleich gegen alle Konten aller IDs ──
KONTEN = [  # andere ID, archiviert zählt mit (Liste enthält alle)
    {"user_id": "x", "name": "150k TDFYSL150104577938 → Challenge", "external_id": "TDFYSL150104577938", "firm": "Tradeify"},
    {"user_id": "y", "name": "150k FTDFYSLX150132677414 → Funded", "external_id": "FTDFYSLX150132677414", "firm": "Tradeify"},
    {"user_id": "z", "name": "50k altes Konto TDFYSL050999888777 ohne ext", "external_id": None, "firm": "Tradeify"},
    {"user_id": "z", "name": "APEX", "external_id": "APEX6416990000021", "firm": "Apex Trader"},
]
gelesen = ["TDFYSL150104577938", "FTDFYSLX150132677414", "TDFYSL150555000111", "TDFYSL150555000222", "tdfysl150555000111", "TDFYSL050999888777",
           "TDFYSL150000000001", "TDFYSL150000000002", "kurz", "TDFYSL…"]
t = g.pa1_neue(gelesen, "Tradeify", KONTEN, vorher={"TDFYSL150000000001"}, weg={"TDFYSL150000000002"})
check(t["challenge"] == ["TDFYSL150555000111", "TDFYSL150555000222"] and not t["unklar"],
      f"Tradeify: nur echte Neue (bekannt/Funded/Name-enthält/vorher/verworfen/Doppel/gekürzt raus) → {t['challenge']}")
t = g.pa1_neue(["APEX-641699-21", "PA-APEX-700001-01", "APEX-700001-02"], "Apex Trader", KONTEN)
check(t["challenge"] == ["APEX7000010000002"] and t["funded"] == ["PAAPEX7000010000001"], f"Apex: Eval neu (normiert), PA = Funded nie ein Kauf → {t}")
check(not any(g.pa1_neue(["TDFYSL150555000111"], "Topstep", []).values()) and not any(g.pa1_neue(["X1234567"], "Tradeify CFD", []).values()),
      "Topstep/CFD: nie etwas")
check(g.pa1_neue(["LFF05097865230001", "LFE050111111110001"], "Lucid Trading", [])["challenge"] == ["LFE050111111110001"], "Lucid: LFE ja, LFF (funded) nein")
check(g.pa1_neue(["FNFTFAFINNSAMUELHERM10001", "FNFTCHFINNSAMUELHERM20002"], "FundedNext Futures", [])["challenge"] == ["FNFTCHFINNSAMUELHERM20002"],
      "FundedNext Futures: Challenge ja, Funded nein")
check(g.pa1_neue(["LFE050111111110001"], "Tradeify", [])["unklar"] == ["LFE050111111110001"], "Kennung ohne Muster der Firma → unklar")
# Muster aus den echten External IDs (Stichproben aus accounts, 25.11.2026)
ECHT = [("Tradeify", "TDFYSL150104577938", "challenge"), ("Tradeify", "FTDFYSLX150132677414", "funded"), ("Apex Trader", "APEX4503090000004", "challenge"),
        ("Apex Trader", "PAAPEX4503090000003", "funded"), ("Lucid Trading", "LFE050100730720001", "challenge"), ("Lucid Trading", "LFF05097865230001", "funded"),
        ("FundedNext Futures", "FNFTCHJONAANTONIOLOG1610", "challenge"), ("FundedNext Futures", "FNFTFAAMIRSHARIF66387", "funded"),
        ("MyFundedFutures", "MFFUEVPRO656214001", "challenge"), ("MyFundedFutures", "MFFUSFPRO656214009", "funded"),
        ("FTMO Futures", "FTMO110764", "mehrdeutig"), ("FTMO Futures", "FTMO409613", "mehrdeutig")]
falsch = [(f, k, g.pa1_art(k, f)) for f, k, soll in ECHT if g.pa1_art(k, f) != soll]
check(not falsch, f"Muster-Tabelle passt zu echten Challenge-/Funded-Nummern je Firma {falsch or ''}")
check(g.pa1_neue(["FTMO123456"], "FTMO Futures", [])["challenge"] == ["FTMO123456"], "FTMO Futures (mehrdeutig) ohne bestandenes Konto → Kauf")
t = g.pa1_neue(["FTMO123456"], "FTMO Futures", [], offen_bestanden=True)
check(t["challenge"] == [] and t["nachfolger"] == ["FTMO123456"] and g.pa1_urteil(t, 1) == "unklar",
      "FTMO Futures mit bestandenem Konto ohne Nachfolger → Nachfolger-Hinweis, kein Kauf, „von Hand“")

# ── FINNS FALL: 3 Challenges laufen, eine wird Funded (neue FTDFYSLX-Nummer), gleichzeitig 1 gekauft → nur die gekaufte Challenge ──
UID = "11111111-1111-4111-8111-111111111111"
DREI = [{"id": f"a{i}", "user_id": UID, "firm": "Tradeify", "account_type": "challenge", "name": f"150k TDFYSL15010000000{i} → Challenge",
         "external_id": f"TDFYSL15010000000{i}", "ziel_erreicht_at": "2026-11-24T18:00:00Z" if i == 2 else None} for i in (1, 2, 3)]
offen = g.pa1_offen_bestanden(DREI, UID, "Tradeify", {})
check([a["id"] for a in offen] == ["a2"], "bestandenes Konto ohne Nachfolger erkannt (Ziel erreicht, noch Challenge, nicht archiviert)")
check(g.pa1_offen_bestanden(DREI, UID, "Tradeify", {"a2": {"archived": True}}) == [], "archiviert → kein offener Nachfolger")
liste = [a["external_id"] for a in DREI] + ["FTDFYSLX150777000999", "TDFYSL150888000123"]
t = g.pa1_neue(liste, "Tradeify", DREI, offen_bestanden=bool(offen))
check(t["challenge"] == ["TDFYSL150888000123"] and t["nachfolger"] == ["FTDFYSLX150777000999"] and g.pa1_urteil(t, 1) == "anlegen",
      f"Finns Fall: nur die gekaufte TDFYSL… wird angelegt, FTDFYSLX… = Nachfolger-Nummer → {t}")
t = g.pa1_neue(liste, "Tradeify", DREI, offen_bestanden=False)
check(t["challenge"] == ["TDFYSL150888000123"] and t["funded"] == ["FTDFYSLX150777000999"] and g.pa1_urteil(t, 1) == "anlegen",
      "auch ohne erkannte Bestanden-Markierung: Funded-Nummer nie ein Kauf")

# ── Größe in der Kennung (Review: 150k gekauft, 50k-Nummer zuerst sichtbar) ──
check(g.pa1_groesse_passt("TDFYSL150555000111", "Tradeify", 150000) and not g.pa1_groesse_passt("TDFYSL050555000111", "Tradeify", 150000)
      and g.pa1_groesse_passt("TDFYSL300555000111", "Tradeify", 300000) and g.pa1_groesse_passt("LFE050978000000001", "Lucid Trading", 50000)
      and not g.pa1_groesse_passt("LFE150982000000001", "Lucid Trading", 50000) and g.pa1_groesse_passt("APEX7000010000002", "Apex Trader", 50000)
      and g.pa1_groesse_passt("TDFYSL050555000111", "Tradeify", None), "Größe aus der Kennung (Tradeify/Lucid) muss zur Vorlage passen, sonst egal")
t = g.pa1_neue(["TDFYSL050555000111", "TDFYSL150555000222"], "Tradeify", [], groesse=150000)
check(t["challenge"] == ["TDFYSL150555000222"] and t["andere_groesse"] == ["TDFYSL050555000111"] and g.pa1_urteil(t, 1) == "anlegen",
      "50k-Nummer bei 150k-Vorlage zählt nicht (anderer Kauf), 150k wird angelegt")

# ── PA1b: mehrere Klicks = EINE Prüfung (Finn: 4–5 Tradeify für dieselbe ID) ──
V150, V300, VA = "aaaaaaaa-0000-4000-8000-000000000150", "aaaaaaaa-0000-4000-8000-000000000300", "aaaaaaaa-0000-4000-8000-0000000000a5"
p = g.pa1_posten({"vorlage_id": V150, "anzahl": 1})
check(p == [{"vorlage_id": V150, "anzahl": 1}], "alte Zeile ohne posten → ein Posten aus vorlage_id/anzahl")
p, s = g.pa1_posten_plus(p, V150, 1, "2026-11-25T10:00:00+00:00")
for _ in range(3):
    p, s = g.pa1_posten_plus(p, V150, 1)
check(s == 5 and len(p) == 1 and p[0]["anzahl"] == 5 and p[0]["at"] == "2026-11-25T10:00:00+00:00", "5 Klicks Tradeify 150k → ein Posten × 5 (eine Prüfung)")
p2, s2 = g.pa1_posten_plus(p, V300, 2, "2026-11-25T10:05:00+00:00")
check(s2 == 7 and [x["anzahl"] for x in p2] == [5, 2] and p2[1]["at"].startswith("2026-11-25T10:05"), "andere Vorlage → zweiter Posten im selben Auftrag")
check(g.pa1_posten_plus(p2, V150, 14)[0] is None and g.pa1_posten_plus(p2, V150, 13)[1] == 20, "Deckel 20 je Suche")
check(g.pa1_nachgekauft({"laeuft_at": "2026-11-25T10:02:00+00:00", "posten": p2}) and not g.pa1_nachgekauft({"laeuft_at": "2026-11-25T10:06:00+00:00", "posten": p2})
      and not g.pa1_nachgekauft({"laeuft_at": None, "posten": p2}), "Klick während des Laufs erkannt (posten.at > laeuft_at) → Folgelauf +1–3 min")
rest = g.pa1_posten_rest(p2, [{"ext": "X1"}, {"ext": "X2", "vorlage_id": V300}], V150)
check(rest == [{"vorlage_id": V150, "rest": 4}, {"vorlage_id": V300, "rest": 1}], "Rest je Posten (alte angelegt ohne vorlage_id zählen zur ersten Vorlage)")
OFF = [{"vorlage_id": V150, "rest": 4, "groesse": 150000}, {"vorlage_id": V300, "rest": 1, "groesse": 300000}]
zu, andere, u = g.pa1_zuordnen(["TDFYSL150000000011", "TDFYSL300000000022", "TDFYSL150000000033", "TDFYSL050000000044"], "Tradeify", OFF)
check(u == "anlegen" and zu == [("TDFYSL150000000011", V150), ("TDFYSL150000000033", V150), ("TDFYSL300000000022", V300)] and andere == ["TDFYSL050000000044"],
      f"Tradeify 150k + 300k in EINER Lesung: Zuordnung nach Größe in der Kennung, 50k zählt nicht → {zu}")
check(g.pa1_zuordnen(["TDFYSL300000000022", "TDFYSL300000000023"], "Tradeify", OFF)[2] == "ueberzahl", "mehr 300k als gekauft → Überzahl, nichts anlegen")
APX = [{"vorlage_id": VA, "rest": 5, "groesse": 50000}]
zu, _a, u = g.pa1_zuordnen([f"APEX70000100000{i:02d}" for i in range(1, 6)], "Apex Trader", APX)
check(u == "anlegen" and len(zu) == 5 and {v for _k, v in zu} == {VA}, "Apex-5er-Pack: 5 neue in einer Lesung → alle 5 angelegt")
check(g.pa1_zuordnen(["APEX7000010000001"], "Apex Trader", APX + [{"vorlage_id": V300, "rest": 1, "groesse": 100000}])[2] == "groessen",
      "Apex mit zwei Größen offen (Größe nicht in der Kennung) → „mehrere Größen · von Hand“")
check(g.pa1_zuordnen([], "Tradeify", OFF)[2] == "keine" and g.pa1_zuordnen(["TDFYSL150000000011"], "Tradeify", [])[2] == "ueberzahl", "keine neuen / nichts mehr offen")

# ── PA1c (Prüfer S2): umgewandelter Mail-Auftrag (created_at 29.10.) — Bezug „vorher gesehen" = erster Kauf-Klick, nicht created_at ──
KLICK = "2026-11-25T08:00:00+00:00"
MAIL = {"art": "gekauft", "created_at": "2026-10-29T06:00:00+00:00", "vorlage_id": VA, "anzahl": 1}
p1, _s = g.pa1_posten_plus([], VA, 1, KLICK)                     # Umwandeln: Posten frisch, ab = Klick
MAIL["posten"] = p1
check(g.pa1_bezug(MAIL) == datetime.fromisoformat(KLICK), "Bezug = erster Kauf-Klick (posten.ab), nicht das alte created_at")
p2_, _s = g.pa1_posten_plus(p1, VA, 1, "2026-11-25T16:00:00+00:00")   # zweiter Klick 8 h später: ab bleibt
check(p2_[0]["ab"] == KLICK and p2_[0]["at"].startswith("2026-11-25T16") and g.pa1_bezug(dict(MAIL, posten=p2_)) == datetime.fromisoformat(KLICK),
      "weiterer Klick verschiebt den Bezug nicht (ab bleibt, at = letzter Klick)")
check(g.pa1_bezug({"created_at": "2026-11-20T00:00:00+00:00"}) == datetime(2026, 11, 20, tzinfo=timezone.utc), "alte Zeile ohne Posten → created_at")
# Der Fall: Apex (keine Größe in der Kennung). Altes, nie eingetragenes Challenge-Konto APEX…0099 sah Puls am 10.11. zuerst; das gekaufte
# APEX…0001 erscheint 10 min nach dem Klick. Mit created_at − 6 h (28.10.) wäre APEX…0099 „neu" → belegt den einen Kauf-Platz.
TVK = [("APEX7000990000099", "2026-11-10T12:00:00+00:00"), ("APEX7000010000001", "2026-11-25T08:10:00+00:00"), ("APEX6000000000001", "2026-10-20T00:00:00+00:00")]
def vorher_ab(bezug):
    return {k for k, z in TVK if datetime.fromisoformat(z) < bezug - timedelta(seconds=g.PA1_VORHER_S)}
LISTE = [k for k, _z in TVK]
alt_v = vorher_ab(datetime.fromisoformat(MAIL["created_at"]))
neu_v = vorher_ab(g.pa1_bezug(MAIL))
t_alt = g.pa1_neue(LISTE, "Apex Trader", [], vorher=alt_v)
t_neu = g.pa1_neue(LISTE, "Apex Trader", [], vorher=neu_v)
check(g.pa1_zuordnen(t_alt["challenge"], "Apex Trader", [{"vorlage_id": VA, "rest": 1, "groesse": 50000}])[2] == "ueberzahl",
      "Gegenprobe: mit created_at als Bezug wären 2 „neu“ (altes …0099 + gekauftes) → Überzahl, das gekaufte bliebe „von Hand“")
zu_c, _a3, u_c = g.pa1_zuordnen(t_neu["challenge"], "Apex Trader", [{"vorlage_id": VA, "rest": 1, "groesse": 50000}])
check(u_c == "anlegen" and zu_c == [("APEX7000010000001", VA)] and any(g.pa1_art(k, "Apex Trader") for k in neu_v),
      "PA1c: mit Bezug = Kauf-Klick nur das gekaufte APEX…0001 angelegt, altes …0099 ausgeschlossen, Basis vorhanden")
er_c = SRC[SRC.index("def _pa1_erledigt("):SRC.index('\n@app.route("/konto-suche"', SRC.index("def _pa1_erledigt("))]
check("erstellt = pa1_bezug(a) or jetzt" in er_c and 'pa1_iso(a.get("created_at"))' not in er_c, "Auswertung rechnet „vorher“ ab pa1_bezug, nicht ab created_at")
check('"ab": jetzt.isoformat()' in SRC, "neuer Auftrag setzt posten.ab")

# ── PA1d: verklickt → zweiter Klick nimmt „Gekauft“ zurück ──
PP = [{"vorlage_id": V150, "anzahl": 3, "ab": KLICK}, {"vorlage_id": V300, "anzahl": 1}]
pm, sm = g.pa1_posten_minus(PP, [], V150, 1)
check(sm == 3 and pm[0]["anzahl"] == 2 and pm[0]["ab"] == KLICK and PP[0]["anzahl"] == 3, "zurück: Posten der Vorlage − 1, Rest bleibt, Eingabe unverändert")
pm, sm = g.pa1_posten_minus(PP, [], V300, 1)
check(sm == 3 and [x["vorlage_id"] for x in pm] == [V150], "Posten auf 0 fällt weg")
check(g.pa1_posten_minus([{"vorlage_id": V150, "anzahl": 1}], [], V150, 1) == ([], 0), "letzter Posten → Summe 0 = Auftrag schließen")
check(g.pa1_posten_minus(PP, [{"ext": "A", "vorlage_id": V300}], V300, 1) == (None, "angelegt"), "schon angelegt → nicht zurücknehmbar")
check(g.pa1_posten_minus(PP, [{"ext": "A"}], V150, 1, V150)[1] == 3 and g.pa1_posten_minus([{"vorlage_id": V150, "anzahl": 1}], [{"ext": "A"}], V150, 1, V150) == (None, "angelegt"),
      "alte angelegt ohne vorlage_id zählen zur alten Vorlage")
check(g.pa1_posten_minus(PP, [], VA, 1) == (None, "nicht_da"), "andere Vorlage → nichts zurückzunehmen")
zr = SRC[SRC.index('@app.route("/konto-suche/zurueck"'):SRC.index("\ndef _pa1_stand(")]
check("_konto_ziel_uid(b)" in zr and '"status": "eq.offen"' in zr and "\"anzahl\": f\"eq.{o.get('anzahl')}\"" in zr and "for _versuch in range(6):" in zr,
      "zurück: Gate wie der Klick, nur offen, Guard auf die alte Anzahl, neu lesen")
check('"code": "laeuft"' in zr and "Puls prüft gerade" in zr and '"zurueckgenommen"' in zr and "sb_insert" not in zr and "_pa1_anlegen" not in zr,
      "zurück: läuft → 409, Summe 0 → geschlossen (zurueckgenommen), legt nie etwas an")
check('!= "zurueckgenommen"' in SRC[SRC.index("\ndef _pa1_stand("):], "Stand zeigt zurückgenommene Aufträge nicht mehr")
check("window.pa1Zurueck = " in HTML and "/konto-suche/zurueck" in HTML, "Frontend: pa1Zurueck für den zweiten Klick")

# ── pa1_urteil ──
U_ = lambda ch, un=(): {"challenge": list(ch), "unklar": list(un), "funded": ["F1"], "nachfolger": ["N1"]}   # noqa: E731
check(g.pa1_urteil(U_([]), 2) == "keine" and g.pa1_urteil(U_(["a"]), 2) == "anlegen" and g.pa1_urteil(U_(["a", "b"]), 2) == "anlegen",
      "Urteil: keine/anlegen bis zur Anzahl, Funded/Nachfolger zählen nie")
check(g.pa1_urteil(U_(["a", "b", "c"]), 2) == "ueberzahl" and g.pa1_urteil(U_(["a"]), 0) == "ueberzahl", "Urteil: mehr als gekauft → Überzahl (nichts anlegen)")
check(g.pa1_urteil(U_(["a"], ["X"]), 2) == "unklar", "Urteil: unklare Nummer → nichts anlegen")

# ── Wartezeiten (Jitter, CME-Wochenende) ──
MI = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)     # Mittwoch
FR_ABEND = datetime(2026, 11, 27, 23, 30, tzinfo=timezone.utc)   # Fr 17:30 Chicago (Winter, UTC−6) → Wochenende
FR_MITTAG = datetime(2026, 11, 27, 22, 30, tzinfo=timezone.utc)  # Fr 16:30 Chicago → noch Werktag
SO_ABEND = datetime(2026, 11, 29, 23, 30, tzinfo=timezone.utc)   # So 17:30 Chicago → Markt offen, Werktag
SA = datetime(2026, 11, 28, 12, 0, tzinfo=timezone.utc)
check(not g.pa1_wochenende(MI) and g.pa1_wochenende(FR_ABEND) and not g.pa1_wochenende(FR_MITTAG) and g.pa1_wochenende(SA) and not g.pa1_wochenende(SO_ABEND),
      "CME-Wochenende: Fr 17:00 bis So 17:00 Chicago")
f0, fr0 = g.pa1_klick_zeiten(MI, 0)
f1, fr1 = g.pa1_klick_zeiten(MI, 1)
check(f0 == MI + timedelta(minutes=1) and f1 == MI + timedelta(hours=6) and fr1 == f1 + timedelta(hours=24), "werktags: erste Prüfung 1 min … 6 h, Frist +24 h")
w1, wfr = g.pa1_klick_zeiten(SA, 1)
check(w1 == SA + timedelta(hours=24) and wfr == w1 + timedelta(hours=48), "Wochenende: erste Prüfung bis 24 h, Frist +48 h")
vs = {int((g.pa1_klick_zeiten(MI)[0] - MI).total_seconds()) for _ in range(300)}
check(len(vs) > 250 and min(vs) >= 60 and max(vs) <= 6 * 3600, "Prüfzeit auf die Sekunde gestreut (nie fest)")
n_we = (g.pa1_naechste(SA, SA + timedelta(days=3), 0) - SA).total_seconds()
check(n_we == 4 * 3600 and (g.pa1_naechste(MI, MI + timedelta(days=1), 0) - MI).total_seconds() == 3600, "Nachprüfung werktags ab 1 h, Wochenende ab 4 h")

# ── pa1_weiter / pa1_nach_fehler ──
J = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
A = {"anzahl": 3, "angelegt": [{"ext": "A1"}], "frist_bis": (J + timedelta(hours=20)).isoformat(), "versuche": 0}
w = g.pa1_weiter(A, 2, J)
check(w["status"] == "erledigt", "alle gekauften da → erledigt")
w = g.pa1_weiter(A, 1, J, 0.5)
d = (datetime.fromisoformat(w["faellig_at"]) - J).total_seconds()
check(w["status"] == "offen" and 3600 <= d <= 3 * 3600, f"Rest fehlt → nächste Prüfung in 1–3 h ({d / 3600:.1f} h)")
w = g.pa1_weiter(dict(A, frist_bis=(J + timedelta(minutes=20)).isoformat()), 0, J, 1)
check(w["status"] == "offen" and datetime.fromisoformat(w["faellig_at"]) == J + timedelta(minutes=20), "nächste Prüfung nie hinter der 24-h-Frist")
check(g.pa1_weiter(dict(A, frist_bis=(J - timedelta(minutes=1)).isoformat()), 0, J)["status"] == "pruefen", "nach 24 h noch nicht alle → pruefen (🟠)")
f = g.pa1_nach_fehler(A, J, 0)
check(f["status"] == "offen" and f["versuche"] == 1, "Lesefehler: neu in 1–3 h")
check(g.pa1_nach_fehler(dict(A, versuche=3), J)["status"] == "pruefen", "4. Lesefehler → pruefen (🟠), kein Dauer-Retry")

# ── Knopf ──
O = {"status": "offen", "anzahl": 1, "angelegt": [], "faellig_at": "2026-11-25T10:37:00+00:00"}
J0 = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)   # Knopf-Zeit fest (PA1f-Zusatz: pa1_knopf kennt „überfällig")
check(g.pa1_knopf(O, J0) == {"text": "✓ Gekauft · Prüfung 14:37", "art": "gruen"}, "Knopf grün mit Prüfzeit (Dubai)")
check(g.pa1_knopf(dict(O, status="laeuft"), J0)["text"] == "läuft …", "Knopf: läuft …")
check(g.pa1_knopf(dict(O, anzahl=3, angelegt=[{"ext": "TDFYSL150555001234"}], faellig_at="2026-11-25T12:10:00Z"), J0)["text"] == "1/3 gefunden · nächste Prüfung 16:10",
      "Knopf: 1/3 gefunden · nächste Prüfung")
# ── PA1f-Zusatz (Finn: „Jedes Mal, wenn er eben nicht darf, wird er immer verschoben.") ──
AV = {"status": "offen", "anzahl": 1, "angelegt": [], "faellig_at": "2026-11-25T10:00:00+00:00", "frist_bis": "2026-11-26T10:00:00+00:00",
      "ergebnis": {"msg": "alt", "pa1_verschoben": {"n": 2}}}
vb = g.pa1_verschieben_body(AV, "Start in 30 min", J0, 0)
vb1 = g.pa1_verschieben_body(AV, "Start in 30 min", J0, 1)
check(vb["faellig_at"] == "2026-11-25T10:03:00+00:00" and vb1["faellig_at"] == "2026-11-25T10:10:00+00:00", "verschoben um 3 … 10 min (gestreut)")
check(vb["ergebnis"]["pa1_verschoben"]["grund"] == "Start in 30 min" and vb["ergebnis"]["pa1_verschoben"]["n"] == 3 and vb["ergebnis"]["msg"] == "alt"
      and "frist_bis" not in vb, "Grund + Zähler in ergebnis.pa1_verschoben, übriges ergebnis bleibt, Frist unverändert")
vs_ = {s: len({g.pa1_verschieben_body(AV, "x", J0)["faellig_at"] for _ in range(80)}) for s in [0]}
check(vs_[0] > 60, "Verschiebung auf die Sekunde gestreut (Jitter-Regel)")
check(g.pa1_verschieben_body(dict(AV, frist_bis="2026-11-25T10:05:00+00:00"), "x", J0, 1)["faellig_at"] == "2026-11-25T10:05:00+00:00", "nie hinter die Frist")
check(g.pa1_verschieben_body(dict(AV, frist_bis="2026-11-25T09:59:00+00:00"), "x", J0) is None, "Frist vorbei → nicht verschieben (🟠 macht der Stand)")
kv = g.pa1_knopf(dict(AV, faellig_at=vb["faellig_at"], ergebnis=vb["ergebnis"]), J0)
check(kv["text"] == "✓ Gekauft · Prüfung 14:03 · verschoben" and kv["titel"] == "Verschoben: Start in 30 min", f"Knopf zeigt die neue Zeit + „verschoben“ → {kv}")
ku = g.pa1_knopf(dict(AV, faellig_at="2026-11-25T09:30:00+00:00", ergebnis={}), J0)
check(ku["text"] == "✓ Gekauft · wartet auf PC (fällig 13:30)", f"fällig, aber 30 min nicht abgeholt → „wartet auf PC“ statt stumm vergangener Zeit → {ku['text']}")
check(g.pa1_knopf(dict(AV, faellig_at="2026-11-25T09:50:00+00:00", ergebnis={}), J0)["text"] == "✓ Gekauft · Prüfung 13:50", "unter 15 min drüber → noch normale Zeit")
pc_ = SRC[SRC.index("def pc_tv_konten_auftrag():"):SRC.index("    try:\n        alt = (jetzt - timedelta(seconds=TV_AUFTRAG_LAUF_MAX_S))")]
nm_ = pc_[pc_.index('if request.args.get("nur_melden") == "1":'):pc_.index("    # Probelauf-Weiche (tv_konten_pcs)")]
check('"art": "eq.gekauft"' in nm_ and "pa1_verschieben_body(dict(_o, ergebnis=_body[\"ergebnis\"]), _sp, _jt) if _schieben else None" in nm_
      and '"status": "eq.offen", "faellig_at": f"lte.{_jz}"' in nm_ and '"status": "laeuft"' not in nm_ and "gesperrt=_sp" in nm_ and "pa1_pc_frei(" in nm_
      and 'request.args.get("verschieben")' not in SRC,
      "nur_melden (Sperr-Meldung des Masters): Grund bleibt in ergebnis.gesperrt, dazu sichtbar verschoben; nie ein Claim, Guard gegen gleichzeitiges Abholen")
check(g.pa1_knopf(dict(O, status="erledigt", angelegt=[{"ext": "TDFYSL150555001234"}])) == {"text": "angelegt: …1234", "art": "fertig"}, "Knopf: angelegt: …1234")
k = g.pa1_knopf(dict(O, status="pruefen", anzahl=2, ergebnis={"pa1_ruhig": "mehr gefunden · von Hand"}))
check(k == {"text": "mehr gefunden · von Hand", "art": "ruhig"}, "Knopf Überzahl ruhig „mehr gefunden · von Hand“ (kein 🟠)")
check(g.pa1_knopf(dict(O, status="pruefen", ergebnis={"code": "login_unklar", "pa1_fehler": True}))["art"] == "warn", "Knopf 🟠 Lesefehler")

# ── Konto-Zeile aus der Vorlage ──
V = {"firm": "Tradeify", "account_type": "challenge", "account_size": 150000, "starting_balance": 150000, "purchase_cost": 89.5, "max_drawdown": 4500,
     "max_daily_drawdown": None, "goal_kind": None, "consistency_pct": 40, "name_template": "{size} {firm} {ex}"}
z = g.pa1_konto_zeile(V, "Tradeify", "TDFYSL150555001234")
check(z["name"] == "150k TDFYSL150555001234 → Challenge", f"Namensregel „<Größe> <External ID> → <Phase>“ (nicht name_template) → {z['name']}")
check(z["firm"] == "Tradeify" and z["account_type"] == "challenge" and z["external_id"] == "TDFYSL150555001234" and z["starting_balance"] == 150000
      and z["purchase_cost"] == 89.5 and z["max_drawdown"] == 4500 and z["consistency_pct"] == 40 and z["wd_farm"] is False
      and "max_daily_drawdown" not in z and "user_id" not in z and "cred_password" not in z, "Felder aus der Vorlage, leere fehlen, nie Zugangsdaten/user_id")
check(g.pa1_name({"account_size": 50000, "account_type": "challenge"}, "LFE1") == "50k LFE1 → Challenge", "50k-Name")

# ── Klick-Body ──
U = "0a1e29c4-0000-4000-8000-000000000001"
check(g.pa1_klick_lesen({"firma": "Tradeify", "vorlage_id": U, "anzahl": 2}) == (("Tradeify", U, 2), None), "Klick gültig")
check(g.pa1_klick_lesen({"firma": "Topstep", "vorlage_id": U})[1][0] == "firma_nicht", "Topstep → firma_nicht (von Hand)")
check(g.pa1_klick_lesen({"firma": "FundedNext", "vorlage_id": U})[1][0] == "firma_nicht", "CFD → firma_nicht")
check(all(g.pa1_klick_lesen({"firma": "Tradeify", "vorlage_id": U, "anzahl": x})[1][0] == "anzahl" for x in (0, 21, True, 2.5, "x", -1)), "anzahl nur 1–20")
check(g.pa1_klick_lesen({"firma": "Tradeify", "vorlage_id": U, "anzahl": "3"})[0][2] == 3, "anzahl als Ziffern-Text")
check(g.pa1_klick_lesen({"firma": "Tradeify", "vorlage_id": "x"})[1][0] == "vorlage", "vorlage_id Pflicht (uuid)")

# ── Wege (Quelltext) ──
def block(start, ende):
    i = SRC.index(start)
    return SRC[i:SRC.index(ende, i + len(start))]


an = block("def _pa1_anlegen(", "\ndef _pa1_erledigt(")
check(an.index('sb_insert("konto_suche_riegel"') < an.index('sb_insert("accounts"'), "Riegel VOR dem Anlegen (Doppel-Anlage unmöglich)")
check("continue" in an[an.index('sb_insert("konto_suche_riegel"'):an.index("zeile = pa1_konto_zeile")], "Riegel belegt → Kennung übersprungen")
check('sb_delete("konto_suche_riegel"' in an, "Anlegen gescheitert → Riegel wieder frei")
check('"kind": "account_purchase"' in an and "-abs(float(zeile[\"purchase_cost\"]))" in an, "Kauf-Buchung wie Bulk-Anlegen (negativ, EUR)")
er = block("def _pa1_erledigt(", '\n@app.route("/konto-suche"')
check('_sb_all("accounts", {"select": "id,user_id,name,firm,external_id,account_type,ziel_erreicht_at"})' in er, "Abgleich gegen Konten ALLER IDs (ohne user_id-Filter)")
ue = er[er.index('if urteil in ("ueberzahl", "unklar", "ohne_basis", "groessen"):'):er.index("else:", er.index('if urteil in ("ueberzahl", "unklar", "ohne_basis", "groessen"):'))]
check("pa1_zuordnen(teile[\"challenge\"]" in er and "dict(x, vorlage_id=vid)" in er and "pa1_nachgekauft(a)" in er and "random.randint(60, 180)" in er,
      "PA1b-Auswertung: Zuordnung je Posten, angelegt merkt die Vorlage, Folgelauf +1–3 min nach einem Klick während des Laufs")
check('if urteil == "anlegen" and not basis:' in er and "basis = any(pa1_art(k, a.get(\"firma\")) for k in vorher)" in er,
      "ohne frühere Lesung der Firma (Basis) nichts automatisch anlegen")
check('"anzahl": f"eq.{anzahl0}"' in er and 'body["angelegt"] = a.get("angelegt") or []' in er, "Abschluss nur mit unveränderter Anzahl, angelegt immer mitgeschrieben")
check("_pa1_alarm(" not in er[:er.index("got = sb_update(")] and "elif alarm and body.get(\"status\") == \"pruefen\":" in er,
      "🟠 erst nach dem greifenden Abschluss-Update (kein Alarm, wenn ein neuer Klick den Auftrag wieder öffnet)")
check('"art": f"eq.{a.get(\'art\') or \'mail\'}"' in block("def pc_tv_konten_auftrag_erledigt():", "\n@app.route(\"/tv-konten/mein\""), "Mail-Zweig: Guard auf die Art — ein eben gekaufter Auftrag endet nie als Mail-Auftrag")
zu_n, _a2, u_n = g.pa1_zuordnen(["TDFYSL150000000011", "TDFYSL300000000022"], "Tradeify",
                                [{"vorlage_id": "ohne", "rest": 1, "groesse": None}, {"vorlage_id": V150, "rest": 1, "groesse": 150000}])
check(u_n == "anlegen" and ("TDFYSL150000000011", V150) in zu_n and ("TDFYSL300000000022", "ohne") in zu_n, "Vorlage ohne Größe nimmt nur, was sonst nirgends passt")
be = er[er.index('elif str(b.get("code") or "") == "belegt":'):er.index("    else:", er.index('elif str(b.get("code") or "") == "belegt":'))]
check("if jetzt < frist else None" in be and "pa1_verschieben_body(a," in be and 'pa1_verschoben=vb["ergebnis"]["pa1_verschoben"]' in er, "belegt: sichtbar verschoben (3–10 min, Grund), Frist gilt (kein endloses Verschieben)")
check("_alarm_fremd_verwaltet(uid)" in block("def _pa1_alarm(", "\ndef _pa1_anlegen("), "🟠 von Emins Gruppe nie an die Master-IDs")
st = block("def _pa1_stand(", '\n@app.route("/konto-suche/nachfolger"')
check('"status": "eq.offen"' in st and "jetzt >= f" in st and "status.eq.pruefen" in st, "Stand: Liegengebliebene nach der Frist → pruefen + 🟠, Endstände 7 Tage sichtbar")
check("_pa1_anlegen" not in ue and "_pa1_alarm" not in ue and "pa1_ruhig" in ue, "Überzahl/unklar: nichts anlegen, ruhig, kein 🟠")
check('neu = [k for k, _vid in zu]' in er and 'pa1_zuordnen(teile["challenge"]' in er and "offen_bestanden=bool(bestanden)" in er, "angelegt werden nur Challenge-Nummern; Bestanden-Konten der ID × Firma zählen")
check('"status": "eq.laeuft"' in er and 'sb_update("tv_konten_auftrag", {"id": f"eq.{aid}"}, {"angelegt"' in er, "Angelegte sofort festgehalten, Status nur aus laeuft")
ks = block('@app.route("/konto-suche", methods=["GET", "POST", "OPTIONS"])', "\ndef _pa1_stand(")
check("_konto_ziel_uid(b)" in ks and "_alarm_fremd_verwaltet(ziel)" not in ks and '"nur_ht"' not in ks, "Klick: eigene ID oder Admin-Gate, alle Gruppen")
check('"login_fehlt"' in ks and "tv_username" in ks and "archived" in ks, "ohne Login (tv_username) oder ohne aktives Konto → login_fehlt")
check('o.get("art") == "gekauft"' in ks and "pa1_posten_plus(" in ks, "je ID × Firma ein Auftrag: Gekauft addiert (auch andere Vorlage), Mail-Auftrag wird Kauf-Auftrag")
check("läuft schon eine Suche mit einer anderen Vorlage" not in ks and "Puls liest gerade" not in ks,
      "kein 409 mehr bei zweitem Klick (andere Vorlage / Auftrag läuft)")
check("\"anzahl\": f\"eq.{o.get('anzahl')}\"" in ks and "for _versuch in range(6):" in ks and "tv_konten_auftrag_offen_uq" in ks,
      "gleichzeitige Klicks: Guard auf die alte Anzahl + Insert-Konflikt → neu lesen und addieren")
check("if gek:" in ks and '"faellig_at"' not in ks[ks.index("if gek:"):ks.index("else:", ks.index("if gek:"))], "weiterer Klick behält die Prüfzeit")
check("pa1_klick_zeiten(jetzt)" in ks, "faellig_at/frist_bis aus pa1_klick_zeiten (werktags 6 h, Wochenende 24 h)")
pc = block("def pc_tv_konten_auftrag():", "\n@app.route(\"/pc/tv-konten-auftrag/erledigt\"")
check("pa1_pc_frei(" in pc and "tv_konten_pc_frei(" in pc and "arten" in pc, "PC-Weiche: Mail wie bisher, Gekauft eigene Weiche (Standard alle)")
ed = block("def pc_tv_konten_auftrag_erledigt():", "\n@app.route(\"/tv-konten/mein\"")
check('if a.get("art") == "gekauft":' in ed and "_pa1_erledigt(uid, a, b, erg)" in ed, "Erledigt-Route: eigener Zweig für Gekauft")
check(ed.index("tv_konten\", params") < ed.index("_pa1_erledigt("), "gelesene Namen landen zuerst in tv_konten (wie bisher)")
check('@app.route("/konto-suche/waehlen"' not in SRC and "kandidaten" not in block("# ══ PA1", "# ══ KONTEN PRÜFEN"), "keine Antipp-Liste/Auswahl-Route (Finn 25.11.)")
nf = block('@app.route("/konto-suche/nachfolger"', "# ══ KONTEN PRÜFEN")
check("_konto_ziel_uid(" in nf and "pa1_nachfolger" in nf and "sb_insert" not in nf and "sb_update" not in nf, "Nachfolger-Nummern: nur lesen/anzeigen, Gate, nie anlegen")
check("password" not in block("def pa1_konto_zeile(", "\ndef pa1_neue(").lower(), "keine Zugangsdaten in der Konto-Zeile")

# ── SQL ──
check("'gekauft'" in SQL and "'pruefen'" in SQL and "konto_suche_riegel" in SQL and "primary key (firma, ext_norm)" in SQL, "SQL: Art/Stand/Riegel")
check("enable row level security" in SQL and "revoke all on public.konto_suche_riegel from anon, authenticated" in SQL, "SQL: Riegel nur Service-Key")

# ── Frontend ──
check("window.pa1Gekauft = " in HTML and "window.pa1Stand = " in HTML and "window.pa1Waehlen" not in HTML, "Frontend: pa1Gekauft / pa1Stand, kein pa1Waehlen")
check('id="suc-pa1-hinweis"' in HTML and "/konto-suche/nachfolger?konto_id=" in HTML and "window._pa1.nachfolger(acc)" in HTML,
      "Nachfolger-Assistent: ruhiger Hinweis „Nachfolger-Nummer gesehen“")
h = HTML[HTML.index("async function pa1NachfolgerHinweis("):HTML.index("window._pa1 = {")]
check("supabase.from(" not in h and "insert" not in h, "Hinweis legt nie etwas an (Klick füllt nur das Feld)")
check("/konto-suche" in HTML and "window.pa1Neu" in HTML, "Frontend ruft /konto-suche, meldet pa1Neu nach einem Lauf")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' FEHLER'}")
sys.exit(1 if FEHLER else 0)
