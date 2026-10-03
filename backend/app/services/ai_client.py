"""Thin OpenAI wrapper. Server-side only; key comes from env. Failures become clean HTTP errors."""
import json, logging, re
from fastapi import HTTPException
from openai import OpenAI
from ..config import settings

log = logging.getLogger("xylon.ai")


def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise HTTPException(503, "OPENAI_API_KEY is not configured on the server")
    return OpenAI(api_key=settings.openai_api_key, timeout=90)


def parse_json(text: str):
    m = re.search(r"[\{\[]", text or "")
    if not m:
        raise ValueError("no JSON in model output")
    end = max(text.rfind("}"), text.rfind("]"))
    return json.loads(text[m.start(): end + 1])


def json_call(system: str, user: str) -> dict:
    """Plain JSON completion (no browsing). Used for analysis and writing."""
    try:
        r = _client().chat.completions.create(
            model=settings.openai_model, temperature=0.3, response_format={"type": "json_object"},
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        return parse_json(r.choices[0].message.content)
    except HTTPException:
        raise
    except Exception as e:
        log.exception("OpenAI json_call failed")
        raise HTTPException(502, f"AI service error: {type(e).__name__}")


def search_call(system: str, user: str) -> tuple[object, list[str]]:
    """Web-search-enabled call. Returns (parsed JSON, cited URLs actually returned by the search tool)."""
    try:
        r = _client().responses.create(model=settings.openai_model, instructions=system, input=user,
                                       tools=[{"type": "web_search"}])
        urls = []
        for item in r.output:
            for c in getattr(item, "content", None) or []:
                for a in getattr(c, "annotations", None) or []:
                    u = getattr(a, "url", None)
                    if u and u not in urls:
                        urls.append(u)
        return parse_json(r.output_text), urls
    except HTTPException:
        raise
    except Exception as e:
        log.exception("OpenAI search_call failed")
        raise HTTPException(502, f"AI search error: {type(e).__name__}")
