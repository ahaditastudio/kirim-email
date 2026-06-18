from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Gmail SMTP
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # App settings
    base_url: str = "http://localhost:8000"
    drive_folder_id: str = ""
    max_upload_size_mb: int = 50
    max_recipients: int = 100
    upload_dir: str = "uploads"
    output_dir: str = "output"

    # Watermark defaults
    default_font_size: int = 42
    default_opacity: float = 0.15
    default_rotation: int = 45
    default_rasterize: bool = False
    default_dpi: int = 200

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

# Ensure directories exist
Path(settings.upload_dir).mkdir(exist_ok=True)
Path(settings.output_dir).mkdir(exist_ok=True)
