# ════════════════════════════════════════════════════════════════════════════
# STRIKING FÜR APEX (SK1, Finn 20.11.2026 ~04:15 Dubai: Konstrukt „passt“, Hedge „0.2 auf max drawdown“)
# Spezifikation: .claude/master/berichte/2026-11-20_SK1_striking_apex_konstrukt.md
#
# Reine Rechnung (kein Supabase, kein Flask) — app.py (fdp_planen) liest Konten, Pläne und Regeln und ruft nur diese
# Funktionen; der Selbsttest tools/selftest_striking.py prüft sie ohne app.py.
#
# Gezählt wird nur der laufende Zyklus: accounts.striking_zyklus_start (Balance) + striking_zyklus_seit (Probation-Start bzw. Payout-Datum) —
# Profit, bester Tag, Tage ≥ Schwelle und Consistency aus den Trades ab diesem Zeitpunkt, nie aus der Lebensdauer des Kontos.
# Jeder Payout braucht 5 Tage mit $300+ / $350+ und Consistency 50 % gegen den NETTO-Profit seit Zyklus-Start, dazu
#   mit Trader Probation (accounts.striking_probation, Marc): „Minimum Profit to Pass“ 3.600 / 4.600 ab Zyklus-Start → Z = max(2 × Cap, Profit);
#   ohne Probation (Jacob): Balance ≥ Mindest-Payout-Balance 103.600 / 154.600 (absolut) → Z = max(2 × Cap, Mindest-Balance − Zyklus-Start).
#   Nie mehr als Z („mehr Profit bringt nichts“).
#   Erst kleine normale Trades (TP 370–420, keine Winning Days), dann Pump-Trades: Rest R = Z − Netto, Deckel c = 50 % × Z × 0,95,
#   n = ceil(R ÷ c), TPs gestreut, jeder ≤ c, der letzte schließt GENAU den Rest. Nach Verlust wird R größer, c bleibt → mehr Trades.
#   SL = Zufall 60–90 % des Daily Loss der Stufe. Hedge 0,2 € je $ Abstand zum Konto-Boden (Balance − Boden).
# ════════════════════════════════════════════════════════════════════════════
import math

# Standard = Werte der Spezifikation; striking_regeln.apex (DB) überschreibt je Schlüssel
SK_STANDARD = {
    "caps": {"100000": [2000, 2500, 2500, 3000, 4000, 4000], "150000": [2500, 3000, 3000, 3000, 4000, 5000]},
    "min_profit": {"100000": 3600, "150000": 4600},             # nur Trader Probation: nötiger Profit ab Zyklus-Start
    "min_payout_balance": {"100000": 103600, "150000": 154600},  # ohne Probation: Balance ≥ Mindest-Payout-Balance (absolut; Jacob 20.11.)
    "tag_schwelle": {"100000": 300, "150000": 350},
    "klein_tp": [370, 420],
    "deckel_pct": 50,
    "puffer": 0.95,
    "sl_pct": [60, 90],
    "hedge_satz": 0.2,
    "tage": 5,                      # Tage mit Profit ≥ Schwelle je Payout (mit und ohne Probation: 5)
    "ziel_tol": 100,                # Rest ≤ so viel $ und die harte Bedingung erfüllt → Ziel erreicht (Schlupf am Fill; wie FDP_PUMP_TP_TOL_USD)
    "tp_min": 100,                  # kein Trade mit kleinerem TP (ein Mikro-Trade hätte 60–90 % Daily Loss als SL)
    "klein_abstand": 50,            # kleiner TP mindestens Tagesschwelle + so viel $ (Schlupf am Fill)
}
SK_LIQ_PUFFER = 50                  # $ zwischen SL und Konto-Boden (wie FDP_LIQ_PUFFER)
SK_SL_MIN = 100                     # darunter kein Trade (wie FDP_SL_MIN_USD)


