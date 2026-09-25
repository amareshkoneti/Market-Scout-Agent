import json
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from llm.nvidia_client import invoke_llm

logger = logging.getLogger(__name__)


def _parse_query_response(raw_response: str, attempted: List[str]) -> List[str]:
    """Extract usable queries when the model adds prose around its answer."""
    import re

    text = (raw_response or "").strip()
    candidates = []

    # Prefer a complete JSON object, even when it is preceded by reasoning or
    # wrapped in a markdown fence.
    json_candidates = re.findall(r"\{.*?\}", text, flags=re.DOTALL)
    for candidate in json_candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("queries"), list):
            candidates.extend(parsed["queries"])
            break

    # Nemotron can emit its answer as quoted bullet points after a reasoning
    # trace. This keeps a malformed response useful without accepting prose.
    if not candidates:
        candidates = re.findall(
            r"(?:^|\n)\s*(?:[-*]\s*|\d+[.)]\s*)[\"']([^\"']+)[\"']",
            text,
        )

    clean_queries = []
    attempted_normalized = {query.strip().casefold() for query in attempted}
    for query in candidates:
        if not isinstance(query, str):
            continue
        query = query.strip()
        if query and query.casefold() not in attempted_normalized and query not in clean_queries:
            clean_queries.append(query)

    return clean_queries


async def plan_queries(
    company: str,
    feedback: Optional[str] = None,
    memory: Optional[Dict[str, Any]] = None,
) -> List[str]:
    """
    Planning brain of the Search Agent.

    Responsibilities:
    - Generate NEW search queries (Tavily-compatible plain language)
    - Respect memory (avoid repeats)
    - Return structured output
    - Fail safely if LLM misbehaves
    """

    attempted = memory.get("attempted_queries", []) if memory else []

    # Inject current date so the LLM doesn't hallucinate old year ranges
    current_month_year = datetime.now().strftime("%B %Y")   # e.g. "April 2026"

    prompt = f"""
Generate exactly 4 search queries for {company}.
Find technical updates released in the last 7 days: APIs, SDKs, models,
platform changes, or infrastructure.

Constraints:
- Plain-language search terms only; no search operators.
- Mention {current_month_year}, this week, or past week in each query.
- Every query must use a different technical angle.
- Do not repeat any attempted query: {attempted}

Return only this JSON object. Do not explain your reasoning, preface the
object, use markdown, or output any other characters:
{{"queries":["query 1","query 2","query 3","query 4"]}}
"""

    if feedback:
        prompt += f"\n\nFeedback from previous iteration (previous queries returned no results):\n{feedback}\nTry completely different query angles.\n"

    # 1️⃣ LLM call (always returns STRING)
    raw_response = await invoke_llm(
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a search planner and JSON-only API. Never reveal reasoning. "
                    "Return the requested object as the first and only output."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.3,
        max_tokens=300,
    )

    logger.debug("SEARCH PLANNER — Raw LLM output:\n%s", raw_response)

    clean_queries = _parse_query_response(raw_response, attempted)

    fallback_queries = [
        f"{company} API release notes {current_month_year}",
        f"{company} AI model launch past week",
        f"{company} developer SDK updates {current_month_year}",
        f"{company} cloud platform infrastructure news this week",
    ]
    attempted_normalized = {query.strip().casefold() for query in attempted}
    for query in fallback_queries:
        if len(clean_queries) >= 4:
            break
        if query.casefold() not in attempted_normalized and query not in clean_queries:
            clean_queries.append(query)

    if not clean_queries:
        logger.error("SEARCH PLANNER — No usable queries in response:\n%s", raw_response)
        raise RuntimeError("Search planner returned no usable queries")

    logger.info(
        "SEARCH PLANNER — Generated %d queries for %s",
        len(clean_queries),
        company,
    )

    return clean_queries