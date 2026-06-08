"""
RAG 파이프라인 서비스
- KURE-v1 임베딩 모델 (HuggingFace)
- ChromaDB 벡터스토어
- 유사 법률 조항 / 판례 검색
"""
import glob
import json
from functools import lru_cache

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma

from app.core.exceptions import AppException

# ── 설정 ────────────────────────────────────────────────────
KURE_MODEL_NAME = "nlpai-lab/KURE-v1"  # KURE-v1
CHROMA_DB_PATH = "./db_store"
COLLECTION_NAME = "legal_clauses"
LEGAL_DOCS_PATH = "./data/legal_docs"


# ── 싱글톤 ──────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _get_embedding_model() -> HuggingFaceEmbeddings:
    """KURE-v1 임베딩 모델 로드 (앱 시작 시 1회)"""
    return HuggingFaceEmbeddings(
        model_name=KURE_MODEL_NAME,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


@lru_cache(maxsize=1)
def _get_vectorstore() -> Chroma:
    """ChromaDB 벡터스토어 로드 (앱 시작 시 1회)"""
    return Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=_get_embedding_model(),
        persist_directory=CHROMA_DB_PATH,
    )


# ── 핵심 함수 ────────────────────────────────────────────────

def search_relevant_clauses(masked_text: str, n_results: int = 5) -> list[dict]:
    """
    마스킹된 계약서 텍스트로 유사 법률 조항 / 판례 검색

    Args:
        masked_text: 비식별화된 계약서 텍스트
        n_results: 반환할 최대 결과 수

    Returns:
        [
            {
                "content": "관련 법률 조항 내용",
                "law": "주택임대차보호법 제3조",
                "category": "보증금",
                "score": 0.87
            },
            ...
        ]
    """
    try:
        vectorstore = _get_vectorstore()
        results = vectorstore.similarity_search_with_score(
            query=masked_text,
            k=n_results,
        )

        return [
            {
                "content": doc.page_content,
                "law": doc.metadata.get("law", ""),
                "category": doc.metadata.get("category", ""),
                "is_legal_basis": doc.metadata.get("is_legal_basis", False),
                "score": float(score),
            }
            for doc, score in results
        ]

    except Exception as e:
        raise AppException(500, "SERVER_ERROR", f"RAG 검색 실패: {str(e)}")


# ── 초기 데이터 로드 ─────────────────────────────────────────

def load_legal_documents() -> None:
    """
    법률 데이터를 ChromaDB에 임베딩하여 저장
    서버 최초 실행 시 1회 실행 (main.py startup 이벤트에서 호출)

    데이터 형식 (data/legal_docs/*.json):
    [
        {
            "content": "임대인은 임차인이 임대차 기간이 끝나기 전...",
            "law": "주택임대차보호법 제6조",
            "category": "계약갱신"
        },
        ...
    ]
    """
    vectorstore = _get_vectorstore()

    # 이미 데이터가 있으면 스킵
    if vectorstore._collection.count() > 0:
        print(f"[RAG] 기존 데이터 {vectorstore._collection.count()}건 유지")
        return

    json_files = glob.glob(f"{LEGAL_DOCS_PATH}/*.json")

    if not json_files:
        print(f"[RAG] 경고: 법률 데이터 없음 ({LEGAL_DOCS_PATH})")
        return

    documents = []
    for filepath in json_files:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        for item in data:
            documents.append(
                Document(
                    page_content=item["content"],
                    metadata={
                        "law": item.get("law", ""),
                        "category": item.get("category", ""),
                        "is_legal_basis": item.get("is_legal_basis", False),
                    },
                )
            )

    vectorstore.add_documents(documents)
    print(f"[RAG] 법률 데이터 {len(documents)}건 임베딩 완료")