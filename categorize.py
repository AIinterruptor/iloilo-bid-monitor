"""
categorize.py — v1.0.0

Keyword-based auto-tagging of postings by title, distinct from the raw
`category` field each scraper already extracts from its source page.
"""

# Order matters: first bucket whose keyword matches wins, so more specific
# buckets (IT/Technology) are checked before generic catch-alls.
CATEGORY_KEYWORDS = [
    ("IT/Technology", [
        "ict", "computer", "laptop", "software", "server", "network",
        "printer", "cctv", "internet", "wifi", "website", "system",
        "database", "biometric",
    ]),
    ("Construction/Infrastructure", [
        "construction", "repair", "rehabilitation", "improvement", "building",
        "road", "bridge", "drainage", "concreting", "renovation", "electrical",
        "plumbing", "civil works", "infrastructure", "flood control",
        "waterworks", "solar panel system",
    ]),
    ("Consulting/Professional Services", [
        "consulting", "consultancy", "professional service", "training",
        "audit", "legal service", "design service", "supervision",
        "facilitator", "resource person", "service provider",
    ]),
    ("Goods & Supplies", [
        "supply and delivery", "supplies", "materials", "equipment",
        "furniture", "medicine", "medical", "food", "catering", "fuel",
        "vehicle", "uniform", "office supplies", "groceries", "veterinary",
    ]),
]

DEFAULT_CATEGORY = "Other"


def categorize(title):
    text = (title or "").lower()
    for label, keywords in CATEGORY_KEYWORDS:
        if any(kw in text for kw in keywords):
            return label
    return DEFAULT_CATEGORY


def apply_categories(postings):
    for p in postings:
        p["category_tag"] = categorize(p.get("title"))
    return postings
