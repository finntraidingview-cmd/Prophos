#!/usr/bin/env python3
"""Selbsttest TC1c (05.11.2026): ebnStartNah zählt einen geclaimten, nie gestarteten Plan nur EBN_CLAIM_FRISCH_MS (15 min) lang als „Start steht an“.
Anlass Jacob FundedNext 100k …7924 (af4f8ee8): 4 alte Claims (15:23/15:51 UTC) sperrten echoLoginLesen dauerhaft → Echo-Ende nie reif, obwohl Master +
Hedge 4 h frisch flach (Balance 98.266,71). Quelltext-Prüfung; das Verhalten der reinen Funktion prüft der Boot-Check über window._ebnStartNahPlaene
(05.11.2026: Jacob-Claims → false, Claim 14 min → true, 16 min → false, Start in 3 min / vor 10 min → true, unbestätigter Auto-Plan → false,
Claim unlesbar → true, gestartet → false). Aufruf: python3 tools/selftest_ebn_claim.py"""
import os
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = open(os.path.join(W, "prophos.html"), encoding="utf-8").read()
FEHLER = []


def check(ok, name):
    print(("✓ " if ok else "✗ ") + name)
    if not ok:
        FEHLER.append(name)


i = HTML.index("function ebnStartNahPlaene(")
f = HTML[i:HTML.index("window._ebnStartNahPlaene", i)]
check("const EBN_CLAIM_FRISCH_MS = 15 * 60000" in HTML, "Claim zählt 15 min")
check("p.startUmGestartetAt && !p.startedAt && (() => { const c = Date.parse(p.startUmGestartetAt); return !isFinite(c) || jetzt - c < EBN_CLAIM_FRISCH_MS })()" in f,
      "alter Claim zählt nicht mehr, unlesbarer Claim vorsichtshalber schon")
check("d < 5 * 60000 && d > -15 * 60000" in f and "!(p.autoPlan === true && !p.autoBestaetigtAt)" in f, "Startfenster und unbestätigte Auto-Pläne wie bisher")
j = HTML.index("function ebnStartNah(){")
g = HTML[j:HTML.index("const EBN_OEFFNEN_MAX", j)]
check("_tpOrbitLaeuft || _osActive || _suLaeuft || _pfV2Laeuft" in g and "ebnStartNahPlaene(tradePlans, Date.now())" in g and "catch(_){ return true }" in g,
      "Lauf-Marken zuerst, sonst die reine Prüfung; Fehler → vorsichtig true")
check(HTML.count("ebnStartNah()") >= 4, "alle Aufrufer (echoLoginLesen, echoGeistAnstossen, ebnTick) nutzen dieselbe Funktion")
print("\nALLES GRÜN" if not FEHLER else f"\n{len(FEHLER)} FEHLER")
sys.exit(1 if FEHLER else 0)
