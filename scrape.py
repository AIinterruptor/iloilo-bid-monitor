"""
scrape.py — v1.2.0

Orchestrator: runs all three source scrapers, normalizes, categorizes,
dedupes against the existing store, and writes back newest-first.

Output lives under docs/ (not the repo root) because GitHub Pages, configured
to serve from docs/, cannot reach a file outside that folder -- the dashboard
fetches this same path client-side as a relative URL.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from categorize import apply_categories
from scrapers import guimaras, iloilo_city, iloilo_province

DATA_PATH = Path(__file__).parent / "docs" / "data" / "postings.json"


def _dedupe_key(posting):
    # Live data breaks the naive "ref_no is unique" assumption: Iloilo City
    # re-lists the same PR number across multiple publish-date batches when a
    # bid fails to attract bidders and gets reposted with a new closing date
    # and a new document -- each is a distinct, currently-open opportunity,
    # so collapsing them on ref_no alone would silently drop live postings.
    # doc_url is unique per posting instance for city/guimaras; province
    # instead uses its canonical node URL (already unique, handles RE-BID).
    if posting["source"] == "iloilo_province":
        return (posting["source"], posting["url"])
    if posting.get("doc_url"):
        return (posting["source"], posting["doc_url"])
    # Some City rows have no doc_url (source lists the filename as plain text,
    # not a link) AND a junk ref_no ("INFRA", "GOODS" -- a mis-scraped category
    # label, not an actual PR number) shared by dozens of unrelated postings.
    # title+date_posted is the identifier that actually holds unique in that
    # case; ref_no alone silently collapsed ~25 distinct INFRA postings into 1.
    if posting.get("ref_no") and posting["ref_no"].strip().lower() not in ("infra", "goods"):
        return (posting["source"], posting["ref_no"])
    return (posting["source"], posting.get("title"), posting.get("date_posted"), posting["url"])


def load_existing():
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def run():
    existing = load_existing()
    existing_keys = {_dedupe_key(p) for p in existing}
    # province scraper needs prior node URLs to know where to stop paginating
    existing_province_urls = {p["url"] for p in existing if p["source"] == "iloilo_province"}

    fresh = []
    fresh.extend(iloilo_city.scrape())
    fresh.extend(iloilo_province.scrape(seen_urls=existing_province_urls))
    fresh.extend(guimaras.scrape())

    apply_categories(fresh)

    new_count = 0
    for posting in fresh:
        key = _dedupe_key(posting)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        existing.append(posting)
        new_count += 1

    existing.sort(key=lambda p: p.get("date_posted") or "", reverse=True)

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return {
        "iloilo_city": sum(1 for p in fresh if p["source"] == "iloilo_city"),
        "iloilo_province": sum(1 for p in fresh if p["source"] == "iloilo_province"),
        "guimaras": sum(1 for p in fresh if p["source"] == "guimaras"),
        "new_postings": new_count,
        "total_postings": len(existing),
    }


if __name__ == "__main__":
    stats = run()
    print(json.dumps(stats, indent=2))
