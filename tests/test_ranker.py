"""Tests for PropertyRanker."""

import pytest

from housemktanalyzr.analysis import PropertyRanker
from housemktanalyzr.models.property import PropertyListing, PropertyType


class TestAnalyzeBatch:
    """Test batch analysis."""

    def test_analyze_multiple(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test analyzing multiple properties."""
        results = ranker.analyze_batch(sample_listings)

        assert len(results) == 3
        for listing, metrics in results:
            assert metrics.property_id == listing.id
            assert metrics.score > 0


class TestRankByScore:
    """Test ranking by investment score."""

    def test_rank_order(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test that ranking is in descending order."""
        ranked = ranker.rank_by_score(sample_listings)

        scores = [m.score for _, m in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_best_first(
        self,
        ranker: PropertyRanker,
        high_yield_listing: PropertyListing,
        low_yield_listing: PropertyListing,
    ):
        """High yield property should rank first."""
        ranked = ranker.rank_by_score([low_yield_listing, high_yield_listing])

        first_listing, _ = ranked[0]
        assert first_listing.id == "high-yield-1"


class TestRankByCapRate:
    """Test ranking by cap rate."""

    def test_rank_order(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test that ranking is in descending cap rate order."""
        ranked = ranker.rank_by_cap_rate(sample_listings)

        cap_rates = [m.cap_rate or 0 for _, m in ranked]
        assert cap_rates == sorted(cap_rates, reverse=True)


class TestRankByCashFlow:
    """Test ranking by cash flow."""

    def test_rank_order(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test that ranking is in descending cash flow order."""
        ranked = ranker.rank_by_cash_flow(sample_listings)

        cash_flows = [m.cash_flow_monthly or 0 for _, m in ranked]
        assert cash_flows == sorted(cash_flows, reverse=True)


class TestFilterByCriteria:
    """Test filtering by investment criteria."""

    def test_filter_by_min_score(
        self,
        ranker: PropertyRanker,
        high_yield_listing: PropertyListing,
        low_yield_listing: PropertyListing,
    ):
        """Test filtering by minimum score."""
        listings = [high_yield_listing, low_yield_listing]

        # Get scores first
        all_results = ranker.analyze_batch(listings)
        high_score = next(m.score for l, m in all_results if l.id == "high-yield-1")

        # Filter with threshold between scores
        filtered = ranker.filter_by_criteria(
            listings,
            min_score=high_score - 5,  # Should include high yield
        )

        # High yield should pass, low yield depends on score
        assert len(filtered) >= 1
        ids = [l.id for l, _ in filtered]
        assert "high-yield-1" in ids

    def test_filter_by_property_type(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test filtering by property type."""
        filtered = ranker.filter_by_criteria(
            sample_listings,
            property_types=[PropertyType.TRIPLEX],
        )

        assert len(filtered) == 1
        assert filtered[0][0].property_type == PropertyType.TRIPLEX

    def test_filter_by_max_price_per_unit(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test filtering by max price per unit."""
        # Duplex: $250k/unit, Triplex: ~$217k/unit, Quadplex: $200k/unit
        filtered = ranker.filter_by_criteria(
            sample_listings,
            max_price_per_unit=220000,
        )

        # Should exclude duplex
        ids = [l.id for l, _ in filtered]
        assert "test-duplex-1" not in ids

    def test_combined_filters(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test multiple filters combined."""
        filtered = ranker.filter_by_criteria(
            sample_listings,
            property_types=[PropertyType.TRIPLEX, PropertyType.QUADPLEX],
            max_price_per_unit=220000,
        )

        # Should only match triplex and quadplex with low price/unit
        for listing, _ in filtered:
            assert listing.property_type in [PropertyType.TRIPLEX, PropertyType.QUADPLEX]


class TestGetTopOpportunities:
    """Test getting top N opportunities."""

    def test_returns_n_results(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test that it returns exactly N results."""
        top = ranker.get_top_opportunities(sample_listings, n=2)
        assert len(top) == 2

    def test_returns_all_if_less_than_n(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test with N larger than list size."""
        top = ranker.get_top_opportunities(sample_listings, n=10)
        assert len(top) == 3  # Only 3 in sample

    def test_sort_by_cap_rate(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test sorting by cap rate."""
        top = ranker.get_top_opportunities(sample_listings, n=3, sort_by="cap_rate")

        cap_rates = [m.cap_rate or 0 for _, m in top]
        assert cap_rates == sorted(cap_rates, reverse=True)


class TestFilterPositiveCashFlow:
    """Test positive cash flow filter."""

    def test_filters_negative(
        self,
        ranker: PropertyRanker,
        high_yield_listing: PropertyListing,
        low_yield_listing: PropertyListing,
    ):
        """Low yield property likely has negative cash flow."""
        listings = [high_yield_listing, low_yield_listing]
        positive = ranker.filter_positive_cash_flow(listings)

        # All results should have positive cash flow
        for _, metrics in positive:
            assert metrics.cash_flow_monthly is not None
            assert metrics.cash_flow_monthly > 0


class TestGenerateReport:
    """Test report generation."""

    def test_report_contains_header(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test report has proper header."""
        report = ranker.generate_report(sample_listings, top_n=5)

        assert "INVESTMENT ANALYSIS REPORT" in report
        assert "Properties Analyzed" in report

    def test_report_contains_listings(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test report includes property data."""
        report = ranker.generate_report(sample_listings, top_n=3)

        # Should contain addresses
        assert "Test Street" in report or "Main Avenue" in report

    def test_empty_listings(self, ranker: PropertyRanker):
        """Test with empty list."""
        report = ranker.generate_report([])
        assert "No properties" in report


class TestGenerateCSV:
    """Test CSV generation."""

    def test_csv_header(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test CSV has proper header."""
        csv = ranker.generate_csv(sample_listings)
        lines = csv.split("\n")

        header = lines[0]
        assert "ID" in header
        assert "Address" in header
        assert "Score" in header

    def test_csv_data_rows(
        self,
        ranker: PropertyRanker,
        sample_listings: list[PropertyListing],
    ):
        """Test CSV has data rows."""
        csv = ranker.generate_csv(sample_listings)
        lines = csv.split("\n")

        # Header + 3 data rows
        assert len(lines) == 4
