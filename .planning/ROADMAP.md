# Roadmap: HouseMktAnalyzr

## Overview

Build a residential real estate investment analyzer for Quebec. Start with project foundation and data models, then research and implement data collection from available sources. Develop a scoring/ranking engine for investment analysis, create a dashboard for comparing opportunities, add an alert system for new matches, and finish with testing and polish.

## Phases

- [x] **Phase 1: Foundation** - Project structure, data models, configuration
- [x] **Phase 2: Data Collection** - Research APIs, implement property data fetching
- [x] **Phase 3: Analysis Engine** - Investment scoring, ROI calculations, ranking
- [x] **Phase 4: Dashboard** - Property comparison interface
- [x] **Phase 5: Alerts** - Notification system for matching criteria
- [x] **Phase 6: Polish** - Testing, documentation, refinements
- [x] **Phase 7: Modern Frontend** - React/Next.js UI with FastAPI backend

## Phase Details

### Phase 1: Foundation
**Goal**: Set up project structure with data models for properties and investment metrics
**Depends on**: Nothing (first phase)
**Plans**: TBD after planning

Plans:
- [x] 01-01: Project setup, data models, configuration system

### Phase 2: Data Collection
**Goal**: Research available data sources and implement property data fetching
**Depends on**: Phase 1
**Plans**: TBD after research

Plans:
- [x] 02-01: Research data sources (FINDINGS.md complete)
- [x] 02-02: Data collector framework and Centris scraper
- [x] 02-03: Supplementary data sources (CMHC, Quebec assessments)

### Phase 3: Analysis Engine
**Goal**: Score and rank properties based on investment potential
**Depends on**: Phase 2
**Plans**: TBD after planning

Plans:
- [x] 03-01: Investment metrics (ROI, cap rate, rental yield)
- [x] 03-02: Scoring algorithm and ranking system

### Phase 4: Dashboard
**Goal**: Interface for viewing and comparing investment opportunities
**Depends on**: Phase 3
**Plans**: TBD after planning

Plans:
- [x] 04-01: Property listing and detail views
- [x] 04-02: Side-by-side comparison feature

### Phase 5: Alerts
**Goal**: Notify user when properties matching criteria appear
**Depends on**: Phase 4
**Plans**: TBD after planning

Plans:
- [x] 05-01: User criteria configuration
- [x] 05-02: Alert generation and delivery

### Phase 6: Polish
**Goal**: Production-ready with tests and documentation
**Depends on**: Phase 5
**Plans**: TBD after planning

Plans:
- [x] 06-01: Testing and bug fixes
- [x] 06-02: Documentation and final refinements

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 1/1 | Complete | 2026-02-06 |
| 2. Data Collection | 3/3 | Complete | 2026-02-06 |
| 3. Analysis Engine | 2/2 | Complete | 2026-02-06 |
| 4. Dashboard | 2/2 | Complete | 2026-02-06 |
| 5. Alerts | 2/2 | Complete | 2026-02-06 |
| 6. Polish | 2/2 | Complete | 2026-02-06 |
| 7. Modern Frontend | 6/6 | Complete | 2026-02-07 |

## v1.0 Complete

All phases complete. Project ready for use.

---

## v2.0 Roadmap

### Phase 7: Modern Frontend
**Goal**: Replace Streamlit with React/Next.js + FastAPI for a full-featured investment platform
**Depends on**: Phase 6

Plans:
- [x] 07-01: FastAPI backend setup
- [x] 07-02: Next.js project initialization
- [x] 07-03: Property search and table
- [x] 07-04: Comparison and analysis views
- [x] 07-05: Charts and analytics
- [x] 07-06: Portfolio tracking (new feature)

## v2.0 Complete

Modern frontend with React/Next.js and FastAPI backend complete.

---

## v3.0 Roadmap

### Completed
- [x] **Background scraper** — Auto-scrape all regions every 4h, DB-first architecture
- [x] **Multi-region support** — 8 regions (Montreal, Laval, Longueuil, South Shore, North Shore, Laurentides, Lanaudiere, Monteregie)
- [x] **Pagination** — Frontend pagination with no result limit
- [x] **Alert system** — Criteria-based matching engine with email notifications (Gmail SMTP)
- [x] **Walk Score integration** — Scrapes walkscore.com for walk/transit/bike scores, no API key needed
- [x] **Walk Score in scrape cycle** — Enriches listings during background scrape (50/cycle, 3s delay)
- [x] **Price drop tracking** — Records price history for alert notifications

### Next Steps
- [ ] **Custom domain + Cloudflare** — Register domain, set up Cloudflare DNS proxy for CDN/DDoS protection
- [ ] **Walk Score in list view** — Display scores as columns in the property table
- [ ] **Map view** — Interactive map with property pins using geocoded coordinates
- [ ] **Filtering by Walk Score** — Filter listings by min walk/transit/bike score
- [ ] **Email delivery verification** — End-to-end test of alert email flow
