"""Website Auditor: deterministic, measurable checks only. No LLM involved, so no invented findings.
Score = weighted share of PASSED checks among checks that were actually measured."""
import re
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from . import fetcher

CTA_WORDS = re.compile(r"\b(get started|contact us|get a quote|request|book|schedule|call us|free consultation|"
                       r"sign up|buy now|shop now|subscribe|talk to|demo|apply)\b", re.I)
BOOKING = re.compile(r"(book|appointment|schedule|calendly|reserve|booking)", re.I)
TRUST = re.compile(r"(testimonial|reviews?|trusted by|our clients|case stud|certified|accredited|award|"
                   r"years of experience|guarantee)", re.I)

NOT_ASSESSED = ["Visual design / modern UX quality (needs human review)",
                "Real mobile rendering (only the viewport tag is checked)",
                "Core Web Vitals / Lighthouse performance",
                "Security beyond HTTPS (headers, vulnerabilities, malware)",
                "Content quality and keyword rankings"]

# check key -> (what we recommend if it fails, related Xylon service)
FIXES = {
    "viewport": ("Add a responsive viewport and mobile-first layout", "Website Redesign"),
    "title": ("Write a unique, descriptive page title (10-70 chars)", "SEO"),
    "meta_description": ("Add a meta description for search snippets", "SEO"),
    "h1": ("Use exactly one clear H1 that states what the company does", "Website Redesign"),
    "nav": ("Add clear primary navigation", "Website Redesign"),
    "cta": ("Add a prominent call-to-action above the fold", "Website Redesign"),
    "form": ("Add a contact / enquiry form to capture leads", "Lead Generation"),
    "booking": ("Add online booking or scheduling", "Custom Web Applications"),
    "contact_visible": ("Show phone or email in an obvious place", "Website Redesign"),
    "key_pages": ("Add the missing key pages", "Website Development"),
    "trust": ("Add testimonials, case studies or credentials", "Website Redesign"),
    "alt_text": ("Add descriptive alt text to images", "SEO"),
    "og": ("Add Open Graph tags for social sharing", "SEO"),
    "schema": ("Add structured data (schema.org JSON-LD)", "SEO"),
    "robots": ("Publish a robots.txt", "SEO"),
    "sitemap": ("Publish an XML sitemap", "SEO"),
    "https": ("Serve the site over HTTPS", "Maintenance & Support"),
    "speed": ("Reduce page weight / server response time", "Website Redesign"),
    "size": ("Reduce HTML size", "Website Redesign"),
}


def _c(key, label, passed, weight, evidence):
    return {"key": key, "label": label, "passed": passed, "weight": weight, "evidence": evidence}


