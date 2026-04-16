"""
data.py
Fetch data saham IDX via yfinance
Support: batch fetch 900 saham, parallel threading, caching
"""

import yfinance as yf
import pandas as pd
import json
import os
import time
import logging
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List

logger = logging.getLogger(__name__)

# ── DAFTAR SAHAM IDX ────────────────────────────────────────────────────────

# Batch 1: LQ45 + IDX30 (prioritas notifikasi)
BATCH_1 = [
    "BBCA", "BBRI", "BMRI", "TLKM", "ASII", "UNVR", "HMSP", "ICBP",
    "KLBF", "PGAS", "JSMR", "SMGR", "INDF", "PTBA", "ADRO", "ANTM",
    "INCO", "VALE", "TINS", "MEDC", "EXCL", "ISAT", "MNCN", "EMTK",
    "GOTO", "BUKA", "BRIS", "ARTO", "BBNI", "BJTM", "BDMN", "MEGA",
    "NISP", "PNBN", "BJBR", "AGRO", "BNGA", "BNLI", "BTPS", "NOBU",
    "AALI", "LSIP", "SSMS", "TBLA", "DSNG", "PALM", "SIMP", "ANJT"
]

# Batch 2: IDX80 + MidCap
BATCH_2 = [
    "ACES", "ARNA", "AUTO", "BALI", "BSDE", "CPIN", "CTRA", "DMAS",
    "DPNS", "ELSA", "ERAA", "ESSA", "FAST", "FILM", "GGRM", "GMFI",
    "HRUM", "INTP", "ITMG", "JPFA", "KAEF", "KIJA", "KPIG", "LINK",
    "LPPF", "MAPI", "MBMA", "MDKA", "MIKA", "MLPT", "MPMX", "MYOR",
    "NCKL", "NRCA", "PANI", "PGEO", "PNLF", "POWR", "PWON", "RAJA",
    "RALS", "SCMA", "SIDO", "SILO", "SMDR", "SMSM", "SOHO", "SRIL",
    "TELE", "TBIG", "TOWR", "TPIA", "TSPC", "ULTJ", "UNTR", "WEGE",
    "WIKA", "WSKT", "WTON", "YPAS"
]

# Batch 3: Sisanya (screened tapi tidak notif)
# Akan di-load dari file eksternal jika tersedia
BATCH_3_FILE = "data/idx_all_tickers.json"


def get_all_tickers() -> List[str]:
    """Return semua ticker IDX yang akan di-screen."""
    tickers = BATCH_1 + BATCH_2

    # Load batch 3 jika file tersedia
    if os.path.exists(BATCH_3_FILE):
        try:
            with open(BATCH_3_FILE) as f:
                batch3 = json.load(f)
            tickers += [t for t in batch3 if t not in tickers]
            logger.info(f"Loaded {len(batch3)} tickers dari batch 3")
        except Exception as e:
            logger.warning(f"Gagal load batch 3: {e}")

    return tickers


def to_yf_symbol(kode: str) -> str:
    """Konversi kode saham IDX ke format yfinance (BBCA → BBCA.JK)"""
    kode = kode.upper().strip()
    if not kode.endswith(".JK"):
        return f"{kode}.JK"
    return kode


def fetch_single(kode: str, period_days: int = 120) -> dict:
    """
    Fetch data harian + mingguan untuk 1 saham.

    Returns:
        {"kode": str, "daily": DataFrame, "weekly": DataFrame, "error": str|None}
    """
    symbol = to_yf_symbol(kode)
    end_date   = datetime.today()
    start_date = end_date - timedelta(days=period_days)

    try:
        ticker = yf.Ticker(symbol)

        df_daily = ticker.history(
            start=start_date.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1d"
        )

        df_weekly = ticker.history(
            start=(end_date - timedelta(days=365*4)).strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1wk"
        )

        if df_daily.empty:
            return {"kode": kode, "daily": None, "weekly": None,
                    "error": "Data kosong"}

        # Normalize: ambil kolom OHLCV saja + strip timezone dari index
        cols = ["Open", "High", "Low", "Close", "Volume"]
        df_daily  = df_daily[cols].copy()
        df_daily.index = df_daily.index.tz_localize(None) \
                         if df_daily.index.tzinfo is None \
                         else df_daily.index.tz_convert(None)

        if df_weekly is not None and not df_weekly.empty:
            df_weekly = df_weekly[cols].copy()
            df_weekly.index = df_weekly.index.tz_localize(None) \
                              if df_weekly.index.tzinfo is None \
                              else df_weekly.index.tz_convert(None)
        else:
            df_weekly = None

        return {"kode": kode, "daily": df_daily, "weekly": df_weekly,
                "error": None}

    except Exception as e:
        return {"kode": kode, "daily": None, "weekly": None,
                "error": str(e)}


def fetch_batch(tickers: List[str], max_workers: int = 20,
                delay: float = 0.1) -> List[dict]:
    """
    Fetch banyak saham secara paralel.

    Parameters:
        tickers     : list kode saham
        max_workers : jumlah thread paralel
        delay       : jeda antar request (detik) untuk hindari rate limit

    Returns:
        list of dict hasil fetch
    """
    results = []
    total   = len(tickers)
    logger.info(f"Mulai fetch {total} saham dengan {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_single, k): k for k in tickers}

        done = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            done += 1

            if done % 50 == 0:
                logger.info(f"Progress: {done}/{total} saham selesai")

            time.sleep(delay)

    logger.info(f"Fetch selesai: {total} saham diproses")
    return results


def fetch_ihsg(period_weeks: int = 210) -> Optional[pd.DataFrame]:
    """Fetch data IHSG mingguan untuk filter mode trading."""
    try:
        end   = datetime.today()
        start = end - timedelta(weeks=period_weeks)
        ticker = yf.Ticker("^JKSE")
        df = ticker.history(
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1wk"
        )
        if df.empty:
            return None
        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.index = df.index.tz_localize(None) \
                   if df.index.tzinfo is None \
                   else df.index.tz_convert(None)
        return df
    except Exception as e:
        logger.error(f"Gagal fetch IHSG: {e}")
        return None


# ── CACHE ────────────────────────────────────────────────────────────────────

CACHE_DIR  = "data/cache"
CACHE_FILE = os.path.join(CACHE_DIR, "screen_result.json")


def save_cache(data: dict):
    """Simpan hasil screener ke JSON cache."""
    import pytz
    wib = pytz.timezone("Asia/Jakarta")
    os.makedirs(CACHE_DIR, exist_ok=True)
    data["cached_at"] = datetime.now(wib).strftime("%Y-%m-%d %H:%M:%S WIB")
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Cache disimpan: {CACHE_FILE}")


def load_cache() -> Optional[dict]:
    """Load cache hasil screener."""
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE) as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Gagal load cache: {e}")
        return None


def is_cache_fresh(max_age_hours: int = 20) -> bool:
    """Cek apakah cache masih fresh (belum kadaluarsa)."""
    cache = load_cache()
    if not cache or "cached_at" not in cache:
        return False
    cached_at = datetime.fromisoformat(cache["cached_at"])
    age = datetime.now() - cached_at
    return age.total_seconds() < max_age_hours * 3600
