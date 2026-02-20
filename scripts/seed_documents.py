"""기존 PDF 문서를 벡터 저장소에 초기 인덱싱하는 스크립트."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# 프로젝트 루트를 PYTHONPATH에 추가
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from backend.app.config import settings
from backend.app.services.document_service import DocumentService


async def seed():
    """프로젝트 루트의 PDF 파일들을 인덱싱합니다."""
    doc_service = DocumentService()

    # 프로젝트 루트에서 PDF 파일 찾기
    root_dir = Path(__file__).resolve().parent.parent
    pdf_files = list(root_dir.glob("*.pdf"))

    # data/documents 디렉토리에서도 찾기
    data_pdfs = list(settings.documents_dir.glob("*.pdf"))
    pdf_files.extend(data_pdfs)

    if not pdf_files:
        print("인덱싱할 PDF 파일이 없습니다.")
        return

    print(f"발견된 PDF 파일: {len(pdf_files)}개")

    for pdf_path in pdf_files:
        print(f"\n처리 중: {pdf_path.name}")
        try:
            content = pdf_path.read_bytes()
            result = await doc_service.upload_and_index(pdf_path.name, content)
            print(f"  완료: {result.total_chunks}개 청크, 상태: {result.status}")
        except Exception as e:
            print(f"  실패: {e}")


if __name__ == "__main__":
    asyncio.run(seed())
