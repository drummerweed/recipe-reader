import requests
import extruct
from recipe_scrapers import scrape_html
from w3lib.html import get_base_url

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 15

# HTTP status codes that indicate bot-blocking (trigger Playwright fallback)
BLOCKED_CODES = {401, 403, 407, 429, 503}


def _minutes_to_str(minutes):
    """Convert integer minutes to a human-readable string."""
    if minutes is None:
        return None
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    mins = minutes % 60
    if mins == 0:
        return f"{hours} hr"
    return f"{hours} hr {mins} min"


def _safe(fn, default=None):
    """Call fn(), returning default on any exception."""
    try:
        result = fn()
        return result if result not in (None, "", [], {}) else default
    except Exception:
        return default


def _fetch_with_requests(url: str):
    """
    Fast HTTP fetch. Returns (html_str, None) on success,
    or (None, status_code_int) if blocked, or raises on network error.
    """
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    if response.status_code in BLOCKED_CODES:
        return None, response.status_code
    response.raise_for_status()
    return response.text, None


def _fetch_with_playwright(url: str) -> str:
    """
    Fallback fetch using a real headless Chromium browser.
    Renders the full page including JavaScript, bypassing most bot-detection.
    Returns the fully-rendered HTML string.
    """
    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
            ],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="en-US",
        )
        page = context.new_page()
        stealth_sync(page)

        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        # Brief wait for any lazy-loaded structured data scripts to execute
        page.wait_for_timeout(2000)

        html = page.content()
        browser.close()
        return html


def _extract_with_recipe_scrapers(html: str, url: str) -> dict:
    """Primary extraction using recipe-scrapers library."""
    scraper = scrape_html(html, org_url=url)

    ingredients = _safe(scraper.ingredients, [])
    instructions = _safe(scraper.instructions_list, [])

    if isinstance(instructions, str):
        instructions = [s.strip() for s in instructions.split("\n") if s.strip()]

    return {
        "title": _safe(scraper.title),
        "image": _safe(scraper.image),
        "description": _safe(scraper.description),
        "prep_time": _minutes_to_str(_safe(scraper.prep_time)),
        "cook_time": _minutes_to_str(_safe(scraper.cook_time)),
        "total_time": _minutes_to_str(_safe(scraper.total_time)),
        "yields": _safe(scraper.yields),
        "ingredients": ingredients,
        "instructions": instructions,
        "nutrients": _safe(scraper.nutrients, {}),
    }


def _extract_with_extruct(html: str, url: str) -> dict:
    """Fallback extraction using raw JSON-LD parsing via extruct."""
    base_url = get_base_url(html, url)
    data = extruct.extract(html, base_url=base_url, syntaxes=["json-ld"])
    json_ld_items = data.get("json-ld", [])

    def is_recipe(obj):
        if not isinstance(obj, dict):
            return False
        dtype = obj.get("@type")
        if isinstance(dtype, list):
            return "Recipe" in dtype
        return dtype == "Recipe"

    recipe = None
    for item in json_ld_items:
        if isinstance(item, dict) and "@graph" in item:
            for node in item.get("@graph", []):
                if is_recipe(node):
                    recipe = node
                    break
            if recipe: break
        
        if is_recipe(item):
            recipe = item
            break

    if not recipe:
        return None

    ingredients = recipe.get("recipeIngredient", [])

    raw_instructions = recipe.get("recipeInstructions", [])
    if isinstance(raw_instructions, str):
        instructions = [s.strip() for s in raw_instructions.split("\n") if s.strip()]
    elif isinstance(raw_instructions, list):
        instructions = []
        for step in raw_instructions:
            if isinstance(step, str):
                instructions.append(step.strip())
            elif isinstance(step, dict):
                text = step.get("text") or step.get("name", "")
                if text:
                    instructions.append(text.strip())
    else:
        instructions = []

    def parse_iso_duration(duration_str):
        if not duration_str:
            return None
        import re
        match = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?", duration_str)
        if not match:
            return None
        hours = int(match.group(1) or 0)
        mins = int(match.group(2) or 0)
        return _minutes_to_str(hours * 60 + mins)

    nutrition_raw = recipe.get("nutrition", {})
    nutrients = {}
    if isinstance(nutrition_raw, dict):
        for k, v in nutrition_raw.items():
            if k != "@type" and v:
                nutrients[k] = str(v)

    image = recipe.get("image")
    if isinstance(image, list):
        image = image[0]
    if isinstance(image, dict):
        image = image.get("url")

    return {
        "title": recipe.get("name"),
        "image": image,
        "description": recipe.get("description"),
        "prep_time": parse_iso_duration(recipe.get("prepTime")),
        "cook_time": parse_iso_duration(recipe.get("cookTime")),
        "total_time": parse_iso_duration(recipe.get("totalTime")),
        "yields": recipe.get("recipeYield"),
        "ingredients": ingredients,
        "instructions": instructions,
        "nutrients": nutrients,
    }


def _extract_recipe_from_html(html: str, url: str) -> dict | None:
    """Try recipe-scrapers first, fall back to extruct. Returns result or None."""
    result = None
    try:
        result = _extract_with_recipe_scrapers(html, url)
    except Exception:
        pass

    if not result or not result.get("ingredients"):
        try:
            fallback = _extract_with_extruct(html, url)
            if fallback and fallback.get("ingredients"):
                result = fallback
        except Exception:
            pass

    return result if (result and result.get("ingredients")) else None


def scrape_recipe(url: str) -> dict:
    """
    Main entry point. Fetches the URL and extracts recipe data.

    Strategy:
      1. Try a fast requests-based fetch.
      2. If blocked (403 etc.), retry with a real Playwright browser.
      3. In both cases, extraction is done by recipe-scrapers / extruct —
         recipe data is always taken verbatim from the page's structured data.

    Returns a dict with success=True and recipe fields, or success=False + error.
    """
    html = None
    used_playwright = False

    # ── Step 1: fast requests fetch ──────────────────────────────────────────
    try:
        html, blocked_code = _fetch_with_requests(url)
    except requests.exceptions.Timeout:
        return {"success": False, "error": "The request timed out. The site may be slow or blocking scrapers."}
    except requests.exceptions.HTTPError as e:
        return {"success": False, "error": f"HTTP error fetching page: {e}"}
    except requests.exceptions.RequestException as e:
        return {"success": False, "error": f"Could not fetch URL: {e}"}

    # ── Step 2: Playwright fallback if blocked ────────────────────────────────
    if html is None:
        try:
            html = _fetch_with_playwright(url)
            used_playwright = True
        except Exception as e:
            return {
                "success": False,
                "error": (
                    f"Site returned HTTP {blocked_code} and the browser fallback also failed: {e}. "
                    "This site may use advanced bot protection (e.g. Cloudflare)."
                ),
            }

    # ── Step 3: Extract recipe from HTML ─────────────────────────────────────
    result = _extract_recipe_from_html(html, url)

    if not result:
        return {
            "success": False,
            "error": (
                "No recipe data found on this page. "
                "The site may not use standard recipe markup, or it may block automated access."
            ),
        }

    result["success"] = True
    result["source_url"] = url
    result["used_browser"] = used_playwright
    return result
