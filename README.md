# FitFindr

FitFindr is a small shopping agent for the supplied thrift listings. A user
describes an item, optionally gives a size and budget, and receives a matching
listing, outfit ideas, and a short caption for the find. The agent keeps one
session dictionary so each step can use the result of the previous step without
asking the user for the same information again. If search finds nothing, the
agent stops immediately and gives the user a specific way to broaden the
request.

![FitFindr agent flow](docs/agent_flow.svg)

## What This Does

FitFindr parses a plain language request with a small regular expression
parser. It recognizes a size request such as `size M` and a budget such as
`under $30`, then searches the forty provided listings. The search tool ranks
keyword matches and applies inclusive size and price filters. When a match
exists, FitFindr selects the first result, asks for outfit ideas using the
saved wardrobe, and writes a short fit card with the item price and platform.

## Tool Inventory

### `search_listings`

**What it does:** Searches the provided listings with a description, optional
size, and optional maximum price.

**Inputs:** `description` is a `str`. `size` is a `str | None`.
`max_price` is a `float | None`.

**Returns:** A ranked `list[dict]` with at most ten listing dictionaries.
Every dictionary includes `id`, `title`, `description`, `category`,
`style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and
`platform`.

**When it has nothing:** Returns an empty list.

### `suggest_outfit`

**What it does:** Uses a selected listing and wardrobe to suggest one or two
wearable combinations.

**Inputs:** `new_item` is one listing `dict`. `wardrobe` is a `dict`
whose `items` key holds a list of wardrobe items.

**Returns:** A nonempty `str` with outfit ideas. When a wardrobe exists, the
prompt asks for exact owned pieces. When it is empty, the prompt asks for
general styling ideas instead.

**When it has nothing:** An empty wardrobe is handled as a normal case. An
empty model response becomes a useful retry message.

### `create_fit_card`

**What it does:** Turns a listing and outfit idea into a short caption that
could accompany the find.

**Inputs:** `outfit` is the `str` returned by `suggest_outfit`.
`new_item` is the selected listing `dict`.

**Returns:** A two to four sentence `str` that asks the model to include the
item name, exact price, and platform.

**When it has nothing:** Blank outfit text returns a message explaining that an
outfit suggestion is needed first.

## Planning Loop

The planning loop lives in `agent.py::run_agent`. It is a state machine with
three possible actions: search, suggest an outfit, and create a fit card.

1. It parses the query and stores `description`, `size`, and `max_price`
   in `session["parsed"]`.
2. It stores the search output in `session["search_results"]`.
3. If that list is empty, it stores a message in `session["error"]` and
   returns immediately. It does not call either model backed tool.
4. If results exist, it stores the first result in
   `session["selected_item"]`, copies the same object to
   `session["outfit_input_item"]`, and calls `suggest_outfit`.
5. It stores the outfit text in `session["outfit_suggestion"]`, then passes
   it with the same selected item to `create_fit_card`.
6. It stores the final caption in `session["fit_card"]` and returns the
   complete session.

![FitFindr session state](docs/session_state.svg)

The parser is deliberately deterministic. Prices and sizes have clear patterns
in the provided command examples, so a model call would make a simple filter
harder to test and would ask the user to spend another model request.

## Sample Run

The following completed run came from `python app.py ask '90s track jacket in
size M'`.

```
Found: 90s Track Jacket, Navy and White Stripe, $45.0 on poshmark

Outfit:
Pair the track jacket with the white ribbed tank top, baggy straight leg jeans,
chunky white sneakers, and the black crossbody bag for a sporty 90s look.

Fit card:
Scored this Champion 90s track jacket on poshmark for $45.0. The navy and white
stripe detail works with a white tank and baggy denim for an easy weekend fit.
```

These are the three tool checks run from the terminal.

```
$ python -c "from tools import search_listings; print([(x['id'], x['price']) for x in search_listings('90s track jacket', size='M')])"
[('lst_004', 45.0), ('lst_022', 75.0), ('lst_013', 30.0), ('lst_032', 33.0)]
```

```
$ python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[3], get_example_wardrobe()))"
Pair the Champion track jacket with a white ribbed tank top, baggy straight leg
jeans, chunky white sneakers, and a black crossbody bag.
```

```
$ python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('White ribbed tank top, baggy jeans, chunky sneakers, and a black crossbody bag.', load_listings()[3]))"
Found a Champion track jacket on poshmark for $45.0. The navy and white stripe
detail gives the outfit a clean sporty 90s feel.
```

The empty search path was also checked with `designer ballgown size XXS under
$5`. It returned an error message that suggests broadening the description,
changing the size, or raising the price limit. Its selected item, outfit
suggestion, and fit card remained `None`.

## How I Used AI

### Moment 1

**What I asked for:** I asked Codex to inspect the supplied listings before
writing the search tool and identify size formats that could make a simple
substring check wrong.

**What came back:** The data includes values such as `S/M`, `M/L`, `W30`,
`US 8`, and `US 8.5`. A substring check would let a request for size 8
match size 8.5 and could confuse apparel sizes with shoe sizes.

**What I changed:** I wrote separate matching rules for apparel ranges, waist
sizes, and numeric shoe sizes. The search check now confirms that `W30`
selects the W30 jeans and size 8 selects the US 8 sneakers rather than US 8.5.

### Moment 2

**What I asked for:** I asked Codex to inspect the planned state handoff and
explain how a future test could prove that the item search selected was the
same item passed to the outfit tool.

**What came back:** Reading only a generated outfit would not prove the item
handoff, because a model can paraphrase an item. The session needs a visible
record of the exact input used for the outfit call.

**What I changed:** I added `session["outfit_input_item"]`. The loop copies
the selected listing there before calling `suggest_outfit`, which makes the
two item ids directly comparable during Unit 4 testing.

## Running the Project

Activate the local environment, then run one of the commands below.

```
source .venv/bin/activate
python test.py
python app.py ask '90s track jacket in size M'
python app.py ask 'designer ballgown size XXS under $5'
```

The project uses Python 3.11. Put the existing Gemini key in `.env` as
`GEMINI_API_KEY=...`. The file is ignored by Git and must never be committed.
