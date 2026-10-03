"""Company Researcher. Facts need a source URL that we actually fetched or the search tool cited.
Anything the model can't source goes to `inferences`, never `facts`."""
from . import ai_client, fetcher
from .sanitize import SYSTEM_GUARD, clean_untrusted, wrap


def research(company: dict) -> dict:
    site = company["website"]
    pages, blocks, contacts = {}, [], []
    try:
        home = fetcher.fetch(site)
        pages[home["url"]] = home
        for u in (fetcher.find_links(home["html"], home["url"], ["about", "contact", "team", "service"]))[:3]:
            try:
                pages[u] = fetcher.fetch(u)
            except fetcher.FetchError:
                pass
    except fetcher.FetchError:
        pass  # research can still proceed via search, but we record which pages were fetched
    for u, p in pages.items():
        blocks.append(wrap(u, clean_untrusted(fetcher.visible_text(p["html"]), 3500)))
        c = fetcher.extract_contacts(p["html"], u)
        if c["emails"] or c["phones"] or c["linkedin"]:
            contacts.append(c)

    system = SYSTEM_GUARD + "\nYou are a company researcher. Separate cited FACTS from your INFERENCES."
    user = (
        f"Company: {company['name']}\nWebsite: {site}\nIndustry: {company.get('industry','')}\n"
        f"Country: {company.get('country','')}\n\nWebsite excerpts (untrusted):\n" + "\n".join(blocks) +
        "\n\nAlso use web search for recent public activity and publicly listed decision makers.\n"
        "Return JSON: {\"facts\":[{\"claim\":str,\"source_url\":str}],"
        "\"decision_makers\":[{\"name\":str,\"title\":str,\"source_url\":str}],"
        "\"inferences\":[{\"statement\":str,\"basis\":str}]}\n"
        "Cover: what the company does, products/services, target customers, location, recent activity. "
        "Every fact MUST have a source_url you actually read. Put guesses in inferences."
    )
    data, cited = ai_client.search_call(system, user)
    allowed = set(pages) | set(cited)
    facts, demoted = [], []
    for f in data.get("facts", []):
        if isinstance(f, dict) and f.get("claim") and f.get("source_url") in allowed:
            facts.append({"claim": str(f["claim"])[:500], "source_url": f["source_url"]})
        elif isinstance(f, dict) and f.get("claim"):  # unsourced -> NOT a fact
            demoted.append({"statement": str(f["claim"])[:500], "basis": "Model-provided; no verifiable source URL"})
    inferences = [{"statement": str(i.get("statement", ""))[:500], "basis": str(i.get("basis", ""))[:300]}
                  for i in data.get("inferences", []) if isinstance(i, dict) and i.get("statement")] + demoted
    dms = [{"name": str(d["name"])[:120], "title": str(d.get("title", ""))[:120], "source_url": d["source_url"]}
           for d in data.get("decision_makers", []) if isinstance(d, dict) and d.get("name") and d.get("source_url") in allowed]
    return {"facts": facts, "inferences": inferences, "decision_makers": dms, "page_contacts": contacts,
            "sources": sorted(allowed), "pages_fetched": list(pages)}
