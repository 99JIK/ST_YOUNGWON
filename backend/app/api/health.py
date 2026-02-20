from fastapi import APIRouter, Depends

from backend.app.config import settings
from backend.app.dependencies import get_document_service, get_nas_path_service
from backend.app.services.document_service import DocumentService
from backend.app.services.nas_path_service import NASPathService

router = APIRouter()


@router.get("/api/health")
async def health_check(
    doc_service: DocumentService = Depends(get_document_service),
    nas_service: NASPathService = Depends(get_nas_path_service),
):
    return {
        "status": "ok",
        "document_count": doc_service.get_document_count(),
        "total_chunks": doc_service.get_total_chunks(),
        "llm_provider": settings.llm_provider,
        "nas_path_count": len(nas_service.list_paths()),
        "nas_file_count": nas_service.get_file_count(),
        "nas_file_chunks": nas_service.get_total_file_chunks(),
    }
