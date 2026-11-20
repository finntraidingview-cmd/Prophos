# ════════════════════════════════════════════════════════════════════════════
# RESPONSIBLE TRADER PROGRAMM (RTP) FÜR TOPSTEP (TS1, Finn 20.11.2026 ~05:15 Dubai: „einfach mal bauen“)
# Spezifikation: .claude/master/berichte/2026-11-20_TS1_topstep_rtp_konstrukt.md, Regelbasis TS0 (help.topstep.com, 20.11.2026):
# im RTP gibt es für neue Express Funded Accounts (XFA) nur den Consistency-Pfad — bester Tag ≤ 40 % des Netto-Profits im Payout-Fenster,
# 3 Handelstage, Daily Loss Limit Pflicht (50K 1.000 / 100K 2.000 / 150K 3.000 $), Max Loss Limit wie jedes XFA (2.000 / 3.000 / 4.500 $).
#
# Reine Rechnung (kein Supabase, kein Flask) — app.py (fdp_planen) liest Konten, Pläne und Regeln und ruft nur diese Funktionen;
# Selbsttest tools/selftest_rtp.py ohne app.py.
#   Ziel Z je Konto gewürfelt 28.000–30.000 $ Profit (XFA startet bei 0 $), fest je Konto (Würfel aus der Konto-ID).
#   Deckel je Trade c = 40 % × Z; Tag 1 genau 40 % von Z; danach TP = min(c, Rest), der letzte schließt den Rest — nach Verlust wird der
#   Rest größer, c bleibt → mehr Tage, Ziel bleibt. SL Zufall 2.500–3.000 $ (150K, auf das DLL der Größe skaliert, nie über DLL − Puffer),
#   NQ 2–3. Finn: „nicht so strikt, grob bei 40 % landen“ — nach Z kommen ohnehin Winning Days, die den Anteil drücken.
# ════════════════════════════════════════════════════════════════════════════
import hashlib
import math

RTP_STANDARD = {
    "ziel": [28000, 30000],          # Profit-Ziel Z je Konto (gewürfelt, ganze 100 $)
    "deckel_pct": 40,                # kein Trade mit mehr Profit als 40 % von Z
    "tag1_pct": 40,                  # erster Tag genau so viel % von Z (MLL-Lock, kein späterer Riesentag)
    "sl": [2500, 3000],              # SL je Trade (150K-Werte; andere Größen anteilig zum DLL)
    "kontrakte": [2, 3],             # NQ je Trade (Zufall, ganzzahlig)
    "symbol": "NQ",
    "dll": {"50000": 1000, "100000": 2000, "150000": 3000},    # Daily Loss Limit im RTP (Pflicht)
    "mll": {"50000": 2000, "100000": 3000, "150000": 4500},    # Max Loss Limit XFA, falls am Konto kein Max Drawdown steht
    "dll_puffer": 100,               # $ zwischen SL und DLL (Schlupf am Fill, wie FDP_TAGES_PUFFER)
    "liq_puffer": 50,                # $ zwischen SL und Liquidation (wie FDP_LIQ_PUFFER)
    "sl_min": 100,                   # darunter kein Trade
    "ziel_tol": 300,                 # Rest ≤ so viel $ → Ziel erreicht (Schlupf + Gebühren am Fill: bei 3 NQ sind 2 Punkte schon 120 $; Prüfer 20.11.)
    "tp_min": 100,                   # kein Trade mit kleinerem TP
}
RTP_SL_BEZUG = 3000.0                # die SL-Spanne der Einstellung gilt für dieses DLL (150K)


