# FitFindr

![FitFindr agent flow](docs/agent_flow.svg)

## What This Does

A user types what they want, for example `90s track jacket in size M` or
`vintage graphic tee under $30`. FitFindr searches the 40 supplied listings,
picks one, checks its price against similar listings, suggests outfits from the
user's wardrobe and writes a short caption with the price and platform. If
nothing matches, it stops and tells the user what to change.

## Tool Inventory

### `search_listings`

- What it does: Keyword search over the listings, with optional size and
  price filters.
- Inputs: `description` (str), `size` (str or None), `max_price`
  (float or None, inclusive).
- Returns: `list[dict]`, at most 10 listing dicts, best keyword match first
  (ties go to the lower price). Each dict has `id`, `title`, `description`,
  `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`,
  `platform`.
- When it has nothing: an empty list `[]`.

Size rule: sizes are matched as tokens, not substrings. `8` matches
`US 8` but not `US 8.5`, `W30` matches `W30 L30`, and `S` matches `S/M` but not
the S in `US 9`.

### `suggest_outfit`

- What it does: Asks the model for one or two outfits built around the
  picked listing.
- Inputs: `new_item` (dict, one listing), `wardrobe` (dict with an
  `items` list).
- Returns: `str`, outfit ideas that name the user's own pieces.
- When it has nothing: with an empty wardrobe it asks for general styling
  ideas instead. If the model returns nothing, it returns a retry message.

### `create_fit_card`

- What it does: Asks the model for a caption someone could post.
- Inputs: `outfit` (str from `suggest_outfit`), `new_item` (dict).
- Returns: `str`, two to four sentences that ask for the title, exact price
  and platform once each.
- When it has nothing: a blank `outfit` returns "I need an outfit
  suggestion before I can make a fit card." without calling the model.

### `compare_price` (stretch)

- What it does: Compares one listing's price with the other listings in the
  same category. No model call.
- Inputs: `new_item` (dict).
- Returns: `dict` with `item_id`, `item_price`, `category`,
  `compared_count`, `median_price`, `lowest_price` and `verdict`. The verdict
  is `above typical` over 1.2 times the median, `below typical` under 0.8
  times, otherwise `typical`.
- When it has nothing: if no other listing shares the category,
  `compared_count` is 0, the prices are None and the verdict is
  `no comparison`.

## Planning Loop

Branch rule: If `search_listings` returns an empty list, put a message in
`session["error"]` that names what to change and stop, without calling
`suggest_outfit`. Otherwise take the first result and go to `compare_price`.

Second branch (stretch): If `compare_price` says the pick is
`above typical` and the user gave no price limit, search again with the
category median as the limit and keep only the same category. If that finds
something, switch to it. Otherwise keep the first pick. Then go to
`suggest_outfit`.

Where it lives: `agent.py::run_agent`

How the query is parsed: regex, in `agent.py::_parse_query`. It pulls out
`size X` and `under $N`, and the rest is the description. I thought a model
call here would cost a request and make the branch harder to test.

What moves through the session: `parsed`, `search_results`,
`selected_item`, `price_check`, `outfit_input_item`, `outfit_suggestion`,
`fit_card`. `error` is set only on an empty search. `original_pick` and
`price_branch` are set only when the second branch runs. Every tool reads its
input back out of the session, and `outfit_input_item` is copied from
`selected_item` so the two ids can be compared in Unit 4.

![FitFindr session state](docs/session_state.svg)

## Sample Run

Pasted as printed, except the model's markdown stars are removed.

### One full query

```
$ python app.py ask '90s track jacket in size M'

  Found:    90s Track Jacket — Navy/White Stripe — $45.0 on poshmark
  Price:    typical ($45.0 vs a median of $40.0 across 7 other outerwear)

  Outfit:   Here are two effortless ways to style your new Champion track jacket using pieces you already own:

Look 1: Streetwear Casual
Pair the track jacket unzipped over the white ribbed tank top, teamed with your baggy straight-leg jeans (dark wash). Finish the outfit with your chunky white sneakers and the black crossbody bag for an easy, sporty 90s aesthetic. 

Look 2: High-Low Contrast
Layer the track jacket over the white ribbed tank top, but tuck it into your wide-leg khaki trousers secured with the brown leather belt. Ground the look with your chunky white sneakers and carry the black crossbody bag for a clean, street-smart mix of athletic and minimal styles.

  Fit card: Scored this pristine Champion 90s Track Jacket on Poshmark for just $45.0, and it is the ultimate lightweight layer for throwing over a white tank and baggy denim. The navy and white sleeve detailing gives it such an authentic retro athletic feel.

0 model calls this session, 2 served from cache
```

