#!/usr/bin/env python3
"""Selbsttest HN1 (Finn 12.11.2026 ~20:15 Dubai: „bei jedem Planer … dieses ‚Heute nicht drin‘ … Je Konto: dass es heute nicht drin ist und der Grund“).
app.py ap_nicht_drin_mischen (alle Challenge-Läufe eines Tags, neueste Aussage je Konto) + Route GET /admin/auto-plan/nicht-drin (nur lesen, Gate wie die
Planer-Leserouten); prophos.html: Gruppen je Grund (hndGruppe, echte Grund-Texte vom 12.11.2026), „schon drin“-Filter (HND_DRIN), Quellen der Funded-Planer
(Q.nichtDrin ohne Leise-Filter) und die WD-Liste ohne Kacheln.
Aufruf:  python3 tools/selftest_hn1_nicht_drin.py"""
import os, re, json, subprocess, tempfile

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
app = open(os.path.join(W, "app.py"), encoding="utf-8").read()
html = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
fehler = []


def check(bed, text):
    print(("✓ " if bed else "✗ ") + text)
    if not bed:
        fehler.append(text)


ns = {}
m = re.search(r"^def ap_nicht_drin_mischen\(.*?(?=^[A-Za-z_@#])", app, re.S | re.M)
check(bool(m), "app.py: ap_nicht_drin_mischen vorhanden")
exec(m.group(0), ns)
mischen = ns["ap_nicht_drin_mischen"]
L = [{"tag": "2026-11-12", "at": "2026-11-11T22:45:00Z", "quelle": "nacht", "aus": [{"konto_id": "a", "grund": "Pause-Tag (Handels-Würfel 75 %) — heute kein Trade, morgen neu gewürfelt"},
                                                                                    {"konto_id": "b", "grund": "Konto deaktiviert — unter Accounts am Stift ausschalten"}], "gep": [{"konto_id": "c"}]},
     {"tag": "2026-11-12", "at": "2026-11-12T05:00:00Z", "quelle": "nachplanen", "aus": [{"konto_id": "c", "grund": "Ziel erreicht (Ziel-Wache) — Phase umstellen, der Bot plant hier nie"}], "gep": [{"konto_id": "a"}]},
     {"tag": "2026-11-12", "at": "2026-11-12T06:00:00Z", "quelle": "nachplanen", "aus": [{"konto_id": "z", "grund": "x"}], "trocken": "true"}]
e = mischen(list(reversed(L)))   # Reihenfolge egal
ids = sorted(x["konto_id"] for x in e["ausgelassen"])
check(ids == ["b", "c"], f"Mischen: Nachtlauf-Grund bleibt (b), später geplant fällt raus (a), später ausgelassen kommt dazu (c), Trockenlauf zählt nicht (z) → {ids}")
check(e["quelle"] == "nachplanen" and e["at"] == "2026-11-12T05:00:00Z" and e["tag"] == "2026-11-12", f"Mischen: Stand = neuester echter Lauf ({e['at']}, {e['quelle']})")
check(mischen([]) == {"tag": None, "at": None, "quelle": None, "ausgelassen": []} and mischen(None)["ausgelassen"] == [], "Mischen: leer/None → leere Liste")

r = re.search(r'@app\.route\("/admin/auto-plan/nicht-drin", methods=\["GET", "OPTIONS"\]\)\ndef admin_auto_plan_nicht_drin\(\):(.*?)(?=\n@app\.route|\ndef )', app, re.S)
check(bool(r), "Route GET /admin/auto-plan/nicht-drin (nur GET)")
rb = r.group(1) if r else ""
check("_ap_zugang(admin_reiter=True)" in rb and "_ap_sicht_aus_anfrage(admin, uid)" in rb and "ap_sicht(erg, sicht)" in rb, "Route: Gate + Sicht wie die Planer-Leserouten")
check("ap_gruppe_von_uid(uid)" in rb and "letzter_lauf" in rb, "Route: Verwalter-Gruppe liest ihren eigenen Lauf, nie den HT-Lauf")
check('order="at.desc", limit="400"' in rb, "Route: neueste Läufe zuerst (Deckel schneidet nie die geltenden ab)")
check("AP_LAUF_NUR_CHALLENGE" in rb and "ap_aus_ohne_plan_laden(erg)" in rb and "ap_ohne_archiv(" in rb, "Route: nur Challenge-Läufe, inzwischen geplant/archiviert fällt raus")
check(not re.search(r"sb_(insert|update|upsert|delete)\(|sb_rpc\(", rb), "Route schreibt nichts")

