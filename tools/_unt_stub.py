"""Gemeinsamer Stub für Selbsttests, die einzelne Funktionen aus app.py in einen eigenen Namensraum laden (UNT3, 05.11.2026): die Konto-Leser
rufen seit Phase 2 „Regel je Unternehmen" ap_unt_firmen / ap_regel_unternehmen / ap_unt_kontext. Im Test gilt — wie in der App ohne Service-Key —
für jede ID der Standard (dieselbe Firmen-Liste). Die Regel je Unternehmen selbst prüfen tools/selftest_regel_unternehmen.py und
tools/selftest_unt3_bitgleich.py."""


def unt_stub(ns):
    ns.setdefault("ap_unt_firmen", lambda uid, firmen_std, ktx=None, streng=True: firmen_std)
    ns.setdefault("ap_regel_unternehmen", lambda uid, firmen_std, firm, ktx=None, streng=True: ns["ap_regel_finden"](firmen_std, firm))
    ns.setdefault("ap_unt_kontext", lambda frisch=False: {"ok": True, "gid_von": {}, "zeilen": {}, "ht": frozenset(), "memo": {}})
    # UNT4: Funded-Regeln je Unternehmen — im Test jede ID Standard (dieselbe Regel-Zeile)
    ns.setdefault("fd_unt_reg", lambda reg, art, uid, ktx=None, streng=False: reg)
    ns.setdefault("fd_unt_an", lambda reg, art, uid, ktx=None, streng=False: [f for f in ((reg or {}).get("firmen") or []) if isinstance(f, dict) and f.get("an")])
    # TW1 (11.11.2026): Handels-Würfel im Test aus (= 100 %, jedes Konto handelt wie vor TW1); den Würfel selbst prüft tools/selftest_tw1_handels_wuerfel.py
    ns.setdefault("tw_pause_grund", lambda planer, a, tag, werte=None, ktx=None: None)
    ns.setdefault("tw_werte", lambda frisch=False: {})
    ns.setdefault("tw_nachplan_filter", lambda kand, konten, tag, firmen: kand)
    return ns
