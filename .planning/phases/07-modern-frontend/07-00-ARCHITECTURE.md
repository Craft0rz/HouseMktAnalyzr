# Phase 7: Modern Frontend Architecture

## Overview

Replace Streamlit dashboard with a modern React/Next.js frontend backed by a Python FastAPI backend.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Next.js Frontend                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌───────────────┐  │
│  │ Search  │ │ Compare │ │ Charts  │ │   Portfolio   │  │
│  │  Page   │ │  Page   │ │  Page   │ │     Page      │  │
│  └────┬────┘ └────┬────┘ └────┬────┘ └───────┬───────┘  │
│       └───────────┴───────────┴───────────────┘          │
│                         │                                 │
│                    API Client                             │
└─────────────────────────┬───────────────────────────────┘
                          │ REST API
┌─────────────────────────┴───────────────────────────────┐
│                   FastAPI Backend                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────────┐    │
│  │  /api/      │ │  /api/      │ │    /api/        │    │
│  │ properties  │ │  analysis   │ │   portfolio     │    │
│  └──────┬──────┘ └──────┬──────┘ └────────┬────────┘    │
│         └───────────────┴─────────────────┘              │
│                         │                                 │
│              Existing Python Modules                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐    │
│  │ Centris  │ │Calculator│ │  Ranker  │ │  Alerts  │    │
│  │ Scraper  │ │          │ │          │ │          │    │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Tech Stack

### Frontend (Next.js 14+)
- **Framework**: Next.js with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui (Radix primitives)
- **State**: React Query (TanStack Query)
- **Charts**: Recharts or Tremor
- **Tables**: TanStack Table
- **Maps**: Leaflet or Mapbox

### Backend (FastAPI)
- **Framework**: FastAPI
- **Async**: Native async/await
- **Validation**: Pydantic (already using)
- **Database**: SQLite → PostgreSQL (later)
- **Auth**: JWT tokens (optional, for portfolio)

## Project Structure

```
HouseMktAnalyzr/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── main.py            # FastAPI app
│   │   ├── routers/
│   │   │   ├── properties.py  # Property search/analysis
│   │   │   ├── analysis.py    # Investment calculations
│   │   │   ├── alerts.py      # Alert management
│   │   │   └── portfolio.py   # Portfolio tracking
│   │   ├── schemas/           # Pydantic schemas
│   │   └── deps.py            # Dependencies
│   └── requirements.txt
├── frontend/                   # Next.js frontend
│   ├── src/
│   │   ├── app/               # Next.js app router
│   │   │   ├── page.tsx       # Home/Search
│   │   │   ├── compare/       # Comparison page
│   │   │   ├── analytics/     # Charts/trends
│   │   │   └── portfolio/     # Portfolio tracker
│   │   ├── components/
│   │   │   ├── ui/            # shadcn components
│   │   │   ├── PropertyTable.tsx
│   │   │   ├── PropertyCard.tsx
│   │   │   ├── ComparisonView.tsx
│   │   │   └── Charts/
│   │   ├── lib/
│   │   │   ├── api.ts         # API client
│   │   │   └── utils.ts
│   │   └── hooks/
│   │       └── useProperties.ts
│   ├── package.json
│   └── tailwind.config.ts
└── src/housemktanalyzr/        # Existing Python modules
```

## Phases

### 07-01: FastAPI Backend Setup
- Create FastAPI app structure
- Expose existing modules as REST endpoints
- Property search endpoint
- Analysis endpoint

### 07-02: Next.js Project Setup
- Initialize Next.js with TypeScript
- Configure Tailwind + shadcn/ui
- Create API client
- Basic layout and navigation

### 07-03: Property Search & Table
- Search page with filters
- Property table with sorting/filtering
- Property detail modal/page
- Pagination

### 07-04: Comparison & Analysis
- Side-by-side comparison view
- Investment metrics cards
- Score breakdown visualization

### 07-05: Charts & Analytics
- Market trends charts
- Price distribution
- Cap rate analysis
- Geographic heatmap

### 07-06: Portfolio Tracking (New Feature)
- Add properties to portfolio
- Track purchase price, current value
- ROI calculations over time
- Rent tracking

## API Endpoints

```
GET  /api/properties/search     # Search with filters
GET  /api/properties/{id}       # Single property
POST /api/properties/analyze    # Analyze listings
GET  /api/properties/compare    # Compare multiple

GET  /api/alerts                # List saved alerts
POST /api/alerts                # Create alert
PUT  /api/alerts/{id}           # Update alert
DELETE /api/alerts/{id}         # Delete alert

GET  /api/portfolio             # User's portfolio
POST /api/portfolio/properties  # Add to portfolio
PUT  /api/portfolio/properties/{id}
DELETE /api/portfolio/properties/{id}

GET  /api/analytics/trends      # Market trends
GET  /api/analytics/distribution # Price/cap distributions
```

## Success Criteria

- [ ] FastAPI serves all existing functionality
- [ ] Next.js frontend replaces Streamlit
- [ ] Property search with real-time filtering
- [ ] Side-by-side comparison with visual diffs
- [ ] Interactive charts for market analysis
- [ ] Portfolio tracking with ROI history
- [ ] Responsive design (mobile-friendly)
- [ ] Fast load times (<2s initial, <100ms interactions)
