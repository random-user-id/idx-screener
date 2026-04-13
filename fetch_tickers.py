"""
fetch_tickers.py  (v2 — Live dari IDX API)
Ambil daftar semua emiten aktif langsung dari API resmi IDX,
validasi via yfinance, simpan ke data/idx_all_tickers.json

Cara pakai:
    python fetch_tickers.py

Estimasi waktu: 10-15 menit
"""

import requests
import yfinance as yf
import json
import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# ── BATCH 1+2 yang sudah ada di data.py (skip duplikat) ──────────────────
EXISTING = {
    "BBCA","BBRI","BMRI","TLKM","ASII","UNVR","HMSP","ICBP",
    "KLBF","PGAS","JSMR","SMGR","INDF","PTBA","ADRO","ANTM",
    "INCO","VALE","TINS","MEDC","EXCL","ISAT","MNCN","EMTK",
    "GOTO","BUKA","BRIS","ARTO","BBNI","BJTM","BDMN","MEGA",
    "NISP","PNBN","BJBR","AGRO","BNGA","BNLI","BTPS","NOBU",
    "AALI","LSIP","SSMS","TBLA","DSNG","PALM","SIMP","ANJT",
    "ACES","ARNA","AUTO","BALI","BSDE","CPIN","CTRA","DMAS",
    "DPNS","ELSA","ERAA","ESSA","FAST","FILM","GGRM","GMFI",
    "HRUM","INTP","ITMG","JPFA","KAEF","KIJA","KPIG","LINK",
    "LPPF","MAPI","MBMA","MDKA","MIKA","MLPT","MPMX","MYOR",
    "NCKL","NRCA","PANI","PGEO","PNLF","POWR","PWON","RAJA",
    "RALS","SCMA","SIDO","SILO","SMDR","SMSM","SOHO","SRIL",
    "TELE","TBIG","TOWR","TPIA","TSPC","ULTJ","UNTR","WEGE",
    "WIKA","WSKT","WTON","YPAS"
}


def fetch_from_idx_api() -> list:
    """Ambil dari API resmi idx.co.id"""
    endpoints = [
        {
            "url": "https://www.idx.co.id/primary/StockData/GetSecurities",
            "params": {"start": 0, "length": 9999, "searchData": "",
                       "exchange": "IDX", "type": "EQUITY"},
            "key_ticker": "KodeEmiten"
        },
        {
            "url": "https://www.idx.co.id/umum/ListedCompanies/GetStockList",
            "params": {"start": 0, "length": 9999, "searchData": "",
                       "columnOrder": "Kode", "orderDir": "ASC"},
            "key_ticker": "Kode"
        }
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 Chrome/120.0",
        "Referer":    "https://www.idx.co.id/",
        "Accept":     "application/json, text/plain, */*"
    }

    for ep in endpoints:
        try:
            logger.info(f"Mencoba: {ep['url']}")
            resp = requests.get(
                ep["url"], params=ep["params"],
                headers=headers, timeout=20
            )
            if resp.status_code == 200:
                data = resp.json()
                key  = ep["key_ticker"]
                if "data" in data and data["data"]:
                    tickers = [
                        str(item.get(key, "")).strip().upper()
                        for item in data["data"]
                        if item.get(key)
                    ]
                    tickers = [t for t in tickers if 2 <= len(t) <= 5]
                    if tickers:
                        logger.info(f"Berhasil: {len(tickers)} emiten")
                        return tickers
        except Exception as e:
            logger.warning(f"Gagal: {e}")
            continue

    return []


def fetch_from_stockbit_api() -> list:
    """Fallback: Stockbit public screener API"""
    try:
        logger.info("Mencoba Stockbit API...")
        url = "https://api.stockbit.com/v2.4/screener/stocks"
        params = {"limit": 9999, "offset": 0, "sort": "symbol", "order": "asc"}
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data:
                tickers = [
                    item.get("symbol", "").strip().upper()
                    for item in data["data"]
                    if item.get("symbol")
                ]
                tickers = [t for t in tickers if 2 <= len(t) <= 5]
                logger.info(f"Stockbit API: {len(tickers)} emiten")
                return tickers
    except Exception as e:
        logger.warning(f"Stockbit API gagal: {e}")

    return []


