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

- **What it does:** Keyword search over the listings, with optional size and
  price filters.
- **Inputs:** `description` (str), `size` (str or None), `max_price`
  (float or None, inclusive).
- **Returns:** `list[dict]`, at most 10 listing dicts, best keyword match first
  (ties go to the lower price). Each dict has `id`, `title`, `description`,
  `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`,
  `platform`.
- **When it has nothing:** an empty list `[]`.

I researched the size values before writing the filter. The data has `S/M`,
`W30 L30`, `US 8` and `US 8.5`, so a substring test would be wrong. Size 8
matches `US 8` but not `US 8.5`, and `S` does not match the S in `US 9`.

### `suggest_outfit`

- **What it does:** Asks the model for one or two outfits built around the
  picked listing.
- **Inputs:** `new_item` (dict, one listing), `wardrobe` (dict with an
  `items` list).
- **Returns:** `str`, outfit ideas that name the user's own pieces.
- **When it has nothing:** with an empty wardrobe it asks for general styling
  ideas instead. If the model returns nothing, it returns a retry message.

### `create_fit_card`

- **What it does:** Asks the model for a caption someone could post.
- **Inputs:** `outfit` (str from `suggest_outfit`), `new_item` (dict).
- **Returns:** `str`, two to four sentences that ask for the title, exact price
  and platform once each.
- **When it has nothing:** a blank `outfit` returns "I need an outfit
  suggestion before I can make a fit card." without calling the model.

### `compare_price` (stretch)

- **What it does:** Compares one listing's price with the other listings in the
  same category. No model call.
- **Inputs:** `new_item` (dict).
- **Returns:** `dict` with `item_id`, `item_price`, `category`,
  `compared_count`, `median_price`, `lowest_price` and `verdict`. The verdict
  is `above typical` over 1.2 times the median, `below typical` under 0.8
  times, otherwise `typical`.
- **When it has nothing:** if no other listing shares the category,
  `compared_count` is 0, the prices are None and the verdict is
  `no comparison`.

## Planning Loop

**Branch rule:** If `search_listings` returns an empty list, put a message in
`session["error"]` that names what to change and stop, without calling
`suggest_outfit`. Otherwise take the first result and go to `compare_price`.

**Second branch (stretch):** If `compare_price` says the pick is
`above typical` and the user gave no price limit, search again with the
category median as the limit and keep only the same category. If that finds
something, switch to it. Otherwise keep the first pick. Then go to
`suggest_outfit`.

**Where it lives:** `agent.py::run_agent`

**How the query is parsed:** regex, in `agent.py::_parse_query`. It pulls out
`size X` and `under $N`, and the rest is the description. I thought a model
call here would cost a request and make the branch harder to test.

**What moves through the session:** `parsed`, `search_results`,
`selected_item`, `price_check`, `outfit_input_item`, `outfit_suggestion`,
`fit_card`. `error` is set only on an empty search. `original_pick` and
`price_branch` are set only when the second branch runs. Every tool reads its
input back out of the session, and `outfit_input_item` is copied from
`selected_item` so the two ids can be compared in Unit 4.

![FitFindr session state](docs/session_state.svg)

## Sample Run

**One full query**

```
$ python app.py ask '90s track jacket in size M'

  Found:    90s Track Jacket — Navy/White Stripe — $45.0 on poshmark
  Price:    typical ($45.0 vs a median of $40.0 across 7 other outerwear)

  Outfit:   Here are two effortless ways to style your new Champion track jacket using pieces you already own:

**Look 1: Streetwear Casual**
Pair the track jacket unzipped over the **white ribbed tank top**, teamed with your **baggy straight-leg jeans (dark wash)**. Finish the outfit with your **chunky white sneakers** and the **black crossbody bag** for an easy, sporty 90s aesthetic. 

**Look 2: High-Low Contrast**
Layer the track jacket over the **white ribbed tank top**, but tuck it into your **wide-leg khaki trousers** secured with the **brown leather belt**. Ground the look with your **chunky white sneakers** and carry the **black crossbody bag** for a clean, street-smart mix of athletic and minimal styles.

  Fit card: Scored this pristine Champion 90s Track Jacket on Poshmark for just $45.0, and it is the ultimate lightweight layer for throwing over a white tank and baggy denim. The navy and white sleeve detailing gives it such an authentic retro athletic feel.

0 model calls this session, 2 served from cache
```

**The empty search**

```
$ python app.py ask 'designer ballgown size XXS under $5'

  I couldn't find a listing that fits those details. Try broadening the description, choosing another size, or raising the price limit.

0 model calls this session
```

**The tools, tested one at a time**

