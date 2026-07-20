"""
guimaras.py — v1.1.0

Scrapes guimaras.gov.ph Governance > Transparency subsections. Postings are
scanned/image PDFs -- no OCR, metadata-only per design.

Live survey (2026-07-20) found the six Transparency subsections are NOT a
uniform template, despite sharing nav placement:
  - Invitation to Bid: two-level -- an accordion index of month links, each
    month page holding the real Date/Description/ITB-Number/View table(s).
  - Bid Supplement: one-level -- a single flat Date/No./Description/Document
    table with all history on one page (plus legacy 3-column appendix tables
    further down, which lack a Date column and are skipped by that check).
  - Invitation to Quote, Negotiated Procurement, Small Value Procurement,
    Notice of Awards: content is stale (newest year found on each page was
    2019, 2019, 2020, and 2017/2021 respectively -- verified by full-page
    year-token count, not just top-of-accordion order). Deferred like
    PhilGEPS rather than scraped for dead data; revisit if the province
    resumes posting to them.
"""
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://guimaras.gov.ph"

ITB_INDEX_URL = f"{BASE_URL}/invitation-to-bid/"
BID_SUPPLEMENT_URL = f"{BASE_URL}/bid-supplement/"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# The ITB accordion goes back to 2017; walking it in full every 6h would be a
# large, low-value historical crawl, so only the newest month links are
# followed per run (first-run bootstrap and steady-state alike).
MONTH_PAGE_CAP = 3

MONTH_LOOKUP = {m.lower(): i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


def _parse_month_year_label(text):
    """'JULY  2026' -> (2026, 7) for sort purposes."""
    m = re.search(r"([A-Za-z]+)\s+(\d{4})", text or "")
    if not m:
        return None
    month = MONTH_LOOKUP.get(m.group(1).strip().lower())
    if not month:
        return None
    return (int(m.group(2)), month)


def _parse_full_date(text):
    """'JULY 15, 2026' -> '2026-07-15'."""
    text = (text or "").strip()
    for fmt in ("%B %d, %Y", "%B %d,%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_itb_index(html):
    """Returns (month_label, month_url) tuples sorted newest-first. DOM order
    isn't trustworthy across every Guimaras subsection (Notice of Awards
    listed 2017 first), so this sorts explicitly rather than assuming."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for panel in soup.select("div.panel.cpt, div.panels.cpt div.panel"):
        for a in panel.find_all("a", href=True):
            label = a.get_text(strip=True)
            key = _parse_month_year_label(label)
            if label and key:
                links.append((key, label, a["href"]))
    links.sort(key=lambda t: t[0], reverse=True)
    return [(label, href) for _, label, href in links]


def _last_pdf_href(cell):
    # "View" cells sometimes split the link text across two <a> tags
    # pointing at different hrefs (a stale one, then the real one) --
    # the last PDF href in the cell is consistently the current document.
    pdf_links = [a["href"] for a in cell.find_all("a", href=True) if ".pdf" in a["href"].lower()]
    return pdf_links[-1] if pdf_links else None


def parse_itb_month_page(html, month_url):
    soup = BeautifulSoup(html, "html.parser")
    postings = []
    content = soup.select_one("div.tem-2") or soup

    # Layout is a flat sequence of <h2>DATE</h2> followed by a <table>; walk
    # siblings rather than trying to nest them structurally.
    for heading in content.find_all("h2"):
        date_posted = _parse_full_date(heading.get_text())
        table = heading.find_next_sibling("table")
        if not table:
            continue
        rows = table.select("tbody tr")[1:]  # skip header row (NO./DESCRIPTION/...)
        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            title = cells[1].get_text(strip=True)
            if not title:
                continue
            ref_no = cells[2].get_text(strip=True) or None
            doc_url = _last_pdf_href(cells[-1])
            postings.append(
                {
                    "source": "guimaras",
                    "title": title,
                    "ref_no": ref_no,
                    "category": "Invitation to Bid",
                    "date_posted": date_posted,
                    "closing_date": None,
                    "url": month_url,
                    "doc_url": doc_url,
                }
            )
    return postings


def parse_bid_supplement(html):
    """Single flat page, all history in one table -- no pagination needed.
    Skips legacy appendix tables further down the page that lack a Date
    column (same template minus that field, PR-2020-era entries)."""
    soup = BeautifulSoup(html, "html.parser")
    postings = []
    content = soup.select_one("div.tem-2") or soup

    for table in content.select("table"):
        header_cells = [c.get_text(strip=True).lower() for c in table.select("tr")[0].find_all("td")]
        if not header_cells or header_cells[0] != "date":
            continue
        for row in table.select("tr")[1:]:
            cells = row.find_all("td")
            if len(cells) < 4:
                continue
            date_posted = _parse_full_date(cells[0].get_text(strip=True))
            ref_no = cells[1].get_text(strip=True) or None
            title = cells[2].get_text(strip=True)
            if not title:
                continue
            doc_url = _last_pdf_href(cells[3])
            postings.append(
                {
                    "source": "guimaras",
                    "title": title,
                    "ref_no": ref_no,
                    "category": "Bid Supplement",
                    "date_posted": date_posted,
                    "closing_date": None,
                    "url": BID_SUPPLEMENT_URL,
                    "doc_url": doc_url,
                }
            )
    return postings


def scrape():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    all_postings = []

    itb_resp = session.get(ITB_INDEX_URL, timeout=30)
    itb_resp.raise_for_status()
    month_links = parse_itb_index(itb_resp.text)[:MONTH_PAGE_CAP]
    for _, href in month_links:
        month_url = urljoin(BASE_URL, href)
        try:
            mresp = session.get(month_url, timeout=30)
            mresp.raise_for_status()
        except requests.RequestException:
            continue
        all_postings.extend(parse_itb_month_page(mresp.text, month_url))

    supp_resp = session.get(BID_SUPPLEMENT_URL, timeout=30)
    supp_resp.raise_for_status()
    all_postings.extend(parse_bid_supplement(supp_resp.text))

    return all_postings


if __name__ == "__main__":
    results = scrape()
    print(f"guimaras: {len(results)} postings")
    for p in results[:5]:
        print(p)
