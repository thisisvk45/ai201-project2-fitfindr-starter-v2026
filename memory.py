"""
Style memory (stretch): a wardrobe that survives between runs.

When run_agent(..., remember=True) finishes with a pick, the pick is saved here
as a wardrobe item. On the next remembering run, saved items are added to the
wardrobe before suggest_outfit sees it.

The file is local and ignored by git. `python app.py forget` clears it.
"""

import json
import os
from pathlib import Path

import config

MEMORY_PATH = Path(os.getenv("FITFINDR_MEMORY", config.ROOT / ".fitfindr_memory.json"))


def load_memory() -> list[dict]:
    """Saved wardrobe items, oldest first. An empty list when nothing is saved."""
    if not MEMORY_PATH.exists():
        return []
    try:
        data = json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data.get("items", []) if isinstance(data, dict) else []


def with_memory(wardrobe: dict) -> dict:
    """A copy of the wardrobe with saved items added after the user's own."""
    items = list(wardrobe.get("items", []))
    known = {item.get("id") for item in items}
    items += [item for item in load_memory() if item.get("id") not in known]
    return {**wardrobe, "items": items}


def remember_item(listing: dict) -> dict:
    """Save a picked listing as a wardrobe item and return what was saved."""
    item = {
        "id": f"mem_{listing['id']}",
        "name": listing["title"],
        "category": listing["category"],
        "colors": list(listing.get("colors", [])),
        "style_tags": list(listing.get("style_tags", [])),
        "notes": f"Saved by FitFindr from {listing['platform']} listing {listing['id']}",
    }
    items = [saved for saved in load_memory() if saved.get("id") != item["id"]]
    items.append(item)
    MEMORY_PATH.write_text(json.dumps({"items": items}, indent=2), encoding="utf-8")
    return item


def forget() -> int:
    """Delete the memory file. Returns how many items it held."""
    count = len(load_memory())
    if MEMORY_PATH.exists():
        MEMORY_PATH.unlink()
    return count
