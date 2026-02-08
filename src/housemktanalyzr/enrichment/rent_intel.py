"""Rent trend analysis and forecasting.

Uses historical CMHC data to compute rent growth trends
and simple linear forecasts for investment analysis.
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RentForecast:
    """Projected rent with confidence interval."""
    year: int
    projected_rent: float
    lower_bound: float
    upper_bound: float


@dataclass
class RentTrend:
    """Rent trend analysis for a zone/bedroom type."""
    zone: str
    bedroom_type: str
    current_rent: float | None
    years: list[int]
    rents: list[float]
    annual_growth_rate: float | None  # percentage
    cagr_5yr: float | None  # 5-year CAGR percentage
    growth_direction: str  # "accelerating", "decelerating", "stable"
    forecasts: list[RentForecast]
    vacancy_rate: float | None = None
    vacancy_direction: str = "stable"


def compute_trend(
    years: list[int],
    values: list[float],
    forecast_years: int = 3,
) -> tuple[float | None, float | None, str, list[RentForecast]]:
    """Compute linear trend and forecast from historical data.

    Args:
        years: List of years (e.g. [2019, 2020, 2021, 2022, 2023])
        values: Corresponding rent values
        forecast_years: How many years to forecast forward

    Returns:
        (annual_growth_rate_pct, cagr_5yr_pct, growth_direction, forecasts)
    """
    if len(years) < 2 or len(values) < 2:
        return None, None, "stable", []

    # Pair and sort
    paired = sorted(zip(years, values))
    xs = [p[0] for p in paired]
    ys = [p[1] for p in paired]
    n = len(xs)

    # Simple linear regression: y = a + b*x
    x_mean = sum(xs) / n
    y_mean = sum(ys) / n
    ss_xy = sum((xs[i] - x_mean) * (ys[i] - y_mean) for i in range(n))
    ss_xx = sum((xs[i] - x_mean) ** 2 for i in range(n))

    if ss_xx == 0:
        return None, None, "stable", []

    slope = ss_xy / ss_xx
    intercept = y_mean - slope * x_mean

    # Annual growth rate as percentage of current value
    current = ys[-1]
    if current > 0:
        growth_rate = (slope / current) * 100
    else:
        growth_rate = 0.0

    # CAGR 5yr: compound annual growth rate over the last 5 years (or all available)
    cagr_5yr = None
    cagr_n = min(5, n - 1)
    if cagr_n >= 1:
        start_val = ys[-(cagr_n + 1)]
        end_val = ys[-1]
        if start_val > 0 and end_val > 0:
            cagr_5yr = round(((end_val / start_val) ** (1 / cagr_n) - 1) * 100, 1)

    # Determine if growth is accelerating or decelerating
    # Compare first-half growth to second-half growth
    if n >= 4:
        mid = n // 2
        first_half_growth = (ys[mid] - ys[0]) / max(mid, 1)
        second_half_growth = (ys[-1] - ys[mid]) / max(n - mid, 1)
        if second_half_growth > first_half_growth * 1.1:
            direction = "accelerating"
        elif second_half_growth < first_half_growth * 0.9:
            direction = "decelerating"
        else:
            direction = "stable"
    else:
        direction = "stable"

    # Residuals for confidence interval
    residuals = [ys[i] - (intercept + slope * xs[i]) for i in range(n)]
    if n > 2:
        std_err = (sum(r ** 2 for r in residuals) / (n - 2)) ** 0.5
    else:
        std_err = 0

    # Forecast: anchor from the last actual observation, project forward using slope
    forecasts = []
    for i in range(1, forecast_years + 1):
        future_year = xs[-1] + i
        projected = current + slope * i
        projected = max(projected, 0)  # rents can't be negative
        forecasts.append(RentForecast(
            year=future_year,
            projected_rent=round(projected, 0),
            lower_bound=round(max(projected - 1.96 * std_err, 0), 0),
            upper_bound=round(projected + 1.96 * std_err, 0),
        ))

    return round(growth_rate, 1), cagr_5yr, direction, forecasts


def analyze_zone_rent(
    zone: str,
    bedroom_type: str,
    historical_rents: list[dict],
    current_vacancy: float | None = None,
    previous_vacancy: float | None = None,
) -> RentTrend:
    """Analyze rent trend for a specific zone and bedroom type.

    Args:
        zone: CMHC zone name
        bedroom_type: "bachelor", "1br", "2br", "3br+"
        historical_rents: List of {"year": int, "rent": float} dicts
        current_vacancy: Current vacancy rate (optional)
        previous_vacancy: Previous year vacancy rate (optional)

    Returns:
        RentTrend with analysis and forecast
    """
    years = [r["year"] for r in historical_rents if r.get("rent") is not None]
    rents = [r["rent"] for r in historical_rents if r.get("rent") is not None]

    growth_rate, cagr_5yr, direction, forecasts = compute_trend(years, rents)

    vacancy_direction = "stable"
    if current_vacancy is not None and previous_vacancy is not None:
        diff = current_vacancy - previous_vacancy
        if abs(diff) > 0.1:
            vacancy_direction = "up" if diff > 0 else "down"

    return RentTrend(
        zone=zone,
        bedroom_type=bedroom_type,
        current_rent=rents[-1] if rents else None,
        years=years,
        rents=rents,
        annual_growth_rate=growth_rate,
        cagr_5yr=cagr_5yr,
        growth_direction=direction,
        forecasts=forecasts,
        vacancy_rate=current_vacancy,
        vacancy_direction=vacancy_direction,
    )