```
$ python -c "from tools import search_listings; print([(x['id'], x['title'], x['price']) for x in search_listings('graphic tee', max_price=30)])"
[('lst_017', 'Mesh Long-Sleeve Top — Black', 15.0), ('lst_002', 'Y2K Baby Tee — Butterfly Print', 18.0), ('lst_033', 'Vintage Band Tee — Faded Grey', 19.0), ('lst_006', 'Graphic Tee — 2003 Tour Bootleg Style', 24.0), ('lst_012', 'Oversized Crewneck Sweatshirt — Vintage Navy', 20.0), ('lst_015', 'Vintage Graphic Hoodie — Faded Black', 26.0), ('lst_011', 'Low-Rise Cargo Pants — Khaki', 27.0)]
```

```
$ python -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
[]
```

```
$ python -c "from tools import suggest_outfit; from utils.data_loader import get_example_wardrobe, load_listings; print(suggest_outfit(load_listings()[3], get_example_wardrobe()))"
Here are two effortless ways to style your new Champion track jacket using pieces you already own:

**Look 1: Streetwear Casual**
Pair the track jacket unzipped over the **white ribbed tank top**, teamed with your **baggy straight-leg jeans (dark wash)**. Finish the outfit with your **chunky white sneakers** and the **black crossbody bag** for an easy, sporty 90s aesthetic. 

**Look 2: High-Low Contrast**
Layer the track jacket over the **white ribbed tank top**, but tuck it into your **wide-leg khaki trousers** secured with the **brown leather belt**. Ground the look with your **chunky white sneakers** and carry the **black crossbody bag** for a clean, street-smart mix of athletic and minimal styles.
```

```
$ python -c "from tools import create_fit_card; from utils.data_loader import load_listings; print(create_fit_card('White ribbed tank top, baggy jeans and chunky white sneakers.', load_listings()[3]))"
Layered this 90s Champion track jacket over a white ribbed tank with baggy denim and chunky sneakers today. Found this lightweight navy and white striped piece in pristine condition for just $45.0 on poshmark. It's the ultimate effortless throw-on piece for transitional weather.
```

```
$ python -c "from tools import compare_price; from utils.data_loader import load_listings; print(compare_price(load_listings()[21]))"
{'item_id': 'lst_022', 'item_price': 75.0, 'category': 'outerwear', 'compared_count': 7, 'median_price': 40.0, 'lowest_price': 27.0, 'verdict': 'above typical'}
```

## Stretch Features

I declared these three before I built them.

1. **A fourth tool, `compare_price`.** It compares the selected listing's price
   with the other listings in the same category and returns the median, the
   lowest price and a verdict.
2. **A second branch.** If `compare_price` says the first pick is above typical
   for its category and the user gave no price limit, the loop searches again
   with the category median as the limit and switches to a cheaper result in
   the same category. If there is none, it keeps the first pick.
3. **Style memory.** With `--remember`, the agent saves each item it picks to a
   local file and adds saved items to the wardrobe on the next run.

### What each one changed

**`compare_price`.** The agent now calls it on every pick. The `Price:` line
in the full query above is its output: the track jacket is typical at $45
against a median of $40.

**Second branch.** For `leather jacket` the first pick was a $75 leather
bomber, above typical for outerwear, and I gave no price limit. The loop
searched again under the $40 outerwear median and switched to the shacket. The cost: the shacket is
not leather. For `cardigan` the pick was above typical but nothing cheaper
matched, so it kept the first pick.

```
$ python app.py ask 'leather jacket'

  Found:    Shacket — Olive Canvas — $33.0 on poshmark
  Price:    below typical ($33.0 vs a median of $42.0 across 7 other outerwear)
  Branch:   switched to a cheaper pick (first pick: 90s Leather Bomber — Black, $75.0)

  Outfit:   **Outfit 1: Casual Streetwear**
Layer the olive canvas shacket open over the white ribbed tank top and baggy dark-wash straight-leg jeans. Cinch the waist with the brown leather belt. Finish with the chunky white sneakers and the black crossbody bag for an easy, transitional everyday look.

**Outfit 2: Earth-Tone Minimal**
Wear the shacket layered directly over the white ribbed tank top, paired with the wide-leg khaki trousers and the brown leather belt. Ground the outfit with the black combat boots for contrast, and carry the black crossbody bag to keep the look effortless and practical.

  Fit card: Found the ultimate transitional layer in this olive canvas shacket—thicker than a shirt, lighter than a jacket, and the exact earthy green I’ve been hunting for. Picked it up on Poshmark for just $33.0, and it’s in amazing condition. Thinking it’ll look so good thrown over a white tank with wide-leg trousers for that easy, everyday uniform.

2 model calls this session, 614 prompt + 209 output tokens
```