# Nachtrag (Master 12.11.2026, Befund S4): still gefilterte Konten als nicht_im_planer[] — Funded-Planer (Firma aus) und Challenge (ID nicht im Planer)
fb = re.search(r"^def fdp_planen\(.*?(?=^def )", app, re.S | re.M).group(0)
check('erg["nicht_im_planer"] = [' in fb and "not ap_regel_finden(an_von(a.get(\"user_id\")), a.get(\"firm\"))" in fb and "FDP_GRUND_FIRMA_AUS" in fb,
      "Funded-Planer: Konten ausgeschalteter Firmen als nicht_im_planer[] mit Grund")
cb = re.search(r"^def fcp_planen\(.*?(?=^def )", app, re.S | re.M).group(0)
check('erg["nicht_im_planer"] = [_nip(a)' in cb and 'erg.setdefault("nicht_im_planer", []).append(_nip(a))' in cb and "FCP_GRUND_FIRMA_AUS" in cb
      and re.search(r'erg\.setdefault\("nicht_im_planer", \[\]\)\.append\(_nip\(a\)\)[^\n]*\n\s+except Exception:\n\s+pass\n\s+continue', cb) is not None, "Funded CFD: Firma ohne Regel / aus als nicht_im_planer[], danach weiter continue (kein Plan)")
check("konten = [a for a in _alle_k if ap_regel_finden(an_von(a.get(\"user_id\")), a.get(\"firm\"))]" in fb, "Funded-Planer: geplant wird weiter nur mit eingeschalteten Firmen")
check('"ergebnis": {k: erg[k] for k in ("geplant", "ziel", "ausgelassen")}' in fb, "Funded-Planer: Lauf-Zeile (auto_plan_lauf) unverändert ohne nicht_im_planer")
m2 = re.search(r"^def fcp_sicht\(.*?(?=^def )", app, re.S | re.M)
ns2 = {"admin_in_sicht": lambda u, s: (str(u) == s) if isinstance(s, str) else (str(u) in s)}
exec(m2.group(0), ns2)
o2 = ns2["fcp_sicht"]({"nicht_im_planer": [{"user_id": "u1"}, {"user_id": "u2"}], "ausgelassen": []}, "u1")
check(o2["nicht_im_planer"] == [{"user_id": "u1"}], "fcp_sicht filtert nicht_im_planer[] nach der Sicht")
check("AP_GRUND_ID_AUS" in rb and "_fdp_ht_ids()" in rb and "if not gr_lauf:" in rb and '"nicht_im_planer": still' in rb and 'ap_sicht({"ausgelassen": still}, sicht)' in rb,
      "Challenge-Route: HT-IDs ohne Planer-Haken mit Grund, nach Sicht gefiltert, nicht für Planer-Gruppen")

# Frontend: Gruppen + Filter mit jsc (echte Funktionen)
def fn(start, ende):
    i = html.index(start); return html[i:html.index(ende, i)]
js = (fn("  const HND_DRIN = ", "  const _hndAuf = ") + "\n"
      + "const G = " + json.dumps([
          "Pause-Tag (Handels-Würfel 75 %) — heute kein Trade, morgen neu gewürfelt", "Waiting for Payout — Payout anfragen, danach plant der Planer wieder",
          "Ziel erreicht (Ziel-Wache) — Phase umstellen, der Bot plant hier nie", "Ziel erreicht → Winning Days", "Konto deaktiviert — unter Accounts am Stift ausschalten",
          "Balance nicht live (seit dem letzten Trade nicht nachgelesen) — ↻ Balance lesen", "kein Echo-Hedge stellbar — Hedge 0,04 Lot unter 0,05 Lot (CFD-Challenges nur mit Hedge)",
          "Abstand zur Liquidation zu klein (412 $)", "Balance nicht über der Liquidation — geblowt? (Konto-Boden …)", "Flex-Konto — plant der Funded-CFD-Planer noch nicht",
          "wartet auf Nachlesung (Überprüfen)", "letzter Trade noch nicht erledigt (Überprüfen)",
          "Tagesdeckel der Firma — höchstens 2 Konten je ID und Tag, dieses Konto kommt an einem anderen Tag dran (2 heute schon belegt)",
          "Block der ID ist heute schon durch — morgen wieder", "Block der ID läuft gerade — morgen wieder", "nicht im Farm (Haken aus)",
          "ohne External ID — der Bot kann das Konto nicht wählen", "Tage sammeln 3/5: Balance nur 12 $ über dem Ziel …",
          "Firma im Funded-Planer aus — unter Funded Planer → Futures → Einstellungen einschalten", "ID nicht im Challenge-Planer — unter „IDs verwalten“ den Haken setzen",
          "wartet auf Payout", "Haken „Auto-Planer“ am Konto aus", "Firma im Funded-CFD-Planer aus — unter Funded Planer → CFD → Einstellungen einschalten"], ensure_ascii=False) + ";\n"
      + "const D = ['hat schon einen geplanten/laufenden Plan', 'schon geplant', 'läuft gerade', 'heute schon gehandelt — ein Trade pro Konto und Tag', 'heute schon 2 Trades', 'Waiting for Payout — x', 'Pause-Tag (x)'];\n"
      + "print(JSON.stringify({ g: G.map(hndGruppe), d: D.map(t => HND_DRIN.test(t)) }))")
