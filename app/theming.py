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
    Renders a theme selector in the sidebar and applies the selected theme's CSS.
    This component should be called once in your app's main script.
    It uses session state to remember the user's choice.
    """
    # Initialize the theme in session state if it's not already there.
    if 'current_theme' not in st.session_state:
        # Default to the first theme in the file.
        st.session_state.current_theme = list(THEMES.keys())[0]

    # Display the selector widget in the sidebar.
    st.sidebar.divider()
    st.sidebar.subheader("Appearance")
    selected_theme = st.sidebar.selectbox(
        "Select Theme",
        options=list(THEMES.keys()),
        # The index is set from session state to remember the selection.
        index=list(THEMES.keys()).index(st.session_state.current_theme),
        key="theme_selector_widget"
    )

    # If the user chooses a new theme, update the session state and rerun the app.
    if selected_theme != st.session_state.current_theme:
        st.session_state.current_theme = selected_theme
        st.rerun()

    # Apply the CSS of the currently selected theme on every app run.
    theme_css = THEMES.get(st.session_state.current_theme, {}).get("css", "")

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