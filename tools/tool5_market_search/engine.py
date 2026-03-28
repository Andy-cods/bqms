"""
Tool 5 — Market Price Search Engine
=====================================
Phases:
  1. QueryBuilder      → Gemini: EN + ZH keywords + key_specs + negative_keywords
  2. ProductMatcher    → Sub-tool: batch verify results match the spec (≥0.7 confidence)
  3. PlatformCrawlers  → crawl4ai async: Alibaba / 1688 / Taiwantrade / Ruten (≥20/platform)
  4. GeminiSynthesizer → Normalize prices, tier suppliers, top 5
  5. AgentEvaluator    → Score Giá/Uy tín/MOQ/Địa điểm/Chứng nhận → CHỐT/XEM XÉT/BỎ QUA
  6. PlatformStats     → Efficiency + price advantage per platform
  7. Storage           → price_confirmed + search_cache in bsmq.db
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Callable, Optional

# Max 2 browser windows open simultaneously (visible popups)
_CRAWL_SEM = asyncio.Semaphore(2)

# ─────────────────────────────────────────────────────────────
# Data classes
# ─────────────────────────────────────────────────────────────

@dataclass
class RawResult:
    platform: str           # 'alibaba' | '1688' | 'taiwantrade' | 'ruten'
    url: str
    title: str
    price_text: str         # raw scraped text
    price_min: float        # parsed, in platform currency
    price_max: float
    currency: str           # 'USD' | 'CNY' | 'TWD'
    price_usd: float = 0.0  # normalized
    moq: int = 0
    moq_unit: str = "pcs"
    supplier_name: str = ""
    supplier_location: str = ""
    supplier_rating: float = 0.0
    tx_count: int = 0
    certifications: list = field(default_factory=list)
    contact_method: str = ""    # platform-specific contact hint
    verified_supplier: bool = False
    raw_snippet: str = ""       # first 500 chars for Gemini verification


@dataclass
class VerifiedResult(RawResult):
    match_confidence: float = 0.0
    match_reason: str = ""
    status: str = "unverified"  # 'keep' | 'review' | 'discard'


@dataclass
class PlatformStats:
    platform: str
    total_crawled: int
    verified_count: int
    match_rate: float        # 0-1
    avg_price_usd: float
    min_price_usd: float
    price_index: int         # 1-5 stars (lower price = more stars)
    crawl_ok: bool = True
    error_msg: str = ""


@dataclass
class SearchResult:
    query_params: dict
    platform_stats: list
    verified_results: list
    synthesis: dict
    evaluation: dict
    total_duration_sec: float = 0.0
    cache_used: bool = False


# ─────────────────────────────────────────────────────────────
# Exchange rates (approximate, update as needed)
# ─────────────────────────────────────────────────────────────

FX = {
    "CNY": 7.2,    # 1 USD = 7.2 CNY
    "TWD": 32.0,   # 1 USD = 32 TWD
    "USD": 1.0,
    "VND": 25400.0,
}


def to_usd(amount: float, currency: str) -> float:
    rate = FX.get(currency.upper(), 1.0)
    return round(amount / rate, 4) if rate else amount


def parse_price(text: str, platform: str) -> tuple[float, float, str]:
    """Return (price_min, price_max, currency) from raw price text."""
    text = text.strip().replace(",", "")
    currency = "CNY" if platform in ("1688",) else "TWD" if platform == "ruten" else "USD"

    # detect currency symbols
    if "¥" in text or "CNY" in text.upper() or "RMB" in text.upper():
        currency = "CNY"
    elif "NT$" in text or "TWD" in text.upper():
        currency = "TWD"
    elif "$" in text or "USD" in text.upper():
        currency = "USD"

    nums = re.findall(r"[\d]+(?:\.\d+)?", text)
    floats = [float(n) for n in nums if float(n) > 0]
    if not floats:
        return 0.0, 0.0, currency
    return min(floats), max(floats), currency


# ─────────────────────────────────────────────────────────────
# Gemini helper (reuse ai_classifier pattern)
# ─────────────────────────────────────────────────────────────

def _get_gemini_keys() -> list[str]:
    try:
        import json as _j, os
        cfg_path = os.path.join(os.path.dirname(__file__), "..", "..", "config.json")
        with open(cfg_path, encoding="utf-8") as f:
            cfg = _j.load(f)
        keys = cfg.get("gemini_keys", [])
        if isinstance(keys, list):
            return [k for k in keys if k and k.strip()]
    except Exception:
        pass
    return []


_key_index = 0
_key_timestamps: dict[str, list] = {}


def _pick_key(keys: list[str]) -> str:
    global _key_index
    now = time.time()
    for _ in range(len(keys)):
        key = keys[_key_index % len(keys)]
        _key_index += 1
        ts_list = _key_timestamps.setdefault(key, [])
        # keep only last 60s
        ts_list[:] = [t for t in ts_list if now - t < 60]
        if len(ts_list) < 55:
            ts_list.append(now)
            return key
    # all exhausted — wait and use first
    time.sleep(5)
    return keys[0]


def _call_gemini(prompt: str, keys: list[str], model: str = "gemini-1.5-flash") -> str:
    if not keys:
        raise RuntimeError("No Gemini API keys configured")
    key = _pick_key(keys)
    try:
        import google.generativeai as genai
        genai.configure(api_key=key)
        m = genai.GenerativeModel(model)
        resp = m.generate_content(prompt)
        return resp.text
    except Exception as e:
        raise RuntimeError(f"Gemini call failed: {e}") from e


def _extract_json(text: str) -> dict | list:
    """Extract first JSON object/array from text."""
    # try ```json block
    m = re.search(r"```(?:json)?\s*([\[\{].*?)\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    # try bare {...} or [...]
    m = re.search(r"([\[\{].*[\]\}])", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    raise ValueError(f"No JSON found in Gemini response:\n{text[:300]}")


# ─────────────────────────────────────────────────────────────
# Phase 1 — Query Builder
# ─────────────────────────────────────────────────────────────

QUERY_PROMPT = """
Bạn là chuyên gia tìm kiếm linh kiện điện tử B2B.
Dựa vào thông tin sản phẩm sau, sinh ra từ khóa tìm kiếm tối ưu.

Thông tin sản phẩm:
- Tên / Spec: {spec}
- Maker / Brand: {maker}
- Mã BQMS: {bqms_code}
- Ngân sách tham khảo: {budget}

