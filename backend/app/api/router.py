from fastapi import APIRouter

from backend.app.api import chat, documents, health, nas_browser, users

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(documents.router, tags=["documents"])
api_router.include_router(nas_browser.router, tags=["nas"])
api_router.include_router(users.router, tags=["users"])
