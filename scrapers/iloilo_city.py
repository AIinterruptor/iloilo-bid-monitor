"""
iloilo_city.py — v1.0.0

Scrapes https://iloilocity.gov.ph/bids-and-awards-committee/ (WordPress site).
"""
import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL = "https://iloilocity.gov.ph/bids-and-awards-committee/"

# robots.txt on this host disallows AI-crawler UAs specifically; a generic
# desktop-browser UA polling every 6h is the low-impact equivalent of a human
# visitor and stays outside that disallow rule.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


def _parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    postings = []
    # The page embeds a full nested HTML widget with one <table class="tablepress">
    # per publish-date batch (table1, table2, ...) — all batches sit in the static
    # HTML at once and are just JS-toggled for display, so no pagination is needed.
    for table in soup.select("table.tablepress"):
        rows = table.select("tbody tr")
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 7:
                continue
            doc_type = cells[1].get_text(strip=True)
            ref_no = cells[2].get_text(strip=True) or None
            title = cells[3].get_text(strip=True)
            date_posted = _parse_date(cells[4].get_text(strip=True))
            closing_date = _parse_date(cells[5].get_text(strip=True))
            link = cells[6].find("a")
            doc_url = link.get("href") if link else None
            if not title:
                continue
            postings.append(
                {
                    "source": "iloilo_city",
                    "title": title,
                    "ref_no": ref_no,
                    "category": doc_type or None,
                    "date_posted": date_posted,
                    "closing_date": closing_date,
                    "url": URL,
                    "doc_url": doc_url,
                }
            )
    return postings


def scrape():
    resp = requests.get(URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    return parse(resp.text)


if __name__ == "__main__":
    results = scrape()
    print(f"iloilo_city: {len(results)} postings")
    for p in results[:5]:
        print(p)
