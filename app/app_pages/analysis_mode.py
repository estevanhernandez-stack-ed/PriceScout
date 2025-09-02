import streamlit as st
import pandas as pd
import datetime
import traceback
from utils import to_csv, format_price_change
import database

def render():
    st.header("🗂️ Historical Analysis")

    try:
        with st.expander("📈 Advanced Trend Analysis", expanded=True):
            # Initialize session state variables
            if 'trend_theaters' not in st.session_state:
                st.session_state.trend_theaters = []
            if 'trend_films' not in st.session_state:
                st.session_state.trend_films = []
            if 'trend_dayparts' not in st.session_state:
                st.session_state.trend_dayparts = []

            all_theaters = database.get_unique_column_values('theater_name')
            if not all_theaters:
                st.info("No data available to analyze.")
            else:
                # --- Step 1: Select Theaters ---
                st.subheader("Step 1: Select Theaters")
                cols = st.columns(4)
                for i, theater in enumerate(all_theaters):
                    is_selected = theater in st.session_state.trend_theaters
                    if cols[i % 4].button(theater, key=f"trend_theater_{i}", type="primary" if is_selected else "secondary", use_container_width=True):
                        if is_selected: st.session_state.trend_theaters.remove(theater)
                        else: st.session_state.trend_theaters.append(theater)
                        # Clear dependent selections
                        st.session_state.trend_films = []
                        st.session_state.trend_dayparts = []
                        st.rerun()

                if st.session_state.trend_theaters:
                    st.divider()
                    
                    # --- Step 2: Select Date Range ---
                    st.subheader("Step 2: Select a Date Range for Analysis")
                    today = datetime.date.today()
                    seven_days_ago = today - datetime.timedelta(days=7)
                    c1, c2 = st.columns(2)
                    start_date = c1.date_input("Start Date", seven_days_ago, key='trend_start_date')
                    end_date = c2.date_input("End Date", today, key='trend_end_date')

                    # --- Step 3: Select Films (using buttons) ---
                    if start_date and end_date and start_date <= end_date:
                        all_dates_in_range = pd.date_range(start_date, end_date).strftime('%Y-%m-%d').tolist()
                        
                        st.subheader("Step 3: Select Films")
                        available_films = database.get_common_films_for_theaters_dates(st.session_state.trend_theaters, all_dates_in_range)
                        
                        if not available_films:
                            st.warning("No films are common to all selected theaters in this date range.")
                        else:
                            film_cols = st.columns(4)
                            for i, film in enumerate(available_films):
                                is_selected = film in st.session_state.trend_films
                                if film_cols[i % 4].button(film, key=f"trend_film_{i}", type="primary" if is_selected else "secondary", use_container_width=True):
                                    if is_selected: st.session_state.trend_films.remove(film)
                                    else: st.session_state.trend_films.append(film)
                                    st.rerun()
                        
                        # --- Step 4: Select Dayparts (using buttons) ---
                        if st.session_state.trend_films:
                            st.subheader("Step 4: Select Dayparts")
                            dayparts_options = ["Matinee", "Twilight", "Prime", "Late Night"]
                            daypart_cols = st.columns(len(dayparts_options))
                            for i, dp in enumerate(dayparts_options):
                                is_selected = dp in st.session_state.trend_dayparts
                                if daypart_cols[i].button(dp, key=f"trend_dp_{i}", type="primary" if is_selected else "secondary", use_container_width=True):
                                    if is_selected: st.session_state.trend_dayparts.remove(dp)
                                    else: st.session_state.trend_dayparts.append(dp)
                                    st.rerun()

                    # --- Step 5: Generate the Advanced Report ---
                    if st.session_state.trend_theaters and st.session_state.trend_films and st.session_state.trend_dayparts:
                        st.divider()
                        if st.button("🚀 Generate Advanced Report", type="primary", use_container_width=True):
                            with st.spinner("Performing advanced analysis..."):
                                raw_data = database.get_data_for_trend_report(
                                    st.session_state.trend_theaters,
                                    all_dates_in_range,
                                    st.session_state.trend_films,
                                    st.session_state.trend_dayparts
                                )
                                # (The rest of the logic remains the same)
                                if raw_data.empty:
                                    st.warning("No price data found for the combination of your selections.")
                                    if 'advanced_report_df' in st.session_state: del st.session_state['advanced_report_df']
                                else:
                                    raw_data['scrape_date'] = pd.to_datetime(raw_data['scrape_date'])
                                    raw_data['Day Type'] = raw_data['scrape_date'].dt.dayofweek.apply(lambda x: 'Weekend' if x >= 5 else 'Weekday')
                                    raw_data = raw_data.sort_values(by='scrape_date')
                                    raw_data['price_change'] = raw_data.groupby(['theater_name', 'film_title', 'ticket_type', 'daypart'])['price'].diff()
                                    def format_cell(row):
                                        price = f"${row['price']:.2f}"
                                        change = format_price_change(row['price_change'])
                                        if change == "$0.00" or change == "N/A": return price
                                        return f"{price} ({change})"
                                    raw_data['display_value'] = raw_data.apply(format_cell, axis=1)
                                    raw_data['scrape_date'] = raw_data['scrape_date'].dt.strftime('%Y-%m-%d')
                                    report_df = raw_data.pivot_table(index=['theater_name', 'film_title', 'Day Type', 'ticket_type', 'daypart'], columns='scrape_date', values='display_value', aggfunc='last').fillna('-')
                                    st.session_state.advanced_report_df = report_df.reset_index()


                                if raw_data.empty:
                                    st.warning("No price data found for the combination of your selections.")
                                    if 'advanced_report_df' in st.session_state:
                                        del st.session_state['advanced_report_df']
                                else:
                                    raw_data['scrape_date'] = pd.to_datetime(raw_data['scrape_date'])
                                    raw_data['Day Type'] = raw_data['scrape_date'].dt.dayofweek.apply(
                                        lambda x: 'Weekend' if x >= 5 else 'Weekday'  # Saturday=5, Sunday=6
                                    )
                                    raw_data = raw_data.sort_values(by='scrape_date')
                                    raw_data['price_change'] = raw_data.groupby(
                                        ['theater_name', 'film_title', 'ticket_type', 'daypart']
                                    )['price'].diff()
                                    
                                    def format_cell(row):
                                        price = f"${row['price']:.2f}"
                                        change = format_price_change(row['price_change'])
                                        if change == "$0.00" or change == "N/A":
                                            return price
                                        return f"{price} ({change})"

                                    raw_data['display_value'] = raw_data.apply(format_cell, axis=1)
                                    raw_data['scrape_date'] = raw_data['scrape_date'].dt.strftime('%Y-%m-%d')
                                    
                                    report_df = raw_data.pivot_table(
                                        index=['theater_name', 'film_title', 'Day Type', 'ticket_type', 'daypart'],
                                        columns='scrape_date',
                                        values='display_value',
                                        aggfunc='last'
                                    ).fillna('-')
                                    
                                    st.session_state.advanced_report_df = report_df.reset_index()

        # --- Display the final Advanced Report ---
        if 'advanced_report_df' in st.session_state:
            st.subheader("Advanced Trend Report")
            st.success("Report generated successfully!")
            df_to_show = st.session_state.advanced_report_df
            st.dataframe(df_to_show, use_container_width=True)
            st.download_button(
                label="📄 Download Advanced Report as CSV",
                data=to_csv(df_to_show),
                file_name='PriceScout_Advanced_Report.csv',
                mime='text/csv'
            )

    except Exception as e:
        st.error(f"An error occurred in the analysis tool: {e}")
        st.code(traceback.format_exc())