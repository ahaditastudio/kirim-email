import logging
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import pages, api

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

app = FastAPI(title="Kirimemail", description="PDF Watermark & Mass Email Tool")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Include routers
app.include_router(pages.router)
app.include_router(api.router)
