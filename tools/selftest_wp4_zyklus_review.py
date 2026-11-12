#!/usr/bin/env python3
"""Selbsttest WP4 (Finn 10.11.2026 ~20:20 Dubai, The5%ers 100k Funded CFD: „Der ist weit über dem Ziel, der muss schon Waiting/ready sein“).
Abhak-Popup zeigte „Payout-Ziel noch nicht erreicht (fehlt: Consistency ≤ 50 %, Payout ab)“. Zwei Fehler in der Zyklus-Zählung:
  a) Zyklus-Beginn = Tag NACH der Payout-Anfrage → ein Trade am Anfrage-Tag NACH der Anfrage fiel aus beiden Zyklen (fcp_zyklus_anfrage_ts, _fcp_im_zyklus)
  b) der Trade in review (wird gerade abgehakt) zählte nicht, steckt aber schon in der Balance (kz_review_mitzaehlen)
Rechnet app.py kz_rechnen (GET /konto-ziele) ohne Netz/DB mit den Werten des Falls (Platzhalter-IDs), dazu Planer-Zählung und Popup-Texte.
Aufruf:  python3 tools/selftest_wp4_zyklus_review.py"""
import os
import re
from datetime import datetime, timezone, timedelta

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {"re": re, "datetime": datetime, "timezone": timezone, "timedelta": timedelta, "json": __import__("json")}


def lade(name):
    m = re.search(r"^def " + re.escape(name) + r"\(.*?(?=^[A-Za-z_@#])", app, re.S | re.M) or re.search(r"^" + re.escape(name) + r"\s*=.*?(?=^[A-Za-z_@#])", app, re.S | re.M)
    if not m:
        raise RuntimeError("nicht gefunden: " + name)
    for _ in range(20):
        try:
            exec(m.group(0), ns)
            return
        except NameError as e:
            lade(str(e).split("'")[1])


def ruf(fn, *a, **k):
    if fn not in ns:
        lade(fn)
    for _ in range(150):
        try:
            return ns[fn](*a, **k)
        except NameError as e:
            lade(str(e).split("'")[1])
    raise RuntimeError(fn)


for n in ("AP_TYPEN", "AP_KONTO_FELDER", "KZ_CHART_MAX", "KZ_BODEN_ART", "WD_FIRMEN_REGELN_STD", "WD_GOOD_DAY_MIN", "WD_ZYKLUS_VORGABE", "WD_ZYKLUS_FU",
          "WD_ZYKLUS_STAFFEL_STD", "WD_ZYKLUS_STAFFEL_VON", "FCP_ERSTER_PAYOUT_STANDARD", "FCP_TP_MODUS_STANDARD", "FCP_ZIEL_TOLERANZ_PCT"):
    lade(n)
for n in ("ap_boden_konto", "_ap_boden", "ap_kw_param", "ap_groesse", "ap_regel_konto", "ap_regel_flex", "ap_boden_sicher", "ap_regel_finden", "_ap_norm",
          "fcp_eins_prozent", "fcp_gewinne", "fcp_tage_zyklus_w", "fcp_param", "fcp_zyklus_anfrage_ts", "_fcp_im_zyklus", "kz_review_mitzaehlen", "fcp_ziel_schwelle",
          "fcp_ziel_toleranz_info", "fcp_konto_rechnen", "fcp_tw_aus", "fcp_wuerfel", "gp_hedge", "FCP_CONS_TP_MIN_USD", "FCP_CONS_ANTEIL_SPANNE", "FCP_CONS_PUFFER_DECKEL", "FCP_CONS_PUFFER_ZIEL", "fcp_cons_finn", "FCP_TP_ZYKLEN_STANDARD", "fcp_tp_deckel"):
    lade(n)
ns["_ap_tz"] = lambda name: __import__("zoneinfo").ZoneInfo(name)

KID = "00000000-0000-4000-8000-000000000001"
ACC = {"id": KID, "user_id": "u-x", "name": "100k 00000000 → Funded", "firm": "The5%ers", "account_type": "funded_cfd", "external_id": "00000000",
       "tv_balance": 101802.83, "tv_balance_at": "2026-11-10T14:40:00+00:00", "fcp_ziel": {"at": "2026-11-06T12:55:26+00:00", "usd": 1454, "zyklus": 2},
       "payout_ready_at": "2026-11-20", "created_at": "2026-10-26T14:39:56+00:00", "on_demand": False, "starting_balance": None, "max_drawdown": None}