def run_checks(home: dict, robots_ok: bool | None, sitemap_ok: bool | None) -> list[dict]:
    html, final = home["html"], home["url"]
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    links = [(a.get("href", ""), a.get_text(" ", strip=True).lower()) for a in soup.find_all("a")]
    out = []
    out.append(_c("https", "Served over HTTPS", final.startswith("https://"), 5, f"Final URL: {final}"))
    vp = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    out.append(_c("viewport", "Responsive viewport tag present", bool(vp), 8,
                  f"viewport: {vp.get('content')}" if vp else "No <meta name=viewport> found in homepage HTML"))
    title = (soup.title.string or "").strip() if soup.title else ""
    out.append(_c("title", "Page title 10-70 characters", 10 <= len(title) <= 70, 5, f"Title ({len(title)} chars): {title[:80]!r}"))
    md = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    out.append(_c("meta_description", "Meta description present", bool(md and md.get("content", "").strip()), 5,
                  "Found" if md else "No meta description in homepage HTML"))
    h1s = soup.find_all("h1")
    out.append(_c("h1", "Exactly one H1", len(h1s) == 1, 5, f"{len(h1s)} H1 element(s) found"))
    nav_links = len(soup.select("nav a")) or len(soup.select("header a"))
    out.append(_c("nav", "Navigation with 3+ links", nav_links >= 3, 5, f"{nav_links} links in nav/header"))
    ctas = [t for _, t in links if CTA_WORDS.search(t)] + [b.get_text(" ", strip=True) for b in soup.find_all("button") if CTA_WORDS.search(b.get_text(" "))]
    out.append(_c("cta", "Call-to-action present on homepage", bool(ctas), 8,
                  f"CTA-like text found: {ctas[:3]}" if ctas else "No CTA-style buttons/links detected by keyword scan"))
    forms = [f for f in soup.find_all("form") if f.find(["input", "textarea"])]
    out.append(_c("form", "Form present on homepage", bool(forms), 5, f"{len(forms)} form(s) on homepage (contact page not scanned)"))
    out.append(_c("booking", "Booking / scheduling signal", bool(BOOKING.search(" ".join(t for _, t in links) + " " + " ".join(h for h, _ in links))), 4,
                  "Keyword scan of homepage links"))
    c = fetcher.extract_contacts(html, final)
    out.append(_c("contact_visible", "Email or phone visible on homepage", bool(c["emails"] or c["phones"]), 5,
                  f"emails={c['emails']} phones={c['phones']}"))
    hrefs = " ".join((h + " " + t).lower() for h, t in links)
    wanted = {"about": "about", "contact": "contact", "privacy policy": "privacy", "services/products": r"(service|product|solution)"}
    missing = [k for k, pat in wanted.items() if not re.search(pat, hrefs)]
    out.append(_c("key_pages", "Links to about / contact / privacy / services pages", not missing, 6,
                  "All linked from homepage" if not missing else f"Not linked from homepage: {missing}"))
    out.append(_c("trust", "Trust signals (reviews, clients, credentials)", bool(TRUST.search(text)), 5, "Keyword scan of visible text"))
    imgs = soup.find_all("img")
    if imgs:
        ratio = sum(1 for i in imgs if (i.get("alt") or "").strip()) / len(imgs)
        out.append(_c("alt_text", "80%+ of images have alt text", ratio >= 0.8, 4, f"{ratio:.0%} of {len(imgs)} images"))
    out.append(_c("og", "Open Graph tags", bool(soup.find("meta", property="og:title")), 2, "og:title check"))
    out.append(_c("schema", "Structured data (JSON-LD)", bool(soup.find("script", type="application/ld+json")), 3, "JSON-LD scan"))
    out.append(_c("robots", "robots.txt reachable", robots_ok, 2, "HTTP 200 check" if robots_ok is not None else "Could not fetch"))
    out.append(_c("sitemap", "sitemap.xml reachable", sitemap_ok, 3, "HTTP 200 check" if sitemap_ok is not None else "Could not fetch"))
    out.append(_c("speed", "Homepage downloaded in under 2.5s", home["ms"] < 2500, 4,
                  f"{home['ms']} ms download from our server (a single sample, NOT Core Web Vitals)"))
    out.append(_c("size", "Homepage HTML under 1 MB", home["bytes"] < 1_000_000, 2, f"{home['bytes'] // 1024} KB"))
    return out


def summarize(checks: list[dict]) -> dict:
    measured = [c for c in checks if c["passed"] is not None]
    total = sum(c["weight"] for c in measured)
    got = sum(c["weight"] for c in measured if c["passed"])
    failed = [c for c in measured if not c["passed"]]
    return {
        "score": round(100 * got / total) if total else None,
        "strengths": [f"{c['label']} ({c['evidence']})" for c in measured if c["passed"]],
        "problems": [f"{c['label']} — {c['evidence']}" for c in failed],
        "opportunities": sorted({FIXES[c["key"]][1] for c in failed if c["key"] in FIXES}),
        "recommendations": [FIXES[c["key"]][0] for c in failed if c["key"] in FIXES],
        "not_assessed": NOT_ASSESSED,
    }


def audit_url(url: str) -> dict:
    home = fetcher.fetch(url)
    if home["status"] >= 400:
        raise fetcher.FetchError(f"Homepage returned HTTP {home['status']}")
    origin = f"{urlparse(home['url']).scheme}://{urlparse(home['url']).netloc}"
    def ok(path):
        try:
            return fetcher.fetch(origin + path, max_bytes=50_000, timeout=6)["status"] == 200
        except fetcher.FetchError:
            return None
    checks = run_checks(home, ok("/robots.txt"), ok("/sitemap.xml"))
    return {"url": home["url"], "checks": checks, **summarize(checks)}
