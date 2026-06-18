import uuid
import os
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse
from pydantic import BaseModel
from typing import Optional
import io

logger = logging.getLogger("kirimemail")

from app.config import settings
from app.services.watermark_service import WatermarkOptions, apply_watermark, generate_preview
from app.services.pdf_service import get_pdf_info
from app.services.email_service import create_job, get_job, send_batch_emails
from app.services.drive_service import upload_batch_to_drive

router = APIRouter(prefix="/api")

# Track uploaded files: file_id -> {path, filename, page_count}
_uploaded_files: dict[str, dict] = {}

# Download tokens: token -> {path, filename, original_filename}
_download_tokens: dict[str, dict] = {}


class PreviewRequest(BaseModel):
    file_id: str
    email: str = "preview@example.com"
    font_size: int = 42
    opacity: float = 0.15
    rotation: int = 45
    color_r: float = 0.7
    color_g: float = 0.7
    color_b: float = 0.7
    spacing_x: int = 200
    spacing_y: int = 150


class SendRequest(BaseModel):
    file_id: str
    emails: list[str]
    subject: str = "Confidential Document"
    message: str = "Please find the attached confidential document."
    font_size: int = 42
    opacity: float = 0.15
    rotation: int = 45
    color_r: float = 0.7
    color_g: float = 0.7
    color_b: float = 0.7
    spacing_x: int = 200
    spacing_y: int = 150
    rasterize: bool = False
    dpi: int = 200


@router.post("/upload")
async def upload_pdf(file: UploadFile = File(...)):
    """Upload a PDF file and return its metadata."""
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # Validate size
    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.max_upload_size_mb:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {settings.max_upload_size_mb}MB",
        )

    # Save file
    file_id = str(uuid.uuid4())
    file_path = os.path.join(settings.upload_dir, f"{file_id}.pdf")
    with open(file_path, "wb") as f:
        f.write(content)

    # Get metadata
    try:
        info = get_pdf_info(file_path)
    except Exception:
        os.remove(file_path)
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    _uploaded_files[file_id] = {
        "path": file_path,
        "filename": file.filename,
        "page_count": info["page_count"],
    }

    return JSONResponse(
        content={
            "file_id": file_id,
            "filename": file.filename,
            "page_count": info["page_count"],
            "size_mb": round(size_mb, 2),
        }
    )


@router.post("/preview")
async def preview_watermark(req: PreviewRequest):
    """Generate a watermarked preview of page 1."""
    file_info = _uploaded_files.get(req.file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found. Please re-upload.")

    options = WatermarkOptions(
        font_size=req.font_size,
        opacity=req.opacity,
        rotation=req.rotation,
        color=(req.color_r, req.color_g, req.color_b),
        spacing_x=req.spacing_x,
        spacing_y=req.spacing_y,
    )

    try:
        pdf_bytes = generate_preview(file_info["path"], req.email, options)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview generation failed: {str(e)}")

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=preview.pdf"},
    )