def pl(pid, en, wert, status="completed"):
    return {"id": pid, "master_account_id": KID, "status": status, "route": "mt5v2", "konto_typ": "funded_cfd", "started_at": en, "ended_at": en,
            "completed_at": en if status == "completed" else None, "master_pl": wert, "mt5_baseline": {}, "tv": {}, "fin": {}}


PL = [pl("p1", "2026-11-04T05:04:01+00:00", 4285.68), pl("p2", "2026-11-05T07:08:59+00:00", 2394.87),
      pl("p3", "2026-11-06T14:20:19+00:00", 328.48), pl("p4", "2026-11-09T15:41:58+00:00", 689.57), pl("p5", "2026-11-10T14:30:06+00:00", 722.03, "review")]
PEND = [{"id": "x1", "account_id": KID, "requested_at": "2026-11-06", "created_at": "2026-11-06T12:53:38+00:00", "received_tx_id": "tx1"}]
TX = [{"id": "tx1", "account_id": KID, "occurred_at": "2026-11-08"}]
FCP = {"firmen": [{"namen": ["the5ers"], "consistency_pct": 50, "je_groesse": {"100000": {"dd": 10000, "sl": [1000, 1200], "lots": [1, 2], "ziel": [1300, 1600]}},
                   "erster_payout": False}]}

# a) genauer Zyklus-Start
ts = ruf("fcp_zyklus_anfrage_ts", PEND, [], TX)
check(ts.get(KID) == datetime(2026, 11, 6, 12, 53, 38, tzinfo=timezone.utc), f"Zyklus-Start genau: Anfrage 06.11. 12:53:38 UTC ({ts.get(KID)})")
check(ruf("fcp_zyklus_start", PEND, [], TX).get(KID) == "2026-11-07", "fcp_zyklus_start unverändert: Folgetag 07.11.")
check(ruf("fcp_zyklus_anfrage_ts", [{"account_id": KID, "requested_at": "2026-11-06", "created_at": "2026-11-07T09:00:00+00:00"}], [], []) == {},
      "created_at an einem anderen Tag → Zeit unbekannt, wie bisher ab dem Folgetag")
check(ruf("fcp_zyklus_anfrage_ts", PEND, [], [{"id": "tx9", "account_id": KID, "occurred_at": "2026-11-06"}]) == {},
      "zweites Ereignis am selben Tag ohne Uhrzeit → unbekannt (fail-closed)")
seit = "2026-11-07"
tw_alt = ruf("fcp_tage_zyklus_w", PL, seit, None)
tw_neu = ruf("fcp_tage_zyklus_w", PL, seit, None, ts.get(KID))
check(tw_alt["w"] == 689.57 and tw_neu["w"] == 1018.05 and tw_neu["b"] == 689.57,
      f"Planer-Zählung: 06.11. 14:20 (+328,48) nach der Anfrage zählt jetzt ({tw_alt['w']} → {tw_neu['w']})")
check(ruf("fcp_tage_zyklus_w", [pl("v", "2026-11-06T09:00:00+00:00", 999.0)], seit, None, ts.get(KID))["w"] == 0,
      "Trade am Anfrage-Tag VOR der Anfrage bleibt im alten Zyklus (BG1)")
check(ruf("fcp_gewinne", PL, seit, ts.get(KID)) == round(328.48 + 689.57, 2), "fcp_gewinne zählt genauso")
# Prüfer S1: alter Ziel-Trade, erst nach der Anfrage abgehakt (ended_at = Erkennung) bzw. über die Anfrage gelaufen → bleibt im alten Zyklus
spaet = dict(pl("s1", "2026-11-06T13:10:00+00:00", 1500.0), started_at="2026-11-06T11:40:00+00:00")
check(ruf("fcp_tage_zyklus_w", [spaet], seit, None, ts.get(KID))["w"] == 0, "Trade über die Anfrage (Start 11:40, Ende 13:10) → alter Zyklus")
check(ruf("fcp_tage_zyklus_w", [dict(spaet, started_at=None)], seit, None, ts.get(KID))["w"] == 0, "ohne started_at am Anfrage-Tag → nicht zählen")
check(ruf("fcp_tage_zyklus", PL, seit, ts.get(KID)) == (689.57, 2), f"fcp_tage_zyklus mit ab_ts: größter Tag 689,57, 2 abgeschlossene Trades ({ruf('fcp_tage_zyklus', PL, seit, ts.get(KID))})")
# Prüfer S2: Anlegetag nach dem Folgetag → nur der Anfrage-Tag selbst, nie Tage davor
check(ruf("fcp_tage_zyklus_w", [pl("s2", "2026-11-08T10:00:00+00:00", 900.0)], "2026-11-09", None, ts.get(KID))["w"] == 0, "Trade vor dem späteren Anlegetag zählt nie")
check(ruf("fcp_tw_broker", PL, seit, None, None, None, ts.get(KID))["w"] == 1018.05, "fcp_tw_broker reicht ab_ts ohne Broker-Eintrag durch")

