"""
main.py
FastAPI Backend — IDX Screener Sistem Merah-Hijau
"""

import logging
import os
import pytz
from datetime import datetime
from contextlib import asynccontextmanager

# Force timezone ke WIB (UTC+7)
os.environ["TZ"] = "Asia/Jakarta"
WIB = pytz.timezone("Asia/Jakarta")

def now_wib():
    """Return datetime sekarang dalam WIB."""
    return datetime.now(WIB)

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from data import (
    get_all_tickers, fetch_batch, fetch_ihsg,
    save_cache, load_cache, is_cache_fresh,
    BATCH_1, BATCH_2
)
from screener import apply_rules, check_ihsg_mode
from notif import send_notification

# ── SETUP ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Jakarta")


# ── SCREENER RUNNER ──────────────────────────────────────────────────────────

async def run_full_screener():
    """
    Job utama: fetch semua saham → screen → cache → kirim notif.
    Dijadwalkan otomatis jam 16.30 WIB setiap hari kerja.
    """
    logger.info("=== SCREENER DIMULAI ===")
    start_time = now_wib()

    # 1. Cek kondisi IHSG
    logger.info("Fetch IHSG...")
    ihsg_weekly = fetch_ihsg()
    ihsg_status = check_ihsg_mode(ihsg_weekly)
    logger.info(f"IHSG Mode: {ihsg_status['mode']}")

    # 2. Fetch semua saham
    tickers = get_all_tickers()
    logger.info(f"Total ticker: {len(tickers)}")

    raw_data = fetch_batch(tickers, max_workers=20)

    # 3. Terapkan rules
    results_hijau  = []
    results_kuning = []
    results_merah  = []
    errors         = []

    priority_tickers = set(BATCH_1 + BATCH_2)

    for item in raw_data:
        kode = item["kode"]
        if item["error"]:
            errors.append({"kode": kode, "error": item["error"]})
            continue

        screen = apply_rules(item["daily"], item["weekly"])
        screen["kode"]     = kode
        screen["priority"] = kode in priority_tickers

        if screen["signal"] == "HIJAU":
            results_hijau.append(screen)
        elif screen["signal"] == "KUNING":
            results_kuning.append(screen)
        else:
            results_merah.append(screen)

    # 4. Simpan ke cache
    cache_data = {
        "ihsg":          ihsg_status,
        "hijau":         results_hijau,
        "kuning":        results_kuning,
        "merah":         results_merah,
        "errors":        errors,
        "total_screened": len(raw_data),
        "duration_sec":  round((now_wib() - start_time).total_seconds(), 1)
    }
    save_cache(cache_data)

    # 5. Kirim notifikasi (hanya sinyal HIJAU dari Batch 1+2)
    priority_hijau = [s for s in results_hijau if s["priority"]]
    if priority_hijau and ihsg_status["mode"] != "DOWNTREND":
        await send_notification(priority_hijau, ihsg_status)

    logger.info(
        f"=== SCREENER SELESAI === "
        f"Hijau: {len(results_hijau)} | "
        f"Kuning: {len(results_kuning)} | "
        f"Merah: {len(results_merah)} | "
        f"Error: {len(errors)} | "
        f"Durasi: {cache_data['duration_sec']}s"
    )


# ── LIFESPAN ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Jadwalkan screener jam 16.30 WIB, Senin–Jumat
    scheduler.add_job(
        run_full_screener,
        trigger="cron",
        day_of_week="mon-fri",
        hour=16,
        minute=30,
        timezone=WIB,
        id="daily_screener"
    )
    scheduler.start()
    logger.info("Scheduler aktif — screener berjalan tiap hari kerja 16.30 WIB")
    yield
    scheduler.shutdown()


# ── APP ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="IDX Screener — Sistem Merah-Hijau",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# ── MODELS ───────────────────────────────────────────────────────────────────

