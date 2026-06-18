# Kirimemail — PDF Watermark & Mass Email Tool

Aplikasi untuk mengirim PDF yang sudah di-watermark secara massal via email. Setiap penerima mendapat salinan PDF unik dengan watermark email mereka — untuk pelacakan kebocoran dokumen.

## Persyaratan

- **Python 3.10+** (direkomendasikan 3.12)
- Akun Gmail dengan **2FA aktif** + [App Password](https://myaccount.google.com/apppasswords) (16 karakter)
- *(Opsional)* Google Cloud project untuk integrasi Google Drive

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/ahaditastudio/kirim-email.git
cd kirim-email
pip install -r requirements.txt
```

### 2. Konfigurasi Environment

```bash
cp .env.example .env
```

Edit file `.env`:

| Variabel | Default | Deskripsi |
|----------|---------|-----------|
| `SMTP_HOST` | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | `587` | SMTP port (STARTTLS) |
| `SMTP_USER` | — | Alamat Gmail kamu |
| `SMTP_PASSWORD` | — | Gmail App Password (16 karakter) |
| `BASE_URL` | `http://localhost:8000` | URL aplikasi (untuk fallback download link) |
| `DRIVE_FOLDER_ID` | — | *(Opsional)* ID folder Google Drive untuk upload PDF |
| `MAX_UPLOAD_SIZE_MB` | `50` | Ukuran maksimal PDF upload |
| `MAX_RECIPIENTS` | `100` | Maksimal penerima per pengiriman |

**Cara mendapatkan Gmail App Password:**
1. Buka https://myaccount.google.com/apppasswords
2. Pastikan 2FA sudah aktif di akun Google kamu
3. Buat App Password baru (16 karakter)
4. Copy dan paste ke `SMTP_PASSWORD` di file `.env`

### 3. Setup Google Drive (Opsional)

Jika ingin PDF otomatis di-upload ke Google Drive:

1. Buat project di [Google Cloud Console](https://console.cloud.google.com/)
2. Aktifkan **Google Drive API**
3. Buat **OAuth 2.0 Client ID** (tipe: Desktop App)
4. Download file JSON credentials, rename jadi `client_secrets.json` dan taruh di root project
5. Jalankan autentikasi:
```bash
python authenticate_drive.py
```
6. Authorize di browser yang terbuka — akan menghasilkan file `drive_token.json`

> **Tanpa Google Drive**, aplikasi tetap jalan — link download akan menggunakan server lokal sebagai fallback.

### 4. Jalankan

```bash
python run.py
```

Buka browser: **http://localhost:8000**

## Cara Pakai

1. **Upload** — Drag & drop atau pilih file PDF
2. **Configure** — Isi daftar email penerima (satu per baris), subject, dan isi pesan
3. **Preview** — Lihat live preview watermark di halaman pertama
4. **Send** — Proses berjalan otomatis:
   - Phase 1: Generate PDF dengan watermark unik per penerima (parallel)
   - Phase 2: Get download links (upload ke Google Drive)
   - Phase 3: Kirim email ke semua penerima
5. **Track** — Pantau progress real-time di halaman status

## Watermark

- **Mode Default:** Dual-layer vector watermark (di atas + di bawah konten). Sulit dihapus secara kasual maupun teknis.
- **High Security Mode:** Rasterize seluruh halaman di 200 DPI — watermark menyatu dengan konten pixel. Trade-off: file lebih besar, teks tidak bisa di-select.

## Batasan Gmail

- Gmail personal: **500 email/hari**
- Google Workspace: **2.000 email/hari**
- Aplikasi mengirim secara sequential dengan delay 0.5 detik antar email

## Project Structure

```
kirimemail/
├── run.py                         # Entry point (uvicorn)
├── requirements.txt               # Python dependencies
├── .env.example                   # Template environment variables
├── authenticate_drive.py          # Script setup OAuth Google Drive
├── app/
│   ├── main.py                    # FastAPI app setup
│   ├── config.py                  # Settings dari .env
│   ├── routers/
│   │   ├── pages.py               # HTML routes (/, /configure, /status)
│   │   └── api.py                 # API endpoints (upload, preview, send)
│   ├── services/
│   │   ├── watermark_service.py   # PDF watermarking engine (PyMuPDF + ReportLab)
│   │   ├── email_service.py       # SMTP batch sending + job tracking
│   │   ├── drive_service.py       # Google Drive upload (OAuth2)
│   │   └── pdf_service.py         # PDF metadata extraction
│   ├── templates/                 # Jinja2 HTML templates
│   └── static/                    # CSS & JS
├── uploads/                       # Temporary uploaded PDFs (gitignored)
└── output/                        # Temporary watermarked PDFs (gitignored)
```

## Tech Stack

- **Backend:** Python, FastAPI, Uvicorn
- **PDF:** PyMuPDF (fitz) + ReportLab
- **Email:** smtplib (SMTP/Gmail)
- **Cloud:** Google Drive API v3 (OAuth2)
- **Frontend:** Vanilla JS, Tailwind CSS (CDN), Jinja2

## License

MIT
