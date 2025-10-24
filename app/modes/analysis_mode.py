import streamlit as st
from app import database
import pandas as pd
import datetime
import altair as alt
import re
import os
from app.utils import normalize_time_string

def render_film_analysis(cache_data):
    """Renders the UI and logic for film-centric analysis."""
    st.subheader("Film Performance Analysis")

    # --- Date Range Selection ---
    today = datetime.date.today()
    default_start = st.session_state.get('film_analysis_date_range_start', today - datetime.timedelta(days=7))
    default_end = st.session_state.get('film_analysis_date_range_end', today)

    # --- Genre Filter ---
    all_genres = database.get_all_unique_genres()
    if 'film_analysis_genres' not in st.session_state:
        st.session_state.film_analysis_genres = []

    selected_genres = st.multiselect(
        "Filter by Genre (optional)",
        options=all_genres,
        default=st.session_state.film_analysis_genres
    )
    st.session_state.film_analysis_genres = selected_genres

    selected_range = st.date_input(
        "Select a date range for analysis",
        value=(default_start, default_end),
        key="film_analysis_date_range_widget"
    )

    if selected_range and len(selected_range) == 2:
        st.session_state.film_analysis_date_range_start, st.session_state.film_analysis_date_range_end = selected_range

    # --- Report Generation ---
    if st.button("📊 Generate Film Report", type="primary", use_container_width=True):
        if 'film_analysis_date_range_start' in st.session_state and 'film_analysis_date_range_end' in st.session_state:
            start_date, end_date = st.session_state.film_analysis_date_range_start, st.session_state.film_analysis_date_range_end
            
            with st.spinner("Querying and analyzing film data..."):
                all_data = database.query_historical_data(start_date, end_date, genres=selected_genres)

                if all_data.empty:
                    st.warning("No film data found for the selected date range.")
                    st.session_state.film_summary_df = pd.DataFrame()
                    st.session_state.film_detail_data = pd.DataFrame()
                else:
                    # --- NEW: Filter for films that have price data ---
                    # This ensures that films only scraped for operating hours are excluded.
                    priced_data = all_data.dropna(subset=['price'])
                    if priced_data.empty:
                        st.warning("No films with price data were found for the selected criteria.")
                        return

                    unique_showtimes = all_data.drop_duplicates(subset=['play_date', 'theater_name', 'film_title', 'showtime'])
                    summary = unique_showtimes.groupby('film_title').agg(
                        total_showings=('showtime', 'size'),
                        num_theaters=('theater_name', 'nunique')
                    ).reset_index()
                    avg_prices = priced_data.groupby('film_title')['price'].mean().reset_index()
                    summary = pd.merge(summary, avg_prices, on='film_title', how='left')
                    
                    summary = summary.rename(columns={
                        'film_title': 'Film Title', 'total_showings': 'Total Showings',
                        'num_theaters': 'Theaters Playing', 'price': 'Average Price'
                    }).sort_values(by='Total Showings', ascending=False)
                    summary['Average Price'] = summary['Average Price'].apply(lambda x: f'${x:,.2f}' if pd.notna(x) else 'N/A')

                    st.session_state.film_summary_df = summary
                    st.session_state.film_detail_data = priced_data
        else:
            st.error("Please select a valid date range.")

    # --- Display Reports ---
    if 'film_summary_df' in st.session_state and not st.session_state.film_summary_df.empty:
        st.subheader("Film Summary Report")
        st.dataframe(st.session_state.film_summary_df, use_container_width=True, hide_index=True)

        # --- Summary Statistics ---
        st.subheader("Summary Statistics")
        summary_df = st.session_state.film_summary_df
        total_films = len(summary_df)
        total_showings = summary_df['Total Showings'].sum()
        
        # Calculate weighted average price
        detail_df = st.session_state.film_detail_data
        # The previous weighted average calculation was flawed. A simple mean correctly ignores NaN values.
        average_price = detail_df['price'].mean()
        if pd.isna(average_price):
            average_price = 0.0 # Default to 0 if no price data exists at all

        top_film = summary_df.iloc[0] # Already sorted by Total Showings

        cols = st.columns(4)
        cols[0].metric("Total Films Analyzed", f"{total_films}")
        cols[1].metric("Total Showings Captured", f"{total_showings:,}")
        cols[2].metric("Average Ticket Price", f"${average_price:,.2f}")
        cols[3].metric("Top Film by Showings", top_film['Film Title'], help=f"{top_film['Total Showings']:,} showings")

        # --- Key Insights Section ---
        st.divider()
        st.subheader("✨ Key Insights")
        insights_col1, insights_col2 = st.columns(2)

        # Insight 1: Weekend vs. Weekday Pricing
        with insights_col1:
            st.markdown("##### Weekend vs. Weekday Pricing")
            df_price_analysis = detail_df.dropna(subset=['price']).copy()
            df_price_analysis['day_type'] = pd.to_datetime(df_price_analysis['play_date']).dt.dayofweek.apply(
                lambda x: 'Weekend' if x >= 4 else 'Weekday' # Friday, Saturday, Sunday are weekend
            )
            price_by_day_type = df_price_analysis.groupby('day_type')['price'].mean().reindex(['Weekday', 'Weekend'])
            
            if not price_by_day_type.dropna().empty:
                st.bar_chart(price_by_day_type)
                
                # Add text summary
                weekday_price = price_by_day_type.get('Weekday', 0)
                weekend_price = price_by_day_type.get('Weekend', 0)
                if weekday_price and weekend_price and weekend_price > weekday_price:
                    diff = (weekend_price - weekday_price) / weekday_price
                    st.info(f"On average, weekend tickets are **{diff:.1%} more expensive** than weekday tickets.")
                elif weekday_price and weekend_price and weekday_price > weekend_price:
                    diff = (weekday_price - weekend_price) / weekend_price
                    st.info(f"Interestingly, weekday tickets are **{diff:.1%} more expensive** than weekend tickets.")
                else:
                    st.info("No significant price difference between weekdays and weekends.")
            else:
                st.info("Not enough data to compare weekday vs. weekend pricing.")

        # Insight 2: Sold-Out Performance
        with insights_col2:
            st.markdown("##### Sold-Out Performance")
            if 'capacity' in detail_df.columns and not detail_df['capacity'].dropna().empty:
                sold_out_df = detail_df[detail_df['capacity'] == 'Sold Out']
                if not sold_out_df.empty:
                    # Calculate total showings for each of the top 5 films
                    top_5_films = summary_df['Film Title'].head(5).tolist()
                    total_showings_top_5 = detail_df[detail_df['film_title'].isin(top_5_films)].groupby('film_title').size()
                    
                    # Calculate sold-out showings for the top 5
                    sold_out_counts = sold_out_df[sold_out_df['film_title'].isin(top_5_films)].groupby('film_title').size()
                    
                    # Calculate percentage
                    sold_out_percentage = (sold_out_counts / total_showings_top_5 * 100).fillna(0).reset_index(name='percentage')
                    sold_out_percentage = sold_out_percentage.set_index('film_title')

                    st.bar_chart(sold_out_percentage, y='percentage')
                    
                    most_sold_out = sold_out_percentage['percentage'].idxmax()
                    st.info(f"**'{most_sold_out}'** has the highest percentage of sold-out showings among the top 5 films.")

                else:
                    st.info("No sold-out showings were recorded in this period.")
            else:
                st.info("No capacity data available to analyze sold-out performance.")


        st.divider()
        st.subheader("Theater Breakdown by Film")
        
        selected_film = st.selectbox("Select a film to see theater details:", options=st.session_state.film_summary_df['Film Title'].tolist())
        
        if selected_film:
            # --- Film Summary Header ---
            film_info = database.get_film_details(selected_film)
            if film_info:
                col_img, col_details = st.columns([1, 4])
                with col_img:
                    if film_info.get('poster_url') and film_info['poster_url'] != 'N/A':
                        st.image(film_info['poster_url'], width=200)

                with col_details:
                    st.subheader(f"Rating: {film_info.get('mpaa_rating', 'N/A')} | Genre: {film_info.get('genre', 'N/A')}")
                    st.caption(f"Director: {film_info.get('director', 'N/A')} | Actors: {film_info.get('actors', 'N/A')}")
                    st.write(film_info.get('plot', 'No plot summary available.'))
                    
                    score1, score2 = st.columns(2)
                    score1.metric("IMDb Rating", f"{film_info.get('imdb_rating', 'N/A')} / 10")
                    score2.metric("Metascore", f"{film_info.get('metascore', 'N/A')} / 100")
                st.divider()

            film_data = st.session_state.film_detail_data[st.session_state.film_detail_data['film_title'] == selected_film].copy()

            # --- NEW: Add market data for market-level comparisons ---
            if 'market' not in film_data.columns:
                theater_to_market_map = {}
                if cache_data and "markets" in cache_data:
                    for market_name, market_info in cache_data["markets"].items():
                        for theater in market_info.get("theaters", []):
                            theater_to_market_map[theater['name']] = market_name
                film_data['market'] = film_data['theater_name'].map(theater_to_market_map).fillna('Unknown')

            if not film_data.empty:
                # --- NEW: Grouping logic ---
                group_by_film = st.radio(
                    "Group breakdown by:",
                    ("Theater", "Market"),
                    horizontal=True,
                    key="film_analysis_group_by"
                )
                grouping_column_film = 'theater_name' if group_by_film == "Theater" else 'market'

                unique_showtimes_film = film_data.drop_duplicates(subset=['play_date', 'theater_name', 'showtime'])
                theater_summary = unique_showtimes_film.groupby(grouping_column_film).agg(showings_count=('showtime', 'size')).reset_index()
                avg_prices_theater = film_data.groupby(grouping_column_film)['price'].mean().reset_index()
                theater_summary = pd.merge(theater_summary, avg_prices_theater, on=grouping_column_film, how='left')
                
                theater_summary = theater_summary.rename(columns={
                    grouping_column_film: group_by_film, 'showings_count': 'Number of Showings', 'price': 'Average Price'
                }).sort_values(by='Number of Showings', ascending=False)
                theater_summary['Average Price'] = theater_summary['Average Price'].apply(lambda x: f'${x:,.2f}' if pd.notna(x) else 'N/A')

                st.dataframe(theater_summary, use_container_width=True, hide_index=True)
                st.subheader(f"Showings per {group_by_film} for '{selected_film}'")
                st.bar_chart(theater_summary.set_index(group_by_film)['Number of Showings'])

            # --- Comparable Film Analysis ---
            if film_info and film_info.get('genre'):
                st.divider()
                st.subheader("Comparable Film Analysis")
                st.info(f"Showing top 10 films in the database that share at least one genre with '{selected_film}'.")
                
                film_genres = [g.strip() for g in film_info['genre'].split(',')]
                comp_df = database.get_comparable_films(selected_film, film_genres)

                if not comp_df.empty:
                    comp_df['Average Price'] = comp_df['Average Price'].map('${:,.2f}'.format)
                    
                    comp_column_config = {
                        "Box Office": st.column_config.TextColumn(width="small"),
                        "IMDb Rating": st.column_config.NumberColumn(width="small"),
                        "Average Price": st.column_config.TextColumn(width="small"),
                        "Total Showings": st.column_config.NumberColumn(width="small"),
                    }

                    st.dataframe(
                        comp_df, 
                        use_container_width=True, 
                        hide_index=True,
                        column_config=comp_column_config
                    )
                else:
                    st.info("No comparable films found in the database yet. Backfill more historical data to enable this feature.")