class ParamsUpdate(BaseModel):
    rsi_threshold:     float = 50.0
    ma_period:         int   = 20
    min_volume_ratio:  float = 1.5
    pullback_pct:      float = 0.97
    support_pct:       float = 1.03


# ── ENDPOINTS ────────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    """Serve frontend HTML."""
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "IDX Screener API", "docs": "/docs"}


@app.get("/health")
async def health():
    """Cek status server dan cache."""
    cache = load_cache()
    return {
        "status":       "ok",
        "time_wib":     now_wib().strftime("%Y-%m-%d %H:%M:%S WIB"),
        "cache_fresh":  is_cache_fresh(),
        "cached_at":    cache.get("cached_at") if cache else None,
        "next_run":     "16:30 WIB (hari kerja)"
    }


@app.get("/screen")
async def get_screen_results(signal: str = "all"):
    """
    Ambil hasil screener dari cache.

    Query params:
        signal = all | hijau | kuning | merah
    """
    cache = load_cache()
    if not cache:
        raise HTTPException(
            status_code=503,
            detail="Belum ada data. Tunggu screener pertama kali jalan (16.30 WIB) "
                   "atau jalankan manual via /screen/run"
        )

    response = {
        "ihsg":      cache.get("ihsg"),
        "cached_at": cache.get("cached_at"),
        "total_screened": cache.get("total_screened"),
        "summary": {
            "hijau":  len(cache.get("hijau", [])),
            "kuning": len(cache.get("kuning", [])),
            "merah":  len(cache.get("merah", []))
        }
    }

    if signal == "hijau":
        response["results"] = cache.get("hijau", [])
    elif signal == "kuning":
        response["results"] = cache.get("kuning", [])
    elif signal == "merah":
        response["results"] = cache.get("merah", [])
    else:
        response["hijau"]  = cache.get("hijau", [])
        response["kuning"] = cache.get("kuning", [])

    return response


@app.get("/screen/{kode}")
async def get_single_stock(kode: str):
    """Analisis 1 saham secara real-time."""
    from data import fetch_single
    import traceback
    kode = kode.upper()
    logger.info(f"Real-time screen: {kode}")

    try:
        item = fetch_single(kode)
        if item["error"]:
            raise HTTPException(status_code=404, detail=f"Gagal fetch {kode}: {item['error']}")

        # Debug: cek struktur data sebelum apply_rules
        logger.info(f"{kode} daily shape: {item['daily'].shape}")
        logger.info(f"{kode} daily columns: {item['daily'].columns.tolist()}")
        logger.info(f"{kode} daily index type: {type(item['daily'].index)}")

        result = apply_rules(item["daily"], item["weekly"])
        result["kode"] = kode
        result["fetched_at"] = now_wib().strftime("%Y-%m-%d %H:%M:%S WIB")
        return result

    except HTTPException:
        raise
    except Exception as e:
        err_detail = traceback.format_exc()
        logger.error(f"Error screen {kode}: {err_detail}")
        # Tampilkan detail error langsung di response (untuk debugging)
        raise HTTPException(
            status_code=500,
            detail={
                "error": str(e),
                "traceback": err_detail.split("\n")
            }
        )


@app.post("/screen/run")
async def trigger_screener(background_tasks: BackgroundTasks):
    """Jalankan screener manual (background job)."""
    background_tasks.add_task(run_full_screener)
    return {
        "message": "Screener dimulai di background.",
        "note": "Cek hasil via GET /screen dalam beberapa menit."
    }


@app.get("/params")
async def get_params():
    """Ambil parameter screener saat ini."""
    # TODO: simpan params ke DB/file untuk persistence
    return ParamsUpdate().model_dump()


@app.post("/params")
async def update_params(params: ParamsUpdate):
    """Update parameter screener (akan dipakai di run berikutnya)."""
    # TODO: simpan ke file params.json
    return {"message": "Parameter diperbarui", "params": params.model_dump()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