Yêu cầu trả về JSON (không thêm text ngoài):
{{
  "en_query": "keyword cho Alibaba và Taiwantrade (tiếng Anh, ngắn gọn, dưới 60 ký tự)",
  "zh_query": "关键词用于1688和露天 (tiếng Trung, ngắn gọn)",
  "key_specs": ["thuộc tính phân biệt 1", "thuộc tính 2", "..."],
  "negative_keywords": ["từ cần loại trừ 1", "từ cần loại trừ 2"],
  "product_category": "Danh mục sản phẩm (IC/resistor/capacitor/connector/...)",
  "search_tips": "Gợi ý tìm kiếm nếu có"
}}
"""


def build_query(spec: str, maker: str = "", bqms_code: str = "",
                budget: str = "") -> dict:
    keys = _get_gemini_keys()
    prompt = QUERY_PROMPT.format(
        spec=spec, maker=maker or "N/A",
        bqms_code=bqms_code or "N/A",
        budget=budget or "Không xác định"
    )
    raw = _call_gemini(prompt, keys)
    result = _extract_json(raw)
    # ensure all fields exist
    result.setdefault("en_query", spec)
    result.setdefault("zh_query", spec)
    result.setdefault("key_specs", [])
    result.setdefault("negative_keywords", [])
    result.setdefault("product_category", "")
    return result


# ─────────────────────────────────────────────────────────────
# Phase 2 — Product Matcher (sub-tool)
# ─────────────────────────────────────────────────────────────

MATCH_PROMPT = """
Bạn là kỹ sư phân tích linh kiện điện tử. Xác minh xem các sản phẩm sau có khớp với yêu cầu không.

Sản phẩm cần tìm:
- Spec gốc: {spec}
- Thuộc tính quan trọng: {key_specs}
- Từ loại trừ: {negative_keywords}

Danh sách kết quả cần xác minh (JSON array):
{results_json}

Với TỪNG kết quả, đánh giá:
1. Có phải đúng loại linh kiện không?
2. Spec có khớp không (voltage, package, tolerance, model...)?
3. Có bị nhầm với sản phẩm tương tự không?

