import os
import logging
from typing import Optional
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import google_auth_httplib2
import httplib2

logger = logging.getLogger("kirimemail")

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CLIENT_SECRETS = "client_secrets.json"
TOKEN_FILE = "drive_token.json"


def _get_creds():
    """Get valid OAuth2 credentials."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if creds and creds.expired and creds.refresh_token:
        logger.info("Refreshing Google Drive token...")
        creds.refresh(Request())
    elif not creds or not creds.valid:
        if not os.path.exists(CLIENT_SECRETS):
            raise FileNotFoundError(
                f"OAuth client secrets not found. "
                f"Place '{CLIENT_SECRETS}' in project root and run 'python3 authenticate_drive.py'."
            )
        flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
        creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    return creds


def _get_drive_service():
    """Get authenticated Google Drive API service with long timeout."""
    creds = _get_creds()

    # Create authorized HTTP with 5-minute timeout
    http = httplib2.Http(timeout=300)
    authorized_http = google_auth_httplib2.AuthorizedHttp(creds, http=http)

    return build("drive", "v3", http=authorized_http)


def upload_to_drive(
    file_path: str,
    filename: str,
    folder_id: Optional[str] = None,
) -> str:
    """Upload a file to Google Drive and return a shareable download link."""
    service = _get_drive_service()

    file_metadata = {"name": filename}
    if folder_id:
        file_metadata["parents"] = [folder_id]

    media = MediaFileUpload(file_path, mimetype="application/pdf", resumable=True)

    uploaded = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id",
    ).execute()

    file_id = uploaded["id"]

    # Make the file publicly accessible (anyone with link can view)
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()

    download_link = f"https://drive.google.com/uc?export=download&id={file_id}"
    logger.info("Uploaded %s to Drive: %s", filename, download_link)
    return download_link


def upload_batch_to_drive(
    pdf_paths: dict[str, str],
    original_filename: str,
    folder_id: Optional[str] = None,
    job=None,
) -> dict[str, str]:
    """Upload multiple watermarked PDFs to Google Drive."""
    download_links: dict[str, str] = {}

    for email, path in pdf_paths.items():
        safe_name = email.replace("@", "_at_").replace(".", "_")
        filename = f"{original_filename}_{safe_name}.pdf"
        try:
            link = upload_to_drive(path, filename, folder_id)
            download_links[email] = link
            if job:
                with job._lock:
                    job.drive_completed += 1
            logger.info("Drive upload %d: %s -> OK", len(download_links), email)
        except Exception as e:
            logger.error("Drive upload failed for %s: %s", email, e)

    return download_links
