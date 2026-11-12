#!/usr/bin/env python3
"""Selbsttest: Echo mit Hedge (route mt5, tpPreflightMt5) — Trade-Fenster geprüft, Order erst mit Scharf-Beweis (30.10.2026, Befund
Slave 8: zwei Echo-mit-Hedge-Master liefen ohne Hedge; plan?file ging ungeprüft raus, master-order feuerte bei alive && !note ohne
armed). Prüft die Verdrahtung in prophos.html und spielt Fenster-Versuche und Bereitschafts-Ticker mit gestellten Antworten nach
(dieselben Regeln wie echoFensterOk / echoScharfUrteil). Aufruf: python3 tools/selftest_echo_fenster_scharf.py

ES2/ES2b (05.11.2026, Slave 7, Prüfer S2/S8): Fenster geht parallel zum Terminal-Start raus (fenP), Höchstwartezeit aus der Einstellung
(echoTempo().scharfMaxMs, 10–120 s, Standard 30 s), jeder Ausstieg ohne Order nimmt das Fenster zurück (fensterWeg →
echoFensterZuruecknehmen) — nur mit Beweis „keine Master-Position" (echoFensterZuruecknehmenUrteil, geschlossen).
ES2d: Scharf-Beweis im Bot (ES3b) nur, wenn das Panel bot_faehig 'scharf_pflicht' meldet — sonst prüft der Tab wie bisher."""
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
FEHLER = []
MAX_MS = 30000


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


def fenster_ok(r):
    """Python-Spiegel von echoFensterOk."""
    st = str(((r or {}).get("plan") or {}).get("status") or "")
    return bool(r and r.get("ok") is True and st in ("geplant", "laufend"))


def urteil(inst, seit_ms, alt_laufend=False, max_ms=None):
    """Python-Spiegel von echoScharfUrteil (max_ms = Einstellung echo_scharf_max_ms, ohne Angabe 30 s)."""
    st = (inst or {}).get("status") or {}
    flach = not (st.get("master_positions") or [])
    if st.get("armed") is True and not (alt_laufend and flach):
        return "scharf"
    return "fehlt" if seit_ms > (max_ms if (max_ms or 0) > 0 else MAX_MS) else "warten"


KEINE = object()   # „Plan-Liste nicht lesbar" (JS: aktuell undefined)


def zurueck_urteil(fen_r, inst, aktuell=KEINE):
    """Python-Spiegel von echoFensterZuruecknehmenUrteil: '' = Fenster darf weg, sonst der Grund (geschlossen: ohne Beweis bleibt es)."""
    p = (fen_r or {}).get("plan") or {}
    if not (fen_r and fen_r.get("ok") is True) or not (isinstance(p.get("id"), (int, float)) and p.get("id") > 0):
        return "kein Fenster"
    if str(p.get("status") or "") != "geplant":
        return "steht nicht auf geplant"
    if aktuell is None:
        return "schon weg"
    if aktuell is KEINE:
        return "Plan-Liste nicht lesbar"
    if str(aktuell.get("status") or "") != "geplant":
        return "inzwischen nicht geplant"
    if str(aktuell.get("armed_at") or "") != str(p.get("armed_at") or ""):
        return "erneuert"
    if not inst:
        return "Instanz nicht lesbar"
    st = inst.get("status") or {}
    if not inst.get("alive") or st.get("note"):
        return "kein frischer Snapshot"
    if not isinstance(st.get("master_positions"), list):
        return "Positionsliste fehlt"
    if st["master_positions"]:
        return "Master-Position offen"
    return ""


def fenster_schreiben(antworten, versuche=3):
    """Spielt echoFensterSchreiben nach: → (ok, Anzahl Aufrufe)."""
    n = 0
    for a in antworten[:versuche]:
        n += 1
        if fenster_ok(a):
            return True, n
    return False, n


def ticker(armed_folge, takt_ms=1000, neu_ms=10000, max_ms=None):
    """Spielt den Bereitschafts-Ticker ab „Terminal bereit" nach: je Tick armed True/False.
    → (Ergebnis 'order' | 'fehlt' | 'offen', Ticks, erneute plan?file-Aufrufe)."""
    t, neu_ab, neu_n = 0, 0, 0
    for i, armed in enumerate(armed_folge):
        u = urteil({"alive": True, "status": {"armed": armed}}, t, False, max_ms)
        if u == "scharf":
            return "order", i + 1, neu_n
        if u == "fehlt":
            return "fehlt", i + 1, neu_n
        if t >= neu_ab:
            if neu_ab:
                neu_n += 1
            neu_ab = t + neu_ms
        t += takt_ms
    return "offen", len(armed_folge), neu_n


