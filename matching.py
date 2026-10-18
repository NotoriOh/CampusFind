import re

from difflib import SequenceMatcher
from datetime import date

def calculate_match_score(lost_item: dict, found_item: dict) -> dict:
    """Return the match score and the reasons for awarded points."""
    lost_tokens = get_item_name_tokens(lost_item["item_name"])
    found_tokens = get_item_name_tokens(found_item["item_name"])

    if not (lost_tokens & found_tokens):
        return {"score": 0, "reasons": []}

    score = 0
    reasons = []

    if lost_item["category"] == found_item["category"]:
        score += 30
        reasons.append("Same category (+30/30)")

    lost_color = lost_item["color"].strip().lower()
    found_color = found_item["color"].strip().lower()

    if lost_color and lost_color == found_color:
        score += 20
        reasons.append("Same color (+20/20)")

    if lost_item["location"] == found_item["location"]:
        score += 20
        reasons.append("Same location (+20/20)")

    date_score = 0

    try:
        lost_date = date.fromisoformat(lost_item["event_date"])
        found_date = date.fromisoformat(found_item["event_date"])
    except (ValueError, TypeError):
        date_score = 0
    else:
        days_apart = (found_date - lost_date).days

        if 0 <= days_apart <= 3:
            date_score = 15 - days_apart * 3
        elif 4 <= days_apart <= 7:
            date_score = 3

        if date_score > 0:
            if days_apart == 0:
                reasons.append("Found on the same day (+15/15)")
            else:
                unit = "day" if days_apart == 1 else "days"
                reasons.append(
                    f"Found {days_apart} {unit} after loss (+{date_score}/15)"
                )

    score += date_score

    lost_name = " ".join(lost_item["item_name"].lower().split())
    found_name = " ".join(found_item["item_name"].lower().split())

    if lost_name and found_name:
        name_similarity = SequenceMatcher(None, lost_name, found_name).ratio()
        name_score = round(name_similarity * 15)
        score += name_score

        if name_score > 0:
            if lost_name == found_name:
                reasons.append("Same item name (+15/15)")
            else:
                reasons.append(f"Item name similarity (+{name_score}/15)")

    return {"score": score, "reasons": reasons}

def get_item_name_tokens(name: str) -> set[str]:
    aliases = {
        "airpods": "earbuds",
        "airpod": "earbuds",
        "earbud": "earbuds",
        "earphone": "earbuds",
        "earphones": "earbuds",
        "headphones": "headphones",
        "calculators": "calculator",
        "iphone": "phone",
        "smartphone": "phone",
        "phones": "phone",
        "macbook": "laptop",
        "laptops": "laptop",
        "backpack": "bag",
        "backpacks": "bag",
        "bags": "bag",
    }

    ignored = {
    "a", "an", "the", "my",
    "lost", "found", "item",
    "pro", "max", "mini",
    "apple", "samsung",
    "white", "black", "blue", "red",
    "green", "silver", "gold",
    "gray", "grey", "pink",
    "case", "cover",
    }

    words = re.findall(r"[^\W_]+", name.casefold())

    return {
        aliases.get(word, word)
        for word in words
        if word not in ignored
    }

def find_matches(lost_item: dict, items: list[dict]) -> list[dict]:
    """Return up to three available matches scoring at least 50."""
    if lost_item["report_type"] != "LOST" or lost_item["status"] != "Open":
        return []

    try:
        lost_date = date.fromisoformat(lost_item["event_date"])
    except (ValueError, TypeError):
        return []

    matches = []

    for found_item in items:
        if found_item["report_type"] != "FOUND":
            continue

        if found_item["status"] != "Open":
            continue

        try:
            found_date = date.fromisoformat(found_item["event_date"])
        except (ValueError, TypeError):
            continue

        if found_date < lost_date:
            continue

        result = calculate_match_score(lost_item, found_item)

        if result["score"] >= 50:
            matches.append({
                "item": found_item,
                "score": result["score"],
                "reasons": result["reasons"],
            })

    matches.sort(key=lambda match: match["score"], reverse=True)
    return matches[:3]
