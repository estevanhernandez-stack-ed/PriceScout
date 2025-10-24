import streamlit as st

def initialize_session_state():
    if 'stage' not in st.session_state: st.session_state.stage = 'initial'
    if 'search_mode' not in st.session_state: st.session_state.search_mode = "Market Mode"
    if 'last_run_log' not in st.session_state: st.session_state.last_run_log = ""
    if 'dev_mode' not in st.session_state: st.session_state.dev_mode = False
    if 'capture_html' not in st.session_state: st.session_state.capture_html = False
    if 'confirm_scrape' not in st.session_state: st.session_state.confirm_scrape = False
    if 'live_search_results' not in st.session_state: st.session_state.live_search_results = {}
    if 'report_running' not in st.session_state: st.session_state.report_running = False
    if 'all_showings' not in st.session_state: st.session_state.all_showings = {}
    if 'selected_films' not in st.session_state: st.session_state.selected_films = []
    if 'selected_showtimes' not in st.session_state: st.session_state.selected_showtimes = {}
    if 'daypart_selections' not in st.session_state: st.session_state.daypart_selections = set()
    if 'dm_stage' not in st.session_state: st.session_state.dm_stage = 'initial'
    if 'selected_region' not in st.session_state: st.session_state.selected_region = None
    if 'selected_market' not in st.session_state: st.session_state.selected_market = None
    if 'selected_theaters' not in st.session_state: st.session_state.selected_theaters = []
    if 'compsnipe_theaters' not in st.session_state: st.session_state.compsnipe_theaters = []
    if 'trend_theaters' not in st.session_state: st.session_state.trend_theaters = []
    if 'trend_films' not in st.session_state: st.session_state.trend_films = []
    if 'trend_dayparts' not in st.session_state: st.session_state.trend_dayparts = []
