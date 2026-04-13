# IDX Screener — Sistem Merah-Hijau
Web app screener saham IDX berbasis 7 rules Sistem Trading Merah-Hijau.
Bisa diakses dari Android sebagai PWA (Progressive Web App).

## Struktur Project

```
idx-screener/
├── main.py          # FastAPI backend + scheduler
├── screener.py      # Logic 7 rules Merah-Hijau
├── data.py          # Fetch data IDX via yfinance
├── notif.py         # Push notification via OneSignal
├── requirements.txt
├── railway.toml     # Config deploy Railway
├── .env.example     # Template environment variables
└── static/
    ├── index.html   # Frontend mobile-first (PWA)
    └── manifest.json
```

## Cara Setup Lokal

```bash
# 1. Clone / download project
cd idx-screener

# 2. Buat virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy dan isi .env
cp .env.example .env
# Edit .env → isi ONESIGNAL_APP_ID dan ONESIGNAL_API_KEY

# 5. Jalankan server
python main.py

# Buka browser: http://localhost:8000
```

## Deploy ke Railway (Gratis)

### Langkah 1 — Push ke GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/USERNAME/idx-screener.git
git push -u origin main
```

### Langkah 2 — Setup Railway
1. Buka https://railway.app
2. Login dengan GitHub
3. Klik "New Project" → "Deploy from GitHub repo"
4. Pilih repo `idx-screener`
5. Railway otomatis detect Python dan deploy

### Langkah 3 — Set Environment Variables
Di Railway dashboard → Settings → Variables:
```
ONESIGNAL_APP_ID   = your-app-id
ONESIGNAL_API_KEY  = your-api-key
```

### Langkah 4 — Dapat URL Publik
Railway beri URL seperti: `https://idx-screener-production.up.railway.app`

## Install ke Android (PWA)

1. Buka URL Railway di **Chrome Android**
2. Tap menu (⋮) → **"Add to Home screen"**
3. App muncul di homescreen seperti app native ✅

## Setup Push Notification (OneSignal)

1. Daftar di https://onesignal.com (gratis)
2. Create new app → pilih "Web"
3. Masukkan URL Railway sebagai site URL
4. Copy **App ID** dan **REST API Key**
5. Isi di `.env` atau Railway Variables
6. Buka app di Android → tab Parameter → "Aktifkan Notifikasi"

## Cara Kerja

- **Auto-run**: Screener jalan otomatis jam **16.30 WIB** setiap Senin–Jumat
- **Data**: Fetch via yfinance (suffix `.JK`) untuk semua saham IDX
- **Cache**: Hasil disimpan ke `data/cache/screen_result.json`
- **Loading user**: Selalu ambil dari cache → instan, tidak berat
- **Notifikasi**: Hanya saham Batch 1+2 (LQ45/IDX80) dengan sinyal HIJAU

## Rules Sistem Merah-Hijau

| Rule | Kondisi | Keterangan |
|------|---------|------------|
| R1 | Close > MA20 > MA50 | Trend harian uptrend |
| R2 | Close ≤ HHV(High,20) × 0.97 | Pullback dari high |
| R3 | Close > Open | Candle hijau |
| R4 ⚠️ | Volume > VolumeMA20 × 1.5 | Volume konfirmasi (WAJIB) |
| R5 | Close ≤ LLV(Low,20) × 1.03 | Dekat support |
| R6 | LLV(Low,5) > LLV(Low,20) | Higher low |
| R7 | Close > MA50W | Trend mingguan sehat |

**Sinyal HIJAU**: R1 ✅ + R4 ✅ + minimal 5/7 rules terpenuhi
**Sinyal KUNING**: R1 ✅ + R4 ✅ + 4/7 rules terpenuhi
**Sinyal MERAH**: Tidak memenuhi minimal

## Filter IHSG

| Mode | Kondisi | Aksi |
|------|---------|------|
| UPTREND | IHSG > MA50W > MA200W | Trading penuh |
| SIDEWAYS | IHSG antara MA50W–MA200W | Selektif, size -50% |
| DOWNTREND | IHSG < MA50W < MA200W | STOP trading |

## API Endpoints

| Method | Endpoint | Fungsi |
|--------|----------|--------|
| GET | `/screen` | Semua hasil screener dari cache |
| GET | `/screen?signal=hijau` | Filter sinyal hijau saja |
| GET | `/screen/{KODE}` | Analisis real-time 1 saham |
| POST | `/screen/run` | Trigger screener manual |
| GET | `/params` | Lihat parameter |
| POST | `/params` | Update parameter |
| GET | `/health` | Status server & cache |
