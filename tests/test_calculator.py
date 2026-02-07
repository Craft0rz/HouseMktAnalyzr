"""Tests for InvestmentCalculator."""

import pytest

from housemktanalyzr.analysis import InvestmentCalculator
from housemktanalyzr.models.property import PropertyListing, PropertyType


class TestGrossRentalYield:
    """Test gross rental yield calculations."""

    def test_basic_yield(self, calculator: InvestmentCalculator):
        """Test basic yield calculation."""
        # $50k annual rent on $500k property = 10%
        yield_pct = calculator.gross_rental_yield(price=500000, annual_rent=50000)
        assert yield_pct == 10.0

    def test_zero_price_returns_zero(self, calculator: InvestmentCalculator):
        """Zero price should return zero yield."""
        yield_pct = calculator.gross_rental_yield(price=0, annual_rent=50000)
        assert yield_pct == 0.0

    def test_typical_montreal_yield(self, calculator: InvestmentCalculator):
        """Test typical Montreal multi-family yield."""
        # $600k property, $42k annual rent = 7%
        yield_pct = calculator.gross_rental_yield(price=600000, annual_rent=42000)
        assert yield_pct == pytest.approx(7.0)


class TestCapRate:
    """Test cap rate calculations."""

    def test_basic_cap_rate(self, calculator: InvestmentCalculator):
        """Test basic cap rate calculation."""
        # $25k NOI on $500k property = 5%
        cap = calculator.cap_rate(price=500000, noi=25000)
        assert cap == 5.0

    def test_zero_price_returns_zero(self, calculator: InvestmentCalculator):
        """Zero price should return zero."""
        cap = calculator.cap_rate(price=0, noi=25000)
        assert cap == 0.0

    def test_high_cap_rate(self, calculator: InvestmentCalculator):
        """Test higher cap rate property."""
        # $35k NOI on $500k = 7%
        cap = calculator.cap_rate(price=500000, noi=35000)
        assert cap == pytest.approx(7.0)


class TestGrossRentMultiplier:
    """Test GRM calculations."""

    def test_basic_grm(self, calculator: InvestmentCalculator):
        """Test basic GRM calculation."""
        # $500k / $50k annual = 10
        grm = calculator.gross_rent_multiplier(price=500000, annual_rent=50000)
        assert grm == 10.0

    def test_zero_rent_returns_infinity(self, calculator: InvestmentCalculator):
        """Zero rent should return infinity."""
        grm = calculator.gross_rent_multiplier(price=500000, annual_rent=0)
        assert grm == float("inf")

    def test_typical_grm(self, calculator: InvestmentCalculator):
        """Test typical Montreal GRM."""
        # $600k / $48k = 12.5
        grm = calculator.gross_rent_multiplier(price=600000, annual_rent=48000)
        assert grm == 12.5


class TestMortgagePayment:
    """Test Canadian mortgage calculations."""

    def test_standard_mortgage_30yr(self, calculator: InvestmentCalculator):
        """Test standard 30-year mortgage at 5% (default)."""
        # $400k loan at 5% for 30 years
        payment = calculator.calculate_mortgage_payment(
            principal=400000,
            annual_rate=0.05,
        )
        # Expected ~$2,138/mo with Canadian semi-annual compounding
        assert 2100 <= payment <= 2175

    def test_25_year_mortgage(self, calculator: InvestmentCalculator):
        """Test 25-year mortgage at 5%."""
        # $400k loan at 5% for 25 years
        payment = calculator.calculate_mortgage_payment(
            principal=400000,
            annual_rate=0.05,
            amortization_years=25,
        )
        # Expected ~$2,327/mo with Canadian semi-annual compounding
        assert 2300 <= payment <= 2350

    def test_zero_principal(self, calculator: InvestmentCalculator):
        """Zero principal should return zero."""
        payment = calculator.calculate_mortgage_payment(
            principal=0,
            annual_rate=0.05,
        )
        assert payment == 0

    def test_higher_rate(self, calculator: InvestmentCalculator):
        """Test higher interest rate."""
        payment = calculator.calculate_mortgage_payment(
            principal=400000,
            annual_rate=0.07,
            amortization_years=25,
        )
        # Higher rate = higher payment
        assert payment > 2700


class TestDownPayment:
    """Test down payment calculations."""

    def test_standard_20_percent(self, calculator: InvestmentCalculator):
        """Test standard 20% down payment."""
        down = calculator.calculate_down_payment(price=500000, down_payment_pct=0.20)
        assert down == 100000

    def test_25_percent(self, calculator: InvestmentCalculator):
        """Test 25% down payment."""
        down = calculator.calculate_down_payment(price=500000, down_payment_pct=0.25)
        assert down == 125000


class TestTotalCashNeeded:
    """Test total cash calculation."""

    def test_standard_closing(self, calculator: InvestmentCalculator):
        """Test with standard closing costs."""
        # $500k, 20% down, 3% closing
        total = calculator.calculate_total_cash_needed(
            price=500000,
            down_payment_pct=0.20,
            closing_costs_pct=0.03,
        )
        # $100k down + $15k closing = $115k
        assert total == 115000


class TestEstimateNOI:
    """Test NOI estimation."""

    def test_standard_expense_ratio(self, calculator: InvestmentCalculator):
        """Test with 35% expense ratio."""
        # $48k annual rent, 35% expenses
        noi = calculator.estimate_noi(annual_rent=48000, expense_ratio=0.35)
        assert noi == 31200  # 48000 * 0.65

    def test_custom_expense_ratio(self, calculator: InvestmentCalculator):
        """Test with custom expense ratio."""
        noi = calculator.estimate_noi(annual_rent=48000, expense_ratio=0.40)
        assert noi == 28800  # 48000 * 0.60


class TestAnalyzeProperty:
    """Test full property analysis."""

    def test_analyze_duplex(
        self,
        calculator: InvestmentCalculator,
        sample_duplex: PropertyListing,
    ):
        """Test analysis of sample duplex."""
        metrics = calculator.analyze_property(sample_duplex)

        assert metrics.property_id == "test-duplex-1"
        assert metrics.purchase_price == 500000
        assert metrics.estimated_monthly_rent == 3000
        assert metrics.price_per_unit == 250000
        assert 0 < metrics.score <= 100

    def test_analyze_triplex(
        self,
        calculator: InvestmentCalculator,
        sample_triplex: PropertyListing,
    ):
        """Test analysis of sample triplex."""
        metrics = calculator.analyze_property(sample_triplex)

        assert metrics.property_id == "test-triplex-1"
        assert metrics.purchase_price == 650000
        assert metrics.price_per_unit == 216666  # 650k / 3

    def test_score_breakdown_present(
        self,
        calculator: InvestmentCalculator,
        sample_duplex: PropertyListing,
    ):
        """Test that score breakdown is included."""
        metrics = calculator.analyze_property(sample_duplex)

        assert metrics.score_breakdown is not None
        assert "cap_rate" in metrics.score_breakdown
        assert "cash_flow" in metrics.score_breakdown
        assert "price_per_unit" in metrics.score_breakdown

    def test_high_yield_scores_better(
        self,
        calculator: InvestmentCalculator,
        high_yield_listing: PropertyListing,
        low_yield_listing: PropertyListing,
    ):
        """High yield property should score better than low yield."""
        high_metrics = calculator.analyze_property(high_yield_listing)
        low_metrics = calculator.analyze_property(low_yield_listing)

        assert high_metrics.score > low_metrics.score
        assert high_metrics.cap_rate > low_metrics.cap_rate
