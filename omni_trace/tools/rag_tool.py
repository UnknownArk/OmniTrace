import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from omni_trace.config import TRANSCRIPTS_PATH
from omni_trace.models import ToolResult
from omni_trace.tools.base import BaseTool

class TranscriptRAGTool(BaseTool):
    name = "search_transcripts"
    description = (
        "Searches show transcripts and scene dialogue. "
        "Supports filtering by episode_id, semantic keyword search, and windowed temporal retrieval "
        "using timestamp_seconds (default +/- 60s tolerance window)."
    )

    def __init__(self, transcripts_path: Optional[str] = None):
        self.transcripts_path = Path(transcripts_path or TRANSCRIPTS_PATH)
        self._chunks: List[Dict[str, Any]] = []
        self._load_transcripts()

    def _load_transcripts(self):
        if not self.transcripts_path.exists():
            self._chunks = []
            return
        with open(self.transcripts_path, "r", encoding="utf-8") as f:
            self._chunks = json.load(f)

    def execute(
        self,
        query: Optional[str] = None,
        episode_id: Optional[int] = None,
        timestamp_seconds: Optional[int] = None,
        window_seconds: int = 60
    ) -> ToolResult:
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

        if episode_id is not None:
            candidates = [c for c in candidates if c.get("episode_id") == episode_id]
            if not candidates:
                return ToolResult(
                    tool_name=self.name,
                    success=True,
                    data=[],
                    row_count=0,
                    is_empty=True,
                    metadata={"message": f"No transcript records exist for episode_id={episode_id}."}
                )

        if timestamp_seconds is not None:
            min_t = max(0, timestamp_seconds - window_seconds)
            max_t = timestamp_seconds + window_seconds
            
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
                            f"(center: {timestamp_seconds}s, window: +/-{window_seconds}s)."
                        )
                    }
                )

        if query and query.strip():
            words = query.lower().split()
            scored = []
            for c in candidates:
                text = f"{c.get('dialogue', '')} {c.get('summary', '')} {c.get('location', '')}".lower()
                matches = sum(1 for w in words if w in text)
                scored.append((matches, c))
            scored.sort(key=lambda x: x[0], reverse=True)
            candidates = [item[1] for item in scored if item[0] > 0] or candidates[:3]

        return ToolResult(
            tool_name=self.name,
            success=True,
            data=candidates[:5],
            row_count=len(candidates[:5]),
            is_empty=(len(candidates) == 0),
            metadata={
                "filters": {
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
    tool = TranscriptRAGTool()
    return tool.execute(
        query=query,
        episode_id=episode_id,
        timestamp_seconds=timestamp_seconds,
        window_seconds=window_seconds
    ).model_dump()
