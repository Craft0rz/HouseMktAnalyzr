"""Streamlit dashboard for HouseMktAnalyzr."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

# Handle both relative and absolute imports for Streamlit compatibility
try:
    from ..alerts import AlertCriteria, CriteriaManager
    from ..analysis import InvestmentCalculator, PropertyRanker
    from ..collectors.centris import CentrisScraper
    from ..models.property import InvestmentMetrics, PropertyListing, PropertyType
except ImportError:
    # Add src to path when running directly with streamlit
    src_path = Path(__file__).parent.parent.parent
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

    from housemktanalyzr.alerts import AlertCriteria, CriteriaManager
    from housemktanalyzr.analysis import InvestmentCalculator, PropertyRanker
    from housemktanalyzr.collectors.centris import CentrisScraper
    from housemktanalyzr.models.property import InvestmentMetrics, PropertyListing, PropertyType

# Page configuration
st.set_page_config(
    page_title="HouseMktAnalyzr",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Region options
REGIONS = {
    "Montreal South Shore": "montreal-south-shore",
    "Montreal Island": "montreal-island",
    "Laval": "laval",
    "North Shore": "montreal-north-shore",
}

# Property type options
PROPERTY_TYPES = {
    "Duplex": PropertyType.DUPLEX,
    "Triplex": PropertyType.TRIPLEX,
    "Quadplex": PropertyType.QUADPLEX,
    "Multiplex (5+)": PropertyType.MULTIPLEX,
    "House": PropertyType.HOUSE,
}


def get_score_color(score: float) -> str:
    """Return color based on score value."""
    if score >= 70:
        return "🟢"
    elif score >= 50:
        return "🟡"
    else:
        return "🔴"


def format_currency(value: int) -> str:
    """Format number as currency."""
    return f"${value:,}"


def format_percent(value: Optional[float]) -> str:
    """Format number as percentage."""
    if value is None:
        return "N/A"
    return f"{value:.1f}%"


def create_property_dataframe(
    results: list[tuple[PropertyListing, InvestmentMetrics]]
) -> pd.DataFrame:
    """Convert analysis results to DataFrame for display."""
    data = []
    for listing, metrics in results:
        data.append({
            "Score": f"{get_score_color(metrics.score)} {metrics.score:.0f}",
            "Address": listing.address[:40],
            "City": listing.city,
            "Type": listing.property_type.value,
            "Units": listing.units,
            "Price": format_currency(listing.price),
            "Price/Unit": format_currency(metrics.price_per_unit),
            "Cap Rate": format_percent(metrics.cap_rate),
            "Cash Flow": f"${metrics.cash_flow_monthly:,.0f}/mo" if metrics.cash_flow_monthly else "N/A",
            "Yield": format_percent(metrics.gross_rental_yield),
            "URL": listing.url,
            "_score": metrics.score,  # Hidden column for sorting
            "_listing": listing,  # Hidden for detail view
            "_metrics": metrics,  # Hidden for detail view
        })
    return pd.DataFrame(data)


async def fetch_properties(
    region: str,
    property_types: list[str],
    min_price: int,
    max_price: int,
) -> list[PropertyListing]:
    """Fetch properties from Centris."""
    scraper = CentrisScraper()

    # Build search URL
    if "plex" in property_types or len(property_types) > 1:
        # Use all plex search for multi-type
        url = f"https://www.centris.ca/en/plexes~for-sale~{region}"
    elif "Duplex" in property_types:
        url = f"https://www.centris.ca/en/duplexes~for-sale~{region}"
    elif "Triplex" in property_types:
        url = f"https://www.centris.ca/en/triplexes~for-sale~{region}"
    elif "House" in property_types:
        url = f"https://www.centris.ca/en/houses~for-sale~{region}"
    else:
        url = f"https://www.centris.ca/en/plexes~for-sale~{region}"

    listings = await scraper.fetch_all_listings(
        url,
        min_price=min_price,
        max_price=max_price,
        max_pages=15,
    )

    # Filter by property type if specific types selected
    if property_types and "All Plex" not in property_types:
        type_set = {PROPERTY_TYPES.get(t) for t in property_types if t in PROPERTY_TYPES}
        listings = [l for l in listings if l.property_type in type_set]

    return listings


def show_comparison_view(properties: list[tuple[PropertyListing, InvestmentMetrics]]):
    """Display side-by-side comparison of selected properties."""
    if len(properties) < 2:
        st.warning("Select at least 2 properties to compare")
        return

    st.subheader("⚖️ Property Comparison")

    # Find best values for highlighting
    scores = [m.score for _, m in properties]
    cap_rates = [m.cap_rate or 0 for _, m in properties]
    cash_flows = [m.cash_flow_monthly or 0 for _, m in properties]
    yields = [m.gross_rental_yield for _, m in properties]
    prices = [l.price for l, _ in properties]
    price_per_units = [m.price_per_unit for _, m in properties]

    best_score = max(scores)
    best_cap = max(cap_rates)
    best_cf = max(cash_flows)
    best_yield = max(yields)
    best_price = min(prices)  # Lower is better
    best_ppu = min(price_per_units)  # Lower is better

    # Create columns for each property
    cols = st.columns(len(properties))

    for i, (col, (listing, metrics)) in enumerate(zip(cols, properties)):
        with col:
            # Winner badge
            if metrics.score == best_score:
                st.success("🏆 Best Score")

            st.markdown(f"### {listing.address[:25]}...")
            st.caption(f"{listing.city} | {listing.property_type.value}")

            st.divider()

            # Score with delta
            score_delta = metrics.score - best_score if metrics.score != best_score else None
            st.metric(
                "Investment Score",
                f"{metrics.score:.0f}/100",
                delta=f"{score_delta:.0f}" if score_delta else None,
                delta_color="normal",
            )

            st.divider()
            st.markdown("**💰 Price**")

            # Price metrics
            price_delta = listing.price - best_price if listing.price != best_price else None
            st.metric(
                "Price",
                format_currency(listing.price),
                delta=f"+{format_currency(price_delta)}" if price_delta else None,
                delta_color="inverse",  # Lower is better
            )

            ppu_delta = metrics.price_per_unit - best_ppu if metrics.price_per_unit != best_ppu else None
            st.metric(
                "Price/Unit",
                format_currency(metrics.price_per_unit),
                delta=f"+{format_currency(ppu_delta)}" if ppu_delta else None,
                delta_color="inverse",
            )

            st.divider()
            st.markdown("**📈 Returns**")

            # Cap rate
            cap_delta = (metrics.cap_rate or 0) - best_cap if (metrics.cap_rate or 0) != best_cap else None
            st.metric(
                "Cap Rate",
                format_percent(metrics.cap_rate),
                delta=f"{cap_delta:.1f}%" if cap_delta else None,
            )

            # Cash flow
            cf = metrics.cash_flow_monthly or 0
            cf_delta = cf - best_cf if cf != best_cf else None
            st.metric(
                "Cash Flow",
                f"${cf:,.0f}/mo",
                delta=f"${cf_delta:,.0f}" if cf_delta else None,
            )

            # Yield
            yield_delta = metrics.gross_rental_yield - best_yield if metrics.gross_rental_yield != best_yield else None
            st.metric(
                "Gross Yield",
                format_percent(metrics.gross_rental_yield),
                delta=f"{yield_delta:.1f}%" if yield_delta else None,
            )

            st.divider()
            st.markdown("**🏠 Property**")
            st.write(f"**Units:** {listing.units}")
            st.write(f"**Beds:** {listing.bedrooms}")
            st.write(f"**Baths:** {listing.bathrooms}")
            st.write(f"**Est. Rent:** {format_currency(metrics.estimated_monthly_rent)}/mo")

            st.link_button("View Listing", listing.url, use_container_width=True)


def show_property_detail(listing: PropertyListing, metrics: InvestmentMetrics):
    """Display detailed property information."""
    st.subheader(f"📍 {listing.address}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Property Details**")
        st.write(f"**Type:** {listing.property_type.value}")
        st.write(f"**City:** {listing.city}")
        st.write(f"**Units:** {listing.units}")
        st.write(f"**Beds:** {listing.bedrooms}")
        st.write(f"**Baths:** {listing.bathrooms}")
        if listing.sqft:
            st.write(f"**Size:** {listing.sqft:,} sqft")

    with col2:
        st.markdown("**Financials**")
        st.write(f"**Price:** {format_currency(listing.price)}")
        st.write(f"**Price/Unit:** {format_currency(metrics.price_per_unit)}")
        if metrics.price_per_sqft:
            st.write(f"**Price/sqft:** ${metrics.price_per_sqft:,.0f}")
        st.write(f"**Est. Rent:** {format_currency(metrics.estimated_monthly_rent)}/mo")

    with col3:
        st.markdown("**Investment Metrics**")
        st.metric("Score", f"{metrics.score:.0f}/100")
        st.write(f"**Cap Rate:** {format_percent(metrics.cap_rate)}")
        st.write(f"**Yield:** {format_percent(metrics.gross_rental_yield)}")
        cash_flow = metrics.cash_flow_monthly or 0
        st.write(f"**Cash Flow:** ${cash_flow:,.0f}/mo")

    # Score breakdown
    if metrics.score_breakdown:
        st.markdown("**Score Breakdown**")
        breakdown_cols = st.columns(5)
        for i, (key, value) in enumerate(metrics.score_breakdown.items()):
            with breakdown_cols[i % 5]:
                st.write(f"{key}: {value:.1f}")

    st.link_button("🔗 View on Centris", listing.url)


def main():
    """Main dashboard application."""
    st.title("🏠 HouseMktAnalyzr")
    st.markdown("*Greater Montreal Investment Property Analyzer*")

    # Initialize session state
    if "results" not in st.session_state:
        st.session_state.results = []
    if "selected_property" not in st.session_state:
        st.session_state.selected_property = None
    if "comparison_list" not in st.session_state:
        st.session_state.comparison_list = []

    # Sidebar filters
    with st.sidebar:
        st.header("🔍 Search Filters")

        region = st.selectbox(
            "Region",
            options=list(REGIONS.keys()),
            index=0,
        )

        property_types = st.multiselect(
            "Property Types",
            options=list(PROPERTY_TYPES.keys()),
            default=["Duplex", "Triplex", "Quadplex"],
        )

        st.markdown("**Price Range**")
        col1, col2 = st.columns(2)
        with col1:
            min_price = st.number_input("Min ($)", value=300000, step=50000)
        with col2:
            max_price = st.number_input("Max ($)", value=1000000, step=50000)

        st.divider()

        st.markdown("**Filter Results**")
        min_score = st.slider("Minimum Score", 0, 100, 40)
        min_cap_rate = st.slider("Minimum Cap Rate (%)", 0.0, 10.0, 4.0, 0.5)

        st.divider()

        search_clicked = st.button("🔎 Search Properties", type="primary", use_container_width=True)

        # Saved Searches section
        st.divider()
        st.header("💾 Saved Searches")

        criteria_mgr = CriteriaManager()
        saved_criteria = criteria_mgr.list_all()

        # Save current search
        with st.expander("Save Current Search"):
            alert_name = st.text_input("Alert Name", placeholder="e.g., South Shore Triplexes")
            if st.button("💾 Save as Alert", use_container_width=True):
                if alert_name:
                    new_criteria = AlertCriteria(
                        name=alert_name,
                        regions=[REGIONS[region]],
                        property_types=[PROPERTY_TYPES[t] for t in property_types if t in PROPERTY_TYPES],
                        min_price=int(min_price) if min_price else None,
                        max_price=int(max_price) if max_price else None,
                        min_score=float(min_score) if min_score else None,
                        min_cap_rate=float(min_cap_rate) if min_cap_rate else None,
                    )
                    criteria_mgr.save(new_criteria)
                    st.success(f"Saved alert: {alert_name}")
                    st.rerun()
                else:
                    st.warning("Please enter a name for the alert")

        # Display saved searches
        if saved_criteria:
            for criteria in saved_criteria:
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        status = "🟢" if criteria.enabled else "⚪"
                        st.markdown(f"{status} **{criteria.name}**")
                        regions_str = ", ".join(criteria.regions)
                        st.caption(f"{regions_str} | Score ≥ {criteria.min_score or 0}")
                    with col2:
                        if st.button("🗑️", key=f"del_{criteria.id}", help="Delete"):
                            criteria_mgr.delete(criteria.id)
                            st.rerun()
        else:
            st.caption("No saved searches yet")

    # Main content area
    if search_clicked:
        with st.spinner(f"Fetching properties from {region}..."):
            try:
                listings = asyncio.run(fetch_properties(
                    REGIONS[region],
                    property_types,
                    int(min_price),
                    int(max_price),
                ))

                if listings:
                    ranker = PropertyRanker()
                    results = ranker.filter_by_criteria(
                        listings,
                        min_score=min_score,
                        min_cap_rate=min_cap_rate,
                    )
                    results = sorted(results, key=lambda x: x[1].score, reverse=True)
                    st.session_state.results = results
                    st.success(f"Found {len(listings)} properties, {len(results)} match your criteria")
                else:
                    st.warning("No properties found. Try adjusting your filters.")
                    st.session_state.results = []

            except Exception as e:
                st.error(f"Error fetching properties: {e}")
                st.session_state.results = []

    # Display results
    if st.session_state.results:
        results = st.session_state.results

        # Summary metrics
        st.subheader(f"📊 {len(results)} Properties Found")

        metric_cols = st.columns(4)
        scores = [m.score for _, m in results]
        cap_rates = [m.cap_rate for _, m in results if m.cap_rate]
        cash_flows = [m.cash_flow_monthly for _, m in results if m.cash_flow_monthly]

        with metric_cols[0]:
            st.metric("Avg Score", f"{sum(scores)/len(scores):.1f}")
        with metric_cols[1]:
            if cap_rates:
                st.metric("Avg Cap Rate", f"{sum(cap_rates)/len(cap_rates):.1f}%")
        with metric_cols[2]:
            if cash_flows:
                positive = len([cf for cf in cash_flows if cf > 0])
                st.metric("Positive Cash Flow", f"{positive}/{len(cash_flows)}")
        with metric_cols[3]:
            best_score = max(scores)
            st.metric("Best Score", f"{best_score:.0f}")

        st.divider()

        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["📋 Property List", "⚖️ Compare", "🏠 Details"])

        with tab1:
            # Property table with selection
            df = create_property_dataframe(results)
            display_cols = ["Score", "Address", "City", "Type", "Units", "Price", "Price/Unit", "Cap Rate", "Cash Flow", "Yield"]

            st.dataframe(
                df[display_cols],
                use_container_width=True,
                height=400,
                hide_index=True,
            )

        with tab2:
            # Comparison view
            st.markdown("Select 2-4 properties to compare side-by-side")

            property_options = [f"{r[0].address[:35]} - {format_currency(r[0].price)}" for r in results]

            selected_indices = st.multiselect(
                "Select properties to compare",
                options=range(len(property_options)),
                format_func=lambda x: property_options[x],
                max_selections=4,
                key="comparison_select",
            )

            if len(selected_indices) >= 2:
                selected_properties = [results[i] for i in selected_indices]
                show_comparison_view(selected_properties)
            elif len(selected_indices) == 1:
                st.info("Select at least one more property to compare")
            else:
                st.info("Select 2-4 properties from the list above to compare them")

        with tab3:
            # Property detail selector
            property_options = [f"{r[0].address[:40]} - {format_currency(r[0].price)}" for r in results]
            selected_idx = st.selectbox(
                "Select a property to view details",
                options=range(len(property_options)),
                format_func=lambda x: property_options[x],
                key="detail_select",
            )

            if selected_idx is not None:
                listing, metrics = results[selected_idx]
                show_property_detail(listing, metrics)

    else:
        # Welcome message
        st.info("👈 Use the sidebar to search for investment properties")

        st.markdown("""
        ### How to use:
        1. Select a **region** (South Shore has ~230 plex listings)
        2. Choose **property types** (duplex, triplex, etc.)
        3. Set your **price range**
        4. Click **Search Properties**

        ### Investment Metrics:
        - **Score**: Overall investment quality (0-100)
        - **Cap Rate**: Net Operating Income / Price
        - **Cash Flow**: Monthly income after expenses and mortgage
        - **Yield**: Gross rental income / Price
        """)


if __name__ == "__main__":
    main()