Trả về JSON array (không thêm text ngoài):
[
  {{
    "id": 0,
    "match": true,
    "confidence": 0.0,
    "reason": "Lý do ngắn (1 câu)"
  }}
]
"""


def verify_batch(spec: str, key_specs: list, negative_keywords: list,
                 batch: list[RawResult]) -> list[VerifiedResult]:
    """Verify a batch of up to 10 results against the original spec."""
    keys = _get_gemini_keys()
    items = []
    for i, r in enumerate(batch):
        items.append({
            "id": i,
            "platform": r.platform,
            "title": r.title,
            "snippet": r.raw_snippet[:300]
        })
    prompt = MATCH_PROMPT.format(
        spec=spec,
        key_specs=", ".join(key_specs) if key_specs else "N/A",
        negative_keywords=", ".join(negative_keywords) if negative_keywords else "N/A",
        results_json=json.dumps(items, ensure_ascii=False, indent=2)
    )
    try:
        raw = _call_gemini(prompt, keys)
        verdicts = _extract_json(raw)
        if not isinstance(verdicts, list):
            verdicts = []
    except Exception:
        verdicts = []

    verdict_map = {v["id"]: v for v in verdicts if isinstance(v, dict)}
    verified = []
    for i, r in enumerate(batch):
        v = verdict_map.get(i, {})
        conf = float(v.get("confidence", 0.5))
        match = v.get("match", True)
        reason = v.get("reason", "Chưa xác minh")
        if not match:
            conf = min(conf, 0.45)
        if conf >= 0.7:
            status = "keep"
        elif conf >= 0.5:
            status = "review"
        else:
            status = "discard"
        vr = VerifiedResult(**asdict(r),
                            match_confidence=conf,
                            match_reason=reason,
                            status=status)
        verified.append(vr)
    return verified


def verify_all(spec: str, key_specs: list, negative_keywords: list,
               results: list[RawResult],
               progress_cb: Optional[Callable] = None) -> list[VerifiedResult]:
    """Verify all results in batches of 10."""
    all_verified = []
    batch_size = 10
    for i in range(0, len(results), batch_size):
        batch = results[i:i + batch_size]
        verified = verify_batch(spec, key_specs, negative_keywords, batch)
        all_verified.extend(verified)
        if progress_cb:
            progress_cb(min(i + batch_size, len(results)), len(results))
        time.sleep(1.5)  # rate limit
    return all_verified


# ─────────────────────────────────────────────────────────────
# Phase 3 — Platform Crawlers
# ─────────────────────────────────────────────────────────────

PLATFORM_CRAWL_CONFIG: dict[str, dict] = {
    "alibaba": {
        "label": "Alibaba.com", "language": "EN",
        "contact": "Contact Supplier / Trade Assurance", "currency": "USD",
        "search_url_template": "https://www.alibaba.com/trade/search?SearchText={query}&page={page}",
        "page_offset": 1, "scroll_to_bottom": True,
        "wait_for": ".organic-gallery-offer-inner, .J-offer-list",
        "selectors": {
            "container":         ".organic-gallery-offer-inner",
            "title":             ".elements-title-normal__outter span",
            "price_text":        ".elements-offer-price-normal__price",
            "moq_text":          ".elements-offer-price-normal__min-order",
            "supplier_name":     ".elements-supplier-name-normal__name span",
            "supplier_location": ".elements-supplier-name-normal__origin",
            "supplier_rating":   None,
            "tx_text":           None,
            "certifications":    None,
            "verified":          ".icons-supplier-icon-verified",
            "url":               "a.elements-title-normal",
        },
    },
    "1688": {
        "label": "1688.com", "language": "ZH",
        "contact": "旺旺/WeChat/电话", "currency": "CNY",
        "search_url_template": "https://s.1688.com/selloffer/offer_search.htm?keywords={query}&beginPage={page}",
        "page_offset": 1, "scroll_to_bottom": True,
        "wait_for": ".space-offer-card-box, .offer-item",
        "selectors": {
            "container":         ".space-offer-card-box",
            "title":             ".title span",
            "price_text":        ".price-text",
            "moq_text":          ".min-order .value",
            "supplier_name":     ".company-name span",
            "supplier_location": ".company-location",
            "supplier_rating":   None,
            "tx_text":           ".deal-cnt",
            "certifications":    None,
            "verified":          ".company-verify-icon",
            "url":               "a.title",
        },
    },
    "taiwantrade": {
        "label": "Taiwantrade.com", "language": "EN",
        "contact": "Email Inquiry Form / Company Contact", "currency": "USD",
        "search_url_template": "https://www.taiwantrade.com/search/{query}?page={page}",
        "page_offset": 1, "scroll_to_bottom": False,
        "wait_for": ".product-card, .product-item",
        "selectors": {
            "container":         ".product-card",
            "title":             ".product-card__title",
            "price_text":        ".product-card__price",
            "moq_text":          ".product-card__moq",
            "supplier_name":     ".product-card__company-name",
            "supplier_location": ".product-card__country",
            "supplier_rating":   None,
            "tx_text":           None,
            "certifications":    ".product-card__certifications li",
            "verified":          ".verified-badge",
            "url":               "a.product-card__link",
        },
    },
    "ruten": {
        "label": "Ruten.com.tw", "language": "ZH_TW",
        "contact": "站內信 / 購物車", "currency": "TWD",
        "search_url_template": "https://find.ruten.com.tw/s/?q={query}&p={page}",
        "page_offset": 1, "scroll_to_bottom": False,
        "wait_for": ".rt-gridbox, .goods-item",
        "selectors": {
            "container":         "li.rt-gridbox",
            "title":             "a.item-title",
            "price_text":        "span.rt-currency",
            "moq_text":          None,
            "supplier_name":     ".rt-store-name",
            "supplier_location": None,
            "supplier_rating":   ".star-wrap span",
            "tx_text":           ".deal-num",
            "certifications":    None,
            "verified":          None,
            "url":               "a.item-title",
        },
    },
    "made_in_china": {
        "label": "Made-in-China.com", "language": "EN",
        "contact": "Contact Supplier", "currency": "USD",
        "search_url_template": "https://www.made-in-china.com/multi-search/{query}/F1/{page}.html",
        "page_offset": 1, "scroll_to_bottom": False,
        "wait_for": ".prod-info",
        "selectors": {
            "container":         ".prod-info",
            "title":             ".product-name a",
            "price_text":        ".price-info",
            "moq_text":          ".prod-attr-item .value",
            "supplier_name":     ".comp-name",
            "supplier_location": ".comp-country",
            "supplier_rating":   None, "tx_text": None, "certifications": None,
            "verified":          ".verified-pro",
            "url":               ".product-name a",
        },
    },
    "global_sources": {
        "label": "Global Sources", "language": "EN",
        "contact": "Contact Supplier", "currency": "USD",
        "search_url_template": "https://www.globalsources.com/search/{query}?page={page}",
        "page_offset": 1, "scroll_to_bottom": False,
        "wait_for": ".product-item",
        "selectors": {
            "container":         ".product-item",
            "title":             ".prod-name",
            "price_text":        ".price",
            "moq_text":          ".moq",
            "supplier_name":     ".company-name",
            "supplier_location": ".country",
            "supplier_rating":   None, "tx_text": None,
            "certifications":    ".cert-logo",
            "verified":          ".verified",
            "url":               "a.prod-name",
        },
    },
    "lcsc": {
        "label": "LCSC.com", "language": "EN",
        "contact": "Add to Cart / Request Quote", "currency": "USD",
        "search_url_template": "https://www.lcsc.com/search?q={query}&page={page}",
        "page_offset": 1, "scroll_to_bottom": False,
        "wait_for": ".product-list-item",
        "selectors": {
            "container":         ".product-list-item",
            "title":             ".product-name",
            "price_text":        ".price-break td:nth-child(2)",
            "moq_text":          ".price-break td:nth-child(1)",
            "supplier_name":     "LCSC",    # static value
            "supplier_location": "China",   # static value
            "supplier_rating":   None,
            "tx_text":           ".sales-count",
            "certifications":    ".cert-icons img",
            "verified":          None,
            "url":               "a.product-name",
        },
    },
}

# Backward-compat alias — used by _build_raw_results() and frontend
PLATFORM_CONFIG = {
    k: {f: v[f] for f in ("label", "language", "contact", "currency")}
    for k, v in PLATFORM_CRAWL_CONFIG.items()
}


def _build_platform_urls(platform: str, query: str, pages: int = 2) -> list[str]:
    """Generic URL builder using PLATFORM_CRAWL_CONFIG search_url_template."""
    import urllib.parse
    cfg = PLATFORM_CRAWL_CONFIG.get(platform, {})
    template = cfg.get("search_url_template", "")
    if not template:
        return []
    offset = cfg.get("page_offset", 1)
    q = urllib.parse.quote(query)
    return [template.format(query=q, page=p) for p in range(offset, offset + pages)]


# Legacy wrappers — kept for backward compatibility
def _build_alibaba_urls(query: str, pages: int = 2) -> list[str]:
    return _build_platform_urls("alibaba", query, pages)

def _build_1688_urls(query: str, pages: int = 2) -> list[str]:
    return _build_platform_urls("1688", query, pages)

def _build_taiwantrade_urls(query: str, pages: int = 2) -> list[str]:
    return _build_platform_urls("taiwantrade", query, pages)

def _build_ruten_urls(query: str, pages: int = 2) -> list[str]:
    return _build_platform_urls("ruten", query, pages)


# Gemini-based extraction prompt (fallback & primary for robustness)
EXTRACT_PROMPT = """
Bạn là công cụ trích xuất dữ liệu sản phẩm từ trang web thương mại điện tử.

Nền tảng: {platform}
Truy vấn tìm kiếm: {query}

Dưới đây là nội dung trang (markdown):
---
{page_content}
---

Trích xuất TỐI ĐA {max_items} sản phẩm từ trang. Chỉ lấy sản phẩm thực sự có trên trang.
Tránh lấy quảng cáo, banner, menu điều hướng.