with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as d:
    d.write("const apGrundKurz = t => 'kurz:' + t;\n" + js)
rr = subprocess.run(["/System/Library/Frameworks/JavaScriptCore.framework/Versions/Current/Helpers/jsc", d.name], capture_output=True, text=True)
os.unlink(d.name)
o = json.loads(rr.stdout.strip().splitlines()[-1]) if rr.returncode == 0 and rr.stdout.strip() else {}
g = o.get("g") or []
soll = ["Pause-Tag (Handels-Würfel)", "Payout angefragt / Waiting", "Ziel erreicht – Phase umstellen", "Ziel erreicht", "Konto deaktiviert", "Balance nicht live", "kein Hedge stellbar",
        "Abstand zur Liquidation zu klein", "geblowt?", "Flex-Konto", "wartet auf Überprüfen", "wartet auf Überprüfen", "Tagesdeckel erreicht",
        "Block der ID heute schon durch", "Block der ID läuft gerade", "vom Planer ausgenommen", "External ID fehlt", "Tage sammeln – von Hand",
        "Firma im Planer aus", "ID nicht im Challenge-Planer", "Payout angefragt / Waiting", "vom Planer ausgenommen", "Firma im Planer aus"]
check(g == soll, "Gruppen je echtem Grund-Text: " + (" · ".join(g) if g != soll else "alle " + str(len(g)) + " richtig") + (rr.stderr[:200] if rr.returncode else ""))
check(o.get("d") == [True, True, True, True, True, False, False], f"„schon drin“ fällt raus, Waiting/Pause bleiben: {o.get('d')}")

# Funded-Quellen: eigene Liste ohne Leise-Filter, hinter der ausg-Anweisung (Falle beim Bau: Einschub zwischen „const ausg = […]“ und „.map(…)“)
for name, start in (("Funded Futures", "  function fdpQuelleBauen(d){"), ("Funded CFD", "  function fcpQuelleBauen(d){")):
    b = fn(start, "\n  }\n")
    check(re.search(r"const ausg = \[.*\]\n      \.map\(x => \(\{ user_id", b) is not None, f"{name}: „const ausg … .map(…)“ unzerteilt")
    nd = re.search(r"const nichtDrin = \{.*?\}\)\) \}", b, re.S)
    check(bool(nd) and "FCP_AUSG_LEISE" not in (nd.group(0) if nd else "x") and "d.ausgelassen" in (nd.group(0) if nd else ""), f"{name}: nichtDrin aus allen ausgelassen[] (ohne Leise-Filter)")
    check(", nichtDrin" in b or "nichtDrin," in b, f"{name}: nichtDrin in der Quelle")
    check("...(d.nicht_im_planer || [])" in (nd.group(0) if nd else ""), f"{name}: nichtDrin enthält nicht_im_planer[]")

check('<div class="panel" id="wd-nd" style="margin:0 0 12px"><div id="wd-nd-grid"></div></div>' in html and "wd-po-kopf" not in fn("  function wdNdRender(){", "\n  }\n"),
      "Winning Days: keine Kacheln mehr, dieselbe Liste (window._hndHtml)")
check("data-wd-nd-rein=" in fn("  function wdNdRender(){", "\n  }\n") and 'id="wdNdAlle"' in fn("  function wdNdRender(){", "\n  }\n") and "data-wd-nd-id=" in fn("  function wdNdRender(){", "\n  }\n"),
      "Winning Days: Würfeln je Konto, Alle würfeln, Klick klappt die ID — gleiche Merkmale")
check('<div data-apg-anker="nichtdrin">${nd}</div>' in html, "Planer (Challenge/Funded): Abschnitt nach „Wartet auf Start“")
check("n <= 10" in fn("  function hndHtml(key, liste, opt){", "\n  }\n"), "ab 11 Konten eingeklappt")

print("ALLES GRÜN" if not fehler else f"{len(fehler)} FEHLER")
raise SystemExit(1 if fehler else 0)
