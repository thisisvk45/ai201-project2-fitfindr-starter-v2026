# Acceptance criteria for FitFindr

These criteria define working behavior before Unit 4 testing begins. Each one
has a measurable target and a reason grounded in the listings data or the
agent pipeline.

## 1. A matching query completes all three tools

Given a query that matches at least one listing, the agent completes all three
tool calls and returns a fit card in at least 4 of 5 tries.

**Why this target:** Search is a deterministic keyword matcher, but its results
depend on the phrasing used in a request and on the fields available in the
forty supplied listings. The two model backed tools can also vary between
runs. Four of five leaves room for one variation while still requiring a
reliable end to end path.

## 2. An impossible query stops before the second tool

Given a query that matches no listings, the agent stops before calling
`suggest_outfit` and returns a message naming what the user can change in 5 of
5 tries.

**Why this target:** This decision happens in deterministic code immediately
after search returns an empty list. It does not depend on a model response, so
the empty path should be reliable every time.

## 3. The selected item survives the state handoff

For 5 matching queries, `session["selected_item"]["id"]` equals
`session["outfit_input_item"]["id"]`, and both values are present.

**Why this target:** The agent stores the first ranked search result before it
calls `suggest_outfit`. Comparing the two recorded ids directly tests the
state handoff instead of guessing from the wording of a model response.

## 4. A fit card includes purchase details in a short caption

For at least 4 of 5 successful runs, the fit card has two to four sentences and
mentions the selected item's price and platform.

**Why this target:** Fit cards are model generated and can vary in tone and
wording, but a shopper still needs the price and marketplace. The prompt asks
for these facts, while a four of five target recognizes that model output is
not deterministic.

## 5. A price ceiling is respected

For 5 queries that include a maximum price, every selected item has a price
less than or equal to `session["parsed"]["max_price"]`.

**Why this target:** The listings contain prices both above and below common
price ceilings. The comparison is performed by the search tool rather than a
model, so selecting an item above the stated budget would be an unambiguous
filtering defect.
