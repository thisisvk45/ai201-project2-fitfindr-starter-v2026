"""
How each try is scored against criteria.md. ← UNIT 4

One function per criterion. Each takes the finished session (or None if the
run crashed) and returns (passed, reason). run_eval.py calls check() for every
try and writes PASS or FAIL with the reason underneath.
"""

import re

# The targets from criteria.md, as passes needed out of five.
TARGETS = {1: 4, 2: 5, 3: 5, 4: 4, 5: 5}

_FALLBACKS = (
    "No outfit suggestion was returned",
    "I need an outfit suggestion",
    "could not generate a fit card",
)


def check(criterion: int, session: dict | None) -> tuple[bool, str]:
    if session is None:
        return False, "the run crashed"
    return _CHECKS[criterion](session)


def _c1(s):
    if s.get("error"):
        return False, f"stopped early: {s['error'][:80]}"
    for field in ("outfit_suggestion", "fit_card"):
        text = (s.get(field) or "").strip()
        if not text or any(f in text for f in _FALLBACKS):
            return False, f"{field} missing or a fallback message"
    return True, "search, outfit and fit card all returned"


def _c2(s):
    if not s.get("error"):
        return False, "did not stop"
    if s.get("outfit_input_item") is not None or s.get("outfit_suggestion") is not None:
        return False, "suggest_outfit was called"
    if s.get("fit_card") is not None:
        return False, "a fit card was made"
    if not re.search(r"description|size|price", s["error"], re.I):
        return False, "message does not name what to change"
    return True, "stopped before suggest_outfit, message names what to change"


def _c3(s):
    a, b = s.get("selected_item"), s.get("outfit_input_item")
    if not a or not b:
        return False, "selected_item or outfit_input_item missing"
    if a["id"] != b["id"]:
        return False, f"ids differ: {a['id']} vs {b['id']}"
    return True, f"both {a['id']}"


def sentence_count(text: str) -> int:
    parts = [p for p in re.split(r"(?<=[.!?])\s+", text.strip()) if p.strip()]
    return len(parts)


def mentions_price(text: str, price: float) -> bool:
    whole = int(price)
    if price == whole:
        pattern = rf"\$\s?{whole}(?:\.0{{1,2}})?(?!\d)|(?<![\d.]){whole}(?:\.0{{1,2}})?\s?(?:dollars|USD)"
    else:
        pattern = rf"\$\s?{price:.2f}|\$\s?{price:g}(?!\d)"
    return bool(re.search(pattern, text, re.I))


def _c4(s):
    card = (s.get("fit_card") or "").strip()
    item = s.get("selected_item") or {}
    if s.get("error") or not card:
        return False, "no fit card"
    n = sentence_count(card)
    misses = []
    if not 2 <= n <= 4:
        misses.append(f"{n} sentences")
    if not mentions_price(card, float(item["price"])):
        misses.append(f"no ${item['price']}")
    if item["platform"].lower() not in card.lower():
        misses.append(f"no {item['platform']}")
    if misses:
        return False, ", ".join(misses)
    return True, f"{n} sentences, price and {item['platform']} present"


def _c5(s):
    limit = (s.get("parsed") or {}).get("max_price")
    item = s.get("selected_item")
    if limit is None:
        return False, "no price limit parsed"
    if not item:
        return False, "nothing selected"
    if item["price"] > limit:
        return False, f"${item['price']} is over ${limit}"
    return True, f"${item['price']} <= ${limit}"


_CHECKS = {1: _c1, 2: _c2, 3: _c3, 4: _c4, 5: _c5}
