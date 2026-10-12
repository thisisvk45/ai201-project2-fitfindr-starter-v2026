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
from tools import suggest_outfit, create_fit_card
from mcp_client import call_tool, MCPError
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
        The session dict. If session["error"] is set, the run stopped early:
        an empty search, the search service failing, or the model being
        unreachable. Later fields stay None.

    Steps: search_listings, then compare_price, then suggest_outfit, then
    create_fit_card. Branch 1: an empty search stops the run. Branch 2: a pick
    that is above typical, with no price limit, triggers a second search under
    the category median. search_listings and compare_price go through MCP.
    """
    if remember:
        wardrobe = memory.with_memory(wardrobe)
    session = new_session(query, wardrobe)
    session["parsed"] = _parse_query(query)
    trace.step("parse_query", inputs=query, returned=_args(session["parsed"]))

    next_step = "search"
    iterations = 0
    while next_step:
        iterations += 1
        trace.check_iterations(iterations)

        if next_step == "search":
            parsed = session["parsed"]
            try:
                session["search_results"] = _search(
                    parsed["description"], parsed["size"], parsed["max_price"]
                )
            except MCPError as exc:
                session["error"] = (
                    "The listings search service didn't respond, so I couldn't search. "
                    "Check that `python mcp_server.py` starts without an error, then try again."
                )
                trace.step("search_listings (via MCP)", inputs=_args(parsed), returned=str(exc),
                           note="MCP call failed, stopping")
                return session

            if not session["search_results"]:
                trace.step("search_listings (via MCP)", inputs=_args(parsed),
                           returned=session["search_results"],
                           note="branch 1: empty, stopping before suggest_outfit")
                session["error"] = (
                    "I couldn't find a listing that fits those details. Try broadening "
                    "the description, choosing another size, or raising the price limit."
                )
                return session

            trace.step("search_listings (via MCP)", inputs=_args(parsed),
                       returned=session["search_results"])
            session["selected_item"] = session["search_results"][0]
            next_step = "compare_price"
            continue

        if next_step == "compare_price":
            pick = session["selected_item"]
            session["price_check"] = _compare(pick)
            trace.step("compare_price (via MCP)", inputs=pick,
                       returned=_price_summary(session["price_check"]))

            # Second branch: the first pick is above typical for its category
            # and the user set no price limit, so look for a cheaper match.
            if (
                session["price_check"]["verdict"] == "above typical"
                and session["parsed"]["max_price"] is None
            ):
                limit = session["price_check"]["median_price"]
                found = _search(
                    session["parsed"]["description"], session["parsed"]["size"], limit
                )
                cheaper = [
                    item for item in found
                    if item["category"] == pick["category"] and item["id"] != pick["id"]
                ]
                if cheaper:
                    session["original_pick"] = pick
                    session["selected_item"] = cheaper[0]
                    session["price_branch"] = "switched to a cheaper pick"
                else:
                    session["price_branch"] = "no cheaper match, kept the first pick"
                trace.step("search_listings (via MCP)",
                           inputs=_args({**session["parsed"], "max_price": limit}),
                           returned=cheaper,
                           note=f"branch 2: above typical, {session['price_branch']}")
                if cheaper:
                    session["price_check"] = _compare(cheaper[0])
                    trace.step("compare_price (via MCP)", inputs=cheaper[0],
                               returned=_price_summary(session["price_check"]))

            next_step = "suggest_outfit"
            continue

        if next_step == "suggest_outfit":
            session["outfit_input_item"] = session["selected_item"]
            try:
                session["outfit_suggestion"] = suggest_outfit(
                    session["outfit_input_item"], session["wardrobe"]
                )
            except ModelUnavailable as exc:
                return _model_down(session, "suggest_outfit", exc)
            trace.step("suggest_outfit",
                       inputs=f"new_item={session['outfit_input_item']['title']!r}, "
                              f"wardrobe={len(session['wardrobe'].get('items', []))} items",
                       returned=session["outfit_suggestion"])
            next_step = "create_fit_card"
            continue

        if next_step == "create_fit_card":
            try:
                session["fit_card"] = create_fit_card(
                    session["outfit_suggestion"], session["selected_item"]
                )
            except ModelUnavailable as exc:
                return _model_down(session, "create_fit_card", exc)
            trace.step("create_fit_card",
                       inputs=f"outfit=<from session>, new_item={session['selected_item']['title']!r}",
                       returned=session["fit_card"])
            next_step = None

    if remember:
        session["remembered_item"] = memory.remember_item(session["selected_item"])
        trace.step("style memory", returned=session["remembered_item"]["name"],
                   note="saved for the next --remember run")
    return session


def _model_down(session: dict, tool: str, exc: Exception) -> dict:
    """Stop with a message the user can act on when the model can't be reached."""
    item = session["selected_item"] or {}
    session["error"] = (
        f"I found {item.get('title', 'a listing')} (${item.get('price')} on "
        f"{item.get('platform')}), but the styling model couldn't be reached, so I "
        f"couldn't write the outfit or fit card. {exc} Then try again."
    )
    trace.step(tool, returned=str(exc), note="model unavailable, stopping")
    return session


def _args(values: dict) -> str:
    return ", ".join(f"{key}={value!r}" for key, value in values.items())


def _price_summary(check: dict) -> str:
    return (f"{check['verdict']}: ${check['item_price']} vs median "
            f"${check['median_price']} ({check['compared_count']} compared)")


def _search(description: str, size, max_price) -> list[dict]:
    """search_listings, called through the MCP server in mcp_server.py."""
    return call_tool("search_listings", {
        "description": description,
        "size": size,
        "max_price": max_price,
    })


def _compare(item: dict) -> dict:
    """compare_price, called through the MCP server in mcp_server.py."""
    return call_tool("compare_price", {"new_item": item})


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