def get_known_batch3() -> list:
    """Fallback terakhir: daftar manual yang sudah dikurasi"""
    return [
        "ABBA","ABDA","ABMM","ADES","ADMF","ADMG","AGII","AHAP",
        "AIMS","AISA","AKKU","AKPI","AKRA","ALKA","ALMI","ALTO",
        "AMAG","AMFG","AMRT","APEX","APII","APLN","ASSA","ASRI",
        "ATAP","ATBR","ATPK","BABP","BACA","BAJA","BANK","BAPA",
        "BBHI","BBKP","BBMD","BBNP","BCAS","BCIC","BCIP","BDKR",
        "BEKS","BELL","BEST","BGTG","BIKA","BINA","BIPI","BIPP",
        "BKJT","BKSL","BLTZ","BMHS","BMTR","BOGA","BOSS","BPFI",
        "BPII","BPTR","BRAM","BRMS","BRPT","BSIM","BSWD","BSSR",
        "BTEK","BTON","BTPN","BUKK","BULL","BUMI","BUVA","BWPT",
        "BYAN","CAKK","CASS","CEKA","CENT","CFIN","CINT","CITY",
        "CLAY","CLPI","CLEO","CMNP","CMNT","CMRY","COAL","COCO",
        "COWL","CPGT","CPRO","CSAP","CSRA","CTBN","CTTH","DADA",
        "DAMO","DAYA","DCII","DEFI","DEWA","DGIK","DIGI","DILD",
        "DIVA","DKFT","DLTA","DNAR","DNET","DOID","DRMA","DSFI",
        "DSSA","DUCK","DUTI","DVLA","DYAN","EDGE","EKAD","EMDE",
        "ENRG","ETWA","FASW","FIRE","FMII","FOOD","FORZ","FORU",
        "FPNI","GAMA","GDST","GEMS","GHON","GIAA","GLVA","GMTD",
        "GOOD","GPRA","GTBO","GULA","GWSA","GZCO","HADE","HDTX",
        "HERO","HITS","HOKI","HRTA","IATA","IGAR","IIKP","IMPC",
        "INAI","INCF","INDO","INDY","INPC","INRU","IPAC","IPOL",
        "IPTV","ISSP","JAWA","JGLE","JKSW","JPRS","JRPT","KARW",
        "KBLI","KBLM","KBLV","KDSI","KEJU","KIAS","KINO","KKGI",
        "KOPI","KPAS","KRAS","LMAS","LMSH","LION","LPBN","LPCK",
        "LPKR","LPMH","LRNA","MAGP","MARK","MAYA","MBAP","MCOL",
        "MCOR","MDKI","MDLN","MERK","MFIN","MFMI","MGRO","MIDI",
        "MKPI","MLBI","MLIA","MMLP","MOLI","MORE","MPPA","MPRO",
        "MRAT","MTDL","MTLA","MYOH","MYRX","NELY","NFCX","NIKL",
        "NIRO","OMRE","PADI","PAMG","PBID","PCAR","PDES","PGUN",
        "PICO","PJAA","PKPK","PLAN","PLIN","PNBS","PNGO","PNIN",
        "POLY","PORT","PPGL","PPRE","PPRO","PSAB","PSGO","PTPP",
        "PTRO","PTSP","PUDP","PURE","RANC","RBMS","RDTX","RELY",
        "RICY","RMBA","RODA","ROTI","RUIS","SAFE","SAIP","SAPX",
        "SDPC","SDRA","SHIP","SIAP","SIMA","SKYB","SMBR","SMCB",
        "SMMT","SMRA","SMRU","SOCI","SONS","SPMA","SQMI","SRAJ",
        "SRSN","SRTG","SSIA","STTP","SULI","SUPR","SURE","SWAT",
        "TAXI","TALF","TARA","TCID","TCPI","TFAS","TGKA","TGRA",
        "TIGA","TIRT","TKIM","TMAN","TMAS","TMPO","TNCA","TNKM",
        "TOBA","TOPS","TPAS","TPMA","TRIM","TRIO","TRIL","TRST",
        "TRUK","UNIC","UNIT","UNSP","URBN","WEHA","WICO","WIFI",
        "WIIM","WINS","WLRM","WMUU","WSBP","YELE","YULO","ZBRA",
        "ZINC","BIRD","DCII","HEAL","MTEL","NCKL","AVIA","CBDK",
        "CUAN","DAYS","DBO","FIRM","GJTL","HELI","INPS","IPPE",
        "JAST","KBAG","KEJU","KMDS","KRYA","LPLI","LUCY","MABA",
        "MAHA","MAPA","MARI","MASA","MBIN","MDIA","MEDS","MHKI",
        "MKNT","MLEN","MOLI","MRAT","MSIE","MSIN","MSKY","MTPS",
        "MUTU","MYOR","NATO","NAYZ","NCKL","NETV","NFCX","NIPS",
        "NRCA","NSSS","NUSA","NWPI","OBMD","OCAP","OKAS","OLIV",
        "OMED","OPMS","PACK","PADI","PALM","PAMG","PCAR","PDES",
        "PEVE","PGEO","PICO","PJAA","PKPK","PLAN","PMJS","PMMP",
        "PNBS","PNGO","PNIN","POLI","POLL","PORT","PPGL","PPRE",
        "PPRO","PRIM","PSAB","PSGO","PTBA","PTMP","PTPP","PTRO",
        "PTSP","PUBM","PUDP","PURE","PURI","RAAM","RANC","RBMS",
        "RDTX","REAL","RELI","RELY","RGAS","RICY","RIMO","RISE",
        "RMBA","RODA","ROTI","RUIS","SAFE","SAIP","SAMA","SAMF",
        "SAPX","SDMU","SDPC","SDRA","SEMA","SGRO","SHIP","SIAP",
        "SICO","SIMA","SINI","SIPD","SLIS","SMAR","SMBR","SMCB",
        "SMIL","SMKL","SMMT","SMRA","SMRU","SOCI","SOFA","SONS",
        "SPMA","SQMI","SRAJ","SRSN","SRTG","SSIA","SSMS","STTP",
        "SULI","SUPR","SURE","SWAT","TALF","TARA","TAXI","TBMS",
        "TCID","TCPI","TFAS","TGKA","TGRA","TIGA","TIRT","TKIM",
        "TMAS","TMPO","TNCA","TNKM","TOBA","TOPS","TPAS","TPMA",
        "TRIL","TRIO","TRIM","TRST","TRUK","UNIC","UNIT","UNSP",
        "URBN","VICI","VINS","VKTR","VNET","WGSH","WEHA","WICO",
        "WIFI","WIIM","WINS","WLRM","WMUU","WOOD","WSBP","YELO",
        "YULE","ZBRA","ZINC","ZONE","ZYRX",
    ]


