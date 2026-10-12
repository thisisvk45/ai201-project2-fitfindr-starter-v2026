"""
The three FitFindr tools.

Each one is a standalone function you can call and test on its own, before any
of them are wired into the loop. Build and test them one at a time — three
untested tools joined by a loop is one problem that looks like six, because you
can't tell which layer is lying to you.

    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)             → str
    create_fit_card(outfit, new_item)              → str
    compare_price(new_item)                        → dict   (stretch)

⚠️ Before you write any of them, fill in the **Tool Inventory** section of your
README (Milestone 2). Four lines per tool: what it does, each input with its
type, exactly what it returns, and what it returns when it has nothing to give.
That last line is what your loop branches on. "Returns a list" earns nothing —
the description has to say what is *in* the list.
"""

import re
import statistics

import config
from generate import generate
from utils.data_loader import load_listings


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the listings data for items matching a description, and optionally a
    size and a price ceiling.

    This is the tool that doesn't call the model, which makes it the easiest one
    to test and the one to move onto MCP in unit 4.

    Args:
        description: keywords describing what the user wants
                     (e.g. "vintage graphic tee").
        size:        a size string to filter by, or None to skip size filtering.
                     Match case-insensitively — "M" should match "S/M".

                     ⚠️ Read the sizes in the data before you reach for a plain
                     substring test. `"s" in "us 9"` is True, and so is
                     `"l" in "xl"`. A filter that returns shoes when someone
                     asked for a small top reads like a broken search, and it
                     will quietly cost you in unit 4 when you test criterion 1.
                     What counts as a size match is part of your spec — decide
                     it and write it into your Tool Inventory.
        max_price:   maximum price, inclusive, or None to skip price filtering.

    Returns:
        A list of matching listing dicts, best match first.
        **Returns an empty list when nothing matches — an empty list, not None,
        and not an exception.** Your loop branches on this.

    Each listing dict has these fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand (str or None), platform

    Note that `brand` is None for most listings. That is deliberate and
    realistic — thrift listings often have no brand. If something you write
    assumes a brand is always there, you will find out in unit 4.

    Test it from a terminal before you move on:
        python -c "from tools import search_listings; print(search_listings('graphic tee', max_price=30))"
    """
    requested_terms = _terms(description)
    ranked: list[tuple[int, dict]] = []

    for listing in load_listings():
        if max_price is not None and listing["price"] > max_price:
            continue
        if size and not _size_matches(size, listing["size"]):
            continue

        searchable = _listing_text(listing)
        matches = sum(term in searchable for term in requested_terms)
        exact_phrase = " ".join(requested_terms) in searchable
        score = matches + (3 if exact_phrase and requested_terms else 0)
        if score:
            ranked.append((score, listing))

    ranked.sort(key=lambda result: (-result[0], result[1]["price"], result[1]["id"]))
    return [listing for _, listing in ranked[: config.SEARCH_RESULT_LIMIT]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest one or two outfits.

    This one calls the model, through `generate()`. You don't need to think
    about rate limits — the adapter handles pacing for you.

    Args:
        new_item: a listing dict — the item the user is considering.
        wardrobe: a wardrobe dict with an 'items' key holding a list of items.
                  **It may be empty.** Handle that.

    Returns:
        A non-empty string with outfit suggestions.
        With an empty wardrobe, return general styling advice rather than
        raising or returning "". Unit 4 has you trigger the empty wardrobe on
        purpose, so decide now what it should do.

    Test it from a terminal before you move on:
        python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[0], get_example_wardrobe()))"
    """
    item_summary = _item_summary(new_item)
    wardrobe_items = wardrobe.get("items", [])

    if wardrobe_items:
        closet = "\n".join(
            f"- {item.get('name', 'unnamed item')} "
            f"({item.get('category', 'unknown category')}; "
            f"colors: {', '.join(item.get('colors', []))}; "
            f"tags: {', '.join(item.get('style_tags', []))})"
            for item in wardrobe_items
        )
        prompt = f"""You are a practical personal stylist. Suggest one or two outfits around this potential thrift find:
{item_summary}

The user already owns:
{closet}

Name the exact wardrobe pieces that work with the find. Keep the answer under 120 words and do not invent items. Write plain text with no markdown: no asterisks, no headings."""
    else:
        prompt = f"""You are a practical personal stylist. Give one or two general styling ideas for this potential thrift find:
{item_summary}

The user has not listed any wardrobe items, so do not claim they own specific pieces. Suggest broadly available pairings. Keep the answer under 120 words. Write plain text with no markdown: no asterisks, no headings."""

    response = generate(prompt).strip()
    return response or "No outfit suggestion was returned. Try the item again."


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Write a short caption someone would actually post about the find.

    This calls the model too.

    Args:
        outfit:   the outfit suggestion string from suggest_outfit().
        new_item: the listing dict for the item.

    Returns:
        A two-to-four sentence caption.
        If `outfit` is empty or whitespace, return a descriptive message rather
        than raising.

    The caption should read like a real post rather than a product description,
    mention the item and its price and platform once each, and be specific about
    the vibe.

    It should also come out **differently for different inputs**. If you run
    this three times on the same item and get three word-for-word identical
    strings, it's one of two things, and both are near the top of `config.py`:

        • CACHE_ENABLED — the adapter handed back an answer it already had
        • TEMPERATURE   — at 0.0 the model gives the same words every time

    Test it from a terminal before you move on:
        python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('jeans and white sneakers', load_listings()[0]))"
    """
    if not outfit or not outfit.strip():
        return "I need an outfit suggestion before I can make a fit card."

    prompt = f"""Write a natural, two-to-four sentence thrift-find caption. It must mention the item's title, exact price, and platform once each. Keep the tone specific and postable, not salesy.

