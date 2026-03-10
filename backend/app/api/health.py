from fastapi import APIRouter, Depends

from backend.app.config import settings
from backend.app.dependencies import get_document_service, get_nas_index_service, get_synology_service
from backend.app.services.document_service import DocumentService
from backend.app.services.nas_index_service import NASIndexService
from backend.app.services.synology_service import SynologyService

router = APIRouter()


@router.get("/api/health")
async def health_check(
    doc_service: DocumentService = Depends(get_document_service),
    synology: SynologyService = Depends(get_synology_service),
    nas_index: NASIndexService = Depends(get_nas_index_service),
):
    # NAS 연결 상태 확인
    nas_connected = False
    if settings.synology_url and settings.synology_username:
        try:
            status = await synology.check_connection()
            nas_connected = status.get("connected", False)
        except Exception:
            pass

    return {
        "status": "ok",
        "document_count": doc_service.get_document_count(),
        "total_chunks": doc_service.get_total_chunks(),
        "llm_provider": settings.llm_provider,
        "nas_connected": nas_connected,
        "nas_base_dir_count": len(synology.list_base_dirs()),
        "nas_index_count": nas_index.total_indexed,
        "nas_index_last_scan": nas_index.last_scan_time.isoformat() if nas_index.last_scan_time else None,
    }
