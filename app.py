# app.py - The Streamlit User Interface (FINAL PRODUCTION VERSION)

import streamlit as st
import pandas as pd
import subprocess
import sys
import os
import datetime

st.set_page_config(layout="wide", page_title="PriceScout")
st.title('🎬 PriceScout: Competitive Pricing Tool')

st.info("""
**How to use:**
1.  Select the date you want to scrape for.
2.  Click the "Generate Live Pricing Report" button.
3.  Please be patient. A process will run in the background for 1-2 minutes to gather live data.
""")

col1, col2 = st.columns(2)
with col1:
    zip_code = st.text_input('Enter ZIP Code for Live Scrape:', value="76107")
with col2:
    scrape_date = st.date_input(
        "Select Date to Scrape",
        datetime.date.today() + datetime.timedelta(days=1)
    )

if st.button('🚀 Generate Live Pricing Report'):
    scrape_date_str = scrape_date.strftime('%Y-%m-%d')
    with st.spinner(f"Running live scraper for {scrape_date_str}... This may take a few minutes."):
        command = [sys.executable, "scraper.py", scrape_date_str]
        result = subprocess.run(command, capture_output=True, text=True, check=False)

    st.subheader("Scraper Log")
    with st.expander("Click to see the full scraper log", expanded=True): # Log is now open by default
        # Using st.text_area to create a scrollable box for the log
        st.text_area("Log Output", result.stdout + "\n" + result.stderr, height=300)

    if os.path.exists('live_report.csv'):
        st.success("Live scrape complete! Loading report...")
        df = pd.read_csv('live_report.csv')
        st.subheader(f"Live Pricing Report for {scrape_date_str}")
        st.dataframe(df)
        st.balloons()
    else:
        st.error("The scraper ran, but it failed to produce a report file. Check the log above for details.")