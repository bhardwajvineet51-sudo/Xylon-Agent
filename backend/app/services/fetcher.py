"""SSRF-safe page fetcher + public-contact extraction. All outbound scraping goes through here."""
import ipaddress, re, socket, time
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup

UA = "XylonGrowthBot/1.0 (B2B research; respects robots/ToS; contact via xylon-technology site)"


class FetchError(Exception):
    pass


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise FetchError("Empty URL")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    p = urlparse(raw)
    if not p.hostname or "." not in p.hostname:
        raise FetchError("Invalid URL")
    return f"{p.scheme}://{p.netloc}{p.path or '/'}".rstrip("/") or raw


def domain_of(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _assert_public(url: str):
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise FetchError("Invalid URL")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror:
        raise FetchError("DNS lookup failed")
    for i in infos:
        ip = ipaddress.ip_address(i[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise FetchError("Blocked non-public address")  # SSRF guard


def fetch(url: str, max_bytes: int = 1_500_000, timeout: float = 10) -> dict:
    cur = url
    with httpx.Client(timeout=timeout, follow_redirects=False, headers={"User-Agent": UA}) as c:
        for _ in range(4):  # manual redirects so every hop is re-validated
            _assert_public(cur)
            t0 = time.perf_counter()
            try:
                with c.stream("GET", cur) as r:
                    if r.is_redirect and r.headers.get("location"):
                        cur = urljoin(cur, r.headers["location"])
                        continue
                    buf = b""
                    for chunk in r.iter_bytes():
                        buf += chunk
                        if len(buf) > max_bytes:
                            break
                    return {"url": cur, "status": r.status_code, "ms": int((time.perf_counter() - t0) * 1000),
                            "bytes": len(buf), "html": buf.decode(r.encoding or "utf-8", "replace"),
                            "content_type": r.headers.get("content-type", "")}
            except httpx.HTTPError as e:
                raise FetchError(f"Request failed: {type(e).__name__}")
    raise FetchError("Too many redirects")


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript", "svg"]):
        t.decompose()
    return soup.get_text(" ", strip=True)


EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
JUNK_EMAIL = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp)$|^(sentry|noreply|no-reply)@|example\.com$", re.I)


def extract_contacts(html: str, page_url: str) -> dict:
    """Only returns values literally present on the page. Nothing is guessed or generated."""
    soup = BeautifulSoup(html, "html.parser")
    emails, phones, linkedin = set(), set(), set()
    for a in soup.find_all("a", href=True):
        h = a["href"].strip()
        if h.lower().startswith("mailto:"):
            emails.add(h[7:].split("?")[0].strip())
        elif h.lower().startswith("tel:"):
            phones.add(h[4:].strip())
        elif "linkedin.com/company" in h or "linkedin.com/in/" in h:
            linkedin.add(h.split("?")[0])
    emails |= set(EMAIL_RE.findall(visible_text(html)))
    emails = {e for e in emails if not JUNK_EMAIL.search(e)}
    return {"emails": sorted(emails)[:5], "phones": sorted(phones)[:3], "linkedin": sorted(linkedin)[:3],
            "source_url": page_url}


def find_links(html: str, base: str, keywords: list[str]) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base_dom, out = domain_of(base), []
    for a in soup.find_all("a", href=True):
        full = urljoin(base, a["href"]).split("#")[0]
        if domain_of(full) != base_dom:
            continue
        blob = (a["href"] + " " + a.get_text(" ")).lower()
        if any(k in blob for k in keywords) and full not in out:
            out.append(full)
    return out
