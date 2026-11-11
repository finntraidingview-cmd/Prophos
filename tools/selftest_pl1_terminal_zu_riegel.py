#!/usr/bin/env python3
"""Selbsttest PL1 (11.11.2026, Master nach Hinweis S2 aus VF3): Terminal-Zu nie während eines Bot-Laufs der Instanz.
panel.terminal_zu_order_riegel (rein) + _terminal_kill_riegel (mit falschem provision/Locks) + Einbau in Trade-Ende-Worker, Leerlauf-Wächter, Knopf
und die 409-Antwort der Order-Routen. Ohne Windows. Aufruf: python3 tools/selftest_pl1_terminal_zu_riegel.py"""
import os
import sys
import threading
import time

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = open(os.path.join(W, "mt5-copier", "panel.py"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


class Prov:
    def __init__(self, pids):
        self.pids, self.kills = list(pids), []

    def terminal_pids(self, d):
        return list(self.pids)

    def _taskkill(self, pid, grace_s=None):
        self.kills.append(pid)


ns = {"threading": threading, "time": time}
exec(SRC[SRC.index("TERMINAL_ZU_HAELT = set()"):SRC.index("def loesch_terminal_dir(")], ns)
R, K = ns["terminal_zu_order_riegel"], ns["_terminal_kill_riegel"]


def welt(pids=(11, 12)):
    ns.update(MASTER_ORDER_LOCKS={}, MASTER_ORDER_GUARD=threading.Lock(), ORDER_ANGEMELDET={}, DEALS_LESEN=set(), VORFLUG_LESEN=set(),
              ORDER_ANGEMELDET_S=60.0, provision=Prov(pids))
    ns["TERMINAL_ZU_HAELT"].clear()
    return ns["provision"]


F = "config-a.json"
J = 1_000_000.0
# 1) rein
check(R(F, {}, {}, set(), J) == "", "frei + kein Lauf → '' (schließen wie heute)")
lk = threading.Lock(); lk.acquire()
check("MASTER_ORDER_LOCK" in R(F, {F: lk}, {}, set(), J), "Lock gehalten → kein Schließen")
check(R(F, {"andere.json": lk}, {}, set(), J) == "", "Lock einer ANDEREN Instanz → zählt nicht")
lk.release()
check(R(F, {F: threading.Lock()}, {}, set(), J) == "", "Lock da, aber frei → ''")
check("Lese-Lauf" in R(F, {}, {}, {F}, J), "DEALS_LESEN/VORFLUG_LESEN führt die Instanz → kein Schließen")
check("angemeldet" in R(F, {}, {F: J - 10}, set(), J), "Order/Close vor 10 s angemeldet → kein Schließen")
check(R(F, {}, {F: J - 61}, set(), J) == "", "Anmeldung älter als 60 s → ''")
check(R(F, {}, {F: "kaputt"}, set(), J) == "", "kaputte Anmeldung → '' (zählt nicht)")

# 2) Kill-Hilfe
p = welt()
ok, n, g = K(F, "C:/t")
check(ok and n == 2 and p.kills == [11, 12] and g == "", "frei + kein Plan → schließen wie heute (alle PIDs)")
check(not ns["MASTER_ORDER_LOCKS"][F].locked() and F not in ns["TERMINAL_ZU_HAELT"], "danach: Lock frei, Kennzeichen weg")
p = welt(())
ok, n, g = K(F, "C:/t")
check(ok and n == 0 and p.kills == [], "schon zu → ok mit 0 PIDs, kein Kill")
p = welt()
lk = threading.Lock(); lk.acquire(); ns["MASTER_ORDER_LOCKS"][F] = lk
t0 = time.time()
ok, n, g = K(F, "C:/t")
check(not ok and p.kills == [] and "MASTER_ORDER_LOCK" in g and time.time() - t0 < 0.5, "Lock gehalten → kein Kill, kein Warten")
check(F not in ns["TERMINAL_ZU_HAELT"], "Prüfer SOLLTE: acquire gescheitert → Merker sofort wieder weg")
ex = SRC[SRC.index("def _terminal_kill_riegel("):SRC.index("def loesch_terminal_dir(")]
check(ex.index("TERMINAL_ZU_HAELT.add(fname)") < ex.index("lock.acquire(blocking=False)")
      and ex.rindex("lock.release()") < ex.rindex("TERMINAL_ZU_HAELT.discard(fname)"),
      "Prüfer SOLLTE: Merker vor dem acquire gesetzt, nach dem release entfernt (keine Lücke für „läuft schon eine Order“)")
lk.release()
p = welt(); ns["VORFLUG_LESEN"].add(F)
check(K(F, "C:/t")[0] is False and p.kills == [], "Vorflug läuft → kein Kill")
p = welt(); ns["DEALS_LESEN"].add(F)
check(K(F, "C:/t")[0] is False and p.kills == [], "Deal-Lesung läuft → kein Kill")
p = welt(); ns["ORDER_ANGEMELDET"][F] = time.time()
check(K(F, "C:/t")[0] is False and p.kills == [], "Order angemeldet → kein Kill")
check(not ns["MASTER_ORDER_LOCKS"].get(F) or not ns["MASTER_ORDER_LOCKS"][F].locked(), "nach Abbruch: Lock nicht hängen geblieben")


# Anmeldung genau zwischen erster Prüfung und acquire (die Route meldet vor ihrem acquire an)
p = welt()
echt_guard = ns["MASTER_ORDER_GUARD"]


class GuardMitAnmeldung:
    def __enter__(self):
        echt_guard.acquire()
        ns["ORDER_ANGEMELDET"][F] = time.time()   # angemeldet, während wir den Lock nehmen
        return self

    def __exit__(self, *a):
        echt_guard.release()


ns["MASTER_ORDER_GUARD"] = GuardMitAnmeldung()
ok, n, g = K(F, "C:/t")
check(not ok and p.kills == [] and "angemeldet" in g and not ns["MASTER_ORDER_LOCKS"][F].locked() and F not in ns["TERMINAL_ZU_HAELT"],
      "Anmeldung zwischen Prüfung und acquire → zweite Prüfung hält, Lock wieder frei")

# während des Kills: Lock gehalten + Kennzeichen gesetzt (die Order-Route sieht terminal_zu)
p = welt()
gesehen = {}


def kill_beobachten(pid, grace_s=None):
    gesehen["lock"] = ns["MASTER_ORDER_LOCKS"][F].locked()
    gesehen["haelt"] = F in ns["TERMINAL_ZU_HAELT"]


p._taskkill = kill_beobachten
K(F, "C:/t")
check(gesehen == {"lock": True, "haelt": True}, "während des Schließens: MASTER_ORDER_LOCK gehalten, TERMINAL_ZU_HAELT gesetzt")
p = welt()


def kill_wirft(pid, grace_s=None):
    raise OSError("weg")


p._taskkill = kill_wirft
try:
    K(F, "C:/t")
    geworfen = False
except OSError:
    geworfen = True
check(geworfen and not ns["MASTER_ORDER_LOCKS"][F].locked() and F not in ns["TERMINAL_ZU_HAELT"], "Kill-Fehler: Lock und Kennzeichen trotzdem frei")

# 3) Einbau (Textanker)
w = SRC[SRC.index("def _terminal_zu_worker(") if "def _terminal_zu_worker(" in SRC else SRC.index("Terminal-Zu in ~"):SRC.index("# ── Leerlauf-Waechter")]
check("_terminal_kill_riegel(fname, install_dir)" in w and "provision._taskkill" not in w, "Trade-Ende-Worker: schließt nur über den Riegel")
lw = SRC[SRC.index("schwelle = _LEERLAUF_SCHWELLE.setdefault"):SRC.index("# MT5-Update ohne UAC-Abfrage")]
check("_terminal_kill_riegel(fname, install_dir)" in lw and "provision._taskkill" not in lw and "continue" in lw[lw.index("if not zu_ok:"):],
      "Leerlauf-Wächter: schließt nur über den Riegel, sonst nächster Takt")
kn = SRC[SRC.index('if u.path == "/api/close-idle-terminals":'):SRC.index('fname = (parse_qs(u.query).get("file") or [""])[0]')]
check("_terminal_kill_riegel(kf, kdir)" in kn and "provision._taskkill" not in kn and "terminal_zu_order_riegel(" in kn,
      "Knopf: Entscheidung meldet Bot-Lauf als übersprungen, Killer schließt nur über den Riegel")
check(SRC.count('if inst["config_file"] in TERMINAL_ZU_HAELT:') == 2 and SRC.count('"grund": "terminal_zu"') == 2,
      "master-order + master-close: Lock vom Terminal-Zu → 409 retry_ok terminal_zu (nichts gesendet)")
m = SRC[SRC.index("def mt5_order_belegt("):SRC.index("TV_ORDER_LOCK = threading.Lock()")]
check("TERMINAL_ZU_HAELT" not in m, "mt5_order_belegt unverändert (Terminal-Zu zählt PC-weit als belegt, wie eine Order)")

print(f"\n{'ALLES GRÜN' if not FEHLER else str(len(FEHLER)) + ' ROT'}")
sys.exit(1 if FEHLER else 0)
