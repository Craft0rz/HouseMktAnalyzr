# 09-01 Summary: Family Home Scoring Engine

**One-liner**: Added a 3-pillar family home scoring engine (Livability 40 + Value 35 + Space 25 = 100) with FamilyHomeMetrics model, FamilyHomeScorer class, and two API endpoints.

## Accomplishments

- **FamilyHomeMetrics model** added to `property.py` with all three pillar scores, cost-of-ownership breakdown fields, and risk flag placeholders (flood_zone, contaminated_nearby)
- **FamilyHomeScorer class** created in `family_scorer.py` implementing:
  - Livability Pillar (0-40): walk score, transit score, safety, school proximity (placeholder), parks (placeholder)
  - Value Pillar (0-35): price vs municipal assessment, price per sqft, affordability/monthly cost estimate
  - Space & Comfort Pillar (0-25): lot size, bedrooms, condition score, property age
  - Cost of ownership: mortgage (Canadian semi-annual compounding via calculator.py), taxes, energy (era-based), insurance (0.35% of value), welcome tax (Quebec brackets), CMHC premium (3.5%)
- **Two API endpoints** added to `analysis.py`:
  - `POST /api/analysis/family-score` — Score a single house with location data enrichment
  - `POST /api/analysis/family-score-batch` — Score multiple houses, filter to HOUSE type, return sorted by family_score descending with summary stats

## Files Created

- `src/housemktanalyzr/analysis/family_scorer.py` — FamilyHomeScorer class (scoring engine + cost calculations)

## Files Modified

- `src/housemktanalyzr/models/property.py` — Added FamilyHomeMetrics model (no changes to existing models)
- `backend/app/routers/analysis.py` — Added FamilyHomeScorer import, HouseWithScore/FamilyBatchResponse models, two new endpoints (no changes to existing endpoints)

## Decisions Made

1. **Mortgage reuse**: Used `InvestmentCalculator.calculate_mortgage_payment()` from calculator.py for Canadian semi-annual compounding instead of duplicating the formula
2. **CMHC premium simplified**: Used flat 3.5% on mortgage amount instead of implementing full tiered premium schedule
3. **Welcome tax**: Standard Quebec brackets only (no Montreal-specific brackets yet)
4. **Energy estimation**: Era-based rate per sqft/month approach (pre-1970 highest, post-2010 lowest)
5. **Placeholders preserved**: School proximity, parks, market trajectory, flood zone, and contamination all have hooks but return None when data is unavailable
6. **Batch filtering**: Family batch endpoint automatically filters to HOUSE-type listings only and reports how many were filtered out

## Issues Encountered

None. All three tasks completed without blockers.

## Next Step

09-02: Frontend Houses Section — /houses page, HouseDetail component, family score visualization, i18n
