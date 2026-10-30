import os
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, Optional

RUNBOOKS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "sample_runbooks" / "runbooks.json"

class HybridVectorStore(ABC):
    @abstractmethod
    def search(
        self,
        query: str,
        service_name: Optional[str] = None,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        pass

class PGVectorStore(HybridVectorStore):
    """
    Production PostgreSQL + PGVector hybrid store.
    Executes single-store relational filtering alongside HNSW cosine distance search.
    """
    def __init__(self, db_url: str):
        self.db_url = db_url

    def search(
        self,
        query: str,
        service_name: Optional[str] = None,
        top_k: int = 3,
        distance_threshold: float = 0.55
    ) -> List[Dict[str, Any]]:
        try:
            import psycopg
        except ImportError:
            raise ImportError("psycopg is required for PGVectorStore. Install via `pip install psycopg[binary]`.")

        sql = """
        SELECT id, service_name, title, content, severity_level,
               (embedding <=> %s::vector) AS cosine_distance
        FROM runbooks
        WHERE (%s IS NULL OR service_name = %s)
          AND (embedding <=> %s::vector) < %s
        ORDER BY cosine_distance ASC
        LIMIT %s;
        """
        # Placeholder mock embedding vector (768 dimensions)
        mock_embedding = [0.01] * 768

        with psycopg.connect(self.db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (
                    mock_embedding,
                    service_name,
                    service_name,
                    mock_embedding,
                    distance_threshold,
                    top_k
                ))
                cols = [desc[0] for desc in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

class LocalHybridStore(HybridVectorStore):
    """
    Zero-dependency embedded vector & keyword store for local execution,
    CI/CD pipelines, and offline evaluation.
    """
    def __init__(self, runbooks_file: Optional[Path] = None):
        self.file_path = runbooks_file or RUNBOOKS_PATH
        self._runbooks = self._load_runbooks()

    def _load_runbooks(self) -> List[Dict[str, Any]]:
        if not self.file_path.exists():
            return []
        with open(self.file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def search(
        self,
        query: str,
        service_name: Optional[str] = None,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        if not self._runbooks:
            self._runbooks = self._load_runbooks()

        candidates = list(self._runbooks)
        if service_name:
            filtered = [rb for rb in candidates if rb.get("service_name") == service_name]
            if filtered:
                candidates = filtered

        query_tokens = set(query.lower().split())
        scored = []
        for rb in candidates:
            text = f"{rb.get('title', '')} {rb.get('content', '')} {' '.join(rb.get('keywords', []))}".lower()
            text_tokens = set(text.split())
            intersection = query_tokens.intersection(text_tokens)
            score = len(intersection)
            scored.append((score, rb))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

def get_vector_store() -> HybridVectorStore:
    db_url = os.getenv("DATABASE_URL")
    if db_url and "postgres" in db_url:
        return PGVectorStore(db_url)
    return LocalHybridStore()
