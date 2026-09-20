"""
E-Commerce Listing compliance — fetch + deterministic extraction.

Pipeline (per the brief):

    URL -> webpage fetch -> HTML / JSON-LD / visible-text extraction ->
    product image extraction -> [OCR on those images, see ocr_service.py] ->
    [multimodal AI extraction for gaps, see multimodal_service.py] ->
    structured product data -> existing rule_engine.py (unchanged)

This module owns everything up to "structured product data" that can be
done deterministically — fetching the page, pulling JSON-LD/OpenGraph
product schema, collecting product image URLs, and running the SAME regex
patterns declaration_service.py already uses against physical label OCR
text, but against the page's own text. Nothing here decides compliance —
see app/api/routers/inspections.py's ecommerce analyze endpoint, which feeds
everything this module produces into the unmodified rule_engine.py.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.services import declaration_service
from app.services.ocr_service import OcrWord

settings = get_settings()
logger = logging.getLogger("labellens.ecommerce")

_USER_AGENT = (
    "Mozilla/5.0 (compatible; LabelLensComplianceBot/1.0; "
    "+https://labellens.example/bot) - automated Legal Metrology compliance check"
)


@dataclass
class ListingData:
    url: str
    title: str
    description: str
    visible_text: str
    json_ld_products: list[dict] = field(default_factory=list)
    price: str | None = None
    currency: str | None = None
    brand: str | None = None
    gtin: str | None = None
    image_urls: list[str] = field(default_factory=list)
    fetch_error: str | None = None
    used_headless_browser: bool = False


class ListingFetchError(Exception):
    pass


def fetch_listing_html(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ListingFetchError("URL must start with http:// or https://")

    try:
        with httpx.Client(
            timeout=settings.ecommerce_fetch_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ListingFetchError(f"Could not fetch the listing page: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type and "text" not in content_type:
        raise ListingFetchError(f"URL did not return an HTML page (content-type: {content_type or 'unknown'}).")

    return response.text


def fetch_listing_html_rendered(url: str) -> tuple[str, bool]:
    """
    Fetches `url` with a headless Chromium browser (Playwright) so that
    client-side-rendered content is present in the returned HTML — most
    real e-commerce product pages render their price, description, and
    critically their full image gallery via JS after the initial page load,
    none of which a plain HTTP GET (fetch_listing_html above) ever sees.

    Returns (html, used_headless_browser). Falls back to the plain HTTP
    fetch — not a hard failure — if Playwright isn't installed, its
    Chromium browser hasn't been downloaded (`playwright install chromium`,
    a separate step from `pip install`, see backend/README.md), or the
    render fails for any reason (navigation timeout, page crash, etc.), so
    the feature degrades to reduced accuracy on JS-heavy sites rather than
    breaking entirely.
    """
    if not settings.ecommerce_use_headless_browser:
        return fetch_listing_html(url), False

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ListingFetchError("URL must start with http:// or https://")

    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
    except ImportError:
        logger.info("Playwright not installed — falling back to a plain HTTP fetch for %s", url)
        return fetch_listing_html(url), False

    timeout_ms = settings.ecommerce_render_timeout_seconds * 1000
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=_USER_AGENT, viewport={"width": 1366, "height": 900})
                page.set_default_timeout(timeout_ms)
                # "load" rather than "networkidle": many sites keep a
                # background connection open (analytics, websockets) that
                # never goes idle, which would otherwise make every fetch
                # wait for the full timeout. A short bounded wait after
                # "load" lets the initial burst of lazy-loading JS run
                # without risking an indefinite hang.
                nav_response = page.goto(url, wait_until="load", timeout=timeout_ms)
                if nav_response is not None and nav_response.status >= 400:
                    raise ListingFetchError(
                        f"Listing page returned HTTP {nav_response.status}."
                    )                # Scroll through the page once — most product-gallery
                # thumbnails and "load more" images use IntersectionObserver
                # and only populate their real `src` once scrolled into
                # view. This is the concrete fix for "multiple angle images
                # aren't being picked up from the listing".
                try:
                    page.evaluate(
                        "() => new Promise(resolve => { let y = 0; const step = () => { "
                        "window.scrollTo(0, y); y += window.innerHeight; "
                        "if (y < document.body.scrollHeight) setTimeout(step, 200); else resolve(); }; step(); })"
                    )
                except Exception:
                    pass  # best-effort — a scroll failure shouldn't block extraction
                page.wait_for_timeout(800)
                html = page.content()
            finally:
                browser.close()
        return html, True
    except PlaywrightTimeoutError as exc:
        logger.warning("Headless render timed out for %s (%s); falling back to static fetch", url, exc)
        return fetch_listing_html(url), False
    except Exception as exc:
        # Covers "Chromium not installed" (Playwright raises a plain
        # Exception with an install hint for that specific case) and any
        # other render-time failure.
        logger.warning("Headless render failed for %s (%s); falling back to static fetch", url, exc)
        return fetch_listing_html(url), False


def _parse_json_ld(soup: BeautifulSoup) -> list[dict]:
    products: list[dict] = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "{}")
        except (ValueError, TypeError):
            continue
        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            # Some sites nest the actual Product node inside @graph.
            graph = item.get("@graph")
            nodes = graph if isinstance(graph, list) else [item]
            for node in nodes:
                if isinstance(node, dict) and str(node.get("@type", "")).lower() == "product":
                    products.append(node)
    return products


def _extract_price(products: list[dict], soup: BeautifulSoup) -> tuple[str | None, str | None]:
    for product in products:
        offers = product.get("offers")
        offers_list = offers if isinstance(offers, list) else [offers] if offers else []
        for offer in offers_list:
            if isinstance(offer, dict) and offer.get("price"):
                return str(offer["price"]), offer.get("priceCurrency")
    meta = soup.find("meta", attrs={"property": "product:price:amount"})
    currency_meta = soup.find("meta", attrs={"property": "product:price:currency"})
    if meta and meta.get("content"):
        return meta["content"], currency_meta["content"] if currency_meta else None
    return None, None


def _extract_gtin(products: list[dict]) -> str | None:
    for product in products:
        for key in ("gtin13", "gtin12", "gtin8", "gtin", "sku", "mpn"):
            value = product.get(key)
            if value and re.fullmatch(r"\d{8,14}", str(value)):
                return str(value)
    return None


def _extract_images(products: list[dict], soup: BeautifulSoup, base_url: str) -> list[str]:
    urls: list[str] = []

    for product in products:
        image = product.get("image")
        image_list = image if isinstance(image, list) else [image] if image else []
        for img in image_list:
            src = img if isinstance(img, str) else (img.get("url") if isinstance(img, dict) else None)
            if src:
                urls.append(urljoin(base_url, src))

    for meta in soup.find_all("meta", attrs={"property": "og:image"}):
        if meta.get("content"):
            urls.append(urljoin(base_url, meta["content"]))

    # Once the page is rendered (see fetch_listing_html_rendered), gallery
    # thumbnails have usually swapped their real image into `src` — but as
    # a robustness net, also check the common lazy-load/responsive-image
    # attributes real sites use so this still works even on a static fetch.
    for img in soup.find_all("img"):
        hint = " ".join(str(img.get(attr, "")) for attr in ("class", "id", "alt")).lower()
        if not any(k in hint for k in ("product", "gallery", "zoom", "main-image", "thumb")):
            continue
        for attr in ("src", "data-src", "data-old-hires", "data-zoom-image", "data-a-dynamic-image"):
            value = img.get(attr)
            if not value:
                continue
            if attr == "data-a-dynamic-image":
                # Amazon-style: a JSON object mapping image URL -> [w, h] in a string attribute.
                try:
                    candidates = list(json.loads(value).keys())
                    if candidates:
                        urls.append(urljoin(base_url, candidates[0]))
                except (ValueError, TypeError):
                    pass
            else:
                urls.append(urljoin(base_url, value))
        srcset = img.get("srcset")
        if srcset:
            # Take the last (typically largest/highest-resolution) candidate in the srcset list.
            last_candidate = srcset.split(",")[-1].strip().split(" ")[0]
            if last_candidate:
                urls.append(urljoin(base_url, last_candidate))

    # Broadest fallback: no hinted/gallery images found at all — take every
    # <img> with a real src, so a differently-structured site still yields
    # something rather than zero images.
    if not urls:
        for img in soup.find_all("img"):
            src = img.get("src") or img.get("data-src")
            if src:
                urls.append(urljoin(base_url, src))

    # Dedupe while preserving order, cap to a sane number of downloads.
    seen = set()
    deduped = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            deduped.append(u)
    return deduped[: settings.ecommerce_max_images]


def parse_listing(url: str, html: str) -> ListingData:
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("title")
    og_title = soup.find("meta", attrs={"property": "og:title"})
    title = (og_title["content"] if og_title and og_title.get("content") else None) or (
        title_tag.get_text(strip=True) if title_tag else ""
    )

    og_desc = soup.find("meta", attrs={"property": "og:description"})
    meta_desc = soup.find("meta", attrs={"name": "description"})
    description = (
        (og_desc["content"] if og_desc and og_desc.get("content") else None)
        or (meta_desc["content"] if meta_desc and meta_desc.get("content") else None)
        or ""
    )

    products = _parse_json_ld(soup)
    price, currency = _extract_price(products, soup)
    gtin = _extract_gtin(products)
    image_urls = _extract_images(products, soup, url)

    brand = None
    for product in products:
        b = product.get("brand")
        if isinstance(b, dict):
            brand = b.get("name")
        elif isinstance(b, str):
            brand = b
        if brand:
            break

    # Strip script/style before pulling visible text, and cap its length —
    # this feeds both the regex extraction below and (if needed) the AI
    # extraction step, neither of which needs the whole page.
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    visible_text = re.sub(r"\n{3,}", "\n\n", soup.get_text("\n", strip=True))[:20000]

    return ListingData(
        url=url,
        title=title,
        description=description,
        visible_text=visible_text,
        json_ld_products=products,
        price=price,
        currency=currency,
        brand=brand,
        gtin=gtin,
        image_urls=image_urls,
    )


def download_image(url: str) -> bytes | None:
    try:
        with httpx.Client(
            timeout=settings.ecommerce_fetch_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            if "image" not in response.headers.get("content-type", ""):
                return None
            return response.content
    except httpx.HTTPError:
        return None


def synthetic_words_from_text(listing: ListingData) -> list[OcrWord]:
    """
    Turns the listing's own text (title + description + JSON-LD fields +
    visible page text) into the same OcrWord shape declaration_service.py
    expects, so the exact same regex-based extraction logic used for
    physical label photos also runs against the webpage text — one
    extraction pipeline, two input sources. Confidence is 1.0 because this
    is the page's actual text, not an OCR guess; the bounding-box height is
    a fixed placeholder (this text has no physical size to measure) so the
    FONT_SIZE rule doesn't misfire against it — see the evidence note added
    where these words are merged in the router.
    """
    combined = "\n".join(
        filter(None, [listing.title, listing.description, listing.visible_text])
    )
    words: list[OcrWord] = []
    for line in combined.splitlines():
        line = line.strip()
        if not line:
            continue
        width = max(10.0, len(line) * 7.0)
        words.append(
            OcrWord(text=line, confidence=1.0, box=[[0, 0], [width, 0], [width, 20], [0, 20]], lang="en")
        )
    return words


def extract_declarations_from_listing(
    listing: ListingData, image_words: dict[str, list[OcrWord]], image_quality: dict[str, dict]
) -> list[declaration_service.ExtractedDeclaration]:
    """Reuses declaration_service.extract_declarations unchanged — the
    "webpage" pseudo-slot carries the page's own text, and every downloaded
    product image is its own slot exactly like a physical multi-angle
    capture."""
    words_by_slot: dict[str, list[OcrWord]] = {"webpage": synthetic_words_from_text(listing)}
    words_by_slot.update(image_words)

    quality_by_slot: dict[str, dict] = {"webpage": {"glare_pct": 0.0, "blur_score": 100.0}}
    quality_by_slot.update(image_quality)

    declarations = declaration_service.extract_declarations(words_by_slot, quality_by_slot)

    # The generic COMMON_NAME heuristic (declaration_service._extract_common_name)
    # picks "the highest-confidence line" when there's no real bounding-box
    # height to rank by — for webpage text every synthetic line has the same
    # 1.0 confidence, so that heuristic degrades to "whichever line happens
    # to come first". A listing's own product name (from JSON-LD, which is
    # structured and authoritative, or its <title>/og:title as a fallback)
    # is a far more reliable signal than that coincidence, so it overrides
    # the generic result whenever one is available.
    product_name = None
    for product in listing.json_ld_products:
        if product.get("name"):
            product_name = str(product["name"]).strip()
            break
    product_name = product_name or (listing.title.strip() if listing.title else None)

    if product_name:
        for decl in declarations:
            if decl.declaration_type == "COMMON_NAME":
                decl.detected_text = product_name
                decl.confidence = 0.9 if listing.json_ld_products else 0.75
                decl.source_image = "webpage"
                decl.status = "PRESENT"
                decl.bounding_box = None
                decl.estimated_text_height_px = None
                decl.readability = None
                break

    return declarations