def main():
    html = open(os.path.join(HIER, "..", "prophos.html"), encoding="utf-8").read()
    h = html[html.index("const ECHO_SCHARF_MAX_MS = "):html.index("window._echoFenster = ")]
    check("const ECHO_SCHARF_MAX_MS = 30000" in h and "r.ok === true && (st === 'geplant' || st === 'laufend')" in h
          and "st.armed === true && !(altLaufend && flach)) return 'scharf'" in h and "seitMs > (maxMs > 0 ? maxMs : ECHO_SCHARF_MAX_MS) ? 'fehlt' : 'warten'" in h,
          "Regeln im Frontend = Spiegel hier (ok + geplant/laufend, armed === true, Standard 30 s, sonst Einstellung)")
    check("scharfMaxMs: ECHO_SCHARF_MAX_MS" in h and "zahl(r.echo_scharf_max_ms, 10000, 120000, s.scharfMaxMs)" in h,
          "Höchstwartezeit aus der Einstellung: Standard 30 s, nie unter 10 s, nie über 120 s (ES2)")
    z = h[h.index("function echoFensterZuruecknehmenUrteil("):h.index("async function echoFensterZuruecknehmen(")]
    check("aktuell === undefined" in z and "if(!inst) return" in z and "if(!inst.alive || st.note) return" in z
          and "if(!Array.isArray(st.master_positions)) return" in z and "if(st.master_positions.length) return 'Master-Position offen'" in z
          and z.index("aktuell === undefined") < z.rindex("return ''"),
          "Rücknahme-Urteil geschlossen: ohne Plan-Liste, ohne Instanz, mit note oder ohne Positionsliste bleibt das Fenster (Prüfer S2)")
    zr = h[h.index("async function echoFensterZuruecknehmen("):]
    check("plan-delete?id=" in zr and zr.index("echoFensterZuruecknehmenUrteil(fenR, inst, aktuell)") < zr.index("plan-delete?id="),
          "plan-delete erst nach dem Urteil (ES2b)")
    check("1500 + Math.random() * 1500" in h and "plan?file=" in h, "echoFensterSchreiben: Wiederholung gestreut 1,5–3 s (Jitter-Regel)")
    s = html.index("async function tpPreflightMt5(plan){")
    t = html[s:html.index("_pfCheckStatus[String(plan.id)] = { state: (!hardFail", s)]
    check("plan?file=" not in t, "tpPreflightMt5 ruft plan?file nur noch über echoFensterSchreiben (kein ungeprüfter Aufruf, kein totes catch)")
    i_p, i_ts = t.index("const fenP = echoFensterSchreiben(file, plan.multiplier, 3)"), t.index("start-terminal?file=")
    check(i_p < i_ts, "Trade-Fenster geht parallel zum Terminal-Start raus (fenP vor start-terminal, ES2 Hebel 2)")
    tsfail = t[t.index("if(!ts.ok){"):t.index("} else {", t.index("if(!ts.ok){"))]
    check("hardFail = true" in tsfail and "await fensterWeg()" in tsfail, "Terminal-Start gescheitert → hardFail + Fenster zurück (ES2b)")
    a = t.index("const fen = await fenP")
    b = t.index("if(!hardFail){\n        // Bereitschafts-Ticker")
    f = t[a:b]
    check("hardFail = true" in f and "schritt: 'm5fenster'" in f and "unklar: false" in f and "await sfEinmal({ schritt: 'm5fenster'" in f and a < b,   # sfEinmal = nur nach Start zur Startzeit (ECHO-STILL-HAENGT)
          "Fenster zu → hardFail (kein Ticker, keine Order) + Start-Fehler m5fenster bei Start zur Startzeit")
    k = t[t.index("if(inst2 && inst2.alive && (!note || imBot)){"):]
    vor_k = t[t.index("_pfMt5Timer = setInterval(async () => {"):t.index("if(inst2 && inst2.alive && (!note || imBot)){")]
    check("const imBot = !altLaufend && echoBotScharfFaehig(d2) && !!(_tpPendingOrder && String(_tpPendingOrder.planId) === String(plan.id))" in vor_k,
          "ES2d: Tab-Warten entfällt nur mit gemeldeter Bot-Fähigkeit, gemerkter Bot-Order und ohne altes „laufend“-Fenster")
    check(k.index("if(!imBot){") < k.index("echoScharfUrteil(inst2") and "}   // Ende Scharf-Beweis im Tab (ES2d)" in k
          and k.index("}   // Ende Scharf-Beweis im Tab (ES2d)") < k.index("master-order?file="),
          "ES2d: ohne Bot-Fähigkeit läuft der Scharf-Beweis im Tab unverändert vor master-order")
    i_u, i_o = k.index("echoScharfUrteil(inst2, Date.now() - scharfAb, altLaufend, scharfMax)"), k.index("master-order?file=")
    fehlt = k[k.index("if(urteil === 'fehlt'){"):k.index("if(urteil === 'warten'){")]
    warten = k[k.index("if(urteil === 'warten'){"):k.index("_pfMt5StopTimer()\n            const fe = document.getElementById('pf-final')")]
    check(i_u < i_o and "return" in fehlt and "return" in warten, "Scharf-Beweis steht VOR master-order, fehlt/warten kehren vorher zurück")
    check("schritt: 'm5scharf'" in fehlt and "_tpPendingOrder = null" in fehlt and "check_fail:true" in fehlt and "_pfMt5StopTimer()" in fehlt,
          "nicht scharf nach der Höchstwartezeit → Ticker aus, gemerkte Order verworfen, Handy-Meldung, Start-Fehler m5scharf")
    check("await fensterWeg()" in fehlt and fehlt.index("await fensterWeg()") < fehlt.index("schritt: 'm5scharf'"), "nicht scharf → Fenster zurück vor dem Start-Fehler (ES2b)")
    order = k[k.index("master-order?file="):]
    body = order[:order.index("if(!mt5OrderWiederholen(r, Date.now() - t0)) break")]
    check("...(imBot ? { scharf_pflicht: true, scharf_max_s: Math.round(scharfMax / 1000) } : {})" in body and html.count("scharf_pflicht: true") == 1,
          "ES2d: scharf_pflicht nur im Echo-mit-Hedge-Body und nur mit Bot-Fähigkeit (Echo V2 nie)")
    mw = html[html.index("function mt5OrderWiederholen(r, seitMs){"):html.index("window._mt5OrderWiederholen = mt5OrderWiederholen")]
    check(mw.index("if(echoBotNichtScharf(r)) return false") < mw.index("const wartbar"), "ES2d: „nicht scharf“ vom Bot wird nie als Terminal-Grund wiederholt")
    nsf = order[order.index("const nichtScharf = echoBotNichtScharf(r)"):order.index("}catch(e){")]
    check("schritt: 'm5scharf'" in nsf and "check_fail:true" in nsf and "state: 'issue'" in nsf and "'✗ Copier nicht scharf — es wurde NICHTS gesendet.'" in nsf
          and "&& !echoAus && !nichtScharf) await sfEinmal({ schritt: 'm5order'" in nsf,
          "ES2d: Bot meldet nicht scharf → Start-Fehler m5scharf, Plakette issue, Handy check_fail, kein m5order")
    nach = order[order.index("pulsSpurSchreiben(plan.id, r)"):order.index("}catch(e){")]
    # EH2 (12.11.2026): + hedgeNull (Panel-Riegel „Hedge wäre 0 Lot“, gesendet false) — auch beweisbar nichts gesendet
    check("(retryOk || echoAus || hedgeNull)) await fensterWeg()" in nach and nach.count("await fensterWeg()") == 1,
          "Order abgelehnt: Fenster nur zurück bei beweisbar nichts gesendet (retry_ok / Echo pausiert / Hedge 0 Lot), nie bei UNKLAR (ES2b)")
    bereit = k[k.index("_pfSet('m5term', 'ok', '✓ Bereit — jetzt im Terminal traden.')") - 300:k.index("if(sec > 240){")]
    check("fensterWeg" not in bereit, "Hand-Weg „Bereit — im Terminal traden“ lässt das Fenster offen (Hand-Trade soll gehedgt werden)")
    tick = t[t.index("_pfMt5Timer = setInterval(async () => {"):]
    check(tick.count("await fensterWeg()") == 6 and t.count("await fensterWeg()") == 7,
          "alle Ausstiege ohne Order nehmen das Fenster zurück: Terminal, Popup zu ×2, Login, Scharf, Order abgelehnt, 4 min (ES2b)")
    check("let altLaufend = String((((fen.r || {}).plan) || {}).status || '') === 'laufend'" in t
          and "echoScharfUrteil(inst2, Date.now() - scharfAb, altLaufend, scharfMax)" in k and "altLaufend = false" in warten,
          "alter „laufend“-Plan: armed zählt erst nach bestätigtem neuen „geplant“ (Prüf-Agent)")
    check("state: 'issue'" in fehlt and "_pfStatusSave()" in fehlt, "nicht scharf → Plakette auf „issue“ statt „Ready“")
    check("8000 + Math.random() * 4000" in warten and "2000 + Math.random() * 2000" in warten and "echoFensterSchreiben(file, plan.multiplier, 1)" in warten,
          "Warten → plan?file gestreut alle 8–12 s erneut, altes „laufend“-Fenster alle 2–4 s (ES2)")
    check(t.count("_pfTickBusy = false }\n        }, 1000)\n        }") == 1, "Ticker liegt vollständig im if(!hardFail)-Block")

    ok = {"ok": True, "plan": {"status": "geplant"}}
    check(fenster_schreiben([{"ok": False, "copier_offline": True, "error": "HTTP 503"}, ok]) == (True, 2), "503 → zweiter Versuch öffnet das Fenster")
    check(fenster_schreiben([{"ok": False, "error": "Zeitlimit 20 s"}] * 5) == (False, 3), "dreimal Fehler → Schluss nach 3 Versuchen, Start-Fehler")
    check(not fenster_ok({"ok": True, "plan": {"status": "beendet"}}) and not fenster_ok({"ok": True}) and fenster_ok({"ok": True, "plan": {"status": "laufend"}}),
          "Panel-Antwort ohne Plan oder mit „beendet“ zählt nicht als offenes Fenster, „laufend“ schon")
    erg = ticker([False] * 4 + [True])
    check(erg[0] == "order" and erg[1] == 5, f"armed kommt nach 4 s → Order im 5. Tick ({erg})")
    erg = ticker([False] * 60)
    check(erg[0] == "fehlt" and erg[1] == 32 and erg[2] == 3, f"armed bleibt aus → nach 30 s Start-Fehler, keine Order, 3× plan?file erneut ({erg})")
    check(ticker([True])[0] == "order", "armed sofort da → Order ohne Wartezeit")
    flach_alt = {"status": {"armed": True, "master_positions": []}}
    check(urteil(flach_alt, 1000, True) == "warten" and urteil(flach_alt, 31000, True) == "fehlt" and urteil(flach_alt, 1000, False) == "scharf",
          "alter „laufend“-Plan + Master flach → keine Order, bis das neue Fenster bestätigt ist (sonst nach 30 s Start-Fehler)")
    check(urteil({"status": {"armed": True, "master_positions": [{"ticket": 1}]}}, 1000, True) == "scharf",
          "„laufend“ mit offener Master-Position bleibt scharf (Fenster gehört zum laufenden Trade)")
    check(urteil({"status": {"armed": "true"}}, 0) == "warten" and urteil({"status": {}}, 31000) == "fehlt",
          "nur armed === true zählt (Text/fehlendes Feld nicht)")
    erg = ticker([False] * 90, max_ms=60000)
    check(erg[0] == "fehlt" and erg[1] == 62, f"Einstellung 60 s → Start-Fehler erst nach 60 s ({erg})")
    check(urteil({"status": {}}, 31000, False, 60000) == "warten" and urteil({"status": {}}, 31000, False, 0) == "fehlt",
          "maxMs 0/fehlt → Standard 30 s")
    # Bot-Fähigkeit (ES2d, Spiegel von echoBotScharfFaehig / echoBotNichtScharf)
    def bot_faehig(d):
        return bool(d and isinstance(d.get("bot_faehig"), list) and "scharf_pflicht" in d["bot_faehig"])
    def bot_nicht_scharf(r):
        return bool(r and not r.get("ok") and r.get("retry_ok") is True and (r.get("grund") == "nicht_scharf" or r.get("code") == "nicht_scharf"))
    check(not bot_faehig({}) and not bot_faehig({"version": "2026-09-22.2091"}) and not bot_faehig({"bot_faehig": "scharf_pflicht"})
          and bot_faehig({"bot_faehig": ["scharf_pflicht"]}), "Bot-Fähigkeit nur mit ausdrücklicher Liste — Versionsnummer allein reicht nicht")
    check(bot_nicht_scharf({"ok": False, "retry_ok": True, "code": "nicht_scharf"}) and not bot_nicht_scharf({"ok": False, "code": "nicht_scharf"})
          and not bot_nicht_scharf({"ok": False, "retry_ok": True, "grund": "terminal_heilt"}), "nicht_scharf nur mit retry_ok (beweisbar nichts gesendet)")
    fz = html[html.index("function echoBotScharfFaehig(d){"):html.index("window._echoFenster = ")]
    check("Array.isArray(d.bot_faehig) && d.bot_faehig.includes('scharf_pflicht')" in fz and "r.retry_ok === true && (r.grund === 'nicht_scharf' || r.code === 'nicht_scharf')" in fz,
          "JS-Regeln = Spiegel hier (bot_faehig, nicht_scharf)")
    # Panel meldet die Fähigkeit (ES2d): reine Funktion aus panel.py gegen den Bot von jetzt und den vor ES3b
    import ast, subprocess
    psrc = open(os.path.join(HIER, "..", "mt5-copier", "panel.py"), encoding="utf-8").read()
    fn = [n for n in ast.parse(psrc).body if isinstance(n, ast.FunctionDef) and n.name == "bot_faehig_aus_quelle"][0]
    ns = {}
    exec(compile(ast.Module([fn], []), "panel.bot_faehig_aus_quelle", "exec"), ns)
    neu = open(os.path.join(HIER, "..", "mt5-copier", "order_bot.py"), encoding="utf-8").read()
    alt = subprocess.run(["git", "show", "ed4ea1b1:mt5-copier/order_bot.py"], capture_output=True, text=True, cwd=os.path.join(HIER, "..")).stdout
    check(bool(alt.strip()), "Vergleichs-Bot vor ES3b (ed4ea1b1) lesbar — sonst prüfte der nächste Punkt nichts")
    check(ns["bot_faehig_aus_quelle"](neu) == ["scharf_pflicht"] and bool(alt.strip()) and ns["bot_faehig_aus_quelle"](alt) == []
          and ns["bot_faehig_aus_quelle"]("") == [], "Panel: scharf_pflicht nur für einen Bot mit Scharf-Beweis (ES3b), nicht für den Bot davor")
    check('"bot_faehig": bot_faehig(),' in psrc and 'if not ohne_hedge and body.get("scharf_pflicht") is True:' in psrc,
          "Panel: instances meldet bot_faehig, master-order reicht scharf_pflicht nur bei Echo mit Hedge durch")
    mo = psrc[psrc.index('if not ohne_hedge and body.get("scharf_pflicht") is True:'):]
    check(mo.index('if "scharf_pflicht" not in bot_faehig():') < mo.index('cmd["scharf_pflicht"] = True') and '"code": "nicht_scharf"' in mo[:mo.index('cmd["scharf_pflicht"] = True')],
          "Panel: beim Senden noch einmal — Bot ohne Scharf-Beweis → nicht_scharf, nichts gestartet (Gegenprüfung ES2d)")
    # Rücknahme-Urteil (ES2b, geschlossen)
    g = {"ok": True, "plan": {"id": 7, "status": "geplant", "armed_at": "2026-11-05T19:00:00"}}
    gleich = {"id": 7, "status": "geplant", "armed_at": "2026-11-05T19:00:00"}
    flach = {"alive": True, "status": {"master_positions": []}}
    check(zurueck_urteil(g, flach, gleich) == "", "Fenster geplant, unverändert, frischer Snapshot flach → darf weg")
    check(zurueck_urteil(g, flach) == "Plan-Liste nicht lesbar" and zurueck_urteil(g, None, gleich) == "Instanz nicht lesbar",
          "Panel nicht lesbar → Fenster bleibt (geschlossen)")
    check(zurueck_urteil(g, {"alive": True, "status": {"note": "warte auf Snapshot des Master-Terminals", "master_positions": []}}, gleich) == "kein frischer Snapshot"
          and zurueck_urteil(g, {"alive": False, "status": {"master_positions": []}}, gleich) == "kein frischer Snapshot",
          "Terminal zu / Copier alt → keine Position beweisbar → Fenster bleibt")
    check(zurueck_urteil(g, {"alive": True, "status": {}}, gleich) == "Positionsliste fehlt", "ohne Positionsliste → Fenster bleibt")
    check(zurueck_urteil(g, {"alive": True, "status": {"master_positions": [{"ticket": 1}]}}, gleich) == "Master-Position offen", "Master-Position offen → Fenster bleibt")
    check(zurueck_urteil(g, flach, dict(gleich, armed_at="2026-11-05T19:00:09")) == "erneuert" and zurueck_urteil(g, flach, dict(gleich, status="laufend")) == "inzwischen nicht geplant",
          "von einem anderen Start erneuert oder inzwischen laufend → Fenster bleibt")
    check(zurueck_urteil(g, flach, None) == "schon weg" and zurueck_urteil({"ok": False}, flach, gleich) == "kein Fenster"
          and zurueck_urteil({"ok": True, "plan": {"id": 7, "status": "laufend"}}, flach, gleich) == "steht nicht auf geplant",
          "nichts zu tun: schon weg, kein Fenster dieses Checks, altes „laufend“")
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
