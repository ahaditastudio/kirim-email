from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/configure")
async def configure(request: Request):
    return templates.TemplateResponse("preview.html", {"request": request})


@router.get("/status/{job_id}")
async def status_page(request: Request, job_id: str):
    return templates.TemplateResponse(
        "status.html", {"request": request, "job_id": job_id}
    )
