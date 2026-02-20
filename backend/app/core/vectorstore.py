from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

import chromadb

from backend.app.config import settings
from backend.app.core.embeddings import EmbeddingProvider, create_embedding_provider

logger = logging.getLogger(__name__)

# ChromaDB 컬렉션 이름
REGULATIONS_COLLECTION = "st_youngwon_regulations"
NAS_PATHS_COLLECTION = "nas_file_paths"
NAS_FILES_COLLECTION = "nas_files"


class VectorStore:
    """ChromaDB 기반 벡터 저장소."""

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self._persist_dir = persist_dir or settings.chromadb_dir
        self._persist_dir.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self._persist_dir)
        )
        self._embedding = embedding_provider or create_embedding_provider()

    def get_or_create_collection(self, name: str) -> chromadb.Collection:
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def add_documents(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict],
        ids: list[str],
        on_embed_progress: Optional[Callable[[int, int], None]] = None,
    ) -> int:
        """문서를 임베딩하여 벡터 저장소에 추가합니다.

        Args:
            on_embed_progress: 임베딩 진행률 콜백 (current, total)
        """
        if not documents:
            return 0

        collection = self.get_or_create_collection(collection_name)
        total = len(documents)

        # 배치 단위로 임베딩 생성 (진행률 추적 가능)
        batch_size = 10
        all_embeddings: list[list[float]] = []

        for i in range(0, total, batch_size):
            batch = documents[i : i + batch_size]
            batch_embeddings = self._embedding.encode(batch)
            all_embeddings.extend(batch_embeddings)

            if on_embed_progress:
                on_embed_progress(min(i + len(batch), total), total)

        # 빈 임베딩(빈 텍스트) 필터링 — ChromaDB에 빈 벡터는 추가 불가
        filtered = [
            (doc, emb, meta, doc_id)
            for doc, emb, meta, doc_id in zip(documents, all_embeddings, metadatas, ids)
            if emb
        ]
        if not filtered:
            logger.warning("유효한 임베딩이 없습니다. 문서 추가를 건너뜁니다.")
            return 0

        f_documents, f_embeddings, f_metadatas, f_ids = zip(*filtered)

        # ChromaDB에 추가 (차원 불일치 시 컬렉션 재생성)
        try:
            collection.add(
                documents=list(f_documents),
                embeddings=list(f_embeddings),
                metadatas=list(f_metadatas),
                ids=list(f_ids),
            )
        except Exception as e:
            if "dimension" in str(e).lower():
                logger.warning(
                    f"임베딩 차원 불일치 감지 — 컬렉션 '{collection_name}' 재생성합니다: {e}"
                )
                self._client.delete_collection(collection_name)
                collection = self.get_or_create_collection(collection_name)
                collection.add(
                    documents=list(f_documents),
                    embeddings=list(f_embeddings),
                    metadatas=list(f_metadatas),
                    ids=list(f_ids),
                )
            else:
                raise

        added = len(f_documents)
        if added < total:
            logger.info(f"빈 텍스트 {total - added}개 건너뜀")
        logger.info(
            f"벡터 저장소에 {added}개 문서 추가 (컬렉션: {collection_name})"
        )
        return added

    def search(
        self,
        collection_name: str,
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """하이브리드 검색: 키워드 우선 + 벡터 검색 보조."""
        collection = self.get_or_create_collection(collection_name)

        if collection.count() == 0:
            return []

        keywords = self._extract_keywords(query)

        # 1. 키워드 검색: 각 문서의 키워드 매칭 횟수 계산
        doc_scores: dict[str, dict] = {}  # id -> {content, metadata, keyword_hits}

        for keyword in keywords:
            try:
                kw_results = collection.get(
                    where_document={"$contains": keyword},
                    include=["documents", "metadatas"],
                )
                for j, doc_id in enumerate(kw_results["ids"]):
                    if doc_id not in doc_scores:
                        doc_scores[doc_id] = {
                            "content": kw_results["documents"][j],
                            "metadata": kw_results["metadatas"][j],
                            "keyword_hits": 0,
                        }
                    doc_scores[doc_id]["keyword_hits"] += 1
            except Exception:
                pass

        # 키워드 결과를 점수화 (매칭 키워드 수 / 전체 키워드 수)
        search_results: list[dict] = []
        if keywords and doc_scores:
            max_hits = max(d["keyword_hits"] for d in doc_scores.values())
            for doc_id, info in doc_scores.items():
                score = 0.7 + 0.3 * (info["keyword_hits"] / max(len(keywords), 1))
                search_results.append(
                    {
                        "content": info["content"],
                        "metadata": info["metadata"],
                        "similarity": round(score, 3),
                    }
                )

        # 2. 벡터 검색 (키워드 결과가 부족할 때 보조)
        if len(search_results) < top_k:
            try:
                query_embedding = self._embedding.encode([query])[0]
                vector_results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=min(top_k, collection.count()),
                    include=["documents", "metadatas", "distances"],
                )
                seen_contents = {r["content"][:100] for r in search_results}

                if vector_results["documents"] and vector_results["documents"][0]:
                    for i, doc in enumerate(vector_results["documents"][0]):
                        if doc[:100] not in seen_contents:
                            distance = vector_results["distances"][0][i]
                            similarity = 1 - distance
                            search_results.append(
                                {
                                    "content": doc,
                                    "metadata": vector_results["metadatas"][0][i],
                                    "similarity": round(similarity * 0.7, 3),  # 벡터만 매칭: 낮은 가중치
                                }
                            )
                            seen_contents.add(doc[:100])
            except Exception as e:
                logger.warning(f"벡터 검색 실패: {e}")

        # 유사도 순 정렬 후 top_k 반환
        search_results.sort(key=lambda x: x["similarity"], reverse=True)
        return search_results[:top_k]

    @staticmethod
    def _extract_keywords(query: str) -> list[str]:
        """검색 쿼리에서 핵심 키워드를 추출합니다."""
        import re

        # 불용어 제거
        stopwords = {
            "이", "가", "은", "는", "을", "를", "의", "에", "에서", "와", "과",
            "도", "로", "으로", "한", "하는", "있는", "없는", "되는", "된",
            "어떻게", "무엇", "뭐", "좀", "알려", "주세요", "되나요", "인가요",
            "건가요", "할", "수", "규정", "관련", "대해", "것", "해주세요",
        }

        # 단어 분리
        words = re.findall(r"[가-힣]+", query)
        keywords = [w for w in words if w not in stopwords and len(w) >= 2]

        # 동의어 확장
        synonyms = {
            "휴가": ["연차", "연차유급휴가", "유급휴가", "휴가", "휴일"],
            "연차": ["연차", "연차유급휴가", "유급휴가", "휴가"],
            "경조사": ["경조사", "경조", "경조휴가", "결혼", "사망", "조사"],
            "급여": ["임금", "봉급", "급료", "수당", "급여", "상여금"],
            "임금": ["임금", "봉급", "급료", "수당", "급여"],
            "출퇴근": ["출근", "퇴근", "근무시간", "근로시간", "출퇴근"],
            "근무": ["근무", "근무시간", "근로시간", "출근", "퇴근"],
            "해고": ["해고", "징계", "경고", "감봉", "정직"],
            "징계": ["징계", "경고", "감봉", "정직", "해고"],
            "복지": ["복리후생", "사내복지", "복지"],
            "퇴직": ["퇴직", "퇴직금", "퇴직급여"],
            "산재": ["산업재해", "산재", "업무상재해", "재해"],
            "출산": ["출산", "육아", "모성보호", "임신"],
            "수습": ["수습", "시용", "시용기간"],
        }

        expanded = set(keywords)
        for kw in keywords:
            if kw in synonyms:
                expanded.update(synonyms[kw])

        return list(expanded)

    def delete_by_source(self, collection_name: str, source_file: str) -> int:
        """특정 소스 파일의 모든 문서를 삭제합니다."""
        collection = self.get_or_create_collection(collection_name)

        # source 메타데이터로 필터링하여 삭제
        results = collection.get(
            where={"source": source_file},
            include=[],
        )

        if results["ids"]:
            collection.delete(ids=results["ids"])
            logger.info(
                f"벡터 저장소에서 {len(results['ids'])}개 문서 삭제 (소스: {source_file})"
            )
            return len(results["ids"])

        return 0

    def get_collection_count(self, collection_name: str) -> int:
        """컬렉션의 문서 수를 반환합니다."""
        collection = self.get_or_create_collection(collection_name)
        return collection.count()