def _process_send_job(
    job_id: str,
    file_path: str,
    emails: list[str],
    subject: str,
    message: str,
    options: WatermarkOptions,
    original_filename: str,
):
    """Background task: parallel watermark generation, then send emails."""
    job = get_job(job_id)
    pdf_paths: dict[str, str] = {}
    total = len(emails)
    logger.info("Job %s started: %d emails, file=%s", job_id, total, file_path)

    # Pre-load source PDF into memory (avoid 400x disk reads)
    with open(file_path, "rb") as f:
        source_bytes = f.read()
    logger.info("Source PDF loaded: %.2f MB", len(source_bytes) / (1024 * 1024))

    # PHASE 1: Generate watermarked PDFs (parallel, 16 workers)
    job.phase = "watermark"
    workers = min(16, total)  # don't spawn more workers than emails
    logger.info("PHASE 1: Generating watermarks (%d recipients, %d workers)...", total, workers)

    def watermark_one(email: str) -> tuple:
        safe_name = email.replace("@", "_at_").replace(".", "_")
        output_path = os.path.join(
            settings.output_dir, f"{job_id}_{safe_name}.pdf"
        )
        apply_watermark(file_path, email, output_path, options, source_bytes=source_bytes)
        return (email, output_path)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(watermark_one, email): email for email in emails}
        for future in futures:
            email = futures[future]
            try:
                email, output_path = future.result()
                pdf_paths[email] = output_path
                with job._lock:
                    job.wm_completed += 1
            except Exception as e:
                logger.error("  Watermark failed for %s: %s", email, e)
                job.failed.append({"email": email, "error": f"Watermark failed: {e}"})

    wm_ok = len(pdf_paths)
    wm_fail = total - wm_ok
    logger.info("PHASE 1 done: %d OK, %d failed.", wm_ok, wm_fail)

    # PHASE 1.5: Upload watermarked PDFs to Google Drive
    download_links: dict[str, str] = {}
    if pdf_paths:
        job.phase = "drive"
        logger.info("Uploading %d PDFs to Google Drive...", len(pdf_paths))
        try:
            pdf_stem = Path(original_filename).stem
            folder_id = settings.drive_folder_id or None
            download_links = upload_batch_to_drive(pdf_paths, pdf_stem, folder_id=folder_id, job=job)
            logger.info("Drive upload done: %d/%d succeeded", len(download_links), len(pdf_paths))

            # Track failed uploads
            for email in pdf_paths:
                if email not in download_links:
                    job.failed.append({"email": email, "error": "Google Drive upload failed"})
        except Exception as e:
            logger.error("Google Drive upload failed: %s", e)
            # Fallback: use local download links
            for email, path in pdf_paths.items():
                token = str(uuid.uuid4())
                safe_name = email.replace("@", "_at_").replace(".", "_")
                filename = f"{Path(original_filename).stem}_{safe_name}.pdf"
                _download_tokens[token] = {"path": path, "filename": filename}
                download_links[email] = f"{settings.base_url}/api/download/{token}"
            logger.info("Fallback: using local download links instead.")

    # Cleanup local PDFs (already uploaded to Drive)
    for path in pdf_paths.values():
        try:
            os.remove(path)
        except OSError:
            pass

    # PHASE 2: Send emails with download links
    if download_links:
        logger.info("PHASE 2: Sending %d emails with download links...", len(download_links))
        send_batch_emails(job, emails, subject, message, download_links, original_filename)
    else:
        job.phase = "done"
        job.status = "done"
        logger.info("PHASE 2 skipped: no PDFs to send.")

    logger.info("Job %s finished. status=%s, sent=%d, failed=%d",
                job_id, job.status, job.send_completed, len(job.failed))


@router.post("/send")
async def send_watermarked(req: SendRequest, background_tasks: BackgroundTasks):
    """Start a watermark + send job."""
    # Validate
    file_info = _uploaded_files.get(req.file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="File not found. Please re-upload.")

    if not settings.smtp_user or not settings.smtp_password:
        raise HTTPException(
            status_code=400,
            detail="SMTP not configured. Set SMTP_USER and SMTP_PASSWORD in .env file.",
        )

    if not req.emails:
        raise HTTPException(status_code=400, detail="No recipients provided")

    if len(req.emails) > settings.max_recipients:
        raise HTTPException(
            status_code=400,
            detail=f"Too many recipients. Maximum is {settings.max_recipients}",
        )

    # Validate email format
    invalid = [e for e in req.emails if "@" not in e or "." not in e.split("@")[-1]]
    if invalid:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid email addresses: {', '.join(invalid[:5])}",
        )

    job_id = str(uuid.uuid4())
    job = create_job(job_id, len(req.emails))

    options = WatermarkOptions(
        font_size=req.font_size,
        opacity=req.opacity,
        rotation=req.rotation,
        color=(req.color_r, req.color_g, req.color_b),
        spacing_x=req.spacing_x,
        spacing_y=req.spacing_y,
        rasterize=req.rasterize,
        dpi=req.dpi,
    )

    background_tasks.add_task(
        _process_send_job,
        job_id,
        file_info["path"],
        req.emails,
        req.subject,
        req.message,
        options,
        file_info["filename"],
    )

    return JSONResponse(
        content={"job_id": job_id, "total": len(req.emails)}
    )


@router.get("/status/{job_id}")
async def job_status(job_id: str):
    """Get the status of a sending job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return JSONResponse(content=job.to_dict())


@router.get("/download/{token}")
async def download_pdf(token: str):
    """Download a watermarked PDF by token."""
    info = _download_tokens.get(token)
    if not info:
        raise HTTPException(status_code=404, detail="Download link expired or invalid")

    path = info["path"]
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File no longer available")

    return FileResponse(
        path=path,
        filename=info["filename"],
        media_type="application/pdf",
    )
