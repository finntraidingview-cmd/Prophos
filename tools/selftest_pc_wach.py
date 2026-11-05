#!/usr/bin/env python3
"""Selbsttest PC WACH HALTEN (PL2, 05.11.2026): panel.py pc_wach_halten mit gemocktem kernel32 + Verdrahtung in main().
Aufruf: python3 tools/selftest_pc_wach.py"""
import ast
import os
import sys

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
ok = True


def chk(bed, text):
    global ok
    print(("  OK   " if bed else "  FEHLER ") + text)
    ok = ok and bool(bed)


pfad = os.path.join(WURZEL, "mt5-copier", "panel.py")
src = open(pfad, encoding="utf-8").read()
ns = {"os": os}
for n in ast.parse(src).body:
    if isinstance(n, ast.FunctionDef) and n.name == "pc_wach_halten":
        exec(compile(ast.Module([n], []), pfad, "exec"), ns)
    if isinstance(n, ast.Assign) and any(getattr(t, "id", "") in ("ES_CONTINUOUS", "ES_SYSTEM_REQUIRED") for t in n.targets):
        exec(compile(ast.Module([n], []), pfad, "exec"), ns)
w = ns["pc_wach_halten"]


class K:
    def __init__(self, rueck=1, wirft=False):
        self.rueck, self.wirft, self.aufrufe = rueck, wirft, []

    def SetThreadExecutionState(self, flags):
        self.aufrufe.append(flags)
        if self.wirft:
            raise OSError("kaputt")
        return self.rueck


k = K()
chk(w(k) is True, "gesetzt → True")
chk(k.aufrufe == [0x80000001], f"Flags = ES_CONTINUOUS | ES_SYSTEM_REQUIRED ({[hex(x) for x in k.aufrufe]})")
chk(not (k.aufrufe[0] & 0x00000002), "ohne ES_DISPLAY_REQUIRED (Bildschirm darf aus)")
chk(not (k.aufrufe[0] & 0x00000040), "ohne ES_AWAYMODE_REQUIRED")
chk(w(K(rueck=0)) is False, "Windows lehnt ab (0) → False")
chk(w(K(wirft=True)) is False, "Fehler → False, wirft nie")
if os.name != "nt":
    chk(w() is None, "kein Windows → None, nichts aufgerufen")
m = src[src.index("\ndef main():"):]
chk(m.index("pc_wach_halten()") < m.index("_selbst_auffrischen()") < m.index("Handler).serve_forever()"), "im Haupt-Thread von main(), vor serve_forever (Zustand gilt je Thread)")
chk("threading.Thread(target=pc_wach_halten" not in src, "nie in einem eigenen Thread (der Zustand endete mit ihm)")
print("\nALLES OK" if ok else "\nFEHLER")
sys.exit(0 if ok else 1)
