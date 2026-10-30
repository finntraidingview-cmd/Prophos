#!/usr/bin/env python3
"""Selbsttest: Echo mit Hedge (route mt5, tpPreflightMt5) — Trade-Fenster geprüft, Order erst mit Scharf-Beweis (30.10.2026, Befund
Slave 8: zwei Echo-mit-Hedge-Master liefen ohne Hedge; plan?file ging ungeprüft raus, master-order feuerte bei alive && !note ohne
armed). Prüft die Verdrahtung in prophos.html und spielt Fenster-Versuche und Bereitschafts-Ticker mit gestellten Antworten nach
(dieselben Regeln wie echoFensterOk / echoScharfUrteil). Aufruf: python3 tools/selftest_echo_fenster_scharf.py"""
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


def urteil(inst, seit_ms, alt_laufend=False):
    """Python-Spiegel von echoScharfUrteil."""
    st = (inst or {}).get("status") or {}
    flach = not (st.get("master_positions") or [])
    if st.get("armed") is True and not (alt_laufend and flach):
        return "scharf"
    return "fehlt" if seit_ms > MAX_MS else "warten"


def fenster_schreiben(antworten, versuche=3):
    """Spielt echoFensterSchreiben nach: → (ok, Anzahl Aufrufe)."""
    n = 0
    for a in antworten[:versuche]:
        n += 1
        if fenster_ok(a):
            return True, n
    return False, n


def ticker(armed_folge, takt_ms=1000, neu_ms=10000):
    """Spielt den Bereitschafts-Ticker ab „Terminal bereit" nach: je Tick armed True/False.
    → (Ergebnis 'order' | 'fehlt' | 'offen', Ticks, erneute plan?file-Aufrufe)."""
    t, neu_ab, neu_n = 0, 0, 0
    for i, armed in enumerate(armed_folge):
        u = urteil({"alive": True, "status": {"armed": armed}}, t)
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
          and "st.armed === true && !(altLaufend && flach)) return 'scharf'" in h and "seitMs > ECHO_SCHARF_MAX_MS ? 'fehlt' : 'warten'" in h,
          "Regeln im Frontend = Spiegel hier (ok + geplant/laufend, armed === true, 30 s)")
    check("1500 + Math.random() * 1500" in h and "plan?file=" in h, "echoFensterSchreiben: Wiederholung gestreut 1,5–3 s (Jitter-Regel)")
    s = html.index("async function tpPreflightMt5(plan){")
    t = html[s:html.index("_pfCheckStatus[String(plan.id)] = { state: (!hardFail", s)]
    check("plan?file=" not in t, "tpPreflightMt5 ruft plan?file nur noch über echoFensterSchreiben (kein ungeprüfter Aufruf, kein totes catch)")
    a = t.index("const fen = await echoFensterSchreiben(file, plan.multiplier, 3)")
    b = t.index("if(!hardFail){\n        // Bereitschafts-Ticker")
    f = t[a:b]
    check("hardFail = true" in f and "schritt: 'm5fenster'" in f and "unklar: false" in f and "await sfEinmal({ schritt: 'm5fenster'" in f and a < b,   # sfEinmal = nur nach Start zur Startzeit (ECHO-STILL-HAENGT)
          "Fenster zu → hardFail (kein Ticker, keine Order) + Start-Fehler m5fenster bei Start zur Startzeit")
    k = t[t.index("if(inst2 && inst2.alive && !note){"):]
    i_u, i_o = k.index("echoScharfUrteil(inst2, Date.now() - scharfAb, altLaufend)"), k.index("master-order?file=")
    fehlt = k[k.index("if(urteil === 'fehlt'){"):k.index("if(urteil === 'warten'){")]
    warten = k[k.index("if(urteil === 'warten'){"):k.index("_pfMt5StopTimer()\n            const fe = document.getElementById('pf-final')")]
    check(i_u < i_o and "return" in fehlt and "return" in warten, "Scharf-Beweis steht VOR master-order, fehlt/warten kehren vorher zurück")
    check("schritt: 'm5scharf'" in fehlt and "_tpPendingOrder = null" in fehlt and "check_fail:true" in fehlt and "_pfMt5StopTimer()" in fehlt,
          "nicht scharf nach 30 s → Ticker aus, gemerkte Order verworfen, Handy-Meldung, Start-Fehler m5scharf")
    check("let altLaufend = String((((fen.r || {}).plan) || {}).status || '') === 'laufend'" in t
          and "echoScharfUrteil(inst2, Date.now() - scharfAb, altLaufend)" in k and "altLaufend = false" in warten,
          "alter „laufend“-Plan: armed zählt erst nach bestätigtem neuen „geplant“ (Prüf-Agent)")
    check("state: 'issue'" in fehlt and "_pfStatusSave()" in fehlt, "nicht scharf → Plakette auf „issue“ statt „Ready“")
    check("8000 + Math.random() * 4000" in warten and "echoFensterSchreiben(file, plan.multiplier, 1)" in warten,
          "Warten → plan?file gestreut alle 8–12 s erneut")
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
    print()
    if FEHLER:
        print(f"✗ {len(FEHLER)} Fehler")
        sys.exit(1)
    print("✓ alles grün")


if __name__ == "__main__":
    main()
