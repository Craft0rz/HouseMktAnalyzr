"""Property ranking and filtering for investment analysis.

This module provides tools for ranking, filtering, and comparing
multiple properties based on investment criteria.
"""

import logging
from statistics import mean, median
from typing import Optional

from ..models.property import InvestmentMetrics, PropertyListing, PropertyType
from .calculator import InvestmentCalculator

logger = logging.getLogger(__name__)


class PropertyRanker:
    """Rank and filter properties by investment criteria.

    Provides methods for batch analysis, ranking by various metrics,
    filtering by criteria, and generating summary reports.

    Example:
        ranker = PropertyRanker()

        # Analyze and rank listings
        top_10 = ranker.get_top_opportunities(listings, n=10)
        for listing, metrics in top_10:
            print(f"{listing.address}: {metrics.score}/100")

        # Filter by criteria
        good_deals = ranker.filter_by_criteria(
            listings,
            min_cap_rate=5.0,
            min_cash_flow=200,
        )
    """

    def __init__(self, calculator: Optional[InvestmentCalculator] = None):
        """Initialize ranker with investment calculator.

        Args:
            calculator: Optional InvestmentCalculator instance.
                       Creates new instance if not provided.
        """
        self.calc = calculator or InvestmentCalculator()

    # =========================================================================
    # Batch Analysis
    # =========================================================================

    def analyze_batch(
        self,
        listings: list[PropertyListing],
        down_payment_pct: float = 0.20,
        interest_rate: float = 0.05,
        expense_ratio: float = 0.35,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Analyze multiple properties and return with metrics.

        Args:
            listings: List of PropertyListing objects to analyze
            down_payment_pct: Down payment percentage (default 20%)
            interest_rate: Mortgage interest rate (default 5%)
            expense_ratio: Operating expense ratio (default 35%)

        Returns:
            List of (PropertyListing, InvestmentMetrics) tuples
        """
        results = []
        for listing in listings:
            try:
                metrics = self.calc.analyze_property(
                    listing,
                    down_payment_pct=down_payment_pct,
                    interest_rate=interest_rate,
                    expense_ratio=expense_ratio,
                )
                results.append((listing, metrics))
            except Exception as e:
                logger.warning(f"Failed to analyze {listing.id}: {e}")
        return results

    # =========================================================================
    # Ranking Methods
    # =========================================================================

    def rank_by_score(
        self,
        listings: list[PropertyListing],
        **kwargs,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Rank properties by investment score (highest first).

        Args:
            listings: Properties to rank
            **kwargs: Passed to analyze_property

        Returns:
            Sorted list of (PropertyListing, InvestmentMetrics) tuples
        """
        analyzed = self.analyze_batch(listings, **kwargs)
        return sorted(analyzed, key=lambda x: x[1].score, reverse=True)

    def rank_by_cap_rate(
        self,
        listings: list[PropertyListing],
        **kwargs,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Rank properties by cap rate (highest first).

        Args:
            listings: Properties to rank
            **kwargs: Passed to analyze_property

        Returns:
            Sorted list of (PropertyListing, InvestmentMetrics) tuples
        """
        analyzed = self.analyze_batch(listings, **kwargs)
        return sorted(
            analyzed,
            key=lambda x: x[1].cap_rate or 0,
            reverse=True,
        )

    def rank_by_cash_flow(
        self,
        listings: list[PropertyListing],
        **kwargs,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Rank properties by monthly cash flow (highest first).

        Args:
            listings: Properties to rank
            **kwargs: Passed to analyze_property

        Returns:
            Sorted list of (PropertyListing, InvestmentMetrics) tuples
        """
        analyzed = self.analyze_batch(listings, **kwargs)
        return sorted(
            analyzed,
            key=lambda x: x[1].cash_flow_monthly or 0,
            reverse=True,
        )

    def rank_by_yield(
        self,
        listings: list[PropertyListing],
        **kwargs,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Rank properties by gross rental yield (highest first).

        Args:
            listings: Properties to rank
            **kwargs: Passed to analyze_property

        Returns:
            Sorted list of (PropertyListing, InvestmentMetrics) tuples
        """
        analyzed = self.analyze_batch(listings, **kwargs)
        return sorted(
            analyzed,
            key=lambda x: x[1].gross_rental_yield,
            reverse=True,
        )

    def rank_by_price_per_unit(
        self,
        listings: list[PropertyListing],
        **kwargs,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Rank properties by price per unit (lowest first).

        Args:
            listings: Properties to rank
            **kwargs: Passed to analyze_property

        Returns:
            Sorted list of (PropertyListing, InvestmentMetrics) tuples
        """
        analyzed = self.analyze_batch(listings, **kwargs)
        return sorted(analyzed, key=lambda x: x[1].price_per_unit)

    # =========================================================================
    # Filtering Methods
    # =========================================================================

    def filter_positive_cash_flow(
        self,
        listings: list[PropertyListing],
        **kwargs,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Filter to only positive cash flow properties.

        Args:
            listings: Properties to filter
            **kwargs: Passed to analyze_property

        Returns:
            List of properties with positive monthly cash flow
        """
        analyzed = self.analyze_batch(listings, **kwargs)
        return [
            (listing, metrics)
            for listing, metrics in analyzed
            if metrics.cash_flow_monthly and metrics.cash_flow_monthly > 0
        ]

    def filter_by_criteria(
        self,
        listings: list[PropertyListing],
        min_cap_rate: Optional[float] = None,
        min_cash_flow: Optional[int] = None,
        max_price_per_unit: Optional[int] = None,
        min_score: Optional[float] = None,
        min_yield: Optional[float] = None,
        property_types: Optional[list[PropertyType]] = None,
        **kwargs,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Filter properties by multiple investment criteria.

        Args:
            listings: Properties to filter
            min_cap_rate: Minimum cap rate percentage (e.g., 5.0)
            min_cash_flow: Minimum monthly cash flow in CAD
            max_price_per_unit: Maximum price per unit in CAD
            min_score: Minimum investment score (0-100)
            min_yield: Minimum gross rental yield percentage
            property_types: List of allowed property types
            **kwargs: Passed to analyze_property

        Returns:
            Filtered list of (PropertyListing, InvestmentMetrics) tuples
        """
        # Filter by property type first (before analysis)
        if property_types:
            listings = [l for l in listings if l.property_type in property_types]

        analyzed = self.analyze_batch(listings, **kwargs)
        results = []

        for listing, metrics in analyzed:
            # Apply filters
            if min_cap_rate and (metrics.cap_rate or 0) < min_cap_rate:
                continue
            if min_cash_flow and (metrics.cash_flow_monthly or 0) < min_cash_flow:
                continue
            if max_price_per_unit and metrics.price_per_unit > max_price_per_unit:
                continue
            if min_score and metrics.score < min_score:
                continue
            if min_yield and metrics.gross_rental_yield < min_yield:
                continue

            results.append((listing, metrics))

        return results

    def get_top_opportunities(
        self,
        listings: list[PropertyListing],
        n: int = 10,
        sort_by: str = "score",
        **kwargs,
    ) -> list[tuple[PropertyListing, InvestmentMetrics]]:
        """Get top N investment opportunities.

        Args:
            listings: Properties to analyze
            n: Number of top properties to return
            sort_by: Metric to sort by ("score", "cap_rate", "cash_flow", "yield")
            **kwargs: Passed to analyze_property

        Returns:
            Top N properties sorted by specified metric
        """
        if sort_by == "cap_rate":
            ranked = self.rank_by_cap_rate(listings, **kwargs)
        elif sort_by == "cash_flow":
            ranked = self.rank_by_cash_flow(listings, **kwargs)
        elif sort_by == "yield":
            ranked = self.rank_by_yield(listings, **kwargs)
        else:
            ranked = self.rank_by_score(listings, **kwargs)

        return ranked[:n]

    # =========================================================================
    # Report Generation
    # =========================================================================

    def generate_report(
        self,
        listings: list[PropertyListing],
        top_n: int = 10,
        **kwargs,
    ) -> str:
        """Generate text summary report of investment opportunities.

        Args:
            listings: Properties to analyze
            top_n: Number of top properties to highlight
            **kwargs: Passed to analyze_property

        Returns:
            Formatted text report
        """
        if not listings:
            return "No properties to analyze."

        analyzed = self.analyze_batch(listings, **kwargs)

        if not analyzed:
            return "Could not analyze any properties."

        # Calculate summary statistics
        scores = [m.score for _, m in analyzed]
        cap_rates = [m.cap_rate for _, m in analyzed if m.cap_rate]
        cash_flows = [m.cash_flow_monthly for _, m in analyzed if m.cash_flow_monthly]
        yields = [m.gross_rental_yield for _, m in analyzed]
        prices = [l.price for l, _ in analyzed]

        # Count by type
        type_counts = {}
        for listing, _ in analyzed:
            t = listing.property_type.value
            type_counts[t] = type_counts.get(t, 0) + 1

        # Get top properties
        top = sorted(analyzed, key=lambda x: x[1].score, reverse=True)[:top_n]

        # Build report
        lines = [
            "=" * 60,
            "INVESTMENT ANALYSIS REPORT",
            "=" * 60,
            "",
            f"Properties Analyzed: {len(analyzed)}",
            "",
            "Property Type Breakdown:",
        ]

        for ptype, count in sorted(type_counts.items()):
            lines.append(f"  {ptype}: {count}")

        lines.extend([
            "",
            "Summary Statistics:",
            f"  Price Range: ${min(prices):,} - ${max(prices):,}",
            f"  Average Score: {mean(scores):.1f}/100",
            f"  Median Score: {median(scores):.1f}/100",
        ])

        if cap_rates:
            lines.append(f"  Average Cap Rate: {mean(cap_rates):.2f}%")
        if cash_flows:
            positive_cf = len([cf for cf in cash_flows if cf > 0])
            lines.append(f"  Positive Cash Flow: {positive_cf}/{len(cash_flows)} ({positive_cf/len(cash_flows)*100:.0f}%)")
        if yields:
            lines.append(f"  Average Gross Yield: {mean(yields):.2f}%")

        lines.extend([
            "",
            "-" * 60,
            f"TOP {min(top_n, len(top))} OPPORTUNITIES",
            "-" * 60,
            "",
        ])

        for i, (listing, metrics) in enumerate(top, 1):
            cf_str = f"${metrics.cash_flow_monthly:,.0f}" if metrics.cash_flow_monthly else "N/A"
            cap_str = f"{metrics.cap_rate:.1f}%" if metrics.cap_rate else "N/A"

            lines.extend([
                f"{i}. {listing.address[:40]}",
                f"   {listing.property_type.value} | {listing.city} | ${listing.price:,}",
                f"   Score: {metrics.score:.0f}/100 | Cap: {cap_str} | Cash Flow: {cf_str}/mo",
                f"   Price/Unit: ${metrics.price_per_unit:,} | Yield: {metrics.gross_rental_yield:.1f}%",
                "",
            ])

        lines.append("=" * 60)

        return "\n".join(lines)

    def generate_csv(
        self,
        listings: list[PropertyListing],
        **kwargs,
    ) -> str:
        """Generate CSV export of analyzed properties.

        Args:
            listings: Properties to analyze
            **kwargs: Passed to analyze_property

        Returns:
            CSV formatted string
        """
        analyzed = self.analyze_batch(listings, **kwargs)

        headers = [
            "ID", "Address", "City", "Type", "Units", "Price",
            "Score", "Cap Rate", "Yield", "Cash Flow", "Price/Unit"
        ]

        lines = [",".join(headers)]

        for listing, metrics in sorted(analyzed, key=lambda x: x[1].score, reverse=True):
            row = [
                listing.id,
                f'"{listing.address}"',
                listing.city,
                listing.property_type.value,
                str(listing.units),
                str(listing.price),
                f"{metrics.score:.1f}",
                f"{metrics.cap_rate:.2f}" if metrics.cap_rate else "",
                f"{metrics.gross_rental_yield:.2f}",
                f"{metrics.cash_flow_monthly:.0f}" if metrics.cash_flow_monthly else "",
                str(metrics.price_per_unit),
            ]
            lines.append(",".join(row))

        return "\n".join(lines)
