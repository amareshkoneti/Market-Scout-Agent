"""
Market Intelligence Scout — Enterprise NVIDIA LLM Gateway

Features:
    • Multiple API key pool
    • Round-robin load balancing
    • Automatic cooldown on 429 errors
    • Semaphore-based concurrency control
    • Retry with exponential backoff
    • Prometheus metrics
    • Centralized enterprise-grade LLM gateway
"""

import logging
import time
import threading
import asyncio
from weakref import WeakKeyDictionary

from itertools import cycle
from typing import List, Dict, Optional

from openai import OpenAI
from app.config import settings
from observability.metrics import (
    LLM_CALL_COUNT,
    LLM_LATENCY,
    LLM_TOKEN_USAGE,
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────

# Add multiple keys in .env:
# NVIDIA_API_KEYS=key1,key2,key3

RAW_KEYS = getattr(settings, "NVIDIA_API_KEYS", "")

API_KEYS = [
    key.strip()
    for key in RAW_KEYS.split(",")
    if key.strip()
]

if not API_KEYS:
    raise RuntimeError(
        "NVIDIA_API_KEYS not configured."
    )

# Round-robin iterator
_key_cycle = cycle(API_KEYS)

# Thread lock for safe concurrent access
_key_lock = threading.Lock()

# Cooldown tracker
# Example:
# {
#   "key1": 1712345678
# }
_cooldown_keys = {}

# Per-event-loop concurrency limiter
# IMPORTANT:
# Avoid binding an asyncio.Semaphore to a different event loop
_loop_semaphores = WeakKeyDictionary()

# Cache clients per key
_clients = {}

# ─────────────────────────────────────────────────────────────
# CLIENT MANAGEMENT
# ─────────────────────────────────────────────────────────────

def _get_client(api_key: str) -> OpenAI:

    if api_key not in _clients:

        _clients[api_key] = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key,
            timeout=30.0,
        )

    return _clients[api_key]

def _get_loop_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _loop_semaphores.get(loop)

    if sem is None:
        sem = asyncio.Semaphore(3)
        _loop_semaphores[loop] = sem

    return sem

# ─────────────────────────────────────────────────────────────
# API KEY MANAGEMENT
# ─────────────────────────────────────────────────────────────

def _get_next_available_key() -> str:

    with _key_lock:

        checked = 0

        while checked < len(API_KEYS):

            key = next(_key_cycle)

            cooldown_until = _cooldown_keys.get(key)

            # Key available
            if cooldown_until is None:
                return key

            # Cooldown expired
            if time.time() > cooldown_until:
                del _cooldown_keys[key]
                return key

            checked += 1

    raise RuntimeError(
        "All NVIDIA API keys are currently cooling down."
    )


def _mark_key_cooldown(
    api_key: str,
    cooldown_seconds: int = 60,
):

    _cooldown_keys[api_key] = (
        time.time() + cooldown_seconds
    )

    logger.warning(
        "API key entered cooldown for %ds",
        cooldown_seconds,
    )


# ─────────────────────────────────────────────────────────────
# AGENT NAME INFERENCE
# ─────────────────────────────────────────────────────────────

def _infer_agent_name(
    messages: List[Dict[str, str]]
) -> str:

    if not messages:
        return "unknown"

    system_msg = (
        messages[0]
        .get("content", "")
        .lower()
    )

    if "security" in system_msg:
        return "guardrails"

    if "search" in system_msg:
        return "search_planner"

    if "content classifier" in system_msg:
        return "content_filter"

    if "credibility" in system_msg:
        return "authority_check"

    if "extraction" in system_msg:
        return "feature_extraction"

    if "intelligence analyst" in system_msg:
        return "synthesis"

    return "unknown"


# ─────────────────────────────────────────────────────────────
# MAIN LLM INVOCATION
# ─────────────────────────────────────────────────────────────

async def invoke_llm(
    messages: List[Dict[str, str]],
    temperature: float = settings.LLM_TEMPERATURE,
    max_tokens: int = settings.LLM_MAX_TOKENS,
    retries: int = settings.MAX_RETRIES,
) -> str:

    last_error = None

    agent_name = _infer_agent_name(messages)

    for attempt in range(1, retries + 1):

        api_key = _get_next_available_key()

        client = _get_client(api_key)

        start_time = time.time()

        try:

            async with _get_loop_semaphore():

                response = await asyncio.to_thread(
                    client.chat.completions.create,

                    model=settings.LLM_MODEL,

                    messages=messages,

                    temperature=temperature,

                    max_tokens=max_tokens,

                    top_p=settings.LLM_TOP_P,

                    extra_body={
                        "chat_template_kwargs": {
                            "enable_thinking": settings.LLM_ENABLE_THINKING,
                        }
                    },
                )

            duration = time.time() - start_time

            content = (
                response
                .choices[0]
                .message.content
            )

            # ── Metrics ─────────────────────

            LLM_CALL_COUNT.labels(
                agent_name=agent_name,
                status="success"
            ).inc()

            LLM_LATENCY.labels(
                agent_name=agent_name
            ).observe(duration)

            if response.usage:

                LLM_TOKEN_USAGE.labels(
                    agent_name=agent_name,
                    token_type="prompt"
                ).inc(response.usage.prompt_tokens)

                LLM_TOKEN_USAGE.labels(
                    agent_name=agent_name,
                    token_type="completion"
                ).inc(response.usage.completion_tokens)

            logger.info(
                "LLM SUCCESS | key=%s | agent=%s | duration=%.2fs",
                api_key[-6:],
                agent_name,
                duration,
            )

            return content

        except Exception as exc:

            duration = time.time() - start_time

            last_error = exc

            error_text = str(exc)

            # ── Metrics ─────────────────────

            LLM_CALL_COUNT.labels(
                agent_name=agent_name,
                status="retry"
            ).inc()

            LLM_LATENCY.labels(
                agent_name=agent_name
            ).observe(duration)

            # ── Handle Rate Limits ──────────

            if "429" in error_text:

                logger.warning(
                    "429 Rate Limit hit for key ending %s",
                    api_key[-6:]
                )

                _mark_key_cooldown(api_key)

            wait = 2 ** attempt

            logger.warning(
                "LLM RETRY %d/%d | waiting %ds | error=%s",
                attempt,
                retries,
                wait,
                exc,
            )

            if attempt < retries:
                await asyncio.sleep(wait)

    # ─────────────────────────────────────
    # FINAL FAILURE
    # ─────────────────────────────────────

    LLM_CALL_COUNT.labels(
        agent_name=agent_name,
        status="failure"
    ).inc()

    raise RuntimeError(
        f"LLM invocation failed after "
        f"{retries} retries: {last_error}"
    )


# ─────────────────────────────────────────────────────────────
# TOOL CALLING SUPPORT
# ─────────────────────────────────────────────────────────────

async def invoke_llm_with_tools(
    messages: List[Dict[str, str]],
    tools: List[Dict],
    temperature: float = settings.LLM_TEMPERATURE,
    max_tokens: int = settings.LLM_MAX_TOKENS,
):

    api_key = _get_next_available_key()

    client = _get_client(api_key)

    async with _get_loop_semaphore():

        response = await asyncio.to_thread(

            client.chat.completions.create,

            model=settings.LLM_MODEL,

            messages=messages,

            tools=tools,

            tool_choice="auto",

            temperature=temperature,

            max_tokens=max_tokens,

            top_p=settings.LLM_TOP_P,
        )

    return response