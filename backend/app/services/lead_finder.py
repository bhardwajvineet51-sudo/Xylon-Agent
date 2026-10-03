"""Lead Researcher: web-search candidate companies, then VERIFY each one ourselves.
The model proposes; our code checks the site is reachable and extracts contacts only from the page."""
import logging
from concurrent.futures import ThreadPoolExecutor
from . import ai_client, fetcher
from .sanitize import SYSTEM_GUARD

log = logging.getLogger("xylon.finder")


def search(req: dict) -> tuple[list[dict], list[str]]:
    system = SYSTEM_GUARD + "\nYou are a B2B lead researcher for Xylon Technology, a web/AI/automation agency."
    user = (
        f"Find up to {req['count'] + 5} real companies using web search.\n"
        f"Industry: {req['industry']}\nCountry: {req['country']}\nRegion/city: {req.get('region') or 'any'}\n"
        f"Company size: {req.get('company_size') or 'any'}\nKeywords: {req.get('keywords') or 'none'}\n"
        f"Service they may need: {req.get('service') or 'any relevant'}\n"
        f"Must have a website: {req['require_website']}\n"
        f"Must show recent public activity (last 12 months): {req['recent_activity']}\n\n"
        "Return JSON: {\"companies\":[{\"name\":str,\"website\":str,\"country\":str,\"industry\":str,"
        "\"description\":str (what they do, from sources),\"source_url\":str (page where you found them),"
        "\"reason\":str (why they MAY need the service; this is your inference)}]}\n"
        "Only include companies you found in search results. Do NOT include email addresses or phone numbers."
    )
    data, urls = ai_client.search_call(system, user)
    items = data.get("companies", data) if isinstance(data, dict) else data
    return [i for i in items if isinstance(i, dict) and i.get("name")], urls


def verify(c: dict, require_website: bool) -> dict | None:
    """Fetch homepage (+ a contact page if linked). Returns enriched candidate or None to drop."""
    try:
        site = fetcher.normalize_url(c.get("website", ""))
    except fetcher.FetchError:
        return None if require_website else {**c, "website": None, "domain": c["name"].lower(), "contacts": None}
    try:
        home = fetcher.fetch(site)
        if home["status"] >= 400:
            raise fetcher.FetchError("bad status")
    except fetcher.FetchError:
        return None  # unreachable site: don't present it as a verified lead
    contact = fetcher.extract_contacts(home["html"], home["url"])
    if not (contact["emails"] or contact["phones"]):
        for u in fetcher.find_links(home["html"], home["url"], ["contact"])[:1]:
            try:
                contact = fetcher.extract_contacts(fetcher.fetch(u)["html"], u)
            except fetcher.FetchError:
                pass
    return {**c, "website": home["url"], "domain": fetcher.domain_of(home["url"]), "contacts": contact}


def verify_all(cands: list[dict], req: dict) -> list[dict]:
    seen, uniq = set(), []
    for c in cands:
        k = (c.get("website") or c["name"]).lower()
        if k not in seen:
            seen.add(k); uniq.append(c)
    with ThreadPoolExecutor(max_workers=5) as ex:
        res = [r for r in ex.map(lambda c: verify(c, req["require_website"]), uniq) if r]
    dedup, doms = [], set()
    for r in res:
        if r["domain"] not in doms:
            doms.add(r["domain"]); dedup.append(r)
    return dedup[: req["count"]]
