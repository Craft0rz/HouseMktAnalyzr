# HouseMktAnalyzr

Residential real estate investment analyzer for Greater Montreal. Find and rank the best multi-family investment opportunities based on cap rate, cash flow, and ROI metrics.

## Features

- **Property Search**: Fetch listings from Centris with multi-type search (duplex, triplex, quadplex)
- **Investment Analysis**: Calculate cap rate, gross yield, cash flow, GRM, and investment score
- **Property Ranking**: Filter and rank properties by investment criteria
- **Interactive Dashboard**: Streamlit-based UI for browsing and comparing properties
- **Side-by-Side Comparison**: Compare 2-4 properties with highlighted metrics
- **Alert System**: Save search criteria and get notified of new matching properties
- **CMHC Data**: Rental estimates based on Montreal area market data

## Installation

### From Source

```bash
git clone https://github.com/yourusername/HouseMktAnalyzr.git
cd HouseMktAnalyzr
pip install -e .
```

### Dependencies

Requires Python 3.10+. Core dependencies:
- streamlit (dashboard)
- pandas (data handling)
- httpx (HTTP client)
- beautifulsoup4 (HTML parsing)
- pydantic (data validation)
- rich (CLI formatting)

## Quick Start

### Launch the Dashboard

```bash
python -m streamlit run src/housemktanalyzr/dashboard/app.py
```

Or after installing:

```bash
housemktanalyzr
```

### Using the Dashboard

1. **Select Region**: Choose from Montreal South Shore, Montreal Island, Laval, etc.
2. **Choose Property Types**: Duplex, Triplex, Quadplex, Multiplex
3. **Set Price Range**: Filter by minimum and maximum price
4. **Set Investment Criteria**: Minimum score, minimum cap rate
5. **Click Search**: Fetch and analyze properties

### Property Comparison

1. Go to the **Compare** tab
2. Select 2-4 properties from the dropdown
3. View side-by-side metrics with highlighted best values

### Saving Alerts

1. Configure your search filters
2. Expand "Save Current Search" in the sidebar
3. Enter a name and click "Save as Alert"
4. Run the alert checker to find new matches

## Alert System

### Run Alert Check

```bash
# Check for new matches
python -m housemktanalyzr.alerts.runner

# Show all matches (not just new)
python -m housemktanalyzr.alerts.runner --all

# List saved criteria
python -m housemktanalyzr.alerts.runner --list
```

### Schedule with Cron

```bash
# Check every hour
0 * * * * cd /path/to/HouseMktAnalyzr && python -m housemktanalyzr.alerts.runner
```

### Email Notifications

Set environment variables for email alerts:

```bash
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=your-email@gmail.com
export SMTP_PASSWORD=your-app-password
```

## Investment Metrics

### Score (0-100)

Properties are scored based on:
- **Cap Rate** (25 pts): 7%+ = excellent
- **Cash Flow** (25 pts): $600+/mo = excellent
- **Price per Unit** (20 pts): <$150k = excellent
- **Gross Yield** (15 pts): 8%+ = excellent
- **GRM** (15 pts): <10 = excellent

### Key Metrics

| Metric | Formula | Good Value |
|--------|---------|------------|
| Cap Rate | NOI / Price × 100 | 5%+ |
| Gross Yield | Annual Rent / Price × 100 | 6%+ |
| GRM | Price / Annual Rent | <12 |
| Cash Flow | Rent - Expenses - Mortgage | Positive |

### Assumptions

- **Down Payment**: 20% (Canadian investment property minimum)
- **Mortgage Rate**: 5% (configurable)
- **Expense Ratio**: 35% of gross rent
- **Amortization**: 30 years
- **Canadian Mortgage**: Semi-annual compounding

## Configuration

### Data Storage

- Criteria: `~/.housemktanalyzr/alerts.json`
- Seen Listings: `~/.housemktanalyzr/seen_listings.json`
- Property Cache: `~/.housemktanalyzr/cache.db`

## Development

### Setup

```bash
git clone https://github.com/yourusername/HouseMktAnalyzr.git
cd HouseMktAnalyzr
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest tests/ -v
```

### Code Style

```bash
ruff check src/
ruff format src/
```

## Project Structure

```
src/housemktanalyzr/
├── analysis/           # Investment calculations and ranking
│   ├── calculator.py   # Cap rate, yield, mortgage, scoring
│   └── ranker.py       # Property ranking and filtering
├── alerts/             # Alert system
│   ├── criteria.py     # AlertCriteria model
│   ├── checker.py      # Find matching properties
│   ├── notifier.py     # Console and email notifications
│   └── runner.py       # CLI for scheduled checks
├── collectors/         # Data collection
│   └── centris.py      # Centris scraper
├── dashboard/          # Streamlit UI
│   └── app.py          # Dashboard application
├── enrichment/         # Supplementary data
│   ├── cmhc.py         # CMHC rental data
│   └── assessment.py   # Quebec assessment data
├── models/             # Data models
│   └── property.py     # PropertyListing, InvestmentMetrics
└── storage/            # Data persistence
    └── cache.py        # SQLite property cache
```

## License

MIT License

## Acknowledgments

- CMHC for rental market data
- Centris for property listings
