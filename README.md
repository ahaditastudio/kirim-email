# Kirimemail - PDF Watermark & Mass Email Tool

## Setup

1. **Install dependencies:**
```bash
pip install -r requirements.txt
```

2. **Configure Gmail SMTP:**
   - Go to https://myaccount.google.com/apppasswords
   - Enable 2FA on your Google account if not already enabled
   - Generate an App Password (16 characters)
   - Copy `.env.example` to `.env` and fill in your credentials:
```bash
cp .env.example .env
```

3. **Run the server:**
```bash
python run.py
```

4. **Open in browser:** http://localhost:8000

## Usage

1. **Upload** a PDF file (drag-drop or click)
2. **Configure** recipients (one email per line), subject, message body
3. **Preview** the watermark with live preview
4. **Send** - each recipient gets a uniquely watermarked PDF
5. **Track** sending progress in real-time

## Watermark Security

- **Default mode**: Dual-layer vector watermark (above + below content) with content stream merging. Defeats casual and most technical removal attempts.
- **High Security Mode** (toggle in UI): Rasterizes entire pages at 200 DPI, making watermark pixel-inseparable from content. Trade-off: larger file size, text no longer selectable.

## Gmail Limits

- Personal Gmail: 500 emails/day
- Google Workspace: 2,000 emails/day
- The app limits concurrent sends to 5 with 1s delay between sends

## Configuration

Edit `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| SMTP_HOST | smtp.gmail.com | SMTP server |
| SMTP_PORT | 587 | SMTP port (STARTTLS) |
| SMTP_USER | (empty) | Your Gmail address |
| SMTP_PASSWORD | (empty) | Gmail App Password (16 chars) |
| MAX_UPLOAD_SIZE_MB | 50 | Max PDF upload size |
| MAX_RECIPIENTS | 100 | Max recipients per job |

## Project Structure

```
kirimemail/
├── app/
│   ├── main.py              # FastAPI app
│   ├── config.py            # Settings from .env
│   ├── routers/
│   │   ├── pages.py         # HTML routes
│   │   └── api.py           # API endpoints
│   ├── services/
│   │   ├── watermark_service.py  # PDF watermarking
│   │   ├── email_service.py      # Gmail SMTP
│   │   └── pdf_service.py        # PDF helpers
│   ├── templates/           # Jinja2 HTML
│   └── static/js/           # Frontend JS
├── uploads/                 # Temp uploads (gitignored)
├── output/                  # Temp output (gitignored)
└── run.py
```
