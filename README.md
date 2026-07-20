# Iloilo Bid Monitor

Tracks public procurement/bid postings across:

- **Iloilo City** BAC — [iloilocity.gov.ph/bids-and-awards-committee](https://iloilocity.gov.ph/bids-and-awards-committee/)
- **Iloilo Province** BAC — [iloilo.gov.ph/en/bac-reports-view](https://iloilo.gov.ph/en/bac-reports-view)
- **Guimaras Province** Transparency (Invitation to Bid, Bid Supplement, Invitation to Quote, Negotiated/Small Value Procurement, Notice of Awards) — [guimaras.gov.ph](https://guimaras.gov.ph/transparency/)

and surfaces them as a filterable, categorized dashboard.

**Live dashboard:** https://AIinterruptor.github.io/iloilo-bid-monitor/

## How it works

```
GitHub Actions (cron, every 6h, + manual dispatch)
  -> scrape.py
       -> scrapers/iloilo_city.py, iloilo_province.py, guimaras.py
       -> categorize.py (keyword auto-tagging)
       -> dedupe against docs/data/postings.json, merge, sort newest-first
  -> commit docs/data/postings.json back to main (only if changed)
  -> GitHub Pages (serving from docs/) rebuilds automatically
```

The dashboard (`docs/index.html` + `docs/app.js`) is a static page with no
build step. It fetches `docs/data/postings.json` client-side and does all
filtering/sorting/search in the browser.

## Running locally

```bash
pip install -r requirements.txt
python scrape.py
```

This updates `docs/data/postings.json` in place. Open `docs/index.html`
directly in a browser (or serve `docs/` with any static file server) to view
the dashboard against your local data.

Run the test suite (uses saved HTML fixtures under `tests/fixtures/`, so it
doesn't depend on the live sites being reachable):

```bash
pytest tests/
```

## Notes on scope

- **PhilGEPS Region VI is deferred.** It has no public API and requires
  legacy ASP.NET session/viewstate-based scraping; too flaky/complex to gate
  v1 on.
- **Guimaras entries are metadata-only.** Postings there are scanned/image
  PDFs — no OCR is attempted. Title, reference number, category, and dates
  come from the page structure around each PDF link, not the PDF content.
- **Iloilo Province scraping is incremental**, not a full crawl. It walks the
  results newest-first and stops once it reaches a posting already present in
  `docs/data/postings.json` (or a 5-page safety cap on first bootstrap run),
  since the live site holds ~665 pages of historical entries.