def _zahl(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def sk_cfg(roh):
    """striking_regeln.apex (dict | None) → vollständige Regel: je Schlüssel DB-Wert, sonst Standard."""
    r = dict(SK_STANDARD)
    if isinstance(roh, dict):
        for k, v in roh.items():
            if k in r and v is not None:
                r[k] = v
    return r


def _je_groesse(tab, groesse):
    """{"100000": x} → Wert zur Kontogröße (± 0,5 $) | None."""
    g = _zahl(groesse)
    if not isinstance(tab, dict) or g is None:
        return None
    for k, v in tab.items():
        kz = _zahl(k)
        if kz is not None and abs(kz - g) < 0.5:
            return v
    return None


def sk_ziel(cfg, groesse, payout_nr, probation=True, start=None):
    """Ziel je Zyklus (Profit ab Zyklus-Start) → (Z, cap, bedingung, z_min) | (None, grund). Payout-Nr 1–len(caps) (Nummer des NÄCHSTEN Payouts).
    z_min = harte Payout-Bedingung als Profit ab Zyklus-Start (für die Ziel-Toleranz in sk_tag_tp).
    Trader Probation (Marc, Nachtrag 2 vom 20.11.): Z = max(2 × Cap, nötiger Profit 3.600 / 4.600 ab Zyklus-Start).
    Ohne Probation (Jacob, Dashboard PA-APEX-670805-03): Z = 2 × Cap, aber die Balance muss die Mindest-Payout-Balance erreichen (100k 103.600,
    150k 154.600, absolut) → Z = max(2 × Cap, Mindest-Payout-Balance − Zyklus-Start)."""
    caps = _je_groesse(cfg.get("caps"), groesse)
    nr = _zahl(payout_nr)
    if not isinstance(caps, list) or not caps:
        return None, f"keine Striking-Werte für {int((_zahl(groesse) or 0) / 1000)}k"
    if nr is None or int(nr) != nr or not 1 <= int(nr) <= len(caps):
        return None, f"Payout-Nr. {payout_nr if payout_nr is not None else 'fehlt'} (1–{len(caps)}) → am Konto eintragen"
    cap = _zahl(caps[int(nr) - 1])
    if cap is None:
        return None, f"Cap für Payout {int(nr)} fehlt"
    if probation:
        mp = _zahl(_je_groesse(cfg.get("min_profit"), groesse))
        if mp is None:
            return None, f"nötiger Profit (Probation) für {int((_zahl(groesse) or 0) / 1000)}k fehlt"
        return round(max(2 * cap, mp), 2), cap, f"Probation: Profit ≥ {round(mp)} $", mp
    mpb, s = _zahl(_je_groesse(cfg.get("min_payout_balance"), groesse)), _zahl(start)
    if mpb is None or s is None:
        return None, f"Mindest-Payout-Balance für {int((_zahl(groesse) or 0) / 1000)}k fehlt"
    return round(max(2 * cap, mpb - s), 2), cap, f"Balance ≥ {round(mpb)} $", round(mpb - s, 2)


def sk_min_payout_balance(cfg, groesse):
    """Mindest-Payout-Balance ohne Probation (absolut) | None."""
    return _zahl(_je_groesse(cfg.get("min_payout_balance"), groesse))


def sk_deckel(cfg, z):
    """Deckel je Trade c = deckel_pct % × Z × puffer."""
    return round((_zahl(cfg.get("deckel_pct")) or 50) / 100.0 * z * (_zahl(cfg.get("puffer")) or 0.95), 2)


def sk_tage_ok(tage, schwelle):
    """Anzahl Tage mit Ergebnis ≥ Schwelle ({tag: $})."""
    return sum(1 for v in (tage or {}).values() if _zahl(v) is not None and _zahl(v) >= schwelle - 1e-9)


def sk_pump_anzahl(rest, c):
    return 0 if rest <= 0.005 else int(math.ceil(round(rest / c, 9)))


def sk_klein_anzahl(rest, tage_noetig, c, klein_mitte, max_k=20):
    """Kleinste Zahl kleiner Trades k, mit der k + Pump-Trades(R − k × klein_mitte) ≥ nötige Tage. Kleine Trades nur, solange danach
    noch etwas für einen Pump bleibt (der Rest wird nie überschritten)."""
    for k in range(0, max_k + 1):
        r_k = rest - k * klein_mitte
        if r_k <= 0:
            return max(0, k - 1)
        if k + sk_pump_anzahl(r_k, c) >= tage_noetig:
            return k
    return max_k


def sk_tag_tp(cfg, groesse, z, netto, tage, rnd, z_min=None):
    """TP des heutigen Striking-Trades → dict. aktion 'ziel' (nichts mehr planen, Konto wartet auf Payout) oder 'planen' mit
    art 'klein' | 'pump' | 'rest' (schließt den Rest), tp, rest, deckel, z_eff, tage_ok, tage_noetig, k_klein, n_pump, hinweis.
    tage = {CME-Tag: $} der beendeten Trades im Zyklus (ohne heute). z_min = harte Bedingung als Profit ab Zyklus-Start (Probation: nötiger
    Profit; sonst Mindest-Payout-Balance − Start) — nur darüber zählt ein Rest ≤ ziel_tol als erreicht (Schlupf am Fill, Prüfer 20.11.).
    Ziel-Anhebungen (je mit Hinweis), weil sonst kein Payout möglich wäre:
      Consistency — liegt ein früherer Tag über 50 % von Z, Ziel = 2 × bester Tag;
      Tage — reicht der Rest nicht mehr für die fehlenden Tage mit je einem kleinen Trade (klein_tp unten), Ziel = Netto + fehlende × klein_tp unten."""
    schwelle = _zahl(_je_groesse(cfg.get("tag_schwelle"), groesse)) or 0.0
    soll = int(_zahl(cfg.get("tage")) or 5)
    lo, hi = [float(x) for x in (cfg.get("klein_tp") or [370, 420])[:2]]
    # „knapp über der Tagesschwelle“: mindestens Schwelle + klein_abstand (150k: 350 + 50 → 400–450), sonst fällt ein kleiner Trade mit Schlupf
    # am Fill unter die Schwelle und zählt nicht als Tag (Selbsttest 20.11.: 370 − 60 $ Schlupf < 350)
    lo_min = schwelle + (_zahl(cfg.get("klein_abstand")) or 0.0)
    if lo < lo_min:
        hi, lo = hi + (lo_min - lo), lo_min
    tol, tp_min = (_zahl(cfg.get("ziel_tol")) or 0.0), (_zahl(cfg.get("tp_min")) or 0.0)
    bester = max([_zahl(v) for v in (tage or {}).values() if _zahl(v) is not None] + [0.0])
    pct = (_zahl(cfg.get("deckel_pct")) or 50) / 100.0
    t_ok = sk_tage_ok(tage, schwelle)
    noetig = max(0, soll - t_ok)
    hinweise = []
    z_eff = round(max(z, bester / pct), 2) if pct > 0 else z
    if z_eff > z:
        hinweise.append(f"Consistency: bester Tag {round(bester)} $ > {int(pct * 100)} % von {round(z)} $ → Ziel {round(z_eff)} $")
    # Prüfer 2 (20.11.): fehlen noch Tage, wird IMMER angehoben — sonst „Ziel erreicht“ mit 4/5 Tagen (Payout unmöglich, Konto steht still)
    if noetig and z_eff - netto < noetig * lo - 0.005:
        z_alt, z_eff = z_eff, round(netto + noetig * lo, 2)
        h_tage = f"Tage: noch {noetig} Tage ≥ {round(schwelle)} $ nötig, Rest {round(z_alt - netto)} $ reicht nicht → Ziel {round(z_eff)} $"
        hinweise.append(h_tage)
    c = sk_deckel(cfg, z_eff)
    rest = round(z_eff - netto, 2)
    out = {"z": z, "z_eff": z_eff, "deckel": c, "rest": rest, "tage_ok": t_ok, "tage_soll": soll, "tage_noetig": noetig,
           "schwelle": schwelle, "bester": round(bester, 2), "hinweis": " · ".join(hinweise)}
    erreicht = noetig == 0 and (rest <= 0.005 or (rest <= tol and (z_min is None or netto >= z_min - 0.005)))
    if erreicht:
        return dict(out, aktion="ziel", tp=None, art=None, k_klein=0, n_pump=0)
    k = sk_klein_anzahl(rest, noetig, c, (lo + hi) / 2.0)
    n = sk_pump_anzahl(rest - k * (lo + hi) / 2.0, c) if k else sk_pump_anzahl(rest, c)
    out.update(k_klein=k, n_pump=n)
    if rest <= hi + 0.005 and noetig <= 1:
        return dict(out, aktion="planen", art="rest", tp=round(max(rest, tp_min), 2))   # letzter Trade: der Rest (nie ein Mikro-Trade unter tp_min)
    if k > 0:
        # Platz für die übrigen nötigen Tage lassen (je mindestens ein kleiner Trade), nie einen Mikro-Rest
        oben = min(hi, rest - (max(noetig, 1) - 1) * lo)
        tp = round(rnd.uniform(lo, oben)) if oben > lo else lo
        if rest - tp < max(tp_min, schwelle):
            return dict(out, aktion="planen", art="rest", tp=round(max(rest, tp_min), 2))
        return dict(out, aktion="planen", art="klein", tp=float(tp))
    n = sk_pump_anzahl(rest, c)
    if n <= 1:
        return dict(out, aktion="planen", art="rest", tp=round(max(rest, tp_min), 2))
    mitte = rest / n
    unten = max(rest - c * (n - 1), mitte * 0.92)
    oben = min(c, mitte * 1.08)
    tp = round(rnd.uniform(unten, oben), 2) if oben > unten else round(mitte, 2)
    tp = min(max(tp, round(unten + 0.005, 2)), oben)
    return dict(out, aktion="planen", art="pump", tp=round(tp, 2), n_pump=n)


def sk_sl(cfg, dll, abstand, rnd, liq_puffer=SK_LIQ_PUFFER):
    """SL in $ = Zufall sl_pct (60–90 %) des Daily Loss der Stufe, höchstens Abstand zum Boden − Puffer; ganze $ → (sl | None, grund)."""
    d, ab = _zahl(dll), _zahl(abstand)
    if not d or d <= 0:
        return None, "Daily Loss der Stufe fehlt (liq_regeln Apex)"
    if ab is None or ab <= 0:
        return None, "Konto-Boden unbekannt bzw. Balance nicht darüber"
    p_lo, p_hi = [float(x) for x in (cfg.get("sl_pct") or [60, 90])[:2]]
    sl = rnd.uniform(p_lo, p_hi) / 100.0 * d
    sl = float(int(min(sl, ab - liq_puffer)))
    if sl < SK_SL_MIN:
        return None, f"zu nah am Konto-Boden (Abstand {round(ab)} $)"
    return sl, ""


def sk_hedge_offen(cfg, balance, boden):
    """Hedge-Basis in € = hedge_satz × (Balance − Konto-Boden) → (offen | None, abstand)."""
    b, f = _zahl(balance), _zahl(boden)
    if b is None or f is None or b <= f:
        return None, None
    ab = b - f
    return round((_zahl(cfg.get("hedge_satz")) or 0.2) * ab, 2), round(ab, 2)
