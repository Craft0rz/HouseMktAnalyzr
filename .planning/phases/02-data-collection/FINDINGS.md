# Research Findings: Data Sources for Greater Montreal Real Estate

## Summary & Recommendation

**UPDATED: With Realtor Access, Centris becomes viable!**

Quebec's real estate market is uniquely challenging - but having a realtor contact changes the options:

### Option A: Centris via Broker Authorization ⭐ BEST IF YOU HAVE REALTOR ACCESS
If you have a realtor willing to share their Centris access:
- **Direct path:** Realtor authorizes their brokerage → Centris provides FTP data feed
- **Via Repliers:** They can build a custom API from your broker's Centris data
- **Data:** Active listings from authorized brokerages (no historical)
- **Cost:** Repliers has no setup fees, month-to-month billing

### Option B: JLR (Equifax) - Property Data Platform
- **7M+ notarized Quebec transactions** with daily updates
- Land registry, municipal assessments, construction permits
- Enterprise/subscription pricing (contact for rates)
- Used by appraisers, investors, and real estate pros

### Option C: Houski API - No Broker Needed
- 17M+ Canadian properties, 200+ data points
- Pay-per-request with free trial
- Works without any real estate industry connections

### Option D: Quebec Open Data + Scraping
- Free municipal assessment XML files (1,140 municipalities)
- Centris web scraping for active listings
- Most work, lowest cost

---

## Detailed Findings

### 1. Centris via Broker Authorization ⭐ NEW OPTION

