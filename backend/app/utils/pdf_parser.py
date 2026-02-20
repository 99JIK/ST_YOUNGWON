from __future__ import annotations

import logging
from pathlib import Path

import fitz  # PyMuPDF

from backend.app.utils.korean_utils import clean_extracted_text

logger = logging.getLogger(__name__)


def extract_pdf_text(file_path: Path) -> list[dict]:
    """PDF 파일에서 페이지별 텍스트를 추출합니다.

    Returns:
        list of {"page_number": int, "text": str, "metadata": dict}
    """
    doc = fitz.open(str(file_path))
    pages = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        text = clean_extracted_text(text)

        if text.strip():
            pages.append(
                {
                    "page_number": page_num + 1,
                    "text": text,
                    "metadata": {
                        "source": file_path.name,
                        "page": page_num + 1,
                    },
                }
            )

    doc.close()
    logger.info(f"PDF 추출 완료: {file_path.name}, {len(pages)}페이지")
    return pages


def extract_full_text(file_path: Path) -> str:
    """PDF 파일에서 전체 텍스트를 하나의 문자열로 추출합니다."""
    pages = extract_pdf_text(file_path)
    return "\n\n".join(p["text"] for p in pages)
