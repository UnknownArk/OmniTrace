"""
Configuration and settings management for OmniTrace.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
DB_PATH = DATA_DIR / "media_analytics.db"
TRANSCRIPTS_PATH = DATA_DIR / "sample_transcripts" / "transcripts.json"

# Load environment variables
load_dotenv(ROOT_DIR / ".env")
# Fallback to adjacent project env if running in monorepo/workspace
if not os.getenv("GEMINI_API_KEY"):
    load_dotenv(ROOT_DIR.parent / "ats-resume-agent" / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Provider & Model configuration
DEFAULT_PROVIDER = os.getenv("OMNITRACE_PROVIDER", "groq" if GROQ_API_KEY else "gemini")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
FALLBACK_GROQ_MODELS = ["qwen/qwen3.8-27b", "openai/gpt-oss-20b", "openai/gpt-oss-120b"]
EMBEDDING_MODEL = "text-embedding-004"

# Agent safeguards
MAX_RETRY_BUDGET = 3       # Maximum self-healing attempts before graceful abort
MAX_AGENT_TURNS = 8        # Maximum total tool iterations per query
DEFAULT_TIME_WINDOW_SEC = 60 # Windowed temporal retrieval tolerance (+/- 60s)
