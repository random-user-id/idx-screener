"""
screener.py
Sistem Trading Merah-Hijau — IDX Screener
Rules: 7 rules dari dokumen Stockbit
"""

import pandas as pd
import numpy as np
from typing import Optional


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def hhv(series: pd.Series, period: int) -> pd.Series:
    """Highest High Value dalam N periode"""
    return series.rolling(window=period).max()


def llv(series: pd.Series, period: int) -> pd.Series:
    """Lowest Low Value dalam N periode"""
    return series.rolling(window=period).min()


def apply_rules(df_daily: Optional[pd.DataFrame], df_weekly: Optional[pd.DataFrame]) -> dict:
    """
    Terapkan 7 rules Sistem Merah-Hijau.

    Parameters:
        df_daily  : DataFrame OHLCV harian, index = datetime
        df_weekly : DataFrame OHLCV mingguan, index = datetime

    Returns:
        dict hasil screening per rule + sinyal akhir
    """
    result = {
        "rule1": False,
        "rule2": False,
        "rule3": False,
        "rule4": False,
        "rule5": False,
        "rule6": False,
        "rule7": False,
        "signal": "MERAH",
        "details": {}
    }

    if df_daily is None or len(df_daily) < 55:
        result["details"]["error"] = "Data harian tidak cukup (min 55 hari)"
        return result

    d = df_daily.copy()
    close = d["Close"]
    high  = d["High"]
    low   = d["Low"]
    open_ = d["Open"]
    vol   = d["Volume"]

    # ── RULE 1: Trend Harian — Struktur Golden ──────────────────────────
    ma20 = sma(close, 20)
    ma50 = sma(close, 50)
    r1 = (close.iloc[-1] > ma20.iloc[-1]) and (ma20.iloc[-1] > ma50.iloc[-1])
    result["rule1"] = bool(r1)
    result["details"]["ma20"]  = round(float(ma20.iloc[-1]), 2)
    result["details"]["ma50"]  = round(float(ma50.iloc[-1]), 2)
    result["details"]["close"] = round(float(close.iloc[-1]), 2)

    # ── RULE 2: Pullback dari High 20 Hari ──────────────────────────────
    hhv20 = hhv(high, 20)
    r2 = close.iloc[-1] <= hhv20.iloc[-1] * 0.97
    result["rule2"] = bool(r2)
    result["details"]["hhv20"]        = round(float(hhv20.iloc[-1]), 2)
    result["details"]["hhv20_97pct"]  = round(float(hhv20.iloc[-1] * 0.97), 2)

    # ── RULE 3: Candle Hijau (Proxy Reversal) ───────────────────────────
    r3 = close.iloc[-1] > open_.iloc[-1]
    result["rule3"] = bool(r3)
    result["details"]["open_last"]  = round(float(open_.iloc[-1]), 2)
    result["details"]["close_last"] = round(float(close.iloc[-1]), 2)

    # ── RULE 4: Volume Konfirmasi — WAJIB ───────────────────────────────
    vol_ma20 = sma(vol, 20)
    r4 = vol.iloc[-1] > vol_ma20.iloc[-1] * 1.5
    result["rule4"] = bool(r4)
    result["details"]["volume"]       = int(vol.iloc[-1])
    result["details"]["volume_ma20"]  = int(vol_ma20.iloc[-1])
    result["details"]["volume_ratio"] = round(float(vol.iloc[-1] / vol_ma20.iloc[-1]), 2)

    # ── RULE 5: Dekat Support (Proxy Low 20 Hari) ───────────────────────
    llv20 = llv(low, 20)
    r5 = close.iloc[-1] <= llv20.iloc[-1] * 1.03
    result["rule5"] = bool(r5)
    result["details"]["llv20"]        = round(float(llv20.iloc[-1]), 2)
    result["details"]["llv20_103pct"] = round(float(llv20.iloc[-1] * 1.03), 2)

    # ── RULE 6: Proxy Higher Low (Struktur HH-HL) ───────────────────────
    llv5  = llv(low, 5)
    r6 = llv5.iloc[-1] > llv20.iloc[-1]
    result["rule6"] = bool(r6)
    result["details"]["llv5"]  = round(float(llv5.iloc[-1]), 2)

    # ── RULE 7: Trend Mingguan ───────────────────────────────────────────
    r7 = False
    if df_weekly is not None and len(df_weekly) >= 50:
        w_close = df_weekly["Close"]
        w_ma50  = sma(w_close, 50)
        r7 = bool(w_close.iloc[-1] > w_ma50.iloc[-1])
        result["details"]["weekly_close"] = round(float(w_close.iloc[-1]), 2)
        result["details"]["weekly_ma50"]  = round(float(w_ma50.iloc[-1]), 2)
    result["rule7"] = r7

    # ── SINYAL AKHIR ─────────────────────────────────────────────────────
    rules_passed = sum([r1, r2, r3, r4, r5, r6, r7])
    result["rules_passed"] = int(rules_passed)

    if r1 and r4 and rules_passed >= 5:
        result["signal"] = "HIJAU"
    elif r1 and r4 and rules_passed == 4:
        result["signal"] = "KUNING"
    else:
        result["signal"] = "MERAH"

    # ── SANITIZE: konversi semua numpy types ke Python native ────────────
    result = sanitize(result)
    return result


def sanitize(obj):
    """
    Rekursif konversi semua numpy/pandas types ke Python native
    supaya bisa di-serialize FastAPI ke JSON.
    """
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize(i) for i in obj]
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    else:
        return obj


def check_ihsg_mode(df_ihsg_weekly: Optional[pd.DataFrame]) -> dict:
    """
    Cek kondisi IHSG untuk filter mode trading.
    Returns: mode = UPTREND / SIDEWAYS / DOWNTREND
    """
    if df_ihsg_weekly is None or len(df_ihsg_weekly) < 200:
        return {"mode": "UNKNOWN", "note": "Data IHSG tidak cukup"}

    w = df_ihsg_weekly["Close"]
    ma50w  = sma(w, 50)
    ma200w = sma(w, 200)

    close_last  = w.iloc[-1]
    ma50_last   = ma50w.iloc[-1]
    ma200_last  = ma200w.iloc[-1]

    if close_last > ma50_last and ma50_last > ma200_last:
        mode = "UPTREND"
        action = "Trading penuh — semua setup valid"
    elif close_last < ma50_last and ma50_last < ma200_last:
        mode = "DOWNTREND"
        action = "STOP trading — cash is position"
    else:
        mode = "SIDEWAYS"
        action = "Selektif — hanya setup paling kuat, position size -50%"

    return sanitize({
        "mode": mode,
        "action": action,
        "ihsg_close": round(float(close_last), 2),
        "ma50w": round(float(ma50_last), 2),
        "ma200w": round(float(ma200_last), 2)
    })
