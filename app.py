# PriceScout PoC - Streamlit Application (app.py)
# FINAL VERSION - Using Synchronous Playwright API

import streamlit as st
from playwright.sync_api import sync_playwright  # <-- The biggest change is here
import pandas as pd
import re
import datetime
import json
import glob
import os
from bs4 import BeautifulSoup

# --- Helper Functions (No changes needed) ---
def clean_ticket_type(description: str) -> str:
    desc_lower = description.lower()
    if 'adult' in desc_lower: return 'Adult'
    if 'senior' in desc_lower: return 'Senior'
    if 'child' in desc_lower: return 'Child'
    if 'student' in desc_lower: return 'Student'
    return description.split('(')[0].strip()

def classify_daypart(showtime_str: str) -> str:
    try:
        normalized_time = showtime_str.lower().replace('p', 'PM').replace('a', 'AM')
        time_obj = datetime.datetime.strptime(normalized_time, "%I:%M%p").time()
        if time_obj < datetime.time(16, 0): return "Matinee"
        elif time_obj <= datetime.time(21, 0): return "Prime"
        else: return "Late Night"
    except ValueError: return "Unknown"

# --- Synchronous Scraper Functions ---
# Note: All 'async' and 'await' keywords have been removed.

def get_theaters_by_zip(zip_code: str, browser):
    target_url = f"https://www.fandango.com/{zip_code}_movietimes"
    page = browser.new_page()
    theaters = []
    try:
        page.goto(target_url, timeout=60000)
        page.wait_for_selector('li.fd-theater', timeout=15000)
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        for block in soup.select('li.fd-theater'):
            name_element = block.select_one('h3.fd-theater__name a')
            if name_element:
                name = name_element.get_text(strip=True)
                url = name_element.get('href')
                if url and url.startswith('/'): url = "https://www.fandango.com" + url
                theaters.append({'name': name, 'url': url})
    finally:
        page.close()
    return theaters

def get_all_showtimes_for_theater(theater_name: str, theater_url: str, browser):
    # This is also the real function, just made synchronous
    page = browser.new_page()
    film_set = set()
    try:
        page.goto(f"{theater_url}?format=all", timeout=60000)
        page.wait_for_selector('ul.thtr-mv-list', timeout=60000)
        html_content = page.content()
        soup = BeautifulSoup(html_content, 'html.parser')
        movie_panels = soup.select('li.thtr-mv-list__panel')
        for movie in movie_panels:
            title_element = movie.select_one('h2.thtr-mv-list__detail-title a')
            if title_element:
                film_set.add(title_element.get_text(strip=True))
    finally:
        page.close()
    return list(film_set)


# --- Main Application Logic ---

st.set_page_config(layout="wide", page_title="PriceScout PoC")
st.title('🎬 PriceScout PoC')

# Initialize session state
if 'theaters' not in st.session_state:
    st.session_state.theaters = []
if 'films' not in st.session_state:
    st.session_state.films = []

zip_code = st.text_input('Enter a 5-digit ZIP Code:', value="76107")

if st.button('Find Theaters & Movies'):
    if re.match(r'^\d{5}$', zip_code):
        with st.spinner(f"Searching for theaters and movies near {zip_code}..."):
            # This is now a simple, direct function call. No asyncio needed.
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                st.session_state.theaters = get_theaters_by_zip(zip_code, browser)
                
                all_films = set()
                if st.session_state.theaters:
                    # Limit to first 3 theaters for initial film search to be fast
                    for theater in st.session_state.theaters[:3]:
                        films_at_theater = get_all_showtimes_for_theater(theater['name'], theater['url'], browser)
                        all_films.update(films_at_theater)
                
                st.session_state.films = sorted(list(all_films))
                browser.close()

        if st.session_state.theaters:
            st.success(f"Found {len(st.session_state.theaters)} theaters and {len(st.session_state.films)} unique movies.")
        else:
            st.error("No theaters found for that ZIP code.")
    else:
        st.error("Please enter a valid 5-digit ZIP code.")

# --- Display selection criteria if theaters are found ---
if st.session_state.theaters:
    st.header("Step 2: Select Your Criteria")
    theater_names = [t['name'] for t in st.session_state.theaters]
    selected_theaters = st.multiselect('Select Theaters:', options=theater_names, default=theater_names)
    selected_films = st.multiselect('Select Films:', options=st.session_state.films, default=st.session_state.films)
    
    st.header("Step 3: Generate Report")
    if st.button('🚀 Generate Pricing Report'):
        st.info("Next step: Wire this up to run the full price scraping loop!")