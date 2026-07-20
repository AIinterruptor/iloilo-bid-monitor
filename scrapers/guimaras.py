"""
guimaras.py — v1.0.0

Scrapes guimaras.gov.ph Governance > Transparency subsections. Each subsection
is a two-level structure: an index page with an accordion of month links,
each month link leading to a page holding the real posting table(s).
Postings are scanned/image PDFs -- no OCR, metadata-only per design.
"""
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://guimaras.gov.ph"

# category label -> subsection index URL. Every one of these follows the same
# accordion-of-months pattern confirmed live on Invitation to Bid / Notice of
# Awards; Bid Supplement, Invitation to Quote and the two Request for Price
# Quotation variants use the same WordPress "cpt" accordion template.
SUBSECTIONS = {
    "Invitation to Bid": f"{BASE_URL}/invitation-to-bid/",
    "Bid Supplement": f"{BASE_URL}/bid-supplement/",
    "Invitation to Quote": f"{BASE_URL}/invitation-to-quote/",
    "Negotiated Procurement": f"{BASE_URL}/negotiated-procurement-2/",
    "Small Value Procurement": f"{BASE_URL}/negotiated-procurement/",
    "Notice of Awards": f"{BASE_URL}/notice-of-awards/",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# Each subsection accordion goes back to 2017; walking it in full every 6h
# would be a large, low-value historical crawl, so only the newest month
# links are followed per run (first-run bootstrap and steady-state alike).
MONTH_PAGE_CAP = 3

MONTH_LOOKUP = {m.lower(): i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], start=1)}


def _parse_month_year_heading(text):
    """'JULY  2026' -> '2026-07-01' (day unknown at this granularity)."""
    m = re.search(r"([A-Za-z]+)\s+(\d{4})", text or "")
    if not m:
        return None
    month = MONTH_LOOKUP.get(m.group(1).strip().lower())
    if not month:
        return None
    return f"{m.group(2)}-{month:02d}-01"


def _parse_full_date(text):
    """'JULY 15, 2026' -> '2026-07-15'."""
    text = (text or "").strip()
    for fmt in ("%B %d, %Y", "%B %d,%Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_subsection_index(html):
    """Returns ordered list of (month_label, month_url) newest-first as they
    appear on the page -- the site lists current year's accordion panel first."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for panel in soup.select("div.panel.cpt, div.panels.cpt div.panel"):
        for a in panel.find_all("a", href=True):
            label = a.get_text(strip=True)
            if label:
                links.append((label, a["href"]))
    if not links:
        # Notice of Awards nests panels one level differently; fall back to
        # any cpt-title anchor on the page.
        for a in soup.select("a:has(h3.cpt-title)"):
            label = a.get_text(strip=True)
            if label and a.get("href"):
                links.append((label, a["href"]))
    return links


def _last_pdf_href(cell):
    # "View" cells sometimes split the link text across two <a> tags
    # pointing at different hrefs (a stale one, then the real one) --
    # the last PDF href in the cell is consistently the current document.
    pdf_links = [a["href"] for a in cell.find_all("a", href=True) if ".pdf" in a["href"].lower()]
    return pdf_links[-1] if pdf_links else None


def parse_month_page(html, category, month_url):
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
            ref_no = cells[2].get_text(strip=True) or None if len(cells) > 2 else None
            doc_url = _last_pdf_href(cells[-1]) if cells else None
            postings.append(
                {
                    "source": "guimaras",
                    "title": title,
                    "ref_no": ref_no,
                    "category": category,
                    "date_posted": date_posted,
                    "closing_date": None,
                    "url": month_url,
                    "doc_url": doc_url,
                }
            )

    if not postings:
        # Some subsections (e.g. Notice of Awards) are simpler and list a PDF
        # per row without the DESCRIPTION/ITB-number table -- fall back to
        # every direct PDF link on the page as a metadata-only posting.
        heading_text = None
        h1 = soup.find("h1")
        if h1:
            heading_text = h1.get_text(strip=True)
        date_posted = _parse_month_year_heading(heading_text)
        for a in soup.select("div.tem-2 a[href]") if soup.select_one("div.tem-2") else soup.select("a[href]"):
            href = a["href"]
            if ".pdf" not in href.lower():
                continue
            title = a.get_text(strip=True) or href.rsplit("/", 1)[-1]
            postings.append(
                {
                    "source": "guimaras",
                    "title": title,
                    "ref_no": None,
                    "category": category,
                    "date_posted": date_posted,
                    "closing_date": None,
                    "url": month_url,
                    "doc_url": href,
                }
            )

    return postings


def scrape():
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    all_postings = []

    for category, index_url in SUBSECTIONS.items():
        resp = session.get(index_url, timeout=30)
        resp.raise_for_status()
        month_links = parse_subsection_index(resp.text)[:MONTH_PAGE_CAP]

        for _, href in month_links:
            month_url = urljoin(BASE_URL, href)
            try:
                mresp = session.get(month_url, timeout=30)
                mresp.raise_for_status()
            except requests.RequestException:
                continue
            all_postings.extend(parse_month_page(mresp.text, category, month_url))

    return all_postings


if __name__ == "__main__":
    results = scrape()
    print(f"guimaras: {len(results)} postings")
    for p in results[:5]:
        print(p)
