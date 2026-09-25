import json
import re
from typing import List, Dict

from llm.nvidia_client import invoke_llm


BATCH_SIZE = 5


def _parse_classifications(raw_response: str, count: int) -> List[bool]:
    for candidate in re.findall(r"\[.*?\]", raw_response or "", flags=re.DOTALL):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(parsed, list):
            continue

        results = [False] * count
        for item in parsed:
            if not isinstance(item, dict):
                continue
            idx = item.get("id")
            technical = item.get("technical")
            if isinstance(idx, int) and 0 <= idx < count and isinstance(technical, bool):
                results[idx] = technical
        return results

    return [False] * count


async def batch_is_technical(
    articles: List[Dict]
) -> List[bool]:

    if not articles:
        return []

    article_blocks = []

    for idx, article in enumerate(articles):

        title = article.get("title", "")

        text = (
            article.get("text", "")
            or article.get("article_text", "")
        )

        trimmed_text = text[:800]

        article_blocks.append(
            f"""
ID: {idx}

TITLE:
{title}

TEXT:
{trimmed_text}
"""
        )

    joined_articles = "\n\n".join(article_blocks)

    prompt = f"""
Determine whether each article below contains REAL technical updates.

Technical updates include:
- APIs
- SDKs
- AI models
- infra/platform releases
- developer tools
- engineering announcements
- technical product launches

Reject:
- marketing
- stock news
- opinions
- general news
- vague announcements

Respond only with this JSON array. Do not explain your reasoning or use markdown:
[{{"id":0,"technical":true}},{{"id":1,"technical":false}}]

ARTICLES:
{joined_articles}
"""

    raw_response = await invoke_llm(
        [
            {
                "role": "system",
                "content": "You are a JSON-only article classifier. Do not reveal reasoning.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=256,
    )

    if isinstance(raw_response, list):
        raw_response = json.dumps(raw_response)
    return _parse_classifications(raw_response, len(articles))