### The empty search

```
$ python app.py ask 'designer ballgown size XXS under $5'

  I couldn't find a listing that fits those details. Try broadening the description, choosing another size, or raising the price limit.

0 model calls this session
```

### The tools, tested one at a time

```
$ python -c "from tools import search_listings; print([(x['id'], x['title'], x['price']) for x in search_listings('graphic tee', max_price=30)])"
[('lst_017', 'Mesh Long-Sleeve Top — Black', 15.0), ('lst_002', 'Y2K Baby Tee — Butterfly Print', 18.0), ('lst_033', 'Vintage Band Tee — Faded Grey', 19.0), ('lst_006', 'Graphic Tee — 2003 Tour Bootleg Style', 24.0), ('lst_012', 'Oversized Crewneck Sweatshirt — Vintage Navy', 20.0), ('lst_015', 'Vintage Graphic Hoodie — Faded Black', 26.0), ('lst_011', 'Low-Rise Cargo Pants — Khaki', 27.0)]
```

```
$ python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[3], get_example_wardrobe()))"
Here are two effortless ways to style your new Champion track jacket using pieces you already own:

...
```

```
$ python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('White ribbed tank top, baggy jeans and chunky white sneakers.', load_listings()[3]))"
Layered this 90s Champion track jacket over a white ribbed tank with baggy denim and chunky sneakers today. Found this lightweight navy and white striped piece in pristine condition for just $45.0 on poshmark. It's the ultimate effortless throw-on piece for transitional weather.
```

## Stretch Features

I declared these three before I built them.

1. A fourth tool, `compare_price`. It compares the selected listing's price
   with the other listings in the same category and returns the median, the
   lowest price and a verdict.
2. A second branch. If `compare_price` says the first pick is above typical
   for its category and the user gave no price limit, the loop searches again
   with the category median as the limit and switches to a cheaper result in
   the same category. If there is none, it keeps the first pick.
3. Style memory. With `--remember`, the agent saves each item it picks to a
   local file and adds saved items to the wardrobe on the next run.

### What each one changed

`compare_price` runs on every pick and prints the `Price:` line above.

Second branch, `leather jacket`: the $75 bomber was above typical with no price
limit, so the loop searched under the $40 median and switched to a $33 shacket.
I realised the cost: the shacket is not leather.

```
$ python app.py ask 'leather jacket'
  Found:    Shacket — Olive Canvas — $33.0 on poshmark
  Branch:   switched to a cheaper pick (first pick: 90s Leather Bomber — Black, $75.0)
  ...
```

Style memory, empty wardrobe both times: run 1 saved the carpenter jeans, and
run 2 built both outfits around them.

```
$ python app.py ask 'baggy carpenter jeans' --empty-wardrobe --remember
  Saved to style memory: Baggy Carpenter Jeans — Dark Wash

$ python app.py ask 'vintage band tee' --empty-wardrobe --remember
(style memory: 1 saved item(s) added to the wardrobe)
  Outfit:   Outfit 1: Effortless 90s Streetwear
  - Bottoms: Baggy Carpenter Jeans (Dark Wash)
  ...
```

Trimmed to the relevant lines. `python app.py forget` clears the memory.

## How I Used AI

1. I asked Codex which size formats in the listings would break a substring
   check. It found `S/M`, `W30`, `US 8` and `US 8.5`. I wrote separate rules for
   clothing, waist and shoe sizes, so size 8 no longer matches `US 8.5`.
2. I asked Codex how a test could prove the searched item reached
   `suggest_outfit`. It said the outfit text cannot prove it, because the model
   paraphrases. I added `session["outfit_input_item"]` so criterion 3 compares
   two ids.
3. I asked Claude to build the Unit 3 stretch features. Testing the second
   search without a category filter, `leather jacket` returned a leather belt
   first, so I kept that search to the same category.