def validate_ticker(kode: str) -> tuple:
    """Cek apakah ticker masih aktif di yfinance (min 30 hari data)."""
    try:
        df = yf.Ticker(f"{kode}.JK").history(period="3mo", interval="1d")
        return (kode, len(df) >= 30)
    except Exception:
        return (kode, False)


def main():
    print("=" * 55)
    print("IDX Ticker Fetcher v2 — Live dari IDX API")
    print("=" * 55)

    # ── Step 1: Coba ambil dari IDX API ──────────────────────
    raw_tickers = fetch_from_idx_api()

    if not raw_tickers:
        raw_tickers = fetch_from_stockbit_api()

    if not raw_tickers:
        logger.warning("Semua API gagal — menggunakan known list")
        raw_tickers = get_known_batch3()

    # Deduplicate & filter existing
    candidates = sorted({
        t for t in raw_tickers
        if t and 2 <= len(t) <= 5
        and t not in EXISTING
    })

    print(f"\nKandidat Batch 3  : {len(candidates)}")
    print(f"Sudah ada (Bat1+2): {len(EXISTING)}")
    print(f"Mulai validasi yfinance ({len(candidates)} ticker)...")
    est = max(5, len(candidates) // 50)
    print(f"Estimasi waktu    : ~{est} menit\n")

    # ── Step 2: Validasi via yfinance ────────────────────────
    valid, invalid = [], []

    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(validate_ticker, k): k for k in candidates}
        done = 0
        for future in as_completed(futures):
            kode, ok = future.result()
            done += 1
            (valid if ok else invalid).append(kode)

            if done % 30 == 0 or done == len(candidates):
                pct = round(done / len(candidates) * 100)
                print(f"  [{pct:3d}%] {done}/{len(candidates)} | "
                      f"✓ {len(valid)} | ✗ {len(invalid)}")
            time.sleep(0.05)

    valid.sort()

    # ── Step 3: Simpan JSON ──────────────────────────────────
    os.makedirs("data", exist_ok=True)
    path = "data/idx_all_tickers.json"
    with open(path, "w") as f:
        json.dump(valid, f, indent=2)

    print(f"\n{'=' * 55}")
    print(f"SELESAI!")
    print(f"Batch 3 valid : {len(valid)} ticker")
    print(f"Invalid/delist: {len(invalid)} ticker")
    print(f"Total screened: {len(valid) + len(EXISTING)} saham")
    print(f"Disimpan ke   : {path}")
    print(f"{'=' * 55}")
    print("\nNext: POST /screen/run untuk jalankan screener penuh")


if __name__ == "__main__":
    main()
