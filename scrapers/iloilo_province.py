"""
iloilo_province.py — v1.0.0

Scrapes https://iloilo.gov.ph/en/bac-reports-view (Drupal site, ~665 pages of
historical entries). page=0 is newest-first (verified live: entries sort by
"created" date descending).
"""
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://iloilo.gov.ph"
LIST_URL = "https://iloilo.gov.ph/en/bac-reports-view"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Full-history first run would be 665 pages of a low-value historical archive;
# this cap bootstraps a useful initial dataset without hammering the site.
FIRST_RUN_PAGE_CAP = 5

REF_PATTERN = re.compile(r"[A-Z]{2,4}-\d{2}-\d{3,4}-[A-Z](?:\s*\(RE-BID\))?", re.I)


def _parse_date(raw):
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None


def _extract_ref_no(title):
    m = REF_PATTERN.search(title or "")
    return m.group(0).strip() if m else None


def parse(html):
    soup = BeautifulSoup(html, "html.parser")
    postings = []
    table = soup.select_one("table.table-bordered")
    if not table:
        return postings
    rows = table.select("tbody tr")
    for row in rows:
        title_cell = row.select_one("td.views-field-title")
        type_cell = row.select_one("td.views-field-field-report-type")
        date_cell = row.select_one("td.views-field-created")
        doc_cell = row.select_one("td.views-field-field-view-document")
        if not title_cell:
            continue
        title_link = title_cell.find("a")
        title = title_link.get_text(strip=True) if title_link else title_cell.get_text(strip=True)
        node_url = urljoin(BASE_URL, title_link["href"]) if title_link and title_link.get("href") else LIST_URL

        # A posting can carry multiple taxonomy tags (e.g. "Bids and Awards" +
        # "Invitation To Bid"); join them so no signal used for categorize.py is lost.
        category = None
        if type_cell:
            tags = [a.get_text(strip=True) for a in type_cell.find_all("a")]
            category = " / ".join(t for t in tags if t) or None

        date_posted = _parse_date(date_cell.get_text(strip=True)) if date_cell else None

        doc_url = None
        if doc_cell:
            doc_link = doc_cell.find("a")
            doc_url = doc_link.get("href") if doc_link else None

        ref_no = _extract_ref_no(title)

        postings.append(
            {
                "source": "iloilo_province",
                "title": title,
                "ref_no": ref_no,
                "category": category,
                "date_posted": date_posted,
                "closing_date": None,
                "url": node_url,
                "doc_url": doc_url,
            }
        )
    return postings


def _fetch_page(session, page_index):
    params = {} if page_index == 0 else {"page": page_index}
    resp = session.get(LIST_URL, params=params, timeout=30)
    resp.raise_for_status()
    return resp.text


def scrape(seen_urls=None):
    """
    seen_urls: set of already-known posting `url` values (node URLs) from
    data/postings.json, used as the incremental stop condition. None/empty
    means first-ever run, so we apply FIRST_RUN_PAGE_CAP instead of a stop
    condition that would never trigger.
    """
    seen_urls = seen_urls or set()
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    all_postings = []
    page_index = 0
    while True:
        html = _fetch_page(session, page_index)
        page_postings = parse(html)
        if not page_postings:
            break

        if seen_urls:
            new_on_page = [p for p in page_postings if p["url"] not in seen_urls]
            all_postings.extend(new_on_page)
            if len(new_on_page) < len(page_postings):
                # hit a previously-seen entry -> everything older is already stored
                break
        else:
            all_postings.extend(page_postings)
            if page_index + 1 >= FIRST_RUN_PAGE_CAP:
                break

        page_index += 1

    return all_postings


if __name__ == "__main__":
    results = scrape()
    print(f"iloilo_province: {len(results)} postings")
    for p in results[:5]:
        print(p)