4. In Unit 4 I asked Claude to score every try in code, one check per
   criterion. All 25 passed. Counting price formats then found 12 of 20 fit
   cards with $45.0, which became my improvement.

# Unit 4: Testing

![How the agent decides each step](docs/decisions.svg)

## Unit 4 Stretch Features

I declared these three before I built them.

1. A second tool on MCP: `compare_price`, alongside `search_listings`.
2. Retry with looser constraints: when a search with a size comes back empty,
   the loop searches once more without the size and says it dropped the size.
3. A second improvement from my diagnosis, measured with a third run log in
   the same format.

## Run Log: Before

From `run_eval.py::main`, scored by `checks.py::check`, cache off. Raw file:
`results/run_2026-10-11_2303_before.md`.

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. matching query completes | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 2. impossible query stops early | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 3. selected item reaches suggest_outfit | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4. fit card is short with price and platform | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 5. price ceiling is respected | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |

One try per criterion:

```
1  vintage graphic tee under $30   PASS, search, outfit and fit card all returned
   fit card: Found this dreamy little butterfly baby tee while digging through the racks this week. It’s listed on depop for $18.0 and looks so good thrown on with baggy denim and a zip-up hoodie. Snag it before I change my mind and keep it for myself!
2  designer ballgown size XXS under $5   PASS, stopped before suggest_outfit
   error: I couldn't find a listing that fits those details. I also tried without the size XXS. Try broadening the description, choosing another size, or raising the price limit.
3  leather jacket   PASS, both lst_032 (branch 2 switched from lst_022)
4  vintage band tee   PASS, 3 sentences, price and depop present
   fit card: Nothing beats a truly broken-in band tee, and this faded grey one is absolute perfection. I love the boxy fit and distressed graphic—it’s just the right amount of grunge. Grabbed it for $19.0 over on depop and I've already got it styled with baggy denim and chunky sneakers.
5  vintage graphic tee under $30   PASS, $18.0 <= $30.0
```

## Verdicts and Diagnoses

| # | Verdict | How I decided | Tighter target I would set |
|---|---|---|---|
| 1 | MET (5/5) | outfit and fit card every try | 5 of 5 over five different queries |
| 2 | MET (5/5) | stopped before `suggest_outfit` every try | five different impossible queries |
| 3 | MET (5/5) | ids matched, including the branch 2 switch | also check the pick against `search_results[0]` |
| 4 | MET (5/5) | 2 to 3 sentences, price and platform | 5 of 5, price written as $45 not $45.0 |
| 5 | MET (5/5) | every pick under the limit | include queries where branch 2 runs |

I revised no criteria. I thought 25 of 25 meant the agent worked. Then I
realised my targets were too easy, so I looked for what they missed:

- Prices printed as $45.0 in 12 of 20 fit cards. Place: the model output.
  Mechanism: `tools.py::_item_summary` passed the float price into the prompt,
  and the prompt asks for the exact price. My criterion 4 check accepted it.
- Markdown stars in 20 of 20 outfits. Place: the model output. Mechanism: the
  `suggest_outfit` prompt never asked for plain text.

## Loop Trace

`python app.py ask '90s track jacket in size M' --trace`

```
[1] parse_query
      in:  90s track jacket in size M
      out: description='90s track jacket', size='M', max_price=None
[2] search_listings (via MCP)
      in:  description='90s track jacket', size='M', max_price=None
      out: 4 items: 90s Track Jacket — Navy/White Stripe, 90s Leather Bomber — Black, 90s Silk Slip Dress — Floral, Midi Length … +1 more
[3] compare_price (via MCP)
      in:  90s Track Jacket — Navy/White Stripe ($45.0, poshmark)
      out: typical: $45.0 vs median $40.0 (7 compared)
[4] suggest_outfit
      in:  new_item='90s Track Jacket — Navy/White Stripe', wardrobe=10 items
      out: Outfit one leans into classic streetwear. Pair the champion track jacket with your white ribbed tank top as a …
[5] create_fit_card
      in:  outfit=<from session>, new_item='90s Track Jacket — Navy/White Stripe'
      out: Unearthed this authentic 90s Champion track jacket and I'm obsessed with the navy and white sleeve detailing. …
```

`python app.py ask 'designer ballgown size XXS under $5' --trace` stops after
search:

