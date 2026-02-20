from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.app.api.router import api_router
from backend.app.config import settings
from backend.app.database import init_db
from backend.app.dependencies import create_token, get_user_service

logger = logging.getLogger(__name__)

# Resolve paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
TEMPLATES_DIR = FRONTEND_DIR / "templates"
STATIC_DIR = FRONTEND_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger.info("ST영원 스마트 오피스 시작")
    logger.info(f"LLM: {settings.llm_provider}, Embedding: {settings.embedding_provider}")

    # Initialize database
    init_db()

    # Ensure data directories exist
    for dir_path in [
        settings.documents_dir,
        settings.extracted_dir,
        settings.chromadb_dir,
        settings.nas_files_dir,
        settings.nas_paths_file.parent,
        settings.data_dir / "files",
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)

    yield

    # Shutdown
    logger.info("ST영원 스마트 오피스 종료")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Include API routes
app.include_router(api_router)


# === Page Routes ===


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/", response_class=HTMLResponse)
async def chat_page(request: Request):
    return templates.TemplateResponse("chat.html", {"request": request})


@app.get("/files", response_class=HTMLResponse)
async def files_page(request: Request):
    return templates.TemplateResponse(
        "files.html",
        {
            "request": request,
            "max_upload_size_mb": settings.max_upload_size_mb,
        },
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "max_upload_size_mb": settings.max_upload_size_mb,
            "app_version": settings.app_version,
        },
    )


# === Auth API ===


@app.post("/api/auth/login")
async def auth_login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
):
    """통합 로그인 API."""
    user_service = get_user_service()
    user = user_service.authenticate(username, password)
    if not user:
        return {"success": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."}

    token = create_token(user)
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        max_age=86400,
        samesite="lax",
    )
    return {
        "success": True,
        "token": token,
        "user": {
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
        },
    }


@app.post("/api/auth/logout")
async def auth_logout(response: Response):
    """로그아웃."""
    response.delete_cookie("auth_token")
    return {"success": True}


@app.get("/api/auth/me")
async def auth_me(request: Request):
    """현재 유저 정보를 반환합니다."""
    from backend.app.dependencies import get_current_user

    try:
        user = await get_current_user(request, request.cookies.get("auth_token"))
        return {"username": user["username"], "display_name": user.get("display_name", ""), "role": user["role"]}
    except Exception:
        return Response(status_code=401)
