"""
notif.py
Push Notification via OneSignal (gratis)
Kirim alert saat saham masuk sinyal HIJAU
"""

import os
import logging
import httpx

logger = logging.getLogger(__name__)

ONESIGNAL_APP_ID  = os.getenv("ONESIGNAL_APP_ID", "")
ONESIGNAL_API_KEY = os.getenv("ONESIGNAL_API_KEY", "")
ONESIGNAL_URL     = "https://onesignal.com/api/v1/notifications"


async def send_notification(hijau_list: list, ihsg_status: dict):
    """
    Kirim push notification untuk saham sinyal HIJAU.

    Parameters:
        hijau_list  : list hasil screener signal HIJAU
        ihsg_status : dict kondisi IHSG
    """
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY:
        logger.warning("OneSignal belum dikonfigurasi — notifikasi dilewati")
        return

    if not hijau_list:
        logger.info("Tidak ada sinyal HIJAU — tidak ada notifikasi")
        return

    mode  = ihsg_status.get("mode", "?")
    total = len(hijau_list)

    # Format pesan
    kode_list = ", ".join([s["kode"] for s in hijau_list[:5]])
    if total > 5:
        kode_list += f" +{total - 5} lainnya"

    title   = f"🟢 {total} Sinyal HIJAU — IHSG {mode}"
    message = f"{kode_list} | Cek chart & verifikasi manual sebelum entry"

    payload = {
        "app_id":             ONESIGNAL_APP_ID,
        "included_segments":  ["All"],
        "headings":           {"en": title, "id": title},
        "contents":           {"en": message, "id": message},
        "data": {
            "screen":      "hijau",
            "ihsg_mode":   mode,
            "total_hijau": total
        }
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ONESIGNAL_URL,
                json=payload,
                headers={
                    "Authorization": f"Basic {ONESIGNAL_API_KEY}",
                    "Content-Type":  "application/json"
                },
                timeout=10.0
            )
            if response.status_code == 200:
                logger.info(f"Notifikasi terkirim: {title}")
            else:
                logger.error(
                    f"Gagal kirim notifikasi: {response.status_code} — {response.text}"
                )
    except Exception as e:
        logger.error(f"Exception saat kirim notifikasi: {e}")


async def send_custom_notification(title: str, message: str, data: dict = None):
    """Kirim notifikasi custom (untuk testing atau alert khusus)."""
    if not ONESIGNAL_APP_ID or not ONESIGNAL_API_KEY:
        logger.warning("OneSignal belum dikonfigurasi")
        return

    payload = {
        "app_id":            ONESIGNAL_APP_ID,
        "included_segments": ["All"],
        "headings":          {"en": title, "id": title},
        "contents":          {"en": message, "id": message},
    }
    if data:
        payload["data"] = data

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                ONESIGNAL_URL,
                json=payload,
                headers={
                    "Authorization": f"Basic {ONESIGNAL_API_KEY}",
                    "Content-Type":  "application/json"
                },
                timeout=10.0
            )
            logger.info(f"Custom notif: {response.status_code}")
    except Exception as e:
        logger.error(f"Exception notif custom: {e}")