Trả về JSON array (không thêm text ngoài):
[
  {{
    "title": "Tên sản phẩm đầy đủ",
    "price_text": "Giá nguyên văn (VD: $1.50-$3.00, ¥10.00, NT$500)",
    "moq_text": "MOQ nguyên văn (VD: 100 pcs, 1 set)",
    "supplier_name": "Tên nhà cung cấp / người bán",
    "supplier_location": "Tỉnh/Thành phố, Quốc gia",
    "rating_text": "Rating nguyên văn (VD: 4.8/5, 95%)",
    "tx_text": "Số giao dịch/đánh giá nguyên văn (VD: 1000+ transactions)",
    "certifications": ["CE", "RoHS"],
    "contact_hint": "Cách liên hệ hiển thị trên trang",
    "verified": true,
    "url": "URL sản phẩm hoặc nhà cung cấp (nếu có)"
  }}
]
"""


def _parse_moq(text: str) -> tuple[int, str]:
    if not text:
        return 1, "pcs"
    nums = re.findall(r"[\d,]+", text.replace(",", ""))
    unit = "pcs"
    for u in ["sets", "set", "pairs", "boxes", "box", "rolls", "pcs", "pieces", "units"]:
        if u in text.lower():
            unit = u
            break
    return int(nums[0]) if nums else 1, unit


def _parse_rating(text: str) -> float:
    if not text:
        return 0.0
    m = re.search(r"([\d.]+)\s*/\s*5", text)
    if m:
        return float(m.group(1))
    m = re.search(r"([\d.]+)\s*%", text)
    if m:
        return float(m.group(1)) / 20  # convert 95% → 4.75
    m = re.search(r"([\d.]+)", text)
    if m:
        v = float(m.group(1))
        return min(v, 5.0)
    return 0.0


def _parse_tx(text: str) -> int:
    if not text:
        return 0
    text = text.replace(",", "")
    m = re.search(r"([\d]+)\+?", text)
    if m:
        return int(m.group(1))
    return 0


# JS injected into every page: wait for user to solve CAPTCHA if detected (up to 120s)
_CAPTCHA_JS = """
const _isCaptcha = () => !!document.querySelector(
  '.captcha, #captcha, [class*="captcha"], iframe[src*="captcha"], ' +
  'iframe[src*="recaptcha"], .slider-verify, .nc_wrapper, #baxia-dialog'
);
if (_isCaptcha()) {
  let _waited = 0;
  while (_isCaptcha() && _waited < 120000) {
    await new Promise(r => setTimeout(r, 3000));
    _waited += 3000;
  }
}
"""

# JS scroll to trigger lazy-loaded product cards (Alibaba, 1688, AliExpress)
_SCROLL_JS = """
window.scrollTo(0, document.body.scrollHeight * 0.5);
await new Promise(r => setTimeout(r, 1000));
window.scrollTo(0, document.body.scrollHeight);
await new Promise(r => setTimeout(r, 1500));
"""


_CAPTCHA_EXPR = (
    "!!document.querySelector("
    "'.captcha,#captcha,[class*=\"captcha\"],iframe[src*=\"captcha\"],"
    "iframe[src*=\"recaptcha\"],.slider-verify,.nc_wrapper,#baxia-dialog')"
)


async def _crawl_page(
    url: str,
    wait_for: str = "body",
    scroll: bool = False,
    delay_min: float = 2.0,
    delay_max: float = 5.0,
) -> str:
    """
    Crawl a page using Playwright directly (headless=False, 950×680 visible window).
    - Window stays open until page loads + optional CAPTCHA solving (up to 120s)
    - Returns raw HTML for BeautifulSoup parsing
    """
    import random
    await asyncio.sleep(random.uniform(delay_min, delay_max))
    try:
        from playwright.async_api import async_playwright

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=False,
                args=[
                    "--window-size=950,700",
                    "--window-position=60,60",
                    "--disable-blink-features=AutomationControlled",
                ],
            )
            ctx = await browser.new_context(
                viewport={"width": 950, "height": 680},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            # Stealth: hide webdriver flag
            await ctx.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )
            page = await ctx.new_page()

            # Navigate — networkidle lets SPAs (Angular/React) finish rendering
            await page.goto(url, wait_until="networkidle", timeout=60000)

            # Extra wait for slow SPAs — ensures JS has rendered product cards
            await asyncio.sleep(2.0)

            # Additionally wait for known product card selectors (best-effort)
            for sel in wait_for.split(","):
                sel = sel.strip()
                if sel and sel != "body":
                    try:
                        await page.wait_for_selector(sel, timeout=8000)
                        break   # found — stop trying
                    except Exception:
                        continue  # try next selector

            # CAPTCHA detection — pause for user to solve (up to 120s)
            try:
                is_captcha = await page.evaluate(_CAPTCHA_EXPR)
                if is_captcha:
                    for _ in range(40):  # 40 × 3s = 120s
                        await asyncio.sleep(3)
                        still_captcha = await page.evaluate(_CAPTCHA_EXPR)
                        if not still_captcha:
                            break
            except Exception:
                pass

            # Scroll to trigger lazy-loaded cards
            if scroll:
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
                await asyncio.sleep(1.0)
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)

            html = await page.content()
            await browser.close()
            return html

    except ImportError:
        import requests
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
        }
        resp = requests.get(url, headers=headers, timeout=25)
        return resp.text
    except Exception as e:
        return f"[CRAWL_ERROR: {e}]"


def _extract_via_gemini(platform: str, query: str,
                        page_content: str, max_items: int = 12) -> list[dict]:
    """Use Gemini to extract product listings from page markdown."""
    keys = _get_gemini_keys()
    # truncate to ~8000 chars to stay within token limits
    content_trimmed = page_content[:8000]
    prompt = EXTRACT_PROMPT.format(
        platform=platform,
        query=query,
        page_content=content_trimmed,
        max_items=max_items
    )
    try:
        raw = _call_gemini(prompt, keys)
        items = _extract_json(raw)
        return items if isinstance(items, list) else []
    except Exception:
        return []


def _extract_with_selectors(platform: str, html: str) -> list[dict]:
    """
    Extract product listings using per-platform CSS selectors (BeautifulSoup).
    Returns same dict shape as _extract_via_gemini() so _build_raw_results() needs no changes.
    Returns [] if BeautifulSoup unavailable or no container elements found (triggers Gemini fallback).
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return []

    cfg = PLATFORM_CRAWL_CONFIG.get(platform, {})
    sel = cfg.get("selectors", {})
    container_sel = sel.get("container")
    if not container_sel:
        return []

    # Try lxml first (faster, more tolerant), fall back to html.parser
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(container_sel)
    if not cards:
        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(container_sel)
    if not cards:
        return []

    def _text(card, s):
        """Extract text from selector s within card. Handles static string values."""
        if not s:
            return ""
        # Static string value (e.g. supplier_name: "LCSC", supplier_location: "China")
        _CSS_STARTS = (".", "#", "[", "a", "s", "d", "l", "h", "p", "i", "t", "u", "f")
        if not s.startswith(_CSS_STARTS) or (len(s) < 20 and " " not in s and not s.endswith(")")):
            # Heuristic: short strings without spaces/parens are likely static values
            if not any(c in s for c in (".", "#", "[", ":")):
                return s
        el = card.select_one(s)
        return el.get_text(strip=True) if el else ""

    results = []
    import urllib.parse as _up
    base_url = cfg.get("search_url_template", "")
    parsed_base = _up.urlparse(base_url)
    base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}" if parsed_base.netloc else ""

    for card in cards:
        title = _text(card, sel.get("title"))
        if not title:
            continue  # skip banners/ads with no product title

        # URL — extract href attribute
        url_sel = sel.get("url")
        href = ""
        if url_sel:
            url_el = card.select_one(url_sel)
            if url_el:
                href = url_el.get("href", "")
                if href and href.startswith("/") and base_origin:
                    href = base_origin + href

        # Certifications — multi-value (text or alt/title attrs for images)
        cert_sel = sel.get("certifications")
        certs = []
        if cert_sel:
            for c in card.select(cert_sel):
                txt = c.get_text(strip=True) or c.get("alt", "") or c.get("title", "")
                if txt:
                    certs.append(txt)

        # Verified — presence of element means True
        ver_sel = sel.get("verified")
        verified = bool(card.select_one(ver_sel)) if ver_sel else False

        results.append({
            "title":             title,
            "price_text":        _text(card, sel.get("price_text")),
            "moq_text":          _text(card, sel.get("moq_text")),
            "supplier_name":     _text(card, sel.get("supplier_name")),
            "supplier_location": _text(card, sel.get("supplier_location")),
            "rating_text":       _text(card, sel.get("supplier_rating")),
            "tx_text":           _text(card, sel.get("tx_text")),
            "certifications":    certs,
            "verified":          verified,
            "url":               href,
            "contact_hint":      cfg.get("contact", ""),
        })

    return results