# b) review-Trade in der Balance
pz = ruf("kz_review_mitzaehlen", PL, ACC["tv_balance_at"])
check([p["status"] for p in pz][-1] == "completed", "review-Trade vor der Balance-Lesung zählt wie abgeschlossen")
check(ruf("kz_review_mitzaehlen", PL, "2026-11-10T14:00:00+00:00")[-1]["status"] == "review", "Lesung VOR dem Trade-Ende → zählt nicht")
check(ruf("kz_review_mitzaehlen", PL, None)[-1]["status"] == "review", "ohne Lesezeit → wie bisher")
check(ruf("kz_review_mitzaehlen", [dict(PL[-1], master_pl=None)], ACC["tv_balance_at"])[0]["status"] == "review", "review ohne P&L → zählt nicht")

# kz_rechnen: das Urteil fürs Abhak-Popup
c = {"bal": ACC["tv_balance"], "bal_quelle": "TV", "bal_stand": ACC["tv_balance_at"], "plaene": PL, "jetzt": "2026-11-10T16:30:00+00:00",
     "ap_firmen": [], "liq_regeln": [], "fcp_regel": FCP, "fcp_pay": (PEND, [], TX), "wd_firmen_regeln": {}, "wd_pay": [], "payouts": (PEND, [], TX)}
o = ruf("kz_rechnen", ACC, c)
ab = o.get("abhak") or {}
cons = ab.get("cons") or {}
check(abs((cons.get("anteil") or 0) - 722.03 / 1740.08) < 1e-6 and cons.get("ok") is True,
      f"Consistency 722,03 ÷ 1.740,08 = 41,5 % ≤ 50 % (vorher 67,7 %) ({cons})")
check(ab.get("bereit") is True and ab.get("erreicht") is True, f"Ziel + Consistency → bereit (Waiting vorausgewählt) ({ab.get('fehlt_text')})")
check("Ziel +1.803 $ / +1.454 $" in (ab.get("ok_text") or "") and "Consistency 41,5 % ≤ 50 %" in (ab.get("ok_text") or ""), f"Grund im Popup mit Zahlen: {ab.get('ok_text')}")
check("Payout ab" not in (ab.get("fehlt_text") or "") and ab.get("fehlt_text") == "", "„Payout ab“ (20.11.) sperrt nur das Anfragen, nicht Waiting")
pab = next((x for x in o["urteil"]["checks"] if x[1] == "Payout ab"), None)
check(pab and pab[0] == "nein", "Payout-Karte zeigt „Payout ab 20.11.“ weiter als offen")
check(o["urteil"]["sub"] == "Zyklus 2 · seit Anfrage 06.11. 13:53", f"Payout-Karte: Zyklus ab der Anfrage-Zeit (Berlin) ({o['urteil']['sub']})")
# ohne Fix (b): nur completed → Consistency 67,7 %? (Gegenprobe: review-Trade nach der Lesung)
o2 = ruf("kz_rechnen", dict(ACC, tv_balance_at="2026-11-10T14:00:00+00:00"), dict(c, bal_stand="2026-11-10T14:00:00+00:00"))
ab2 = o2.get("abhak") or {}
check(ab2.get("bereit") is False and "Consistency 67,7 % > 50 %" in (ab2.get("fehlt_text") or "") and "größter Tag 690 $ / Gewinn-Tage 1.018 $" in (ab2.get("fehlt_text") or ""),
      f"fehlt mit Zahlen: {ab2.get('fehlt_text')}")
o3 = ruf("kz_rechnen", dict(ACC, tv_balance=101300.0), dict(c, bal=101300.0, plaene=PL[:4]))
check("Ziel +1.300 $ von +1.454 $ — zählt ab +1.309 $, fehlen 9 $" in ((o3.get("abhak") or {}).get("fehlt_text") or ""), f"Ziel fehlt mit Zahlen: {(o3.get('abhak') or {}).get('fehlt_text')}")

