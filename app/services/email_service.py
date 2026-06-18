import smtplib
import logging
import time
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path

from app.config import settings

logger = logging.getLogger("kirimemail")


@dataclass
class JobStatus:
    job_id: str
    total: int
    phase: str = "watermark"  # watermark | drive | sending | done
    wm_completed: int = 0
    drive_completed: int = 0
    send_completed: int = 0
    failed: list = field(default_factory=list)
    status: str = "running"
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "total": self.total,
            "phase": self.phase,
            "wm_completed": self.wm_completed,
            "drive_completed": self.drive_completed,
            "send_completed": self.send_completed,
            "failed": self.failed,
            "status": self.status,
        }


_jobs: dict[str, JobStatus] = {}


def get_job(job_id: str) -> Optional[JobStatus]:
    return _jobs.get(job_id)


def create_job(job_id: str, total: int) -> JobStatus:
    job = JobStatus(job_id=job_id, total=total)
    _jobs[job_id] = job
    return job


def _connect_smtp() -> smtplib.SMTP:
    """Create a fresh SMTP connection with STARTTLS + login."""
    server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
    server.ehlo()
    server.starttls()
    server.ehlo()
    server.login(settings.smtp_user, settings.smtp_password)
    return server


def send_batch_emails(
    job: JobStatus,
    recipients: list[str],
    subject: str,
    body: str,
    download_links: dict[str, str],
    original_filename: str,
) -> None:
    """Send all emails with download links using a single SMTP connection (fast!)."""
    job.phase = "sending"
    server = None

    # Single connection for all emails (text-only, no large attachments)
    try:
        server = _connect_smtp()
        logger.info("SMTP connected for batch sending (%d emails)", len(recipients))
    except Exception as e:
        logger.error("SMTP connect failed: %s", e)
        for recipient in recipients:
            job.failed.append({"email": recipient, "error": f"SMTP connection failed: {e}"})
            with job._lock:
                job.send_completed += 1
        job.phase = "done"
        job.status = "done"
        return

    for i, recipient in enumerate(recipients):
        link = download_links.get(recipient)
        if not link:
            job.failed.append({"email": recipient, "error": "No download link generated"})
            with job._lock:
                job.send_completed += 1
            continue

        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = settings.smtp_user
            msg["To"] = recipient
            msg["Subject"] = subject

            safe_name = recipient.replace("@", "_at_").replace(".", "_")
            filename = f"{Path(original_filename).stem}_{safe_name}.pdf"

            # Plain text
            full_body = f"{body}\n\nDownload your document here:\n{link}\n\nFilename: {filename}"
            msg.attach(MIMEText(full_body, "plain"))

            # HTML with button
            html_body = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px;">
                <p>{body}</p>
                <p style="margin-top: 20px;">
                    <a href="{link}" style="display: inline-block; background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold;">
                        Download Document
                    </a>
                </p>
                <p style="color: #6b7280; font-size: 12px; margin-top: 16px;">
                    Filename: {filename}<br>
                    This document contains a personalized watermark for tracking purposes.
                </p>
            </div>
            """
            msg.attach(MIMEText(html_body, "html"))

            server.send_message(msg)
            logger.info("Email %d/%d sent to %s", i + 1, len(recipients), recipient)
            with job._lock:
                job.send_completed += 1

        except Exception as e:
            logger.error("Send to %s failed: %s", recipient, e)
            job.failed.append({"email": recipient, "error": str(e)})
            with job._lock:
                job.send_completed += 1

            # Connection broken — try reconnect
            try:
                server.quit()
            except Exception:
                pass
            server = None

            if i < len(recipients) - 1:
                try:
                    server = _connect_smtp()
                    logger.info("SMTP reconnected for remaining emails")
                except Exception as reconn_err:
                    for r in recipients[i + 1:]:
                        job.failed.append({"email": r, "error": f"SMTP reconnect failed: {reconn_err}"})
                        with job._lock:
                            job.send_completed += 1
                    break

        # Small delay to avoid Gmail rate limit
        if i < len(recipients) - 1:
            time.sleep(0.5)

    if server:
        try:
            server.quit()
        except Exception:
            pass

    job.phase = "done"
    job.status = "done"
    logger.info("Job %s done. sent=%d, failed=%d", job.job_id, job.send_completed, len(job.failed))
