from __future__ import annotations

import re
from dataclasses import dataclass, field

# 한국어 규정 문서 구조 패턴
CHAPTER_PATTERN = re.compile(r"^제\s*(\d+)\s*장\s+(.+)$", re.MULTILINE)
ARTICLE_PATTERN = re.compile(
    r"^제\s*(\d+)\s*조\s*[\(（](.+?)[\)）]", re.MULTILINE
)
PARAGRAPH_PATTERN = re.compile(r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]")


@dataclass
class Chunk:
    content: str
    metadata: dict = field(default_factory=dict)
    chunk_id: str = ""


def chunk_regulation_text(
    text: str,
    source_file: str = "",
    max_chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[Chunk]:
    """규정 문서 텍스트를 구조 인식하여 청킹합니다.

    전략:
    1. 제X조 (조항) 단위로 1차 분할
    2. 조항이 max_chunk_size 초과 시 ①②③ 단위로 2차 분할
    3. 그래도 클 경우 고정 크기로 분할
    """
    chunks: list[Chunk] = []
    current_chapter = ""

    # 조항별 분할
    articles = _split_by_articles(text)

    for i, article in enumerate(articles):
        article_text = article["text"].strip()
        if not article_text:
            continue

        # 장(chapter) 추적
        chapter_match = CHAPTER_PATTERN.search(article_text)
        if chapter_match:
            current_chapter = f"제{chapter_match.group(1)}장 {chapter_match.group(2)}"

        metadata = {
            "source": source_file,
            "chapter": current_chapter,
            "article_number": article.get("number", ""),
            "article_title": article.get("title", ""),
        }

        if len(article_text) <= max_chunk_size:
            chunks.append(
                Chunk(
                    content=article_text,
                    metadata=metadata,
                    chunk_id=f"{source_file}_art{i}",
                )
            )
        else:
            # 항(paragraph) 단위로 재분할
            sub_chunks = _split_by_paragraphs(
                article_text, max_chunk_size, chunk_overlap
            )
            for j, sub_text in enumerate(sub_chunks):
                # 조항 제목을 접두어로 추가
                prefix = ""
                if article.get("title"):
                    prefix = f"[제{article.get('number', '')}조 ({article['title']})] "

                chunks.append(
                    Chunk(
                        content=prefix + sub_text,
                        metadata=metadata,
                        chunk_id=f"{source_file}_art{i}_p{j}",
                    )
                )

    return chunks


def _split_by_articles(text: str) -> list[dict]:
    """제X조 기준으로 텍스트를 분할합니다."""
    matches = list(ARTICLE_PATTERN.finditer(text))

    if not matches:
        # 조항 구조가 없으면 전체를 하나로
        return [{"text": text, "number": "", "title": ""}]

    articles = []

    # 첫 조항 이전 텍스트 (전문, 목적 등)
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            articles.append({"text": preamble, "number": "0", "title": "전문"})

    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        article_text = text[start:end].strip()

        articles.append(
            {
                "text": article_text,
                "number": match.group(1),
                "title": match.group(2),
            }
        )

    return articles


def _split_by_paragraphs(
    text: str, max_size: int, overlap: int
) -> list[str]:
    """①②③ 기준으로 텍스트를 분할하고, 그래도 크면 고정 크기로 분할합니다."""
    lines = text.split("\n")
    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        if PARAGRAPH_PATTERN.match(line.strip()) and current:
            paragraphs.append("\n".join(current))
            current = [line]
        else:
            current.append(line)

    if current:
        paragraphs.append("\n".join(current))

    # 항 단위로 나눈 것도 너무 크면 고정 크기로 재분할
    result: list[str] = []
    for para in paragraphs:
        if len(para) <= max_size:
            result.append(para)
        else:
            result.extend(_fixed_size_split(para, max_size, overlap))

    return result


def chunk_general_text(
    text: str,
    source_file: str = "",
    max_chunk_size: int = 800,
    chunk_overlap: int = 100,
) -> list[Chunk]:
    """일반 텍스트를 청킹합니다 (규정 구조가 아닌 문서용).

    단락 단위로 분할하고, 큰 단락은 고정 크기로 재분할합니다.
    """
    chunks: list[Chunk] = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if not paragraphs:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    # 단락을 합쳐서 적절한 크기로 만듦
    current_text = ""
    chunk_idx = 0

    for para in paragraphs:
        if len(current_text) + len(para) + 1 <= max_chunk_size:
            current_text = f"{current_text}\n{para}" if current_text else para
        else:
            if current_text:
                chunks.append(
                    Chunk(
                        content=current_text,
                        metadata={"source": source_file},
                        chunk_id=f"{source_file}_chunk{chunk_idx}",
                    )
                )
                chunk_idx += 1
            if len(para) > max_chunk_size:
                sub_parts = _fixed_size_split(para, max_chunk_size, chunk_overlap)
                for sub in sub_parts:
                    chunks.append(
                        Chunk(
                            content=sub,
                            metadata={"source": source_file},
                            chunk_id=f"{source_file}_chunk{chunk_idx}",
                        )
                    )
                    chunk_idx += 1
                current_text = ""
            else:
                current_text = para

    if current_text:
        chunks.append(
            Chunk(
                content=current_text,
                metadata={"source": source_file},
                chunk_id=f"{source_file}_chunk{chunk_idx}",
            )
        )

    return chunks


def _fixed_size_split(text: str, max_size: int, overlap: int) -> list[str]:
    """고정 크기로 텍스트를 분할합니다. 문장 경계를 존중합니다."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_size
        if end >= len(text):
            chunks.append(text[start:])
            break

        # 마침표, 줄바꿈 등 문장 경계 찾기
        boundary = text.rfind(".", start, end)
        if boundary == -1 or boundary <= start:
            boundary = text.rfind("\n", start, end)
        if boundary == -1 or boundary <= start:
            boundary = end

        chunks.append(text[start : boundary + 1])
        start = boundary + 1 - overlap

    return chunks