```
$ python app.py ask 'cardigan'

  Found:    Knit Cardigan — Chunky Brown — $35.0 on depop
  Price:    above typical ($35.0 vs a median of $20.5 across 14 other tops)
  Branch:   no cheaper match, kept the first pick

  Outfit:   **Outfit 1: Casual Streetwear**
Layer the chunky brown cardigan over the white ribbed tank top and pair with your baggy dark-wash straight-leg jeans. Cinch the waist with the brown leather belt, and finish with the chunky white sneakers and black crossbody bag. 

**Outfit 2: Earth-Tone Minimalist**
Wear the cardigan open over the white ribbed tank top tucked into your wide-leg khaki trousers. Accessorize with the brown leather belt, and ground the look with the black combat boots for a cozy, grounded silhouette.

  Fit card: Found the ultimate chunky brown knit cardigan to live in all season. It’s in gorgeous shape, hits right at the hip, and is ready for all your oversized layering needs. Grab it on depop for $35.0 before I change my mind and keep it for myself.

2 model calls this session, 616 prompt + 172 output tokens
```

**Style memory.** Both runs use an empty wardrobe. The first run has nothing
saved, so the outfit is general advice. It saves the carpenter jeans. The
second run adds them to the wardrobe, and the outfit builds both looks around
them. The model also named pieces the wardrobe does not hold, such as a hoodie
and boots, even though the prompt says not to.

```
$ python app.py forget
Cleared 0 item(s) from style memory.

$ python app.py ask 'baggy carpenter jeans' --empty-wardrobe --remember
(running with an empty wardrobe)
(style memory: 0 saved item(s) added to the wardrobe)

  Found:    Baggy Carpenter Jeans — Dark Wash — $36.0 on depop
  Price:    typical ($36.0 vs a median of $30.0 across 9 other bottoms)

  Outfit:   At $36, these dark wash carpenter jeans are a versatile streetwear staple. Since they have a relaxed, 90s silhouette, balance the volume with your top half. 

**Idea 1: The Casual Streetwear Look**
Pair them with a cropped graphic tee or a fitted ribbed tank top to contrast the baggy fit. Layer with an unbuttoned flannel or a vintage leather bomber jacket, and finish with retro sneakers like chunky skate shoes.

**Idea 2: Elevated Workwear**
Lean into the utility aesthetic by tucking in a crisp, oversized white button-down shirt. Cinch the waist with a simple leather belt, and style with chunky loafers or leather boots for a cool, mixed-genre outfit.

  Fit card: Major 90s workwear vibes with these dark wash baggy carpenter jeans, complete with the classic side hammer loop. I just listed this W32 pair for $36 on depop, and they're ready to be styled with a fitted ribbed tank and retro skate shoes.

  Saved to style memory: Baggy Carpenter Jeans — Dark Wash

2 model calls this session, 434 prompt + 208 output tokens
$ python app.py ask 'vintage band tee' --empty-wardrobe --remember
(running with an empty wardrobe)
(style memory: 1 saved item(s) added to the wardrobe)

  Found:    Vintage Band Tee — Faded Grey — $19.0 on depop
  Price:    typical ($19.0 vs a median of $21.5 across 14 other tops)

  Outfit:   **Outfit 1: Effortless 90s Streetwear**
*   **Top:** Vintage Band Tee (Faded Grey)
*   **Bottoms:** Baggy Carpenter Jeans (Dark Wash)
*   **Footwear:** White Canvas Low-Top Sneakers 
*   **Layer:** Oversized Black Zip-Up Hoodie
*   **Accessories:** Silver Chain Necklace

**Outfit 2: Grungy Casual**
*   **Top:** Vintage Band Tee (Faded Grey)
*   **Bottoms:** Baggy Carpenter Jeans (Dark Wash)
*   **Footwear:** Black Leather Combat Boots
*   **Layer:** Distressed Red Flannel Shirt (worn open or tied around the waist)
*   **Accessories:** Black Webbed Belt with Metal Buckle

  Fit card: Found the ultimate boxy, well-loved vintage band tee with the best natural fade. I’ve got it listed over on depop for $19.0 to complete all your 90s streetwear fits. Throw it on with some baggy dark wash denim and combat boots and you're good to go.

  Saved to style memory: Vintage Band Tee — Faded Grey

2 model calls this session, 469 prompt + 229 output tokens
$ python app.py memory
Style memory holds 2 item(s):

  mem_lst_031  bottoms      Baggy Carpenter Jeans — Dark Wash
  mem_lst_033  tops         Vintage Band Tee — Faded Grey
```

`python app.py forget` clears the memory. The file, `.fitfindr_memory.json`,
is ignored by git.

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

### Moment 3

**What I asked for:** I asked Claude to build the three stretch features,
starting with a README declaration committed before any code.

**What came back:** When I tested the second search without a category
filter, `leather jacket` under $40 returned a leather belt first.

**What I changed:** The second search keeps only results in the same category
as the first pick, so the switch is from one jacket to another.

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
