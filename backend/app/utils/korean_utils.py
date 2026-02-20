from __future__ import annotations

import re
import unicodedata


def normalize_korean_text(text: str) -> str:
    """한국어 텍스트 정규화."""
    # NFC 유니코드 정규화 (한국어 자모 결합)
    text = unicodedata.normalize("NFC", text)
    # PDF 추출 아티팩트 정리: 과도한 공백 축소
    text = re.sub(r"[ \t]{2,}", " ", text)
    # 연속 빈 줄 축소
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 줄 앞뒤 공백 정리
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(lines)
    return text.strip()


def is_header_or_footer(line: str, doc_title: str = "") -> bool:
    """페이지 헤더/푸터인지 판별."""
    stripped = line.strip()
    if not stripped:
        return False
    # 페이지 번호만 있는 줄
    if re.match(r"^-?\s*\d+\s*-?$", stripped):
        return True
    # "- N -" 형태
    if re.match(r"^-\s*\d+\s*-$", stripped):
        return True
    # 문서 제목이 반복되는 경우
    if doc_title and stripped == doc_title:
        return True
    return False


def clean_extracted_text(text: str, doc_title: str = "") -> str:
    """추출된 텍스트에서 헤더/푸터 제거 및 정규화."""
    lines = text.split("\n")
    cleaned = [
        line for line in lines if not is_header_or_footer(line, doc_title)
    ]
    return normalize_korean_text("\n".join(cleaned))