def _build_raw_results(items: list[dict], platform: str) -> list[RawResult]:
    results = []
    cfg = PLATFORM_CONFIG.get(platform, {})
    for item in items:
        if not item.get("title"):
            continue
        price_text = str(item.get("price_text", "0"))
        p_min, p_max, currency = parse_price(price_text, platform)
        moq, moq_unit = _parse_moq(str(item.get("moq_text", "")))
        rating = _parse_rating(str(item.get("rating_text", "")))
        tx = _parse_tx(str(item.get("tx_text", "")))
        price_usd = to_usd((p_min + p_max) / 2 if p_max else p_min, currency)
        snippet = f"{item.get('title','')} | {price_text} | {item.get('supplier_name','')}"
        r = RawResult(
            platform=platform,
            url=str(item.get("url", "")),
            title=str(item.get("title", "")),
            price_text=price_text,
            price_min=p_min,
            price_max=p_max,
            currency=currency,
            price_usd=price_usd,
            moq=moq,
            moq_unit=moq_unit,
            supplier_name=str(item.get("supplier_name", "")),
            supplier_location=str(item.get("supplier_location", "")),
            supplier_rating=rating,
            tx_count=tx,
            certifications=item.get("certifications", []),
            contact_method=str(item.get("contact_hint", cfg.get("contact", ""))),
            verified_supplier=bool(item.get("verified", False)),
            raw_snippet=snippet[:500],
        )
        results.append(r)
    return results


