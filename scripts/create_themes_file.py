import json
import os

themes = {
  "PriceScout Dark": {
    "css": """
      :root {
        --primary-color: #F63366;
        --background-color: #0E1117;
        --secondary-background-color: #262730;
        --text-color: #FAFAFA;
        --font: \"sans serif\";
        --sidebar-background: #1a1c22;
        --widget-background: #31333F;
        --border-color: #444;
        --button-border-radius: 12px;
      }

      body {
        color: var(--text-color);
      }

      .stApp {
        background-color: var(--background-color);
      }

      [data-testid=\"stSidebar\"] {
        background-color: var(--sidebar-background);
        border-right: 1px solid var(--border-color);
      }

      /* --- BUTTONS --- */
      .stButton > button {
        border-radius: var(--button-border-radius) !important;
        border: 1px solid var(--primary-color) !important;
        color: var(--primary-color) !important;
        background-color: transparent !important;
        transition: all 0.2s ease-in-out !important;
        font-weight: bold;
      }

      .stButton > button:hover {
        color: white !important;
        background-color: var(--primary-color) !important;
        box-shadow: 0 0 10px 0 var(--primary-color);
      }

      .stButton > button:focus {
        box-shadow: 0 0 0 2px var(--background-color), 0 0 0 4px var(--primary-color) !important;
      }

      /* Primary buttons */
      .stButton > button[kind=\"primary\"] {
        background-color: var(--primary-color) !important;
        color: white !important;
      }

      .stButton > button[kind=\"primary\"]:hover {
        filter: brightness(1.2);
        box-shadow: 0 0 15px 0 var(--primary-color);
      }

      /* --- OTHER WIDGETS --- */
      .stExpander {
        border: 1px solid var(--border-color) !important;
        border-radius: var(--button-border-radius) !important;
        background-color: var(--secondary-background-color) !important;
      }

      .stTextInput input, .stTextArea textarea {
        background-color: var(--widget-background) !important;
        color: var(--text-color) !important;
        border-radius: 8px !important;
        border: 1px solid var(--border-color) !important;
      }
    """
  },
  "Corporate Light": {
    "css": """
      :root {
        --primary-color: #1976D2;
        --background-color: #FFFFFF;
        --secondary-background-color: #F0F2F6;
        --text-color: #31333F;
        --font: \"sans serif\";
        --sidebar-background: #F8F9FA;
        --widget-background: #FFFFFF;
        --border-color: #E0E0E0;
        --button-border-radius: 8px;
      }

      body {
        color: var(--text-color);
      }

      .stApp {
        background-color: var(--background-color);
      }

      [data-testid=\"stSidebar\"] {
        background-color: var(--sidebar-background);
        border-right: 1px solid var(--border-color);
      }

      /* --- BUTTONS --- */
      .stButton > button {
        border-radius: var(--button-border-radius) !important;
        border: 1px solid var(--primary-color) !important;
        color: var(--primary-color) !important;
        background-color: transparent !important;
        transition: all 0.2s ease-in-out !important;
        font-weight: bold;
      }

      .stButton > button:hover {
        color: white !important;
        background-color: var(--primary-color) !important;
      }

      .stButton > button:focus {
        box-shadow: 0 0 0 2px var(--background-color), 0 0 0 4px var(--primary-color) !important;
      }

      /* Primary buttons */
      .stButton > button[kind=\"primary\"] {
        background-color: var(--primary-color) !important;
        color: white !important;
      }

      .stButton > button[kind=\"primary\"]:hover {
        filter: brightness(1.1);
      }

      /* --- OTHER WIDGETS --- */
      .stExpander {
        border: 1px solid var(--border-color) !important;
        border-radius: var(--button-border-radius) !important;
        background-color: var(--secondary-background-color) !important;
      }
      
      .stTextInput input, .stTextArea textarea {
        background-color: var(--widget-background) !important;
        color: var(--text-color) !important;
        border-radius: 8px !important;
        border: 1px solid var(--border-color) !important;
      }
    """
  }
}

file_path = os.path.join('app', 'themes.json')
with open(file_path, 'w') as f:
    json.dump(themes, f, indent=2)

print(f"Successfully created {file_path}")