Item:
{_item_summary(new_item)}

Outfit idea:
{outfit.strip()}

Return only the caption."""
    response = generate(prompt).strip()
    return response or "I found the item, but could not generate a fit card yet."


# ── Tool 4 (stretch): compare_price ─────────────────────────────────────────

# A pick is "above typical" when it costs more than 1.2 times the median price
# of the other listings in its category, and "below typical" under 0.8 times.
PRICE_ABOVE_RATIO = 1.2
PRICE_BELOW_RATIO = 0.8


def compare_price(new_item: dict) -> dict:
    """
    Compare one listing's price with the other listings in the same category.

    Deterministic, no model call.

    Args:
        new_item: a listing dict with at least id, category and price.

    Returns:
        A dict with item_id (str), item_price (float), category (str),
        compared_count (int), median_price (float | None),
        lowest_price (float | None) and verdict (str): one of
        "below typical", "typical", "above typical" or "no comparison".

    When it has nothing: if no other listing shares the category, it returns
    compared_count 0, median_price and lowest_price None, and the verdict
    "no comparison".
    """
    others = [
        listing["price"] for listing in load_listings()
        if listing["category"] == new_item.get("category")
        and listing["id"] != new_item.get("id")
    ]
    result = {
        "item_id": new_item.get("id"),
        "item_price": float(new_item.get("price", 0)),
        "category": new_item.get("category"),
        "compared_count": len(others),
        "median_price": None,
        "lowest_price": None,
        "verdict": "no comparison",
    }
    if not others:
        return result

    median = float(statistics.median(others))
    result["median_price"] = median
    result["lowest_price"] = float(min(others))
    price = result["item_price"]
    if price > median * PRICE_ABOVE_RATIO:
        result["verdict"] = "above typical"
    elif price < median * PRICE_BELOW_RATIO:
        result["verdict"] = "below typical"
    else:
        result["verdict"] = "typical"
    return result


# ── Search helpers ───────────────────────────────────────────────────────────

_STOP_WORDS = {
    "a", "an", "and", "for", "in", "looking", "of", "on", "the", "to",
    "under", "want", "with",
}


def _terms(text: str) -> list[str]:
    """Lowercase searchable words, preserving useful terms such as ``90s``."""
    return [
        word for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in _STOP_WORDS
    ]


def _listing_text(listing: dict) -> str:
    """The fields a buyer can reasonably expect a text search to use."""
    values = [
        listing.get("title", ""),
        listing.get("description", ""),
        listing.get("category", ""),
        listing.get("brand") or "",
        *listing.get("style_tags", []),
        *listing.get("colors", []),
    ]
    return " ".join(str(value).lower() for value in values)


def _size_matches(requested: str, available: str) -> bool:
    """Match apparel, waist, and shoe sizes without substring false positives."""
    wanted = requested.strip().upper().replace(" ", "")
    offered = available.strip().upper()
    offered_compact = offered.replace(" ", "")
    if not wanted:
        return True

    # Shoe sizes: ``8`` is a match for ``US 8``, but not ``US 8.5`` or ``W28``.
    if re.fullmatch(r"\d+(?:\.\d+)?", wanted):
        number = re.escape(wanted)
        return bool(re.search(rf"(?<![\d.]){number}(?![\d.])", offered))

    # Waist/inseam requests are written in the data as W30, W28, and so on.
    if re.fullmatch(r"W\d+", wanted):
        return bool(re.search(rf"{re.escape(wanted)}(?!\d)", offered_compact))

    # S/M and M/L are ranges; extract only clothing-size tokens so ``S`` does
    # not accidentally match the S in ``US 9`` or in ``oversized``.
    if wanted in {"XXS", "XS", "S", "M", "L", "XL", "XXL"}:
        clothing_sizes = re.findall(r"(?<![A-Z])(XXL|XXS|XL|XS|S|M|L)(?![A-Z])", offered)
        return wanted in clothing_sizes

    return wanted == offered_compact


def _price_text(price) -> str:
    """How a price tag reads: $45 for whole dollars, $45.50 otherwise."""
    if price is None:
        return "price unknown"
    price = float(price)
    return f"${price:.0f}" if price.is_integer() else f"${price:.2f}"


def _item_summary(item: dict) -> str:
    """A stable, complete listing description for the two model prompts."""
    brand = item.get("brand") or "unbranded"
    return (
        f"{item.get('title', 'Unnamed item')} — {_price_text(item.get('price'))} "
        f"on {item.get('platform', 'unknown platform')}; size {item.get('size', 'unknown')}; "
        f"{item.get('condition', 'unknown')} condition; brand: {brand}; "
        f"colors: {', '.join(item.get('colors', []))}; "
        f"tags: {', '.join(item.get('style_tags', []))}. "
        f"Description: {item.get('description', '')}"
    )