def _zahl(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def rtp_cfg(roh):
    """rtp_regeln.topstep (dict | None) → vollständige Regel: je Schlüssel DB-Wert, sonst Standard."""
    r = dict(RTP_STANDARD)
    if isinstance(roh, dict):
        for k, v in roh.items():
            if k in r and v is not None:
                r[k] = v
    return r


def rtp_je_groesse(tab, groesse):
    g = _zahl(groesse)
    if not isinstance(tab, dict) or g is None:
        return None
    for k, v in tab.items():
        kz = _zahl(k)
        if kz is not None and abs(kz - g) < 0.5:
            return _zahl(v)
    return None


def rtp_ziel(cfg, schluessel):
    """Ziel Z (Profit) je Konto, fest gewürfelt aus schluessel (Konto-ID) in der Spanne cfg.ziel, auf ganze 100 $."""
    lo, hi = [float(x) for x in (cfg.get("ziel") or [28000, 30000])[:2]]
    if hi < lo:
        lo, hi = hi, lo
    u = int(hashlib.sha256(f"rtp|{schluessel}".encode("utf-8")).hexdigest()[:12], 16) / float(16 ** 12)
    return float(round((lo + u * (hi - lo)) / 100.0) * 100)


def rtp_tag_tp(cfg, z, netto, tage):
    """TP des heutigen RTP-Trades → dict: aktion 'ziel' (Z erreicht → Winning Days) oder 'planen' mit art 'tag1' | 'pump' | 'rest', tp, rest, deckel,
    tage_n, bester, anteil (bester Tag ÷ Z). tage = {CME-Tag: $} der beendeten Trades (ohne heute); netto = Profit seit XFA-Start (Balance 0-basiert)."""
    c = round((_zahl(cfg.get("deckel_pct")) or 40) / 100.0 * z, 2)
    rest = round(z - netto, 2)
    werte = [v for v in (_zahl(x) for x in (tage or {}).values()) if v is not None]
    bester = max(werte + [0.0])
    out = {"z": z, "deckel": c, "rest": rest, "tage_n": len(werte), "bester": round(bester, 2), "anteil": round(bester / z, 4) if z else None,
           "bester_pct": round(100.0 * bester / netto, 1) if netto > 0 else None}   # % vom Netto (Topstep-Consistency), S3-Statuszeile
    if rest <= (_zahl(cfg.get("ziel_tol")) or 0.0) + 1e-9:
        return dict(out, aktion="ziel", art=None, tp=None)
    tp_min = _zahl(cfg.get("tp_min")) or 0.0
    if not werte:
        t1 = round((_zahl(cfg.get("tag1_pct")) or 40) / 100.0 * z, 2)
        if t1 < rest - 0.005:
            return dict(out, aktion="planen", art="tag1", tp=t1)
    if rest <= c + 0.005:
        return dict(out, aktion="planen", art="rest", tp=round(max(rest, tp_min), 2))
    return dict(out, aktion="planen", art="pump", tp=c)


def rtp_sl(cfg, dll, abstand_liq, tag_verlust, rnd):
    """SL in $ = Zufall cfg.sl (150K-Spanne, anteilig zum DLL der Größe), höchstens DLL − heutiger Verlust − dll_puffer und Abstand zur Liquidation −
    liq_puffer; ganze $ → (sl | None, grund)."""
    d, ab = _zahl(dll), _zahl(abstand_liq)
    if not d or d <= 0:
        return None, "Daily Loss Limit der Größe fehlt (rtp_regeln.topstep.dll)"
    if ab is None or ab <= 0:
        return None, "Liquidation unbekannt bzw. Balance nicht darüber"
    lo, hi = [float(x) for x in (cfg.get("sl") or [2500, 3000])[:2]]
    f = d / RTP_SL_BEZUG
    sl = rnd.uniform(lo * f, hi * f)
    deckel_dll = d - float(tag_verlust or 0) - (_zahl(cfg.get("dll_puffer")) or 0.0)
    deckel_liq = ab - (_zahl(cfg.get("liq_puffer")) or 0.0)
    sl = float(int(min(sl, deckel_dll, deckel_liq)))
    if sl < (_zahl(cfg.get("sl_min")) or 0.0):
        grund = (f"Daily Loss Limit heute fast erreicht (−{round(float(tag_verlust or 0))} $ von {round(d)} $)" if deckel_dll <= deckel_liq
                 else f"zu nah an der Liquidation (Abstand {round(ab)} $)")
        return None, grund
    return sl, ""


def rtp_kontrakte(cfg, rnd):
    lo, hi = [int(_zahl(x) or 1) for x in (cfg.get("kontrakte") or [2, 3])[:2]]
    if hi < lo:
        lo, hi = hi, lo
    return max(1, rnd.randint(lo, hi))
