#!/usr/bin/env python3
"""Selbsttest HARTE LINIE AUCH FÜR ECHO (30.10.2026, Finn: „auf gar keinen Fall ein interner Hedge"; Audit Slave 1: Echo mt5/mt5v2 von
Hand am PC hatte keine DB-Linie). Prüft am Quelltext:
  · panel.py /api/master-order fragt richtung_frei VOR Lock und Bot-Start, sperrt ohne plan_id/Richtung (fail-closed) und bei
    gegenrichtung/riegel_unerreichbar — mit retry_ok=True und gesendet=False (beweisbar nichts gesendet);
  · big_trade_nah/_unklar (Heim-Regel des Puls-Chrome) sperren eine MT5-Order nicht;
  · beide master-order-Aufrufe im PC-Tab schicken plan_id mit;
  · der Echo-V2-Check liest die Pläne streng (DB-Fehler wirft) und sperrt, statt nur zu warnen.
Aufruf:  python3 tools/selftest_echo_richtung_riegel.py"""
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fehler = 0


def soll(name, ok):
    global fehler
    print(("ok   " if ok else "FEHL ") + name)
    fehler += 0 if ok else 1


def main():
    panel = open(os.path.join(WURZEL, "mt5-copier", "panel.py"), encoding="utf-8").read()
    i = panel.index('if u.path == "/api/master-order":')
    blk = panel[i:panel.index('if u.path == "/api/master-close":', i)]
    k_riegel = blk.find("richtung_frei(_pid, cmd[\"richtung\"])")
    soll("master-order ruft richtung_frei", k_riegel > 0)
    soll("richtung_frei vor dem Instanz-Lock", 0 < k_riegel < blk.find("lock.acquire(blocking=False)"))
    soll("richtung_frei vor dem Bot-Start", 0 < k_riegel < blk.find("subprocess.run("))
    soll("richtung_frei vor dem Echo-Pause-Riegel nicht nötig, aber vor ohne_hedge-Riegeln", 0 < k_riegel < blk.find("ohne_hedge = bool("))
    k_ohne = blk.find('re.fullmatch(r"[0-9a-f-]{36}", _pid)')
    soll("ohne plan_id/Richtung gesperrt (fail-closed)", 0 < k_ohne < k_riegel and "alter Prophos-" in blk)
    soll("Sperre meldet retry_ok + gesendet False", blk.count('"retry_ok": True, "gesendet": False') >= 2)
    soll("nur gegenrichtung/riegel_unerreichbar sperren (Heim-Regel nicht)", '_code in ("gegenrichtung", "riegel_unerreichbar")' in blk)
    # richtung_frei selbst bleibt fail-closed (kein Token / Netz → nicht frei)
    j = panel.index("def richtung_frei(")
    rf = panel[j:panel.index("\ndef ", j + 10)]
    soll("richtung_frei: ohne Token nicht frei", 'return False, ("Riegel-Prüfung (Gegenrichtung) nicht möglich' in rf)
    soll("richtung_frei: Netzfehler nicht frei", rf.rstrip().endswith('"riegel_unerreichbar"'))

    html = open(os.path.join(WURZEL, "prophos.html"), encoding="utf-8").read()
    aufrufe = html.split("master-order?file=")[1:]
    soll("zwei master-order-Aufrufe im Tab", len(aufrufe) == 2)
    for n, a in enumerate(aufrufe, 1):
        soll(f"Aufruf {n} schickt plan_id", "plan_id: String(plan.id)" in a[:900])
    soll("v2RichtungKonflikt kennt streng (wirft bei DB-Fehler)", "if(o.streng && (error || !Array.isArray(data))) throw" in html
         and "}catch(e){ if(o.streng) throw e }" in html)
    soll("Echo-V2-Check liest streng", "frisch: true, streng: true })" in html)
    soll("Echo-V2-Check sperrt bei nicht prüfbar", "fail('v2dir', `Richtungs-Schutz nicht prüfbar" in html
         and "_pfSet('v2dir', 'warn', 'Richtungs-Schutz nicht prüfbar" not in html)
    soll("Echo (mt5, mit Hedge) sperrt bei nicht prüfbar", "_pfSet('m5dir', 'err', `Richtungs-Schutz nicht prüfbar" in html
         and "_pfSet('m5dir', 'warn', 'Richtungs-Schutz nicht prüfbar" not in html)
    print("ALLE OK" if not fehler else f"{fehler} FEHLER")
    sys.exit(1 if fehler else 0)


if __name__ == "__main__":
    main()
