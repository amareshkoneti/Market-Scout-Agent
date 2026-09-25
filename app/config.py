"""
Market Intelligence Scout — Application Configuration

Centralised, validated settings via Pydantic BaseSettings.
All secrets are sourced from environment variables (OWASP A05).
"""

import os
from typing import Set
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # ── Application ────────────────────────────────────────────────
    APP_NAME: str = "Market Intelligence Scout"
    DEBUG: bool = os.getenv("DEBUG", "False") == "True"

    # ── NVIDIA LLM ─────────────────────────────────────────────────
    # NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
    NVIDIA_API_KEYS: str = os.getenv("NVIDIA_API_KEYS", "")

    LLM_MODEL: str = "nvidia/nemotron-3-super-120b-a12b"
    LLM_ENABLE_THINKING: bool = False
    LLM_MAX_TOKENS: int = 4096
    LLM_TEMPERATURE: float = 0.2
    LLM_TOP_P: float = 0.7  

    # ── Search ─────────────────────────────────────────────────────
    TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
    SEARCH_DEPTH: str = "advanced"
    SEARCH_MAX_RESULTS: int = 15

    # ── Hugging Face Inference API ─────────────────────────────────
    HF_API_TOKEN: str = os.getenv("HF_API_TOKEN", "")  # Optional, increases rate limits

    # ── Database ───────────────────────────────────────────────────
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:admin@127.0.0.1:5433/market_db",
    )

    # ── Redis ──────────────────────────────────────────────────────
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    CACHE_EXPIRY: int = 21600           # 6 hours in seconds
    REPORT_CACHE_TTL: int = 21600       # Report cache TTL (6 hours)

    # ── Security / OWASP ───────────────────────────────────────────
    MAX_INPUT_LENGTH: int = 200         # Max characters for company name
    RATE_LIMIT_REQUESTS: int = 10       # Requests per window
    RATE_LIMIT_WINDOW: int = 60         # Window in seconds

    # Keywords that indicate malicious or out-of-scope intent
    BLOCKED_KEYWORDS: Set[str] = {
        "leak", "hack", "confidential", "exploit",
        "password", "internal", "secret", "breach",
        "jailbreak", "ignore previous", "system prompt",
    }

    # Domains allowed for scraping (OWASP A10 — SSRF prevention)
    ALLOWED_DOMAINS: Set[str] = {
        "github.com", "arxiv.org", "huggingface.co",
        "medium.com", "producthunt.com", "techcrunch.com",
        "theverge.com", "venturebeat.com", "wired.com",
        "zdnet.com", "arstechnica.com", "thenewstack.io",
        "infoq.com", "devblogs.microsoft.com",
    }

    # Domain prefixes automatically allowed (docs.*, developer.*, blog.*)
    ALLOWED_DOMAIN_PREFIXES: Set[str] = {
        "docs.", "developer.", "blog.", "engineering.",
        "ai.", "cloud.", "devblogs.", "openai.com",
    }

    # ── Scraping ───────────────────────────────────────────────────
    SCRAPE_TIMEOUT: int = 15            # Seconds per request
    MAX_ARTICLE_LENGTH: int = 8000      # Characters to keep per article
    USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    # ── Verification ───────────────────────────────────────────────
    SBERT_MODEL: str = "all-MiniLM-L6-v2"
    SIMILARITY_THRESHOLD: float = 0.85  # Cosine similarity for clustering

    # ── Pipeline ───────────────────────────────────────────────────
    DATE_WINDOW_DAYS: int = 7           # Only features ≤ 7 days old
    MAX_RETRIES: int = 3                # Retry count for transient failures

    # ── Gmail API Configuration ────────────────────────────────────

    EMAIL_SENDER: str = os.getenv(
        "EMAIL_SENDER",
        ""
    )

    GOOGLE_CREDENTIALS_PATH: str = os.getenv(
        "GOOGLE_CREDENTIALS_PATH",
        "credentials/credentials.json"
    )

    GOOGLE_TOKEN_PATH: str = os.getenv(
        "GOOGLE_TOKEN_PATH",
        "credentials/token.json"
    )

    # Comma-separated browser origins allowed for cross-origin API calls
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "")


settings = Settings()
