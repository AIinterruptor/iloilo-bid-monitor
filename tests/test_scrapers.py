"""
test_scrapers.py — v1.0.0

Parses saved HTML fixtures so scraper correctness is independent of live
site availability.
"""
from pathlib import Path

import pytest

from scrapers import guimaras, iloilo_city, iloilo_province
from categorize import categorize

FIXTURES = Path(__file__).parent / "fixtures"


def read_fixture(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


REQUIRED_FIELDS = {"source", "title", "ref_no", "category", "date_posted", "closing_date", "url", "doc_url"}


class TestIloiloCity:
    def test_parses_postings(self):
        postings = iloilo_city.parse(read_fixture("iloilo_city.html"))
        assert len(postings) > 0

    def test_schema_fields(self):
        postings = iloilo_city.parse(read_fixture("iloilo_city.html"))
        assert REQUIRED_FIELDS.issubset(postings[0].keys())

    def test_known_entry(self):
        postings = iloilo_city.parse(read_fixture("iloilo_city.html"))
        match = next(p for p in postings if p["ref_no"] == "CMA-100-25-09-146A")
        assert match["title"] == "Supply and Delivery of Furniture and Fixtures"
        assert match["date_posted"] == "2025-10-01"
        assert match["closing_date"] == "2025-10-08"
        assert match["category"] == "Request for Quotation"
        assert match["doc_url"].startswith("https://drive.google.com/")
        assert match["source"] == "iloilo_city"


class TestIloiloProvince:
    def test_parses_postings(self):
        postings = iloilo_province.parse(read_fixture("iloilo_province_index.html"))
        assert len(postings) == 20

    def test_schema_fields(self):
        postings = iloilo_province.parse(read_fixture("iloilo_province_index.html"))
        assert REQUIRED_FIELDS.issubset(postings[0].keys())

    def test_known_entry(self):
        postings = iloilo_province.parse(read_fixture("iloilo_province_index.html"))
        match = next(p for p in postings if p["ref_no"] == "PEO-26-924-B")
        assert "Purchase of Outer Tires" in match["title"]
        assert match["date_posted"] == "2026-07-18"
        assert "Invitation To Bid" in match["category"]
        assert match["url"].startswith("https://iloilo.gov.ph/")
        assert match["source"] == "iloilo_province"

    def test_rebid_ref_no_distinct_from_base(self):
        postings = iloilo_province.parse(read_fixture("iloilo_province_index.html"))
        rebid = next(p for p in postings if "RE-BID" in (p["ref_no"] or ""))
        assert rebid["ref_no"] != "PEN-25-924-B"
        assert rebid["url"] != ""

    def test_dates_already_iso(self):
        postings = iloilo_province.parse(read_fixture("iloilo_province_index.html"))
        for p in postings:
            if p["date_posted"]:
                assert len(p["date_posted"]) == 10
                assert p["date_posted"][4] == "-"


class TestGuimaras:
    def test_parses_subsection_index(self):
        links = guimaras.parse_subsection_index(read_fixture("guimaras_subsection_index.html"))
        assert len(links) > 0
        # newest-first: current year's accordion panel is listed first on the page
        assert "2026" in links[0][0]

    def test_parses_month_page(self):
        postings = guimaras.parse_month_page(
            read_fixture("guimaras_month_page.html"),
            "Invitation to Bid",
            "https://guimaras.gov.ph/invitation-to-bid/july-2026/",
        )
        assert len(postings) == 6

    def test_schema_fields(self):
        postings = guimaras.parse_month_page(
            read_fixture("guimaras_month_page.html"),
            "Invitation to Bid",
            "https://guimaras.gov.ph/invitation-to-bid/july-2026/",
        )
        assert REQUIRED_FIELDS.issubset(postings[0].keys())

    def test_known_entry_and_last_pdf_anchor_wins(self):
        postings = guimaras.parse_month_page(
            read_fixture("guimaras_month_page.html"),
            "Invitation to Bid",
            "https://guimaras.gov.ph/invitation-to-bid/july-2026/",
        )
        match = next(p for p in postings if p["ref_no"] == "2026-06-202")
        assert "CATERING SERVICES" in match["title"]
        assert match["date_posted"] == "2026-07-15"
        # cell has two <a> hrefs (stale SAGIP-SAKA.pdf, then the real doc) --
        # must resolve to the second, not the first
        assert match["doc_url"].endswith("2026-06-202.pdf")
        assert match["source"] == "guimaras"


class TestCategorize:
    def test_construction_keyword(self):
        assert categorize("Road Rehabilitation Project Phase 2") == "Construction/Infrastructure"

    def test_it_keyword(self):
        assert categorize("Supply and Delivery of ICT Equipment") == "IT/Technology"

    def test_goods_keyword(self):
        assert categorize("Supply and Delivery of Office Equipment") == "Goods & Supplies"

    def test_consulting_keyword(self):
        assert categorize("Hiring of Training Provider") == "Consulting/Professional Services"

    def test_fallback_other(self):
        assert categorize("Some Unrelated Posting Title") == "Other"
