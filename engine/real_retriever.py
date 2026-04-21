"""
Real Retriever cho Lab 14.

Thay thế `_simulate_retrieval` giả trong MainAgent bằng retrieval THẬT từ ChromaDB.
Hỗ trợ 3 tầng fallback để mọi máy trong nhóm đều chạy được:

  Tier 1 (ưu tiên nhất): Dùng code Lab 8 sẵn có — `from index import get_embedding, CHROMA_DB_DIR`
  Tier 2: Nếu có OPENAI_API_KEY — embed query bằng text-embedding-3-small rồi query ChromaDB
  Tier 3 (offline fallback): Dùng BM25 trên các documents đã lưu trong ChromaDB

Tất cả đều trả về cùng một interface → MainAgent không cần biết đang dùng tầng nào.
"""

from __future__ import annotations

import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Tuple

CHROMA_DB_DIR = "./chroma_db"
COLLECTION_NAME = "rag_lab"


def _normalize_vn(text: str) -> str:
    """Bỏ dấu tiếng Việt + lowercase — dùng cho BM25 tokenizer."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


def _tokenize(text: str) -> List[str]:
    """Tokenizer đơn giản cho cả tiếng Việt (đã bỏ dấu) và tiếng Anh."""
    normalized = _normalize_vn(text)
    tokens = re.findall(r"[a-z0-9]+", normalized)
    return [t for t in tokens if len(t) > 1]


class RealRetriever:
    """
    Retriever với 3-tier fallback.

    Cách dùng:
        r = RealRetriever()
        results = r.retrieve("Làm sao đổi mật khẩu?", top_k=5)
        # results = [{"id": "...", "text": "...", "score": 0.87, "metadata": {...}}, ...]

    Reranking:
        r = RealRetriever(rerank=True)  # bật MMR-lite reranking cho V2
    """

    def __init__(self, rerank: bool = False):
        self.rerank = rerank
        self.mode: str = "uninitialized"
        self._collection = None
        self._get_embedding = None
        self._bm25 = None
        self._bm25_ids: List[str] = []
        self._bm25_docs: List[str] = []
        self._bm25_metas: List[Dict[str, Any]] = []
        self._init_retriever()

    # ---------- Khởi tạo 3 tầng ----------

    def _init_retriever(self) -> None:
        """Thử lần lượt 3 tầng, dùng tầng nào hoạt động được."""
        # Tier 1: Code Lab 8 của đội — từ `index.py`
        if self._try_init_lab8():
            self.mode = "tier1_lab8_index"
            return

        # Tier 2: OpenAI embedding trực tiếp
        if self._try_init_openai():
            self.mode = "tier2_openai_embedding"
            return

        # Tier 3: BM25 offline fallback
        self._init_bm25()
        self.mode = "tier3_bm25_offline"

    def _try_init_lab8(self) -> bool:
        """Cố import `get_embedding` và `CHROMA_DB_DIR` từ index.py của Lab 8."""
        try:
            import importlib

            index_mod = importlib.import_module("index")
            self._get_embedding = getattr(index_mod, "get_embedding", None)
            chroma_dir = getattr(index_mod, "CHROMA_DB_DIR", CHROMA_DB_DIR)
            if not callable(self._get_embedding):
                return False

            import chromadb

            client = chromadb.PersistentClient(path=str(chroma_dir))
            self._collection = client.get_collection(COLLECTION_NAME)
            # Sanity check: thử embed một câu
            _ = self._get_embedding("test")
            return True
        except Exception:
            self._get_embedding = None
            self._collection = None
            return False

    def _try_init_openai(self) -> bool:
        """Dùng OpenAI embeddings trực tiếp nếu có OPENAI_API_KEY."""
        if not os.getenv("OPENAI_API_KEY"):
            return False
        try:
            from openai import OpenAI
            import chromadb

            self._openai_client = OpenAI()
            self._openai_model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

            def _embed(text: str) -> List[float]:
                resp = self._openai_client.embeddings.create(
                    model=self._openai_model, input=text
                )
                return resp.data[0].embedding

            self._get_embedding = _embed
            client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
            self._collection = client.get_collection(COLLECTION_NAME)
            _ = self._get_embedding("test")
            return True
        except Exception:
            self._get_embedding = None
            self._collection = None
            return False

    def _init_bm25(self) -> None:
        """
        Fallback cuối: build BM25 index từ documents đã lưu sẵn trong ChromaDB.

        Điều quan trọng: CHROMA_DB vẫn là nguồn sự thật cho doc IDs + content,
        chúng ta chỉ thay cơ chế matching từ vector → keyword-based BM25.
        Hit Rate / MRR vẫn có nghĩa vì doc IDs vẫn đúng format golden set.
        """
        from rank_bm25 import BM25Okapi

        try:
            import chromadb

            client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
            col = client.get_collection(COLLECTION_NAME)
            data = col.get(include=["documents", "metadatas"])
            self._bm25_ids = list(data["ids"])
            self._bm25_docs = list(data["documents"])
            self._bm25_metas = list(data["metadatas"])
        except Exception as e:
            # Không có ChromaDB → không thể retrieve gì cả
            raise RuntimeError(
                f"Không đọc được ChromaDB tại '{CHROMA_DB_DIR}'. "
                f"Hãy chắc chắn chroma_db/ tồn tại và có collection '{COLLECTION_NAME}'. "
                f"Lỗi gốc: {e}"
            )

        tokenized = [_tokenize(doc) for doc in self._bm25_docs]
        self._bm25 = BM25Okapi(tokenized)

    # ---------- API chính ----------

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Trả list chunks theo thứ tự giảm dần của độ liên quan."""
        if self._collection is not None and self._get_embedding is not None:
            results = self._retrieve_vector(query, top_k * 2 if self.rerank else top_k)
        else:
            results = self._retrieve_bm25(query, top_k * 2 if self.rerank else top_k)

        if self.rerank and len(results) > top_k:
            results = self._mmr_rerank(query, results, top_k)
        return results[:top_k]

    def _retrieve_vector(self, query: str, n: int) -> List[Dict[str, Any]]:
        query_emb = self._get_embedding(query)
        raw = self._collection.query(
            query_embeddings=[query_emb],
            n_results=min(n, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for doc_id, doc, meta, dist in zip(
            raw["ids"][0],
            raw["documents"][0],
            raw["metadatas"][0],
            raw["distances"][0],
        ):
            out.append({
                "id": doc_id,
                "text": doc,
                "metadata": meta or {},
                "score": max(0.0, 1.0 - float(dist)),  # cosine: dist→score
            })
        return out

    def _retrieve_bm25(self, query: str, n: int) -> List[Dict[str, Any]]:
        tokens = _tokenize(query)
        if not tokens or self._bm25 is None:
            return []
        scores = self._bm25.get_scores(tokens)
        max_score = max(scores) if len(scores) > 0 else 1.0
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:n]
        out = []
        for idx, score in ranked:
            if score <= 0:
                continue
            out.append({
                "id": self._bm25_ids[idx],
                "text": self._bm25_docs[idx],
                "metadata": self._bm25_metas[idx] or {},
                "score": float(score / max_score) if max_score > 0 else 0.0,
            })
        return out

    def _mmr_rerank(
        self, query: str, candidates: List[Dict[str, Any]], top_k: int, lambda_mult: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        MMR-lite reranking (V2 improvement):
          - Cân bằng relevance (score gốc) vs diversity (overlap token với chunks đã chọn)
          - Giảm hallucination vì không trả về 5 chunks quá giống nhau
        """
        if not candidates:
            return candidates
        selected: List[Dict[str, Any]] = []
        remaining = candidates.copy()
        while remaining and len(selected) < top_k:
            if not selected:
                best = remaining.pop(0)
                selected.append(best)
                continue

            def mmr_score(cand):
                relevance = cand["score"]
                cand_tokens = set(_tokenize(cand["text"]))
                max_sim = 0.0
                for s in selected:
                    s_tokens = set(_tokenize(s["text"]))
                    if cand_tokens and s_tokens:
                        sim = len(cand_tokens & s_tokens) / max(len(cand_tokens | s_tokens), 1)
                        max_sim = max(max_sim, sim)
                return lambda_mult * relevance - (1 - lambda_mult) * max_sim

            remaining.sort(key=mmr_score, reverse=True)
            selected.append(remaining.pop(0))
        return selected


# ---------- Smoke test ----------
if __name__ == "__main__":
    r = RealRetriever()
    print(f"Retriever mode: {r.mode}")
    for q in [
        "Làm thế nào để đổi mật khẩu?",
        "Chính sách hoàn tiền sau bao nhiêu ngày?",
        "Thời gian xử lý P1 SLA là gì?",
    ]:
        print(f"\nQuery: {q}")
        for hit in r.retrieve(q, top_k=3):
            print(f"  [{hit['score']:.3f}] {hit['id']}: {hit['text'][:80]}...")