**Source:** [Repliers Quebec Guide](https://help.repliers.com/en/article/accessing-real-estate-listing-data-in-quebec-5xl37f/)

| Aspect | Finding |
|--------|---------|
| API Access | **Via Repliers with broker authorization** |
| Data Access | Broker authorizes → Centris grants access → FTP or API via Repliers |
| Historical Data | Not available - active listings only |
| Coverage | Single brokerage's listings, or multi-brokerage with multiple authorizations |

**With a Realtor Contact:**
- Your realtor can authorize their brokerage's data sharing
- [Repliers](https://repliers.com/) can build a custom API feed from Centris
- No setup fees, month-to-month billing, cancel anytime
- They handle the Centris integration complexity

**Verdict:** VIABLE if you have a realtor willing to authorize access.

---

### 2. JLR Land Title Solutions (Equifax)

**Source:** [JLR Solutions](https://solutions.jlr.ca/en/)

| Aspect | Finding |
|--------|---------|
| Coverage | All Quebec - 7M+ notarized transactions |
| Data Types | Land registry, municipal assessments, construction permits, transaction history |
| Updates | Daily |
| Access | Subscription/enterprise (contact for pricing) |
| Target Users | Appraisers, investors, brokers, lenders |

**Key Features:**
- Complete transaction history from Quebec Land Register
- Municipal assessment rolls
- Construction permit data
- Neighbourhood information
- 600K transactions analyzed annually

**Verdict:** Excellent for historical/assessment data. Contact for API access.

---

### 3. Quebec Municipal Assessment Rolls (Free)

**Source:** [Open Government Portal](https://open.canada.ca/data/en/dataset/061c8cb7-ca4e-45be-a990-61fce7e7d2dc)

| Aspect | Finding |
|--------|---------|
| Coverage | 1,140 municipalities in Quebec |
| Format | XML files (downloadable) |
| Data | Property assessments, building characteristics |
| Limitations | No owner names/addresses (redacted) |
| Cost | FREE |

**Verdict:** Free baseline data for property valuations. Good supplement.

---

### 4. Centris (Direct - No Broker)

---

### 2. Realtor.ca DDF

**Source:** [DDF Documentation](https://ddfapi-docs.realtor.ca/)

| Aspect | Finding |
|--------|---------|
| Coverage | ~65% of Canadian listings |
| Quebec Support | **Quebec does NOT participate** |
| Access | Requires becoming a technology provider |

**Verdict:** Not useful for Greater Montreal - Quebec is excluded from DDF.

---

### 3. Houski API ⭐ RECOMMENDED

**Source:** [Houski API Documentation](https://www.houski.ca/api-documentation)

| Aspect | Finding |
|--------|---------|
| Coverage | 17M+ Canadian properties including Quebec |
| Data Points | 200+ per property |
| Pricing | Pay-per-request, 30-day free trial |
| SDKs | Python, JavaScript, PHP, Ruby |
| Data Types | Property characteristics, transactions, assessments, market analytics |
| Updates | Daily |
| Uptime | 99.9% SLA |

**Key Features:**
- Property characteristics (bedrooms, bathrooms, sqft, lot size, year built)
- Historical transaction data (past sales, listing history, price trends)
- Assessment and tax information
- Neighborhood context (demographics, amenities)
- `price_quote` parameter for cost estimation before requests

**Verdict:** Best option for legal, comprehensive data access. Start with free trial.

---

### 4. Web Scraping Centris.ca

**Sources:**
- [harshhes/centris-ca-scrape](https://github.com/harshhes/centris-ca-scrape)
- [enesrizaates/centris.ca-crawler](https://github.com/enesrizaates/centris.ca-crawler)
- [Apify Centris Scraper](https://apify.com/ecomscrape/centris-property-search-scraper)

| Aspect | Finding |
|--------|---------|
| Feasibility | Possible with Selenium/browser automation |
| Existing Code | Multiple GitHub projects available |
| Challenges | CAPTCHA, rate limiting, legal gray area |
| Data Available | Addresses, prices, sqft, bedrooms, images |

**Verdict:** Viable as backup. Use existing GitHub scrapers as starting point.

---

### 5. Rental Price Data

**Sources:**
- [CMHC Portal](https://www03.cmhc-schl.gc.ca/hmip-pimh/)
- [Statistics Canada](https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=4610009201)

| Source | Data Available | Access |
|--------|---------------|--------|
| CMHC | Average rents by bedroom count, vacancy rates | Free downloads |
| Statistics Canada | Quarterly asking rents by CMA | Free API/downloads |
| Rentals.ca | Market reports | No public API |

**Verdict:** CMHC provides free rental data for estimating income potential.

---

### 6. Other APIs Considered

| API | Verdict |
|-----|---------|
| [RapidAPI Realty-in-CA](https://rapidapi.com/apidojo/api/realty-in-ca1) | Mirrors Realtor.ca - Quebec excluded |
| [Zyla Labs Canada RE API](https://zylalabs.com/api-marketplace/tools/canada+real+estate+api/5902) | Unknown Quebec coverage |
| [MappedBy](https://www.mappedby.com/api) | US/Canada but unclear on Quebec |

---

## Implementation Recommendation

### IF you have realtor access (RECOMMENDED):

**Path A: Centris via Repliers**
1. Talk to your realtor about data sharing authorization
2. Realtor authorizes brokerage → Contact Repliers
3. Repliers builds custom Centris feed/API
4. Supplement with CMHC rental data + Quebec assessment rolls

### IF no realtor access:

**Path B: Multi-Source Approach**
1. Start with Houski API (free trial, test Montreal coverage)
2. Download Quebec municipal assessment XML files (free)
3. Add CMHC rental data for income estimates
4. Consider Centris scraping as backup

### Data Layer Architecture (Either Path)

```
┌─────────────────────────────────────────────────┐
│              PropertyListing Model               │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌───────────┐  ┌───────────┐  ┌─────────────┐ │
│  │  Centris  │  │  Houski   │  │  Scraper    │ │
│  │  (broker) │  │   API     │  │  (backup)   │ │
│  └─────┬─────┘  └─────┬─────┘  └──────┬──────┘ │
│        │              │               │        │
│        └──────────────┼───────────────┘        │
│                       ▼                        │
│              DataCollector                     │
│         (unified interface)                    │
│                       │                        │
│        ┌──────────────┼──────────────┐        │
│        ▼              ▼              ▼        │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐   │
│  │  CMHC    │  │  Quebec   │  │   JLR    │   │
│  │  Rental  │  │  Assess.  │  │  (opt)   │   │
│  └──────────┘  └───────────┘  └──────────┘   │
│                                                │
└─────────────────────────────────────────────────┘
```

---

## Metadata

| Attribute | Value |
|-----------|-------|
| **Confidence** | HIGH (with broker) / MEDIUM (without) |
| **Confidence Reason** | Broker path is well-documented; Houski needs testing |
| **Dependencies** | Either: Realtor authorization OR Houski API key |
| **Open Questions** | 1. Is your realtor willing to authorize data sharing? 2. Which brokerage are they with? (affects coverage) |
| **Assumptions** | Repliers can deliver on custom Centris feed as advertised |

---

## Decision Needed

**Do you have a realtor who would authorize Centris data access?**

- **YES** → Use Centris via Repliers (best data, direct from source)
- **NO** → Use Houski API + Quebec open data + optional scraping
- **MAYBE** → Worth asking - it's the cleanest path to Quebec data
