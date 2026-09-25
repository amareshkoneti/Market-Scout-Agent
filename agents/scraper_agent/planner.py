# agents/scraper_agent/planner.py

import json
import logging
import re
from llm.nvidia_client import invoke_llm

logger = logging.getLogger(__name__)

MAX_FAILURES = 3
DEFAULT_ORDER = ["beautifulsoup", "newspaper3k", "playwright"]
VALID_TOOLS = set(DEFAULT_ORDER)


def _parse_order(raw: str) -> list[str]:
    for candidate in re.findall(r"\{.*?\}", raw or "", flags=re.DOTALL):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        order = parsed.get("order") if isinstance(parsed, dict) else None
        if isinstance(order, list):
            valid_order = [tool for tool in order if tool in VALID_TOOLS]
            if set(valid_order) == VALID_TOOLS and len(valid_order) == len(VALID_TOOLS):
                return valid_order
    return []

async def decide_strategy(url: str) -> list[str]:
    prompt = f"""
Choose the best scraping order for this URL: {url}
Use each of these tools exactly once: newspaper3k, beautifulsoup, playwright.
Return only this JSON object, with no reasoning or markdown:
{{"order":["beautifulsoup","newspaper3k","playwright"]}}
"""

    raw = await invoke_llm(
        messages=[
            {
                "role": "system",
                "content": "You are a JSON-only scraping planner. Do not reveal reasoning.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=128,
    )

    # ── DEFENSIVE PARSING ─────────────────────────────
    if not raw:
        logger.warning("PLANNER — Empty LLM response, using default")
        return DEFAULT_ORDER

    if isinstance(raw, dict):
        return raw.get("order", DEFAULT_ORDER)

    if isinstance(raw, str):
        parsed_order = _parse_order(raw)
        if parsed_order:
            return parsed_order
        else:
            logger.warning("PLANNER — Invalid JSON from LLM: %s", raw[:200])

    logger.warning("PLANNER — Fallback to default strategy")
    return DEFAULT_ORDER

def should_stop(memory: dict) -> bool:
    return memory.get("failures", 0) >= MAX_FAILURES