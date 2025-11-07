import streamlit as st
import json
import os

# It's good practice to define paths relative to the current file.
# This makes the app more portable.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
THEMES_FILE = os.path.join(SCRIPT_DIR, 'themes.json')

def load_themes():
    """
    Loads theme configurations from the themes.json file.
    Includes a fallback to a default theme if the file is missing or invalid.
    """
    try:
        with open(THEMES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Provide a default theme so the app doesn't crash if the file is missing.
        return {"Default": {"css": "/* Default theme: No custom styles */"}}

# Load themes once when the module is imported.
THEMES = load_themes()

def apply_css(css: str):
    """
    Injects a string of custom CSS into the Streamlit app's HTML head.
    """
    if css:
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

def theme_selector_component():
    """
    Renders a simple dark mode toggle in the sidebar.
    Uses session state to remember the user's choice.
    """
    # Initialize dark mode in session state if it's not already there.
    if 'dark_mode' not in st.session_state:
        st.session_state.dark_mode = False

    # Display dark mode toggle
    st.sidebar.divider()
    dark_mode = st.sidebar.toggle(
        "🌙 Dark Mode",
        value=st.session_state.dark_mode,
        key="dark_mode_toggle"
    )

    # If the user toggles dark mode, update session state and rerun
    if dark_mode != st.session_state.dark_mode:
        st.session_state.dark_mode = dark_mode
        st.rerun()

    # Apply dark mode CSS if enabled
    if st.session_state.dark_mode:
        dark_mode_css = """
        /* Dark mode styles */
        .stApp {
            background-color: #0E1117;
            color: #FAFAFA;
        }
        .stSidebar {
            background-color: #262730;
        }
        .stSidebar .stMarkdown {
            color: #FAFAFA;
        }
        div[data-testid="stMetric"] div {
            color: #FAFAFA !important;
        }
        /* Ensure button text is always visible */
        button[kind="primary"] p,
        button[kind="secondary"] p,
        button[kind="primary"] div,
        button[kind="secondary"] div {
            color: #FFFFFF !important;
        }
        /* Fix for secondary buttons in dark mode */
        button[kind="secondary"] {
            background-color: #262730 !important;
            border-color: #4A4A4A !important;
        }
        button[kind="secondary"]:hover {
            background-color: #3A3A3A !important;
            border-color: #5A5A5A !important;
        }
        /* Ensure text inputs and selectboxes are readable */
        input, textarea, select {
            background-color: #262730 !important;
            color: #FAFAFA !important;
        }
        /* Fix dataframe text in dark mode */
        .dataframe {
            color: #FAFAFA !important;
        }
        """
        theme_css = dark_mode_css
    else:
        # Light mode - no custom CSS needed beyond defaults
        theme_css = ""

    # This CSS override ensures that the primary button color is consistent
    # with the desired branding, as it was likely lost during a refactor.
    primary_button_override_css = """
    button[kind="primary"] {
        background-color: #8b0e04 !important;
        color: white !important;
        border: 1px solid #8b0e04 !important;
    }
    button[kind="primary"]:hover {
        background-color: #a31004 !important;
        border-color: #a31004 !important;
    }
    button[kind="primary"]:focus {
        box-shadow: 0 0 0 0.2rem rgba(139, 14, 4, 0.5) !important;
    }
    """

    # --- NEW: Fix for st.metric text color ---
    # This ensures that the text inside metric components is always dark and readable.
    metric_text_override_css = """
    div[data-testid="stMetric"] div {
        color: #31333F !important;
    }
    """
    apply_css(theme_css + primary_button_override_css + metric_text_override_css)