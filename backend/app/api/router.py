from fastapi import APIRouter

from backend.app.api import chat, documents, filesystem, health, nas_paths, users

api_router = APIRouter()

api_router.include_router(health.router, tags=["health"])
api_router.include_router(chat.router, tags=["chat"])
api_router.include_router(documents.router, tags=["documents"])
api_router.include_router(nas_paths.router, tags=["nas"])
api_router.include_router(filesystem.router, tags=["filesystem"])
api_router.include_router(users.router, tags=["users"])