def _generate_operating_hours_report(theaters: list[str], start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
    """
    [REFACTORED] Fetches, processes, and compares operating hours data.
    This is a self-contained function for Analysis Mode to ensure reliability.
    """
    # 1. Fetch current week's data
    current_df = database.get_operating_hours_for_theaters_and_dates(theaters, start_date, end_date)
    # --- NEW: Fallback to calculating from showings if no dedicated op_hours data exists ---
    if current_df.empty:
        st.info("No dedicated operating hours found. Calculating from scraped showtimes as a backup...")
        current_df = database.calculate_operating_hours_from_showings(theaters, start_date, end_date)

    if current_df.empty:
        return pd.DataFrame()

    current_df['scrape_date'] = pd.to_datetime(current_df['scrape_date'])
    current_df['Date'] = current_df['scrape_date'].dt.strftime('%a, %b %d')
    
    # Handle cases where a theater was scraped but had no showtimes
    current_df['Current Hours'] = current_df.apply(
        lambda row: f"{row['open_time']} - {row['close_time']}" if pd.notna(row['open_time']) else "No Showings Found",
        axis=1
    )

    # 2. Fetch previous week's data for comparison
    start_date_prev = start_date - datetime.timedelta(days=7)
    end_date_prev = end_date - datetime.timedelta(days=7)
    prev_df = database.get_operating_hours_for_theaters_and_dates(theaters, start_date_prev, end_date_prev)
    # --- NEW: Also use fallback for previous week's data for a consistent comparison ---
    if prev_df.empty:
        prev_df = database.calculate_operating_hours_from_showings(theaters, start_date_prev, end_date_prev)

    # 3. Compare and create the final report DataFrame
    if not prev_df.empty:
        prev_df['scrape_date'] = pd.to_datetime(prev_df['scrape_date'])
        prev_df['comparison_date'] = prev_df['scrape_date'] + datetime.timedelta(days=7)
        prev_df['Previous Hours'] = prev_df.apply(
            lambda row: f"{row['open_time']} - {row['close_time']}" if pd.notna(row['open_time']) else "No Showings Found",
            axis=1
        )
        # Create a lookup dictionary for previous hours
        prev_lookup = prev_df.set_index(['theater_name', 'comparison_date'])['Previous Hours'].to_dict()
        # Map the previous hours to the new dataframe
        current_df['Previous Hours'] = current_df.set_index(['theater_name', 'scrape_date']).index.map(prev_lookup).fillna('N/A')
    else:
        current_df['Previous Hours'] = 'N/A'

    current_df['Changed'] = current_df.apply(
        lambda row: 'Yes' if row['Previous Hours'] != 'N/A' and row['Current Hours'] != row['Previous Hours'] else ('New' if row['Previous Hours'] == 'N/A' else 'No'),
        axis=1
    )
    
    # Reorder columns for final display
    return current_df[['theater_name', 'Date', 'Previous Hours', 'Changed', 'Current Hours']].rename(columns={'theater_name': 'Theater'})

def render_theater_analysis(markets_data, cache_data): # noqa: C901
    """
    Renders a streamlined, top-down analysis workflow for theater-centric data.
    This major refactor simplifies the UI and data fetching logic.
    """
    df = pd.DataFrame()
    # --- NEW: Add market data for market-level comparisons ---
    theater_to_market_map = {} # This map is now used by multiple sections
    if cache_data and "markets" in cache_data:
        for market_name, market_info in cache_data["markets"].items():
            for theater in market_info.get("theaters", []):
                theater_to_market_map[theater['name']] = market_name

    # --- 1. DEFINE SCOPE ---
    st.subheader("Step 2: Define Scope")
    selected_company = st.session_state.selected_company

    # Director Selection
    st.write("1. Select Director")
    director_options = list(markets_data.get(selected_company, {}).keys())
    director_cols = st.columns(len(director_options))
    for i, director in enumerate(director_options):
        is_selected = st.session_state.get('analysis_director_select') == director
        if director_cols[i].button(director, key=f"analysis_director_{director}", use_container_width=True, type="primary" if is_selected else "secondary"):
            st.session_state.analysis_director_select = director if not is_selected else None
            # Clear downstream selections
            st.session_state.analysis_market_select = None
            st.session_state.analysis_theaters = []
            st.rerun()
    selected_director = st.session_state.get('analysis_director_select')

    # Market Selection
    if selected_director:
        st.write("2. Select Market")
        market_options = ["All Markets"] + list(markets_data.get(selected_company, {}).get(selected_director, {}).keys())
        market_cols = st.columns(min(len(market_options), 5))
        for i, market in enumerate(market_options):
            is_selected = st.session_state.get('analysis_market_select') == market
            if market_cols[i % 5].button(market, key=f"analysis_market_{market}", use_container_width=True, type="primary" if is_selected else "secondary"):
                st.session_state.analysis_market_select = market if not is_selected else None
                st.session_state.analysis_theaters = [] # Clear theater selection
                st.rerun()
    selected_market = st.session_state.get('analysis_market_select')

    # --- NEW: Competitor Analysis Filters ---
    if selected_market and selected_market != "All Markets" and st.session_state.analysis_data_type == "Prices":
        st.divider()
        st.subheader("Competitor Analysis Filter")
        
        # Get all unique companies within the selected market
        director_markets = markets_data.get(selected_company, {}).get(selected_director, {})
        # --- FIX: Import the utility function needed for company extraction ---
        from app.utils import _extract_company_name

        markets_to_scan = director_markets if selected_market == "All Markets" else {selected_market: director_markets.get(selected_market, {})}
        theaters_in_scope = []
        for market_name, market_info in markets_to_scan.items():
            theaters_in_scope.extend(cache_data.get("markets", {}).get(market_name, {}).get("theaters", []))
        
        all_companies_in_market = sorted(list(set(_extract_company_name(t.get('company', t['name'])) for t in theaters_in_scope)))

        def render_company_selection_buttons(title, options, session_state_key, num_cols=4):
            """Helper function to render a grid of company selection buttons."""
            st.write(f"**{title}**")
            
            if session_state_key not in st.session_state or not isinstance(st.session_state.get(session_state_key), list):
                st.session_state[session_state_key] = []
            selected_companies = st.session_state[session_state_key]

            # Select/Deselect All button
            all_selected = set(selected_companies) == set(options)
            select_all_label = f"Deselect All" if all_selected else f"Select All"
            if st.button(select_all_label, key=f"select_all_{session_state_key}", use_container_width=True):
                st.session_state[session_state_key] = [] if all_selected else options
                st.rerun()

            # Company buttons
            cols = st.columns(num_cols)
            for i, company in enumerate(options):
                is_selected = company in selected_companies
                if cols[i % num_cols].button(company, key=f"btn_{session_state_key}_{company}", type="primary" if is_selected else "secondary", use_container_width=True):
                    if is_selected:
                        st.session_state[session_state_key].remove(company)
                    else:
                        st.session_state[session_state_key].append(company)
                    st.rerun()

        # Render the two selection areas
        focus_col, competitor_col = st.columns(2)
        with focus_col:
            render_company_selection_buttons("Select Your Company/Focus Theaters", all_companies_in_market, 'analysis_focus_companies')
        with competitor_col:
            render_company_selection_buttons("Select Competitor Theaters", all_companies_in_market, 'analysis_competitor_companies')

    # Theater Selection
    theater_options = []
    if selected_director and selected_market:
        director_markets = markets_data.get(selected_company, {}).get(selected_director, {})
        # Adjust markets_to_scan to handle "All Theaters" correctly
        if selected_market == "All Markets":
            markets_to_scan = director_markets
        else:
            markets_to_scan = {selected_market: director_markets.get(selected_market, {})}
        for market_name, market_info in markets_to_scan.items():
            theaters_in_market = cache_data.get("markets", {}).get(market_name, {}).get("theaters", [])
            # --- FIX: Extend with the full theater object, not just the name string ---
            theater_options.extend(theaters_in_market)
    
    if selected_market:
        st.write("3. Select Theaters")
        scope_cols = st.columns([3, 1]) # Column for multiselect, column for button
        with scope_cols[0]:
            # Use a dictionary to get unique theaters by name, then get the names for the multiselect
            unique_theater_options_by_name = {t['name']: t for t in theater_options}
            unique_theater_options = sorted(unique_theater_options_by_name.keys())
            selected_theaters = st.multiselect(
                "Theaters", unique_theater_options, default=st.session_state.get('analysis_theaters', []), key="analysis_theaters_widget", label_visibility="collapsed"
            )
            st.session_state.analysis_theaters = selected_theaters
        with scope_cols[1]:
            if unique_theater_options:
                all_selected = set(selected_theaters) == set(unique_theater_options)
                button_label = "Deselect All" if all_selected else "Select All"
                if st.button(button_label, key="analysis_select_all_theaters_btn", use_container_width=True):
                    if all_selected:
                        st.session_state.analysis_theaters = []
                    else:
                        st.session_state.analysis_theaters = unique_theater_options
                    st.rerun()

    # --- DEFINE DATE RANGE & PRE-FILTERS ---
    st.subheader("Step 3: Define Date Range & Filters")
    date_cols = st.columns(2)
    today = datetime.date.today()
    default_start = st.session_state.get('analysis_date_range_start', today - datetime.timedelta(days=7))
    default_end = st.session_state.get('analysis_date_range_end', today)
    
    selected_range = date_cols[0].date_input(
        "Select a date range for analysis",
        value=(default_start, default_end),
        key="analysis_date_range_widget"
    )
    if selected_range and len(selected_range) == 2:
        st.session_state.analysis_date_range = selected_range

    # --- REFACTORED: Market At a Glance Report v2 ---
    if selected_market and selected_market != "All Markets":
        st.divider()
        st.subheader(f"Market At a Glance: {selected_market}")

        theaters_in_market_objects = [t for t in theater_options if isinstance(t, dict)]
        
        # --- NEW: Use the selected date range for the glance report ---
        start_date, end_date = st.session_state.analysis_date_range

        with st.spinner(f"Generating 'At a Glance' report for {selected_market}... This may take a moment."):
            selected_films = st.session_state.get('analysis_films_pre_filter', [])
            report_data, latest_scrape_date = database.get_market_at_a_glance_data([t['name'] for t in theaters_in_market_objects], start_date, end_date, films=selected_films)
            
            # --- NEW: Data Freshness Check ---
            if latest_scrape_date:
                days_since_scrape = (datetime.date.today() - latest_scrape_date).days
                if days_since_scrape > 7:
                    st.warning(f"Data for this market may be outdated. Last scrape was {days_since_scrape} days ago.")
                    if st.button("Scrape This Market Now", key="glance_scrape_now"):
                        # Pre-fill Market Mode state for a quick scrape
                        st.session_state.search_mode = "Market Mode"
                        st.session_state.selected_region = selected_director
                        st.session_state.selected_market = selected_market
                        st.session_state.theaters = theater_options
                        st.session_state.selected_theaters = [t['name'] for t in theaters_in_market_objects]
                        st.session_state.stage = 'theaters_listed'
                        st.rerun()

            if report_data.empty:
                st.info("No pricing data from the last 3 weeks found for this market.")
            else:
                # Define the core ticket types and dayparts we care about
                core_dayparts = ['Matinee', 'Prime', 'Twilight', 'Late Night']
                core_tickets = ['Adult', 'Senior', 'Child']
                other_tickets = ['Student', 'Military']

                # --- NEW: Add company info to the report data ---
                from app.utils import _extract_company_name
                theater_to_company_map = {t['name']: _extract_company_name(t.get('company', t['name'])) for t in theaters_in_market_objects}
                report_data['company'] = report_data['theater_name'].map(theater_to_company_map)

                # --- NEW: Apply Competitor Filter if active ---
                focus_companies = st.session_state.get('analysis_focus_companies', [])
                competitor_companies = st.session_state.get('analysis_competitor_companies', [])
                if focus_companies or competitor_companies:
                    companies_to_show = set(focus_companies + competitor_companies)
                    report_data = report_data[report_data['company'].isin(companies_to_show)]

                # --- Data Processing ---
                # --- FIX: Create a more descriptive 'ticket_type_plf' column using the format ---
                def create_plf_ticket_type(row):
                    if row['is_plf'] and row['format']:
                        # Extract the PLF format (anything not '2D' or '3D')
                        formats = {f.strip() for f in row['format'].split(',')}
                        plf_formats = formats - {'2D', '3D'}
                        if plf_formats:
                            # Use the first (and likely only) PLF format found
                            return f"{row['ticket_type']} ({sorted(list(plf_formats))[0]})"
                    return row['ticket_type']
                report_data['ticket_type_plf'] = report_data.apply(create_plf_ticket_type, axis=1)

                # --- REFACTORED: Aggregate all unique prices instead of min/max ---
                # --- FIX: Group by format as well to associate prices with their amenities ---
                summary_per_film = report_data.groupby(['company', 'theater_name', 'film_title', 'ticket_type', 'format', 'daypart']).agg(
                    all_prices=('price', lambda x: sorted(list(x.unique()))), # Get unique prices for this exact combo
                    example_film=('film_title', lambda x: x.iloc[0]),
                    release_date=('release_date', 'first') # Get the release date for context
                ).reset_index()

                def create_price_string(group):
                    """Creates a descriptive price string that includes format and film title."""
                    price_format_pairs = set()
                    for _, row in group.iterrows():
                        for price in row['all_prices']:
                            price_str = f"${price:.2f}"
                            format_label = f" ({row['format']})" if row['format'] and row['format'] != '2D' else ""
                            # --- NEW: Add film title to the label ---
                            film_label = row.get('film_title', 'Unknown Film')
                            full_label = f"{price_str}{format_label} ({film_label})"
                            price_format_pairs.add((price, full_label))
                    
                    # Sort by price, then return the unique, sorted strings for a clean output
                    return " | ".join([pair[1] for pair in sorted(list(price_format_pairs))])

                # --- REFACTORED: Group by film title to create price strings per film ---
                final_summary = summary_per_film.groupby(['company', 'theater_name', 'ticket_type', 'daypart', 'film_title']).apply(create_price_string).reset_index(name='Price')
                final_summary = pd.merge(final_summary, summary_per_film.groupby(['company', 'theater_name', 'ticket_type', 'daypart', 'film_title']).agg(
                    example_film=('example_film', 'first'),
                    release_date=('release_date', 'first')).reset_index(), on=['company', 'theater_name', 'ticket_type', 'daypart'])


                # --- Build the Structured Report ---
                st.subheader("Core Pricing Report (Adult, Senior, Child)")
                st.info("This table shows the primary ticket prices for Matinee (before 4pm) and Evening (4pm and after).")
                
                # Combine evening dayparts for the report
                final_summary['report_daypart'] = final_summary['daypart'].apply(lambda d: 'Matinee' if d == 'Matinee' else 'Evening')

                # Filter based on the original ticket type
                core_df = final_summary[final_summary['ticket_type'].isin(core_tickets)]
                
                if not core_df.empty:
                    core_pivot = core_df.pivot_table(
                        index=['company', 'theater_name'], # Add company to the index
                        columns=['report_daypart', 'ticket_type'],
                        values='Price',
                        # --- REFACTORED: Join the detailed price strings from the create_price_string function ---
                        aggfunc=lambda x: ' | '.join(sorted(x.dropna().unique()))
                    ).fillna('N/A')
                    
                    # Reorder columns for readability
                    desired_order = []
                    for daypart in ['Matinee', 'Evening']:
                        for t_type in ['Adult', 'Senior', 'Child']:
                            desired_order.append((daypart, t_type))
                    
                    # Filter to only columns that actually exist in the pivot table
                    final_order = [col for col in desired_order if col in core_pivot.columns]
                    st.dataframe(core_pivot[final_order], use_container_width=True)
                else:
                    st.info("No core pricing data (Adult, Senior, Child) found.")

                # --- Display Other Ticket Types ---
                other_df = final_summary[~final_summary['ticket_type'].isin(core_tickets)]
                if not other_df.empty:
                    st.subheader("Other Ticket Prices (Student, Military, Events, etc.)")
                    other_pivot = other_df.pivot_table(
                        index=['company', 'theater_name', 'ticket_type'], # Add company to the index
                        columns='daypart',
                        values='Price',
                        aggfunc=lambda x: ' | '.join(sorted(x.dropna().unique()))
                    ).fillna('')
                    st.dataframe(other_pivot, use_container_width=True)

                # --- Display Surcharge Details ---
                surcharge_df = final_summary[final_summary['Price'].str.contains('|', regex=False)]
                if not surcharge_df.empty:
                    with st.expander("View Potential Surcharge Pricing Details"):
                        st.warning("The following ticket types have multiple prices within the same daypart, which may indicate surcharge pricing for specific films or formats.")
                        
                        # --- NEW: Add context about opening week pricing ---
                        def surcharge_context(row):
                            if pd.notna(row.get('release_date')):
                                try:
                                    release_dt = pd.to_datetime(row['release_date']).date()
                                    if (datetime.date.today() - release_dt).days <= 14:
                                        return "Recent Release (likely opening week pricing)"
                                except (ValueError, TypeError):
                                    pass
                            return "Standard Film"
                        surcharge_df_display = surcharge_df.copy()
                        surcharge_df_display['Context'] = surcharge_df_display.apply(surcharge_context, axis=1)

                        st.dataframe(
                            surcharge_df_display[['theater_name', 'ticket_type', 'daypart', 'Price', 'example_film', 'Context']].rename(columns={
                                'theater_name': 'Theater', 'ticket_type': 'Ticket Type', 'daypart': 'Daypart', 'example_film': 'Example Film'
                            }),
                            use_container_width=True, hide_index=True
                        )

    # --- DEFINE DATE RANGE & PRE-FILTERS ---
    # Pre-Query Filters (Genre, Rating)
    if st.session_state.analysis_data_type in ["Prices", "Showtimes"]:
        with date_cols[1]:
            all_genres = database.get_all_unique_genres()
            # --- NEW: Add Film Filter ---
            # Get available films based on the selected theaters and date range.
            # This is a "pre-filter" that affects the main database query.
            available_films = []
            # --- FIX: Populate films based on selected theaters, not a pre-query ---
            if st.session_state.get('analysis_theaters'):
                # This is much faster as it queries only for the list of films.
                available_films = database.get_available_films(st.session_state.analysis_theaters)
            
            selected_films_pre_filter = st.multiselect("Filter by Film (optional)", options=available_films, key='analysis_films_pre_filter')

    # --- GENERATE REPORT ---
    st.subheader("Step 4: Generate Report")
    selected_theaters = st.session_state.get('analysis_theaters', [])
    if st.button("📊 Generate Report", type="primary", use_container_width=True, disabled=not selected_theaters):
        data_type = st.session_state.analysis_data_type
        theaters = st.session_state.analysis_theaters
        start_date, end_date = st.session_state.analysis_date_range

        with st.spinner("Querying historical data..."):
            if data_type == "Operating Hours":
                df = _generate_operating_hours_report(theaters, start_date, end_date)
            elif data_type in ["Prices", "Showtimes"]: # --- MODIFIED: Pass film filter to query ---
                # --- REMOVED: Genre and Rating filters ---
                films = st.session_state.get('analysis_films_pre_filter', [])
                df = database.query_historical_data(start_date, end_date, theaters=theaters, films=films)
            else: # Should not happen
                df = pd.DataFrame()

        st.session_state.analysis_report_df = df
        # Reset post-report filters
        st.session_state.analysis_film_filter = []
        st.session_state.analysis_daypart_filter = []
        st.session_state.analysis_format_filter = []
        st.session_state.analysis_ticket_type_filter = []
        st.session_state.analysis_capacity_filter = []
        st.rerun()

    if not st.session_state.analysis_report_df.empty:
        df = st.session_state.analysis_report_df
        
        # --- NEW: "At a Glance" Summary for the initial, unfiltered report ---
        if not st.session_state.get('analysis_filters_applied'):
            st.subheader("Scope Summary: At a Glance")
            start_date, end_date = st.session_state.analysis_date_range
            summary_df = database.get_theater_comparison_summary(st.session_state.analysis_theaters, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            if not summary_df.empty:
                summary_df['Overall Avg. Price'] = pd.to_numeric(summary_df['Overall Avg. Price'], errors='coerce')
                # --- REFACTORED: Use st.data_editor for better display and sorting ---
                st.data_editor(
                    summary_df.rename(columns={'theater_name': 'Theater Name'}),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Overall Avg. Price": st.column_config.NumberColumn(format="$%.2f")
                    },
                    disabled=True # Make it read-only
                )
            else:
                st.info("Not enough data to generate a comparison summary for this scope.")
            st.divider()

        # --- NEW: Add market data for market-level comparisons ---
        theater_to_market_map = {} # This map is now used by multiple sections
        if cache_data and "markets" in cache_data:
            for market_name, market_info in cache_data["markets"].items():
                for theater in market_info.get("theaters", []):
                    theater_to_market_map[theater['name']] = market_name
        
        if 'theater_name' in df.columns:
            df['market'] = df['theater_name'].map(theater_to_market_map).fillna('Unknown')

        # --- Add Filters ---
        if 'film_title' in df.columns:
            st.subheader("Post-Report Filters")
            all_films = sorted(df['film_title'].unique())
            all_dayparts = sorted(df['daypart'].dropna().unique()) if 'daypart' in df.columns else []
            
            # --- NEW: Get individual formats for multi-select ---
            all_formats_combined = df['format'].dropna().unique()
            all_individual_formats = sorted(list(set(f.strip() for format_string in all_formats_combined for f in format_string.split(','))))

            all_ticket_types = sorted(df['ticket_type'].dropna().unique()) if 'ticket_type' in df.columns else []
            all_capacities = sorted(df['capacity'].dropna().unique()) if 'capacity' in df.columns else []

            # --- Initialize filters if they don't exist ---
            if not st.session_state.get('analysis_film_filter'): st.session_state.analysis_film_filter = all_films
            if not st.session_state.get('analysis_daypart_filter'): st.session_state.analysis_daypart_filter = all_dayparts
            if not st.session_state.get('analysis_format_filter'): st.session_state.analysis_format_filter = all_individual_formats
            if not st.session_state.get('analysis_ticket_type_filter'): st.session_state.analysis_ticket_type_filter = all_ticket_types
            if not st.session_state.get('analysis_capacity_filter'): st.session_state.analysis_capacity_filter = all_capacities

            filter_cols = st.columns(4)

            with filter_cols[0]:
                selected_films = st.multiselect(
                    "Filter by Film:",
                    options=all_films,
                    default=st.session_state.analysis_film_filter
                )
                st.session_state['analysis_film_filter'] = selected_films
            
            with filter_cols[1]:
                if all_dayparts:
                    selected_dayparts = st.multiselect(
                        "Filter by Daypart:",
                        options=all_dayparts,
                        default=st.session_state.analysis_daypart_filter
                    )
                    st.session_state['analysis_daypart_filter'] = selected_dayparts
            
            with filter_cols[2]:
                if all_individual_formats:
                    selected_formats = st.multiselect(
                        "Filter by Format:",
                        options=all_individual_formats,
                        default=st.session_state.analysis_format_filter
                    )
                    st.session_state['analysis_format_filter'] = selected_formats
            
            with filter_cols[3]:
                if all_ticket_types:
                    selected_ticket_types = st.multiselect(
                        "Filter by Ticket Type:",
                        options=all_ticket_types,
                        default=st.session_state.analysis_ticket_type_filter
                    )
                    st.session_state['analysis_ticket_type_filter'] = selected_ticket_types
            
            with st.expander("More Filters..."):
                if all_capacities:
                    selected_capacities = st.multiselect(
                        "Sold Out?:",
                        options=all_capacities,
                        default=st.session_state.analysis_capacity_filter
                    )
                    st.session_state['analysis_capacity_filter'] = selected_capacities

            # --- NEW: Track if filters have been applied ---
            st.session_state.analysis_filters_applied = True

            # Apply the filter for display
            df = df[df['film_title'].isin(selected_films)]
            if all_dayparts and st.session_state.analysis_daypart_filter:
                df = df[df['daypart'].isin(st.session_state.analysis_daypart_filter)]
            
            # --- NEW: Apply format filter with partial string matching ---
            if all_individual_formats and st.session_state.analysis_format_filter:
                pattern = '|'.join([re.escape(f) for f in st.session_state.analysis_format_filter])
                df = df[df['format'].str.contains(pattern, na=False)]

            if all_ticket_types and st.session_state.analysis_ticket_type_filter:
                df = df[df['ticket_type'].isin(st.session_state.analysis_ticket_type_filter)]
            if all_capacities and st.session_state.analysis_capacity_filter:
                df = df[df['capacity'].isin(st.session_state.analysis_capacity_filter)]

        st.subheader("Detailed Report")

        # --- NEW: Summary Statistics ---
        if st.session_state.analysis_data_type in ["Prices", "Showtimes"] and not df.empty:
            st.markdown("---")
            st.subheader("Summary Statistics (for filtered data)")
            
            # Calculate stats from the filtered dataframe
            total_showings = len(df.drop_duplicates(subset=['play_date', 'theater_name', 'film_title', 'showtime']))
            num_films = df['film_title'].nunique() if 'film_title' in df.columns else 0
            
            # Handle cases where 'price' column might not exist or be all NaN
            avg_price = 0
            min_price = 0
            max_price = 0
            if 'price' in df.columns and not df['price'].dropna().empty:
                avg_price = df['price'].mean()
                min_price = df['price'].min()
                max_price = df['price'].max()

            # Display metrics
            stat_cols = st.columns(4)
            stat_cols[0].metric("Total Showings", f"{total_showings:,}")
            stat_cols[1].metric("Unique Films", f"{num_films}")
            stat_cols[2].metric("Average Price", f"${avg_price:,.2f}")
            
            if min_price == max_price:
                stat_cols[3].metric("Price", f"${min_price:,.2f}")
            else:
                stat_cols[3].metric("Price Range", f"${min_price:,.2f} - ${max_price:,.2f}")
            st.markdown("---")

        # --- Prepare DataFrame for display ---
        df_display = df.copy()

        # --- Logic to find and highlight surcharge pricing ---
        # --- FIX: This logic should only run for "Prices" reports. It was incorrectly filtering other report types. ---
        surcharge_indices = pd.Index([])
        if st.session_state.get('analysis_data_type') == "Prices":
            grouping_keys = ['play_date', 'theater_name', 'ticket_type', 'daypart']
            # Ensure price column exists and is numeric before proceeding
            if 'price' in df_display.columns and pd.api.types.is_numeric_dtype(df_display['price']):
                # Drop rows where price is NaN for accurate grouping
                df_for_logic = df_display.dropna(subset=['price'])
                # Check if all grouping keys exist in the dataframe columns
                if not df_for_logic.empty and all(key in df_for_logic.columns for key in ['play_date', 'theater_name', 'ticket_type', 'daypart']):
                    surcharge_groups = df_for_logic.groupby(grouping_keys).filter(lambda x: x['price'].nunique() > 1)
                    if not surcharge_groups.empty:
                        surcharge_indices = surcharge_groups.index
        
        def highlight_surcharge_rows(row):
            """Applies a highlight color to rows identified as having surcharge pricing."""
            color = '#fff3cd' if row.name in surcharge_indices else '' # A light yellow
            return [f'background-color: {color}'] * len(row)

        # Format column headers: replace underscores and capitalize
        df_display.columns = [col.replace('_', ' ').title() for col in df_display.columns]
        # Reorder columns to make 'Play Date' the first column
        if 'Play Date' in df_display.columns:
            cols = df_display.columns.tolist()
            cols.insert(0, cols.pop(cols.index('Play Date')))
            df_display = df_display[cols]

        column_config = {
            "Play Date": st.column_config.DateColumn(
                "Date",
                format="YYYY-MM-DD",
            ),
            "Showtime": st.column_config.TextColumn(
                width="small"
            ),
            "Daypart": st.column_config.TextColumn(
                width="small"
            ),
            "Format": st.column_config.TextColumn(
                width="small"
            ),
            "Price": st.column_config.NumberColumn(
                format="$%.2f",
                width="small"
            ),
            "Ticket Type": st.column_config.TextColumn(
                width="medium"
            ),
            "Capacity": st.column_config.TextColumn(
                "Sold Out?",
                width="small"
            )
        }

        # --- FIX: Removed custom styling that caused poor contrast ---
        st.dataframe(df_display, use_container_width=True, hide_index=True, column_config=column_config)

    # --- NEW: Film Showtime Comparison ---
    # This section now appears after the main data table
    if len(st.session_state.get('analysis_film_filter', [])) == 1 and len(st.session_state.analysis_theaters) > 1 and not df.empty:
        st.divider()
        selected_film = st.session_state.analysis_film_filter[0]
        st.subheader(f"Showtime Schedule Comparison for '{selected_film}'")
        st.info("This section compares the showtime strategy for the selected film across the chosen theaters.")

        # 1. Prepare data for comparison table
        comparison_data = []
        # df is already filtered to the selected film
        # We need to drop duplicates based on the full showing signature to get accurate counts
        unique_showings = df.drop_duplicates(subset=['play_date', 'theater_name', 'film_title', 'showtime', 'format'])

        for theater_name, group in unique_showings.groupby('theater_name'):
            try:
                # Get unique showtimes for this theater
                showtimes_str = group['showtime'].unique()
                showtimes = sorted([datetime.datetime.strptime(normalize_time_string(t), "%I:%M%p").time() for t in showtimes_str])
                if not showtimes:
                    continue
                
                first_showing = min(showtimes)
                last_showing = max(showtimes)
                
                first_dt = datetime.datetime.combine(datetime.date.today(), first_showing)
                last_dt = datetime.datetime.combine(datetime.date.today(), last_showing)
                spread_hours = (last_dt - first_dt).total_seconds() / 3600
                
                comparison_data.append({
                    "Theater": theater_name,
                    "Showings": len(showtimes),
                    "First Showing": first_showing.strftime("%I:%M %p").lstrip('0'),
                    "Last Showing": last_showing.strftime("%I:%M %p").lstrip('0'),
                    "Spread (hrs)": f"{spread_hours:.1f}"
                })
            except (ValueError, TypeError) as e:
                st.warning(f"Could not process showtimes for {theater_name}: {e}")

        if comparison_data:
            # 2. Display summary table
            summary_df = pd.DataFrame(comparison_data).sort_values(by="First Showing")
            st.dataframe(summary_df, use_container_width=True, hide_index=True)

            # 3. Display visual chart
            chart_df = unique_showings[['theater_name', 'showtime', 'format']].copy()
            chart_df['Showtime_DT'] = chart_df['showtime'].apply(lambda x: datetime.datetime.strptime(normalize_time_string(x), "%I:%M%p"))
            
            chart = alt.Chart(chart_df).mark_circle(size=100, opacity=0.8).encode(
                x=alt.X('hoursminutes(Showtime_DT):T', title='Time of Day', axis=alt.Axis(format='%I:%M %p')),
                y=alt.Y('theater_name:N', title='Theater', sort=alt.SortField(field="Showtime_DT", op="min", order="ascending")),
                color=alt.Color('format:N', title="Format"),
                tooltip=['theater_name', alt.Tooltip('hoursminutes(Showtime_DT):T', format='%I:%M %p'), 'format']
            ).interactive().properties(title=f"Showtime Distribution for '{selected_film}'")
            st.altair_chart(chart, use_container_width=True)

    # --- NEW: Smart suggestion if no data is found ---
    elif st.session_state.get('analysis_theaters') and st.session_state.get('analysis_date_range'):
        st.warning("No data found for the selected criteria.")

        # --- FIX for UnboundLocalError ---
        # Initialize an empty DataFrame to prevent errors in the charting section below.
        df_for_charts_unfiltered = pd.DataFrame()

        st.info("This often means no scrapes have been run for these theaters on these dates.")
        
        if st.button("Go to Market Mode to Scrape This Data"):
            # Pre-populate Market Mode state to make it easy for the user
            st.session_state.search_mode = "Market Mode"
            st.session_state.selected_theaters = st.session_state.analysis_theaters
            st.session_state.market_date_range = st.session_state.analysis_date_range
            # We need to find the director/market for the selected theaters to set the context
            # This is a simplification; for now, we just switch modes.
            st.session_state.stage = 'theaters_listed'
            st.rerun()

        # --- Charting Section ---
        st.divider()
        st.subheader("Visual Analysis")

        # --- NEW: Grouping logic for Market vs. Theater comparison ---
        group_by_charts = st.radio(
            "Group charts by:",
            ("Theater", "Market"),
            horizontal=True,
            key="analysis_group_by",
            help="Choose to view charts aggregated by individual theater or by market."
        )
        grouping_column = 'theater_name' if group_by_charts == "Theater" else 'market'


        if group_by_charts == "Market" and 'market' in df_for_charts_unfiltered.columns:
            available_groups = sorted(df_for_charts_unfiltered['market'].unique())
            default_groups = available_groups[:5]
            label = "Compare Markets in Charts"
        else: # group_by_charts == "Theater"
            available_groups = st.session_state.analysis_theaters
            default_groups = available_groups[:5]
            label = "Compare Theaters in Charts"

        if len(available_groups) > 1:
            st.info(f"Use the selector below to choose which {group_by_charts.lower()}s to include in the charts.")
            selected_groups = st.multiselect(
                label,
                options=available_groups,
                default=default_groups
            )
        else:
            selected_groups = available_groups

        # --- FIX: Handle different column names from different report types ---
        df_for_charts = pd.DataFrame()
        if 'theater_name' in df.columns:
            df_for_charts = df_for_charts_unfiltered[df_for_charts_unfiltered[grouping_column].isin(selected_groups)]
        elif 'Theater' in df.columns: # Fallback for Operating Hours report
            df_for_charts_unfiltered = df_for_charts_unfiltered.rename(columns={'Theater': 'theater_name'})
            grouping_column = 'theater_name'
            df_for_charts = df_for_charts_unfiltered[df_for_charts_unfiltered[grouping_column].isin(selected_groups)]


        # --- FIX: Only show charts relevant to the selected data type ---
        if st.session_state.analysis_data_type == "Prices" and 'price' in df_for_charts.columns and not df_for_charts.empty:
            st.subheader("Average Price by Film")
            try:
                avg_price_pivot = df_for_charts.pivot_table(index='film_title', columns=grouping_column, values='price', aggfunc='mean')
                st.bar_chart(avg_price_pivot)
            except Exception as e:
                st.error(f"Could not generate price chart: {e}")

        if st.session_state.analysis_data_type == "Prices" and 'price' in df_for_charts.columns and 'play_date' in df_for_charts.columns and not df_for_charts.empty:
            df_copy = df_for_charts.copy()
            df_copy['date'] = pd.to_datetime(df_copy['play_date']).dt.date
            
            if df_copy['date'].nunique() > 1:
                st.subheader("Price Trend Over Time")
                try:
                    trend_df = df_copy.groupby(['date', grouping_column])['price'].mean().unstack()
                    st.line_chart(trend_df)
                except Exception as e:
                    st.error(f"Could not generate price trend chart: {e}")

        # --- Showtime Analysis Charts ---
        if st.session_state.analysis_data_type in ["Prices", "Showtimes"] and 'daypart' in df_for_charts.columns and 'play_date' in df_for_charts.columns and not df_for_charts.empty:
            
            # Create a copy and get unique showtimes for accurate counting
            df_for_showtime_analysis = df_for_charts.copy()
            df_for_showtime_analysis['date'] = pd.to_datetime(df_for_showtime_analysis['play_date']).dt.date
            unique_showtimes_df = df_for_showtime_analysis.drop_duplicates(subset=['date', 'theater_name', 'film_title', 'showtime'])

            # Chart 1: Showtime Distribution by Daypart
            st.subheader("Showtime Distribution by Daypart")
            try:
                daypart_pivot = unique_showtimes_df.pivot_table(index='daypart', columns=grouping_column, values='showtime', aggfunc='count')
                st.bar_chart(daypart_pivot)
            except Exception as e:
                st.error(f"Could not generate daypart distribution chart: {e}")

            # Chart 2: Total Showtimes Per Day
            if unique_showtimes_df['date'].nunique() > 1:
                st.subheader("Total Showtimes Per Day")
                try:
                    showtimes_per_day = unique_showtimes_df.groupby(['date', grouping_column])['showtime'].count().unstack()
                    st.line_chart(showtimes_per_day)
                except Exception as e:
                    st.error(f"Could not generate showtimes per day chart: {e}")

        # Chart 3: Ticket Type Distribution
        if st.session_state.analysis_data_type == "Prices" and 'ticket_type' in df_for_charts.columns and not df_for_charts.empty:
            st.subheader("Ticket Type Distribution")
            try:
                ticket_type_pivot = df_for_charts.pivot_table(index='ticket_type', columns=grouping_column, values='price', aggfunc='count')
                st.bar_chart(ticket_type_pivot)
            except Exception as e:
                st.error(f"Could not generate ticket type distribution chart: {e}")
        
        # Chart 4: Format Distribution
        if st.session_state.analysis_data_type in ["Prices", "Showtimes"] and 'format' in df_for_charts.columns and not df_for_charts.empty:
            st.subheader("Format Distribution by Theater")
            try:
                # Get unique showings to avoid overcounting formats from different ticket types for the same showing
                unique_showings_for_format = df_for_charts.drop_duplicates(subset=['play_date', 'theater_name', 'film_title', 'showtime', 'format'])
                # Create a new DataFrame by exploding the formats
                exploded_formats = unique_showings_for_format.assign(format=unique_showings_for_format['format'].str.split(', ')).explode('format')
                # Now create a pivot table
                format_pivot = exploded_formats.pivot_table(index='format', columns=grouping_column, values='showtime', aggfunc='count', fill_value=0)
                st.bar_chart(format_pivot)
            except Exception as e:
                st.error(f"Could not generate format distribution chart: {e}")
        
        # Chart 5: Aggregate Format Distribution (Pie Chart)
        if st.session_state.analysis_data_type in ["Prices", "Showtimes"] and 'format' in df_for_charts.columns and not df_for_charts.empty:
            st.subheader("Overall Format Distribution (All Selected Theaters)")
            try:
                # Reuse the exploded_formats DataFrame if it was created for the bar chart
                if 'exploded_formats' not in locals():
                    unique_showings_for_format = df_for_charts.drop_duplicates(subset=['play_date', 'theater_name', 'film_title', 'showtime', 'format'])
                    exploded_formats = unique_showings_for_format.assign(format=unique_showings_for_format['format'].str.split(', ')).explode('format')
                
                format_counts = exploded_formats['format'].value_counts().reset_index()
                format_counts.columns = ['format', 'count']

                pie_chart = alt.Chart(format_counts).mark_arc(innerRadius=50).encode(
                    theta=alt.Theta(field="count", type="quantitative"),
                    color=alt.Color(field="format", type="nominal", title="Format"),
                    tooltip=['format', 'count']
                ).properties(title='Overall Format Distribution')
                st.altair_chart(pie_chart, use_container_width=True)
            except Exception as e:
                st.error(f"Could not generate format pie chart: {e}")

def render_analysis_mode(markets_data, cache_data):
    st.header("🗂️ Historical Data and Analysis")
    st.info("Analyze and visualize historical pricing, showtime, and operating hours data collected from your scrapes.")

    # Initialize session state variables for this mode
    if 'analysis_data_type' not in st.session_state: st.session_state.analysis_data_type = None
    if 'analysis_theaters' not in st.session_state: st.session_state.analysis_theaters = []
    if 'analysis_date_range' not in st.session_state: st.session_state.analysis_date_range = ()
    if 'analysis_report_df' not in st.session_state: st.session_state.analysis_report_df = pd.DataFrame()
    if 'analysis_film_filter' not in st.session_state: st.session_state.analysis_film_filter = []
    if 'analysis_daypart_filter' not in st.session_state: st.session_state.analysis_daypart_filter = []
    if 'analysis_format_filter' not in st.session_state: st.session_state.analysis_format_filter = []
    if 'analysis_ticket_type_filter' not in st.session_state: st.session_state.analysis_ticket_type_filter = []
    if 'analysis_capacity_filter' not in st.session_state: st.session_state.analysis_capacity_filter = []
    # New state for film analysis
    if 'film_summary_df' not in st.session_state: st.session_state.film_summary_df = pd.DataFrame()
    if 'film_detail_data' not in st.session_state: st.session_state.film_detail_data = pd.DataFrame()
    if 'film_analysis_genres' not in st.session_state: st.session_state.film_analysis_genres = []
    if 'analysis_director_select' not in st.session_state: st.session_state.analysis_director_select = None
    if 'analysis_market_select' not in st.session_state: st.session_state.analysis_market_select = None

    if 'analysis_genres' not in st.session_state: st.session_state.analysis_genres = []
    if 'analysis_ratings' not in st.session_state: st.session_state.analysis_ratings = []
    # Step 1: Select Data Type
    st.subheader("Step 1: Select Data Type")
    cols = st.columns(4)
    data_types = ["Film", "Showtimes", "Prices", "Operating Hours"]
    for i, dt in enumerate(data_types):
        if cols[i].button(dt, key=f"data_type_{dt}", use_container_width=True, type="primary" if st.session_state.get('analysis_data_type') == dt else "secondary"):
            # Reset state when changing data type
            st.session_state['analysis_data_type'] = dt
            st.session_state['analysis_theaters'] = []
            st.session_state['analysis_date_range'] = ()
            st.session_state['analysis_report_df'] = pd.DataFrame()
            st.session_state['analysis_film_filter'] = []
            st.session_state['analysis_daypart_filter'] = []
            st.session_state['analysis_format_filter'] = []
            st.session_state['analysis_ticket_type_filter'] = []
            st.session_state['analysis_capacity_filter'] = []
            st.session_state['film_summary_df'] = pd.DataFrame()
            st.session_state['film_detail_data'] = pd.DataFrame()
            st.session_state['analysis_genres'] = []
            st.session_state['analysis_ratings'] = []
            st.rerun()

    if st.session_state.get('analysis_data_type') == "Film":
        render_film_analysis(cache_data)
    elif st.session_state.get('analysis_data_type'):
        render_theater_analysis(markets_data, cache_data)
    else:
        st.info("Select a data type to begin analysis.")