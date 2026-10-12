"""
The FitFindr planning loop.

This is the file that makes FitFindr an agent rather than a script. It decides
which tool to run next based on what the last one returned.

If your loop calls all three tools no matter what comes back, you have a list
of function calls. A loop looks at the last result before it picks the next
step. **That branch is the graded part of this unit.**

Build and test your three tools in `tools.py` first. Then come here.

    python agent.py          runs both example paths below
"""

import re

import config
import trace
from tools import suggest_outfit, create_fit_card, compare_price
from mcp_client import call_tool
from generate import ModelUnavailable
import memory


# ── session state ─────────────────────────────────────────────────────────────

def new_session(query: str, wardrobe: dict) -> dict:
    """
    A fresh session for one user interaction.

    The session is the single source of truth for a run. Every tool result goes
    in here, and the next tool reads it back out.

    You could pass values straight from one call to the next. It would work,
    and you would not be able to test it — you can't print a variable you have
    already overwritten. Going through the session is what makes the state
    visible, and unit 4 has you write a criterion about exactly that.

    Add fields if you need them.
    """
    return {
        "query": query,              # what the user typed
        "parsed": {},                # description / size / max_price you pulled out of it
        "search_results": [],        # everything search_listings returned
        "selected_item": None,       # the one you chose — goes into suggest_outfit
        "outfit_input_item": None,   # exact item supplied to suggest_outfit
        "wardrobe": wardrobe,        # the user's wardrobe
        "outfit_suggestion": None,   # what suggest_outfit returned
        "fit_card": None,            # what create_fit_card returned
        "error": None,               # set when the run ended early
        "price_check": None,         # compare_price result for the final pick
        "price_branch": None,        # what the second branch did, if it ran
        "original_pick": None,       # first pick, kept when the branch switches
        "remembered_item": None,     # what style memory saved after this run
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict, remember: bool = False) -> dict:
    """
    Run the loop once and return the finished session.

    Args:
        query:    what the user asked for, e.g. "vintage graphic tee under $30".
        wardrobe: get_example_wardrobe() or get_empty_wardrobe().
        remember: add saved items to the wardrobe and save the final pick
                  (style memory, see memory.py).

    Returns:
        The session dict. If session["error"] is set, the search was empty and
        the run stopped before suggest_outfit.

    Steps: search_listings, then compare_price, then suggest_outfit, then
    create_fit_card. Branch 1: an empty search stops the run. Branch 2: a pick
    that is above typical, with no price limit, triggers a second search under
    the category median.
    """
    if remember:
        wardrobe = memory.with_memory(wardrobe)
    session = new_session(query, wardrobe)
    session["parsed"] = _parse_query(query)

    next_step = "search"
    iterations = 0
    while next_step:
        iterations += 1
        trace.check_iterations(iterations)

        if next_step == "search":
            parsed = session["parsed"]
            session["search_results"] = _search(
                parsed["description"], parsed["size"], parsed["max_price"]
            )

            if not session["search_results"]:
                session["error"] = (
                    "I couldn't find a listing that fits those details. Try broadening "
                    "the description, choosing another size, or raising the price limit."
                )
                return session

            session["selected_item"] = session["search_results"][0]
            next_step = "compare_price"
            continue

        if next_step == "compare_price":
            pick = session["selected_item"]
            session["price_check"] = compare_price(pick)

            # Second branch: the first pick is above typical for its category
            # and the user set no price limit, so look for a cheaper match.
            if (
                session["price_check"]["verdict"] == "above typical"
                and session["parsed"]["max_price"] is None
            ):
                cheaper = [
                    item for item in _search(
                        session["parsed"]["description"],
                        session["parsed"]["size"],
                        session["price_check"]["median_price"],
                    )
                    if item["category"] == pick["category"] and item["id"] != pick["id"]
                ]
                if cheaper:
                    session["original_pick"] = pick
                    session["selected_item"] = cheaper[0]
                    session["price_check"] = compare_price(cheaper[0])
                    session["price_branch"] = "switched to a cheaper pick"
                else:
                    session["price_branch"] = "no cheaper match, kept the first pick"

            next_step = "suggest_outfit"
            continue

        if next_step == "suggest_outfit":
            session["outfit_input_item"] = session["selected_item"]
            session["outfit_suggestion"] = suggest_outfit(
                session["outfit_input_item"], session["wardrobe"]
            )
            next_step = "create_fit_card"
            continue

        if next_step == "create_fit_card":
            session["fit_card"] = create_fit_card(
                session["outfit_suggestion"], session["selected_item"]
            )
            next_step = None

    if remember:
        session["remembered_item"] = memory.remember_item(session["selected_item"])
    return session


def _search(description: str, size, max_price) -> list[dict]:
    """search_listings, called through the MCP server in mcp_server.py."""
    return call_tool("search_listings", {
        "description": description,
        "size": size,
        "max_price": max_price,
    })


def _parse_query(query: str) -> dict:
    """Extract the supported structured filters without asking the user twice.

    A small regex parser is deliberate here: price and size have clear forms in
    the supplied CLI examples, so model parsing would spend an extra call and
    make the deterministic search branch harder to test.
    """
    normalized = " ".join(query.strip().split())
    price_match = re.search(r"\bunder\s*\$?\s*(\d+(?:\.\d+)?)\b", normalized, re.I)
    size_match = re.search(
        r"\b(?:in\s+)?size\s+(XXS|XS|S|M|L|XL|XXL|\d+(?:\.\d+)?|W\d+)\b",
        normalized,
        re.I,
    )

    description = normalized
    if price_match:
        description = description.replace(price_match.group(0), " ")
    if size_match:
        description = description.replace(size_match.group(0), " ")
    description = " ".join(description.split()) or normalized

    return {
        "description": description,
        "size": size_match.group(1).upper() if size_match else None,
        "max_price": float(price_match.group(1)) if price_match else None,
    }


# ── running it directly ───────────────────────────────────────────────────────

def _show(session: dict) -> None:
    if session["error"]:
        print(f"  stopped: {session['error']}")
        print(f"  fit_card is {session['fit_card']!r} — it should still be None here")
        return

    item = session["selected_item"] or {}
    print(f"  found:    {item.get('title')} — ${item.get('price')} on {item.get('platform')}")
    print(f"  outfit:   {session['outfit_suggestion']}")
    print(f"  fit card: {session['fit_card']}")


if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe

    print("=== A query the data can match ===")
    _show(run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    ))

    print("\n=== A query it can't ===")
    _show(run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    ))

    print(
        "\nThe second one should stop before the fit card. If both paths look "
        "the same,\nthe branch isn't doing anything yet."
    )