async def crawl_platform(
    platform: str,
    query: str,
    max_results: int = 20,
    progress_cb: Optional[Callable] = None,
) -> tuple[list[RawResult], PlatformStats]:
    """
    Crawl one platform with a visible browser window.
    Strategy: CSS selectors first → Gemini fallback if < 3 items extracted.
    Max 2 browser windows open simultaneously via _CRAWL_SEM.
    """
    cfg = PLATFORM_CRAWL_CONFIG.get(platform)
    if not cfg:
        return [], PlatformStats(platform, 0, 0, 0, 0, 0, 0, False, "Unknown platform")

    pages_needed = max(2, -(-max_results // 12))  # ceil division
    urls = _build_platform_urls(platform, query, pages=pages_needed)
    wait_for_sel = cfg.get("wait_for", "body")
    should_scroll = cfg.get("scroll_to_bottom", False)

    all_items: list[dict] = []
    error_msg = ""

    async with _CRAWL_SEM:  # max 2 visible browser windows at once
        try:
            for i, url in enumerate(urls):
                if progress_cb:
                    progress_cb(f"[{platform}] Đang crawl trang {i+1}/{len(urls)}...")
                html = await _crawl_page(url, wait_for=wait_for_sel, scroll=should_scroll)
                if html.startswith("[CRAWL_ERROR"):
                    error_msg = html
                    break
                # Primary: CSS selectors (fast, accurate when selectors match)
                items = _extract_with_selectors(platform, html)
                if len(items) < 3:
                    # Fallback: Gemini reads the raw HTML
                    if progress_cb:
                        progress_cb(f"[{platform}] CSS={len(items)} kết quả → dùng Gemini fallback...")
                    items = _extract_via_gemini(platform, query, html[:8000], max_items=12)
                all_items.extend(items)
                if len(all_items) >= max_results:
                    break
        except Exception as e:
            error_msg = str(e)

    results = _build_raw_results(all_items, platform)[:max_results]

    # compute stats (before verification)
    prices = [r.price_usd for r in results if r.price_usd > 0]
    avg_price = round(sum(prices) / len(prices), 4) if prices else 0.0
    min_price = min(prices) if prices else 0.0

    stats = PlatformStats(
        platform=platform,
        total_crawled=len(results),
        verified_count=0,  # filled after verification
        match_rate=0.0,
        avg_price_usd=avg_price,
        min_price_usd=min_price,
        price_index=0,   # filled after all platforms
        crawl_ok=not bool(error_msg),
        error_msg=error_msg,
    )
    return results, stats


# ─────────────────────────────────────────────────────────────
# Phase 4 — Gemini Synthesis
# ─────────────────────────────────────────────────────────────

SYNTHESIS_PROMPT = """
Bạn là chuyên gia phân tích thị trường linh kiện điện tử B2B.
Tổng hợp dữ liệu giá từ các nền tảng sau đây.

Sản phẩm cần tìm: {spec}
Ngân sách tham khảo: {budget}

Dữ liệu thu thập (JSON):
{results_json}

Nhiệm vụ:
1. Xác định dải giá thị trường: min / typical / max (USD)
2. Phân loại tier nhà cung cấp: budget (<{budget_low}) / standard / premium (>{budget_high})
3. Lọc loại bỏ kết quả outlier bất thường (giá quá cao/thấp bất thường)
4. Xác định top 5 nhà cung cấp phù hợp nhất
5. Tóm tắt thị trường bằng tiếng Việt

Trả về JSON (không thêm text ngoài):
{{
  "price_analysis": {{
    "min_usd": 0.0,
    "typical_usd": 0.0,
    "max_usd": 0.0,
    "currency_note": "Ghi chú về tỷ giá nếu cần"
  }},
  "top_suppliers": [
    {{
      "rank": 1,
      "platform": "alibaba",
      "supplier_name": "",
      "price_usd": 0.0,
      "price_display": "Giá hiển thị (VD: $1.20/pcs hoặc ¥8.5/pcs)",
      "moq": 0,
      "moq_unit": "pcs",
      "location": "",
      "rating": 0.0,
      "tx_count": 0,
      "verified": false,
      "certifications": [],
      "contact_method": "",
      "url": "",
      "tier": "budget|standard|premium",
      "highlight": "Điểm nổi bật (1 câu)"
    }}
  ],
  "market_summary": "Tóm tắt thị trường bằng tiếng Việt (2-3 câu)",
  "data_quality": "good|partial|poor",
  "total_sources": 0
}}
"""


def synthesize(verified_results: list[VerifiedResult],
               spec: str, budget_usd: float = 0.0) -> dict:
    keys = _get_gemini_keys()
    # only use 'keep' + 'review' results
    usable = [r for r in verified_results if r.status in ("keep", "review")]

    items = []
    for r in usable[:60]:  # cap to avoid token overload
        items.append({
            "platform": r.platform,
            "title": r.title,
            "price_text": r.price_text,
            "price_usd": r.price_usd,
            "moq": r.moq,
            "moq_unit": r.moq_unit,
            "supplier": r.supplier_name,
            "location": r.supplier_location,
            "rating": r.supplier_rating,
            "tx_count": r.tx_count,
            "verified": r.verified_supplier,
            "certs": r.certifications,
            "contact": r.contact_method,
            "url": r.url,
            "match_confidence": r.match_confidence,
        })

    prices = [r.price_usd for r in usable if r.price_usd > 0]
    budget_low = budget_usd * 0.7 if budget_usd else (min(prices) * 1.2 if prices else 1.0)
    budget_high = budget_usd * 1.3 if budget_usd else (max(prices) * 0.8 if prices else 9999.0)

    prompt = SYNTHESIS_PROMPT.format(
        spec=spec,
        budget=f"${budget_usd:.2f}" if budget_usd else "Không xác định",
        results_json=json.dumps(items, ensure_ascii=False, indent=2),
        budget_low=f"{budget_low:.2f}",
        budget_high=f"{budget_high:.2f}",
    )
    try:
        raw = _call_gemini(prompt, keys, model="gemini-1.5-pro")
        return _extract_json(raw)
    except Exception as e:
        # fallback: build basic synthesis from raw data
        avg = round(sum(prices) / len(prices), 4) if prices else 0
        return {
            "price_analysis": {
                "min_usd": min(prices) if prices else 0,
                "typical_usd": avg,
                "max_usd": max(prices) if prices else 0,
                "currency_note": "Tổng hợp tự động (Gemini không khả dụng)"
            },
            "top_suppliers": [
                {
                    "rank": i + 1,
                    "platform": r.platform,
                    "supplier_name": r.supplier_name,
                    "price_usd": r.price_usd,
                    "price_display": r.price_text,
                    "moq": r.moq,
                    "moq_unit": r.moq_unit,
                    "location": r.supplier_location,
                    "rating": r.supplier_rating,
                    "tx_count": r.tx_count,
                    "verified": r.verified_supplier,
                    "certifications": r.certifications,
                    "contact_method": r.contact_method,
                    "url": r.url,
                    "tier": "standard",
                    "highlight": ""
                }
                for i, r in enumerate(sorted(usable, key=lambda x: x.price_usd)[:5])
            ],
            "market_summary": f"Lỗi Gemini: {e}. Hiển thị dữ liệu thô.",
            "data_quality": "poor",
            "total_sources": len(usable),
        }


# ─────────────────────────────────────────────────────────────
# Phase 5 — Agent Evaluator
# ─────────────────────────────────────────────────────────────

AGENT_PROMPT = """
Bạn là Procurement Agent cho AMA Bắc Ninh — nhà cung cấp linh kiện điện tử cho Samsung Electronics Vietnam.

Nhiệm vụ: Đánh giá và xếp hạng các nhà cung cấp dưới đây để tìm nguồn hàng tốt nhất.

Sản phẩm: {spec}
Ngân sách tham khảo: {budget}

Danh sách nhà cung cấp:
{suppliers_json}

Tiêu chí chấm điểm (mỗi tiêu chí 1-10):
① GIÁ CẢ      — Cạnh tranh so với mức thị trường và ngân sách
② UY TÍN      — Rating, số giao dịch, verified badge, tuổi tài khoản
③ MOQ          — Phù hợp với đơn hàng Samsung (thường 50-500 pcs)
④ ĐỊA ĐIỂM   — CN/TW/JP/KR ưu tiên (logistics tốt hơn cho VN)
⑤ CHỨNG NHẬN — CE, RoHS, ISO, UL (Samsung yêu cầu nghiêm ngặt)

Trả về JSON (không thêm text ngoài):
{{
  "evaluated_suppliers": [
    {{
      "rank": 1,
      "supplier_name": "",
      "platform": "",
      "scores": {{
        "price": 8.0,
        "reliability": 7.0,
        "moq_fit": 9.0,
        "location": 8.0,
        "certifications": 6.0
      }},
      "total_score": 7.6,
      "recommendation": "CHỐT|XEM XÉT|BỎ QUA",
      "action": "Hành động cụ thể cần làm (1-2 câu)",
      "risks": ["Rủi ro 1", "Rủi ro 2"],
      "contact_guide": "Hướng dẫn liên hệ phù hợp với nền tảng này"
    }}
  ],
  "final_pick": {{
    "best_overall": "Tên NCC tốt nhất tổng thể",
    "best_price": "Tên NCC giá tốt nhất",
    "best_reliability": "Tên NCC uy tín nhất",
    "rationale": "Lý do chọn (2-3 câu)",
    "next_steps": ["Bước 1", "Bước 2", "Bước 3"]
  }},
  "market_verdict": "GIÁ TỐT|GIÁ CAO|KHÓ TÌM|DỒI DÀO|GIÁ ỔN ĐỊNH"
}}
"""


def evaluate(synthesis: dict, spec: str, budget_usd: float = 0.0) -> dict:
    keys = _get_gemini_keys()
    suppliers = synthesis.get("top_suppliers", [])
    prompt = AGENT_PROMPT.format(
        spec=spec,
        budget=f"${budget_usd:.2f}" if budget_usd else "Không xác định",
        suppliers_json=json.dumps(suppliers, ensure_ascii=False, indent=2)
    )
    try:
        raw = _call_gemini(prompt, keys, model="gemini-1.5-pro")
        return _extract_json(raw)
    except Exception as e:
        return {
            "evaluated_suppliers": [],
            "final_pick": {
                "best_overall": "",
                "best_price": "",
                "best_reliability": "",
                "rationale": f"Lỗi đánh giá: {e}",
                "next_steps": []
            },
            "market_verdict": "KHÔNG XÁC ĐỊNH",
        }


# ─────────────────────────────────────────────────────────────
# Phase 6 — Platform Stats (price index)
# ─────────────────────────────────────────────────────────────

def compute_platform_stats(all_stats: list[PlatformStats],
                            verified_results: list[VerifiedResult]) -> list[PlatformStats]:
    """Fill verified_count, match_rate, price_index for all platforms."""
    # group verified results by platform
    by_platform: dict[str, list] = {}
    for r in verified_results:
        by_platform.setdefault(r.platform, []).append(r)

    for s in all_stats:
        vr = by_platform.get(s.platform, [])
        kept = [r for r in vr if r.status in ("keep", "review")]
        s.verified_count = len(kept)
        s.match_rate = round(len(kept) / s.total_crawled, 2) if s.total_crawled else 0.0
        prices = [r.price_usd for r in kept if r.price_usd > 0]
        s.avg_price_usd = round(sum(prices) / len(prices), 4) if prices else 0.0
        s.min_price_usd = min(prices) if prices else 0.0

    # price_index: rank by avg_price ascending → best = 5 stars
    ranked = sorted([s for s in all_stats if s.avg_price_usd > 0],
                    key=lambda x: x.avg_price_usd)
    for i, s in enumerate(ranked):
        s.price_index = max(1, 5 - i)

    return all_stats


# ─────────────────────────────────────────────────────────────
# Main Orchestrator
# ─────────────────────────────────────────────────────────────

def _cache_key(platforms: list[str], query: str) -> str:
    raw = "|".join(sorted(platforms)) + "|" + query.lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()


def search(
    spec: str,
    maker: str = "",
    bqms_code: str = "",
    budget_usd: float = 0.0,
    platforms: Optional[list[str]] = None,
    max_per_platform: int = 20,
    use_cache: bool = True,
    db_path: str = "./bsmq.db",
    progress_cb: Optional[Callable] = None,
) -> SearchResult:
    """
    Full search pipeline. Returns SearchResult.
    progress_cb(message: str) is called with status updates.
    """
    if platforms is None:
        platforms = ["alibaba", "1688", "taiwantrade", "ruten"]

    start_time = time.time()

    def _cb(msg: str):
        if progress_cb:
            progress_cb(msg)

    # ── Cache check ──
    key = _cache_key(platforms, spec + maker)
    if use_cache:
        cached = get_search_cache(key, db_path)
        if cached:
            _cb("Đang dùng kết quả cache (< 24h)...")
            cached["cache_used"] = True
            return SearchResult(**{k: v for k, v in cached.items()
                                   if k in SearchResult.__dataclass_fields__},
                                cache_used=True,
                                total_duration_sec=round(time.time() - start_time, 1))

    # ── Phase 1: Query Builder ──
    _cb("Phase 1: Đang tạo từ khóa tìm kiếm...")
    try:
        query_info = build_query(spec, maker, bqms_code,
                                 f"${budget_usd:.2f}" if budget_usd else "")
    except Exception as e:
        query_info = {
            "en_query": f"{spec} {maker}".strip(),
            "zh_query": f"{spec} {maker}".strip(),
            "key_specs": [],
            "negative_keywords": [],
            "product_category": "",
        }
        _cb(f"  Query builder lỗi ({e}), dùng spec gốc")

    en_query = query_info.get("en_query", spec)
    zh_query = query_info.get("zh_query", spec)
    key_specs = query_info.get("key_specs", [])
    neg_kw = query_info.get("negative_keywords", [])

    platform_query = {
        "alibaba": en_query,
        "1688": zh_query,
        "taiwantrade": en_query,
        "ruten": zh_query,
        "made_in_china": en_query,
        "global_sources": en_query,
        "lcsc": en_query,
        "aliexpress": en_query,
        "ec21": en_query,
    }

    # ── Phase 3: Parallel Crawl ──
    _cb("Phase 3: Đang crawl các nền tảng...")
    all_raw: list[RawResult] = []
    all_stats: list[PlatformStats] = []

    async def _run_all():
        tasks = []
        for p in platforms:
            q = platform_query.get(p, en_query)
            tasks.append(crawl_platform(p, q, max_per_platform,
                                         progress_cb=lambda msg: _cb(msg)))
        return await asyncio.gather(*tasks, return_exceptions=True)

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        crawl_results = loop.run_until_complete(_run_all())
        loop.close()
    except Exception as e:
        crawl_results = []
        _cb(f"  Crawl lỗi: {e}")

    for item in crawl_results:
        if isinstance(item, Exception):
            _cb(f"  Một platform crawl thất bại: {item}")
            continue
        results, stats = item
        all_raw.extend(results)
        all_stats.append(stats)

    _cb(f"  Tổng kết quả thô: {len(all_raw)}")

    # ── Phase 2: Product Matcher ──
    _cb("Phase 2: Đang xác minh kết quả sản phẩm...")
    if all_raw:
        try:
            verified = verify_all(spec, key_specs, neg_kw, all_raw,
                                   progress_cb=lambda cur, tot: _cb(
                                       f"  Xác minh {cur}/{tot} kết quả..."))
        except Exception as e:
            _cb(f"  Xác minh lỗi ({e}), dùng kết quả thô")
            verified = [
                VerifiedResult(**asdict(r), match_confidence=0.6,
                               match_reason="Bỏ qua xác minh", status="review")
                for r in all_raw
            ]
    else:
        verified = []

    # Update platform stats
    all_stats = compute_platform_stats(all_stats, verified)

    # ── Phase 4: Synthesis ──
    _cb("Phase 4: Đang tổng hợp dữ liệu giá...")
    try:
        synthesis = synthesize(verified, spec, budget_usd)
    except Exception as e:
        _cb(f"  Tổng hợp lỗi: {e}")
        synthesis = {}

    # ── Phase 5: Agent Evaluation ──
    _cb("Phase 5: Đang đánh giá nhà cung cấp...")
    try:
        evaluation = evaluate(synthesis, spec, budget_usd)
    except Exception as e:
        _cb(f"  Đánh giá lỗi: {e}")
        evaluation = {}

    duration = round(time.time() - start_time, 1)
    _cb(f"Hoàn tất sau {duration}s")

    result = SearchResult(
        query_params={
            "spec": spec, "maker": maker, "bqms_code": bqms_code,
            "budget_usd": budget_usd, "platforms": platforms,
            "query_info": query_info,
        },
        platform_stats=[vars(s) for s in all_stats],
        verified_results=[asdict(r) for r in verified],
        synthesis=synthesis,
        evaluation=evaluation,
        total_duration_sec=duration,
        cache_used=False,
    )

    # ── Save cache ──
    try:
        save_search_cache(key, platforms, spec, vars(result), db_path)
    except Exception:
        pass

    return result


# ─────────────────────────────────────────────────────────────
# DB helpers for price_confirmed and search_cache
# ─────────────────────────────────────────────────────────────

def init_market_tables(db_path: str = "./bsmq.db"):
    """Create market-related tables if they don't exist."""
    import sqlite3
    con = sqlite3.connect(db_path)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS price_confirmed (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        bqms_code       TEXT,
        product_name    TEXT    NOT NULL,
        spec            TEXT,
        maker           TEXT,
        confirmed_price REAL    NOT NULL,
        currency        TEXT    DEFAULT 'USD',
        price_usd       REAL,
        supplier_name   TEXT,
        supplier_url    TEXT,
        platform        TEXT,
        moq             INTEGER,
        notes           TEXT,
        confirmed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS search_cache (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        cache_key   TEXT    UNIQUE NOT NULL,
        platforms   TEXT,
        query       TEXT,
        result_json TEXT,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)
    con.commit()
    con.close()


def save_confirmed_price(data: dict, db_path: str = "./bsmq.db"):
    """Save a confirmed price to price_confirmed table."""
    import sqlite3
    # normalize price_usd
    price = float(data.get("confirmed_price", 0))
    currency = data.get("currency", "USD")
    price_usd = to_usd(price, currency)

    con = sqlite3.connect(db_path)
    con.execute("""
        INSERT INTO price_confirmed
          (bqms_code, product_name, spec, maker,
           confirmed_price, currency, price_usd,
           supplier_name, supplier_url, platform, moq, notes)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        data.get("bqms_code", ""),
        data.get("product_name", ""),
        data.get("spec", ""),
        data.get("maker", ""),
        price, currency, price_usd,
        data.get("supplier_name", ""),
        data.get("supplier_url", ""),
        data.get("platform", ""),
        data.get("moq", 0),
        data.get("notes", ""),
    ))
    # also update products table if bqms_code exists
    if data.get("bqms_code"):
        con.execute("""
            UPDATE products
            SET price=?, price_source=?, price_updated=date('now'), price_status='ok', updated_at=CURRENT_TIMESTAMP
            WHERE code=?
        """, (price_usd, data.get("supplier_name", ""), data.get("bqms_code")))
    con.commit()
    con.close()


def get_confirmed_prices(bqms_code: str = "", db_path: str = "./bsmq.db") -> list[dict]:
    """Fetch saved confirmed prices, optionally filtered by bqms_code."""
    import sqlite3
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    if bqms_code:
        rows = con.execute(
            "SELECT * FROM price_confirmed WHERE bqms_code=? ORDER BY confirmed_at DESC",
            (bqms_code,)
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT * FROM price_confirmed ORDER BY confirmed_at DESC LIMIT 200"
        ).fetchall()
    con.close()
    return [dict(r) for r in rows]


def delete_confirmed_price(row_id: int, db_path: str = "./bsmq.db"):
    import sqlite3
    con = sqlite3.connect(db_path)
    con.execute("DELETE FROM price_confirmed WHERE id=?", (row_id,))
    con.commit()
    con.close()


def get_search_cache(cache_key: str, db_path: str = "./bsmq.db",
                     ttl_hours: int = 24) -> Optional[dict]:
    """Return cached result if still valid, else None."""
    import sqlite3
    con = sqlite3.connect(db_path)
    row = con.execute(
        "SELECT result_json, created_at FROM search_cache WHERE cache_key=?",
        (cache_key,)
    ).fetchone()
    con.close()
    if not row:
        return None
    created_at = datetime.fromisoformat(row[1])
    if datetime.utcnow() - created_at > timedelta(hours=ttl_hours):
        return None
    try:
        return json.loads(row[0])
    except Exception:
        return None


def save_search_cache(cache_key: str, platforms: list, query: str,
                      result: dict, db_path: str = "./bsmq.db"):
    import sqlite3
    # Exclude large verified_results from cache to save space
    cache_data = {k: v for k, v in result.items() if k != "verified_results"}
    # Keep top 20 verified for display
    cache_data["verified_results"] = result.get("verified_results", [])[:20]
    con = sqlite3.connect(db_path)
    con.execute("""
        INSERT OR REPLACE INTO search_cache (cache_key, platforms, query, result_json)
        VALUES (?,?,?,?)
    """, (cache_key, json.dumps(platforms), query, json.dumps(cache_data, ensure_ascii=False)))
    con.commit()
    con.close()
