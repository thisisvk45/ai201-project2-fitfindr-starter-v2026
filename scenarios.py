"""
The runs my test needs. ← UNIT 4, MILESTONE 3

run_eval.py runs every scenario five times. A scenario with a "queries" list
uses one query per try, in order, so a criterion written as "for 5 queries"
gets five different queries. checks.py decides PASS or FAIL for each try.
"""

SCENARIOS = [
    {
        # Criterion 1: one matching query, five tries.
        "name": "matching query completes",
        "query": "vintage graphic tee under $30",
        "wardrobe": "example",
        "criterion": 1,
    },
    {
        # Criterion 2: nothing can match, five tries.
        "name": "impossible query stops early",
        "query": "designer ballgown size XXS under $5",
        "wardrobe": "example",
        "criterion": 2,
    },
    {
        # Criterion 3: five matching queries. "leather jacket" takes branch 2,
        # so the item the outfit tool receives is not the first search result.
        "name": "selected item reaches suggest_outfit",
        "queries": [
            "90s track jacket in size M",
            "leather jacket",
            "silk slip dress in midi length under $40",
            "platform sneakers size 8",
            "denim jacket under $50",
        ],
        "wardrobe": "example",
        "criterion": 3,
    },
    {
        # Criterion 4: five different items, so five different fit cards.
        "name": "fit card is short with price and platform",
        "queries": [
            "vintage band tee",
            "corduroy pants",
            "knit cardigan",
            "baggy carpenter jeans",
            "vintage windbreaker",
        ],
        "wardrobe": "example",
        "criterion": 4,
    },
    {
        # Criterion 5: five queries with a price ceiling.
        "name": "price ceiling is respected",
        "queries": [
            "vintage graphic tee under $30",
            "denim jacket under $50",
            "silk slip dress under $40",
            "jeans under $35",
            "sneakers under $45",
        ],
        "wardrobe": "example",
        "criterion": 5,
    },
]

WARDROBES = ("example", "empty")


def query_for(scenario: dict, attempt: int) -> str:
    """The query for try number `attempt` (1-based)."""
    queries = scenario.get("queries")
    if queries:
        return queries[(attempt - 1) % len(queries)]
    return scenario["query"]


def validate() -> list[str]:
    """Complain about anything malformed, before a long run rather than during."""
    problems = []
    for i, scenario in enumerate(SCENARIOS, 1):
        if not scenario.get("query", "").strip() and not scenario.get("queries"):
            problems.append(f"scenario {i} has no query")
        if scenario.get("wardrobe") not in WARDROBES:
            problems.append(
                f"scenario {i} has wardrobe {scenario.get('wardrobe')!r} — "
                f"it should be one of {WARDROBES}"
            )
    return problems
