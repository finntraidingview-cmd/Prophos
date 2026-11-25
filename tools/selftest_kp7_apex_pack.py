"""KP7 (Finn 25.11.2026): Apex-Pack erst bei <= 2 laufenden Challenges. Rein rechnend: vorrat_kauf_deckel aus dem Backend per AST."""
import ast, os, sys
W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(W, "app.py"), encoding="utf-8").read()
tree = ast.parse(src)
fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "vorrat_kauf_deckel")
ns = {"VORRAT_LAUFEND_TYPEN": ("challenge", "phase1", "phase2"), "VORRAT_FNF_SPERRE": "ab 1. FN-Payout"}
exec(compile(ast.Module(body=[fn], type_ignores=[]), "app.py", "exec"), ns)
f = ns["vorrat_kauf_deckel"]
P = {"max_laufend": {"Apex Trader": 5}, "kauf_pack": {"Apex Trader": 5}, "pack_nachkauf_ab": {"Apex Trader": 2}}


def k(n):
    return [{"stufe": "challenge", "balance_at": "x"} for _ in range(n)]


fehler = []


def ok(b, t):
    print(("✓ " if b else "✗ ") + t)
    if not b:
        fehler.append(t)


ok(f(5, k(0), "Apex Trader", P, erwartet=0, ziel=10000)["n"] == 5, "0 laufend -> 1 Pack")
ok(f(5, k(2), "Apex Trader", P, erwartet=0, ziel=10000)["n"] == 5, "2 laufend -> 1 Pack")
ok(f(5, k(3), "Apex Trader", P, erwartet=0, ziel=10000)["n"] == 0, "3 laufend -> nichts")
ok(f(5, k(1), "Apex Trader", P, erwartet=12000, ziel=10000)["n"] == 0, "erwartet >= Ziel -> nichts (nie übers Ziel)")
ok(f(3, k(1), "Tradeify", dict(P, max_laufend={"Tradeify": 4}), erwartet=0, ziel=1)["n"] == 3, "Tradeify unverändert min(Lücke, Max - laufend)")
print("ALLES GRÜN" if not fehler else f"FEHLER ({len(fehler)})")
sys.exit(1 if fehler else 0)
