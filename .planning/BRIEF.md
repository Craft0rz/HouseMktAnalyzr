# HouseMktAnalyzr

**One-liner**: Residential real estate investment analyzer for Greater Montreal that identifies and ranks the best mid/long-term opportunities.

## Problem

Finding profitable real estate investments requires analyzing multiple data points across hundreds of listings - rental yields, appreciation potential, cap rates, price-to-rent ratios. Manually comparing opportunities is time-consuming and error-prone. Investors need a tool that aggregates data, scores opportunities, and surfaces the best investments automatically.

## Success Criteria

How we know it worked:

- [ ] Top 10 ranked investment opportunities displayed with clear scoring breakdown
- [ ] Dashboard allows side-by-side comparison of multiple properties
- [ ] Alert system notifies when properties matching user criteria hit the market
- [ ] Recommendations include data-backed reasoning (ROI projections, rental yields, etc.)

## Constraints

- **Region**: Greater Montreal initially (expandable to other regions later)
- **Property Types**: Houses, duplexes, triplexes, and multi-door buildings
- **Data Sources**: Research needed - Centris, Realtor.ca, potential API access
- **Tech Stack**: Python recommended (aligns with user's existing tooling)

## Out of Scope

What we're NOT building:

- Commercial real estate analysis
- Property management features
- Transaction/closing workflow tools
- Mortgage calculator (beyond basic affordability)
- Integration with MLS systems requiring broker credentials (initially)
