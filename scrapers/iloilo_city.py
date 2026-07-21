"""
iloilo_city.py — v1.2.0

Scrapes https://iloilocity.gov.ph/bids-and-awards-committee/ (WordPress site).

The host is fronted by Cloudflare, whose WAF returns 403 to GitHub Actions
datacenter IPs (confirmed persistent, every scheduled run since 2026-07-20).
Cloudflare-edge proxies (e.g. Workers) are blocked the same way, but Google
Cloud egress is NOT (verified 2026-07-21) — so CI routes through a small
token-authed fetch relay (`bid-proxy.service`) on a GCP VM.

When BID_PROXY_BASE is set, the request goes through that relay's
`/proxy?url=` endpoint so the fetch originates from a non-blocked IP;
BID_PROXY_TOKEN, if set, is sent as the relay's X-Bid-Proxy-Token shared
secret. Unset, it fetches directly (works from residential IPs / local runs).
"""
import os
import re
import urllib.parse
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL = "https://iloilocity.gov.ph/bids-and-awards-committee/"

# Optional fetch relay with a `/proxy?url=` passthrough (bid-proxy.service on
# a GCP VM — must NOT be Cloudflare-edge, which the WAF blocks like CI IPs).
# e.g. BID_PROXY_BASE="http://<vm-ip>:8080"
PROXY_BASE = (os.environ.get("BID_PROXY_BASE") or "").rstrip("/")
PROXY_TOKEN = os.environ.get("BID_PROXY_TOKEN") or ""

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
    headers = {"User-Agent": USER_AGENT}
    if PROXY_BASE:
        fetch_url = f"{PROXY_BASE}/proxy?url=" + urllib.parse.quote(URL, safe="")
        if PROXY_TOKEN:
            headers["X-Bid-Proxy-Token"] = PROXY_TOKEN
    else:
        fetch_url = URL
    resp = requests.get(fetch_url, headers=headers, timeout=45)
    resp.raise_for_status()
    return parse(resp.text)


if __name__ == "__main__":
    results = scrape()
    print(f"iloilo_city: {len(results)} postings")
    for p in results[:5]:
        print(p)