# Frontend: Daten der Checkliste (jsc, echte Funktion mit der kz_rechnen-Antwort von oben). AP9 (Finn 12.11.2026: „komplett weglassen“):
# die Anzeige (wpChecklisteHtml) ist raus — wpCheckliste bleibt, weil Vorauswahl und Ziel-Karte (mwdErlZielOk) daran hängen
import json, subprocess, tempfile
def _fn(start, ende):
    i = html.index(start); return html[i:html.index(ende, i)]
js = (_fn("  function escapeHtml(s){", "\n  }\n") + "\n  }\n" + _fn("  function wpCheckliste(d){", "  window._wpCheckliste")
      + "\nconst D = " + json.dumps({"abhak": o["abhak"], "urteil": o["urteil"]}) + ", D2 = " + json.dumps({"abhak": o2["abhak"], "urteil": o2["urteil"]}) + ";\n"
      + "const L = wpCheckliste(D), L2 = wpCheckliste(D2);\n"
      + "print(JSON.stringify({ L, L2 }))")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write(js)
rr = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
e = json.loads(rr.stdout.strip().splitlines()[-1]) if rr.returncode == 0 else {}
L = e.get("L") or []
check([r["name"] for r in L] == ["Ziel bis Waiting", "Consistency ≤ 50 %", "Payout ab"] and [r["st"] for r in L] == ["ok", "ok", "info"],
      f"Checkliste: Ziel ✓, Consistency ✓, Payout ab nur Info ({[(r['name'], r['st']) for r in L]} {rr.stderr[:200]})")
check(L and L[1]["wert"] == "41,5 % · bester Tag 722 $ ÷ 1.740 $" and "+1.803 $ / +1.454 $" in L[0]["wert"] and "20.11" in L[2]["wert"], f"Werte: {[r['wert'] for r in L]}")
# AP2 (11.11.2026): Anzeige-Felder — Ist groß rechts, Soll/fehlt klein darunter; keine Textwand mehr
check(L and str(L[0].get("titel") or "").startswith("Ziel") and L[0].get("gross") == "+1.803 $" and "erreicht" in (L[0].get("klein") or "") and L[1].get("gross") == "41,5 %"
      and L[1].get("klein") == "erlaubt ≤ 50 % · bester Tag 722 $ von 1.740 $ Gewinn-Tagen", f"AP2 Anzeige-Felder: {[(r.get('titel'), r.get('gross'), r.get('klein')) for r in L]}")
L2 = e.get("L2") or []
check(L2 and L2[1]["st"] == "nein" and "67,7 %" in str(L2[1].get("gross") or ""), f"Consistency verletzt → Zeile „nein“ ({L2[1:2]})")
check("ruhig && !_wpFcfd && !_wpZiel && !(_mwdErlWp && wdlFcfdZielMoeglich(pw))" in html and "!(opts && opts.nurStill)" in html,
      "Ein Klick bei Funded CFD öffnet immer das Popup, der stille Takt nie")
# AP9: Checkliste weder im Radar-Popup noch im Trades-Dialog, keine Reste (Platzhalter, Neuberechnung beim Tippen, Hinweiszeile, CSS)
check(all(x not in html for x in ('id="mwd-erl-pcheck"', 'id="tc-pcheck"', 'function wpChecklisteHtml', 'function wpErgText', 'function wpLokal',
      'function wpPlatzhalterHtml', 'mwdErlPcheckZeichnen', 'mwd-erl-waiting-hint', '.wpck')), "AP9: Checkliste samt Resten weg (Popup + Trades-Dialog)")
check("_mwdErlU = an && typeof window._wpGemerkt === 'function'" in html and "function mwdErlZielOk()" in html and "mwdErlWpAnwenden(u)" in html,
      "AP9: Urteil/Vorladen/Vorauswahl/Ziel-Karte bleiben")

# Frontend: Popup-Texte
check("okText: String(ab.ok_text || '')" in html and "'fehlt: ' + String(ab.fehlt_text)" in html, "wpUrteil liest ok_text/fehlt_text")
check("zyklus_ts.get(aid)" in app and app.count("zyklus_ts.get(aid)") >= 4, "Planer zählt mit dem genauen Zyklus-Start")

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
