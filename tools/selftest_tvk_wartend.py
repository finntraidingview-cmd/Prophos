#!/usr/bin/env python3
"""Selbsttest L7 (05.11.2026): Mail-Aufträge „Konto-Liste lesen" (tv_konten_auftrag) lagen seit 29.10. offen mit versuche 0 — die Weiche
auto_plan_regeln.regeln.tv_konten_pcs stand seit dem Probelauf auf ["pc-c19p2l"], jeder andere PC bekam pc_frei false. app.py tvk_wartend zählt
die offenen Mail-Aufträge ohne freigegebenen PC ihrer ID, GET /admin/tv-konten-pcs liefert sie als „wartend", die Admin-Zeile „TV-Konten lesen auf"
zeigt „⏳ n Mail-Aufträge warten". Abholen selbst unverändert (Weiche + tvkFrei). Aufruf: python3 tools/selftest_tvk_wartend.py"""
import os
import re
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {}
exec(re.search(r"^def tvk_wartend\(.*?(?=^[A-Za-z_@#])", app, re.S | re.M).group(0), ns)
W_ = ns["tvk_wartend"]
# echte offene Aufträge 05.11.2026 (gekürzt): Chris (pc-c19p2l, freigegeben) + Moritz, Jacob, Ina, …
A = [{"user_id": "7b1bc9a3", "firma": "Tradeify", "art": "mail", "status": "offen"},
     {"user_id": "6c206a34", "firma": "Apex Trader", "art": "mail", "status": "offen"},
     {"user_id": "d1f5bcae", "firma": "Tradeify", "art": "mail", "status": "offen"},
     {"user_id": "368076fd", "firma": "Tradeify", "art": "mail", "status": "offen"},
     {"user_id": "7b1bc9a3", "firma": "Apex Trader", "art": "taeglich", "status": "offen"},
     {"user_id": "6c206a34", "firma": "Tradeify", "art": "mail", "status": "laeuft"}]
PCS = {"pc-c19p2l": "7b1bc9a3", "pc-usq1i6": "368076fd", "pc-t8wg97": "d1f5bcae"}
w = W_(A, PCS, ["pc-c19p2l"])
check({x["user_id"] for x in w} == {"6c206a34", "d1f5bcae", "368076fd"} and len(w) == 3,
      f"Weiche nur pc-c19p2l: 3 Mail-Aufträge warten (Chris nicht — sein PC ist frei; Tages-/laufende nie) → {[x['user_id'] for x in w]}")
check(W_(A, PCS, ["alle"]) == [], "Weiche „alle“ → nichts wartet")
check({x["user_id"] for x in W_(A, PCS, ["pc-c19p2l", "pc-usq1i6", "pc-t8wg97"])} == {"6c206a34"}, "ID ohne PC der letzten 24 h wartet weiter (kein Tab zum Abholen)")
check(W_([], PCS, []) == [] and len(W_(A, {}, [])) == 4, "leere Weiche: jede offene Mail wartet")
r = app[app.index('@app.route("/admin/tv-konten-pcs"'):]
r = r[:r.index("\n\n\n")]
check('"wartend": wartend' in r and "tvk_wartend(offen, pcs, liste)" in r and "_alarm_fremd_verwaltet(w[\"user_id\"])" in r,
      "Route: wartend in der Antwort, nur HT-IDs (Emins Gruppe nie)")
p = app[app.index('def pc_tv_konten_auftrag():'):]
p = p[:p.index("\n\n\n")]
check("tv_konten_pc_frei(request.args.get(\"pc\"))" in p, "Abholen unverändert: Weiche bleibt das Gate (/pc/tv-konten-auftrag)")
check("Mail-Auftr${wt.length === 1 ? 'ag wartet' : 'äge warten'}" in html and "esc(wer.join(" in html, "Admin-Zeile zeigt die wartenden Aufträge (escaped)")
print(f"\n{len(fehler)} Fehler" if fehler else "\nalle grün")
sys.exit(1 if fehler else 0)
