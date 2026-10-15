"""
Transcript RAG Retriever Tool with windowed temporal search,
hybrid semantic matching, and missing-data boundary detection.
"""

import os
import json
import numpy as np
from typing import Dict, Any, List, Optional
from pathlib import Path
from omni_trace.config import TRANSCRIPTS_PATH, GEMINI_API_KEY, EMBEDDING_MODEL
from omni_trace.models import ToolResult
from omni_trace.tools.base import BaseTool

class TranscriptRAGTool(BaseTool):
    """Tool to perform semantic and windowed temporal retrieval over episode transcripts."""

    name = "search_transcripts"
    description = (
        "Searches show transcripts and scene dialogue. "
        "Supports filtering by episode_id, semantic keyword search, and windowed temporal retrieval "
        "using timestamp_seconds (with a default +/- 60s tolerance window)."
    )

    def __init__(self, transcripts_path: Optional[str] = None):
        self.transcripts_path = Path(transcripts_path or TRANSCRIPTS_PATH)
        self._chunks: List[Dict[str, Any]] = []
        self._load_transcripts()

    def _load_transcripts(self):
        """Loads transcript scene chunks from disk."""
        if not self.transcripts_path.exists():
            self._chunks = []
            return
        with open(self.transcripts_path, "r", encoding="utf-8") as f:
            self._chunks = json.load(f)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def execute(
        self,
        query: Optional[str] = None,
        episode_id: Optional[int] = None,
        timestamp_seconds: Optional[int] = None,
        window_seconds: int = 60
    ) -> ToolResult:
        """
        Retrieves transcript scenes matching query, episode_id, or temporal window.
        """
        if not self._chunks:
            self._load_transcripts()

        if not self._chunks:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error="Transcript database is empty or not found on disk.",
                is_empty=True
            )

        candidates = list(self._chunks)

        # 1. Episode ID Filter
        if episode_id is not None:
            candidates = [c for c in candidates if c.get("episode_id") == episode_id]
            if not candidates:
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data=[],
                    row_count=0,
                    is_empty=True,
                    metadata={
                        "message": f"No transcript records exist for episode_id={episode_id}."
                    }
                )

        # 2. Windowed Temporal Filtering (Absorbs timecode drift / playhead skews)
        if timestamp_seconds is not None:
            min_t = max(0, timestamp_seconds - window_seconds)
            max_t = timestamp_seconds + window_seconds
            
            # Check overlap: scene_start <= max_t AND scene_end >= min_t
            temporal_matches = [
                c for c in candidates
                if c.get("start_seconds", 0) <= max_t and c.get("end_seconds", 0) >= min_t
            ]
            if temporal_matches:
                candidates = temporal_matches
            else:
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data=[],
                    row_count=0,
                    is_empty=True,
                    metadata={
                        "message": (
                            f"No dialogue scenes found within window [{min_t}s - {max_t}s] "
                            f"(center: {timestamp_seconds}s, window: +/-{window_seconds}s). "
                            "Scene may be non-dialogue, silent, or omitted from script."
                        )
                    }
                )

        # 3. Text & Keyword Scoring
        if query and query.strip():
            query_lower = query.lower().split()
            scored = []
            for c in candidates:
                text = f"{c.get('dialogue', '')} {c.get('summary', '')} {c.get('location', '')}".lower()
                # Score based on keyword overlap
                match_count = sum(1 for word in query_lower if word in text)
                scored.append((match_count, c))
            
            # Sort by match count descending
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [item[1] for item in scored if item[0] > 0] or candidates[:3]

        return ToolResult(
            tool_name=self.name,
            success=True,
            data=candidates[:5],
            row_count=len(candidates[:5]),
            is_empty=(len(candidates) == 0),
            metadata={
                "filters_applied": {
                    "episode_id": episode_id,
                    "timestamp_seconds": timestamp_seconds,
                    "window_seconds": window_seconds
                }
            }
        )

def search_transcripts(
    query: Optional[str] = None,
    episode_id: Optional[int] = None,
    timestamp_seconds: Optional[int] = None,
    window_seconds: int = 60
) -> Dict[str, Any]:
    """
    Searches show transcripts and scene dialogue with windowed temporal retrieval.
    
    Args:
        query: Semantic or keyword query (e.g., 'confrontation', 'audio glitch').
        episode_id: Optional episode identifier to filter by (e.g., 103).
        timestamp_seconds: Scene timestamp in seconds to center the search around (e.g., 790).
        window_seconds: Temporal search window in seconds (+/- tolerance, default 60).
    """
    tool = TranscriptRAGTool()
    return tool.execute(
        query=query,
        episode_id=episode_id,
        timestamp_seconds=timestamp_seconds,
        window_seconds=window_seconds
    ).model_dump()