```
[1] parse_query
      in:  designer ballgown size XXS under $5
      out: description='designer ballgown', size='XXS', max_price=5.0
[2] search_listings (via MCP)
      in:  description='designer ballgown', size='XXS', max_price=5.0
      out: [] (empty)
      →    empty with size XXS, retrying without it
[3] search_listings (via MCP)
      in:  description='designer ballgown', size=None, max_price=5.0
      out: [] (empty)
      →    branch 1: empty, stopping before suggest_outfit
```

MCP move: `search_listings` is registered in `mcp_server.py` and called through
`mcp_client.call_tool` in `agent.py::_search`. I checked that it returns the
same list as the direct call. The only change I found is time: 0.43 s per
search against 0.001 s, because each call starts the server.

## Failure Modes

```
Empty search:
  I couldn't find a listing that fits those details. I also tried without the size XXS. Try broadening the description, choosing another size, or raising the price limit.

Empty wardrobe (--empty-wardrobe), suggest_outfit gives general advice:
  Outfit:   For an effortless casual daytime look, layer the cropped Wrangler jacket over a simple ribbed white tank top and high-waisted black wide-leg trousers. Finish this outfit with retro leather s...

Model unavailable (one character of the key changed for one run, new query):
  I found Corduroy Wide-Leg Pants — Rust ($32.0 on depop), but the styling model couldn't be reached, so I couldn't write the outfit or fit card. The model rejected your API key. Check GEMINI_API_KEY in your .env file, or create a fresh key at aistudio.google.com. Then try again.
```

For the bad key I changed one character for one run. `agent.py::_model_down`
catches `ModelUnavailable` and keeps the item it found.

## The Improvement

I changed `tools.py::_price_text` so prompts get $45, not $45.0. It targets the
$45.0 fit cards.

### Run Log: After

Raw file: `results/run_2026-10-11_2306_after.md`.

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. matching query completes | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 2. impossible query stops early | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 3. selected item reaches suggest_outfit | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4. fit card is short with price and platform | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 5. price ceiling is respected | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |

### Second Improvement (stretch)

I asked `suggest_outfit` for plain text. Raw file: `results/run_2026-10-11_2308_second.md`.

| Criterion | Target | Try 1 | Try 2 | Try 3 | Try 4 | Try 5 | Verdict |
|---|---|---|---|---|---|---|---|
| 1. matching query completes | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 2. impossible query stops early | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 3. selected item reaches suggest_outfit | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 4. fit card is short with price and platform | 4 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |
| 5. price ceiling is respected | 5 of 5 | PASS | PASS | PASS | PASS | PASS | MET (5/5) |

Both helped. The criteria stayed at 5/5, so I measured the two failures
directly:

```
$ python measure.py <before> <after> <second>
results/run_2026-10-11_2303_before.md
  fit cards with a price like $45.0: 12 of 20
  outfits with markdown stars:       20 of 20
results/run_2026-10-11_2306_after.md
  fit cards with a price like $45.0: 0 of 20
  outfits with markdown stars:       20 of 20
results/run_2026-10-11_2308_second.md
  fit cards with a price like $45.0: 0 of 20
  outfits with markdown stars:       0 of 20
```

Second MCP tool: `compare_price`, step 3 in the trace above. Retry:

```
[1] parse_query
      in:  leather bomber size S
      out: description='leather bomber', size='S', max_price=None
[2] search_listings (via MCP)
      in:  description='leather bomber', size='S', max_price=None
      out: [] (empty)
      →    empty with size S, retrying without it
[3] search_listings (via MCP)
      in:  description='leather bomber', size=None, max_price=None
      out: 4 items: 90s Leather Bomber — Black, Leather Belt — Brown, Braided, Mini Shoulder Bag — Tan Leather … +1 more
```

## What's Still Broken

- The model still names clothes the wardrobe does not hold. I stopped because
  checking it needs fuzzy name matching I have not built.
- The retry can return the wrong size. It says so, but does not ask first.

## Running the Project

```
source .venv/bin/activate
python test.py
python app.py ask '90s track jacket in size M'
python app.py ask 'leather jacket'
python app.py ask 'designer ballgown size XXS under $5'
python app.py ask 'baggy carpenter jeans' --empty-wardrobe --remember
python app.py memory
python app.py forget
```

Python 3.11. The Gemini key goes in `.env`, which git ignores.
