import streamlit as st
from app import users
from app.config import PROJECT_DIR
import glob
import os
import json
import shutil

def _render_user_row(user, companies):
    """Renders a single row in the user management list."""
    with st.container():
        col1, col2, col3, col4, col5, col6 = st.columns([2, 2, 2, 2, 1, 1])
        with col1:
            new_username = st.text_input("Username", value=user['username'], key=f"username_{user['id']}")
        with col2:
            is_admin = st.checkbox("Is Admin?", value=user['is_admin'], key=f"is_admin_{user['id']}")
        with col3:
            # Company assignment (for non-admins)
            try:
                index = companies.index(user['company'])
            except ValueError:
                index = 0
            selected_company = st.selectbox("Company", options=companies, index=index, key=f"company_{user['id']}")
        with col4: # --- NEW: Default Company Selector ---
            try:
                default_index = companies.index(user['default_company'])
            except ValueError:
                default_index = 0
            selected_default_company = st.selectbox("Default Company", options=companies, index=default_index, key=f"default_company_{user['id']}")
        with col5:
            if st.button("Update", key=f"update_{user['id']}"):
                company = selected_company if selected_company != "All Companies" else None
                default_company = selected_default_company if selected_default_company != "All Companies" else None
                users.update_user(user['id'], new_username, is_admin, company, default_company)
                st.success(f"User {new_username} updated.")
                st.rerun()
        with col6:
            if st.button("Delete", key=f"delete_{user['id']}"):
                users.delete_user(user['id'])
                st.success(f"User {user['username']} deleted.")
                st.rerun()

def _render_user_management(companies):
    """Renders the user management section."""
    st.subheader("User Management")
    all_users = users.get_all_users()
    for user in all_users:
        _render_user_row(user, companies)

def _render_add_user_form(companies):
    """Renders the form for adding a new user."""
    st.subheader("Add New User")
    with st.form("add_user_form"):
        new_username = st.text_input("New Username")
        new_password = st.text_input("New Password", type="password")
        is_admin = st.checkbox("Is Admin?")
        company = st.selectbox("Assigned Company (for non-admins)", options=companies)
        default_company = st.selectbox("Default Company on Login", options=companies)
        submitted = st.form_submit_button("Add User")
        if submitted:
            if new_username and new_password:
                selected_company = company if company != "All Companies" else None
                selected_default = default_company if default_company != "All Companies" else None
                success, message = users.create_user(new_username, new_password, is_admin, selected_company, selected_default)
                if success:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            else:
                st.error("Please provide both a username and password.")

def _delete_company_data(company_to_delete):
    """Handles the logic of finding and deleting a company's data directory."""
    try:
        # Find the directory for the selected company
        company_dir = None
        all_market_files = glob.glob(os.path.join(PROJECT_DIR, "data", "*", "markets.json"))
        for market_file in all_market_files:
            with open(market_file, 'r') as f:
                data = json.load(f)
                if company_to_delete in data:
                    company_dir = os.path.dirname(market_file)
                    break
        
        if company_dir and os.path.isdir(company_dir):
            shutil.rmtree(company_dir)
            st.success(f"Company '{company_to_delete}' and its data have been deleted.")
            # Clean up session state
            del st.session_state.confirm_delete
            st.rerun()
        else:
            st.error(f"Could not find the data directory for company '{company_to_delete}'.")

    except Exception as e:
        st.error(f"An error occurred while deleting the company: {e}")

def _render_company_management(markets_data):
    """Renders the company management section for deleting companies."""
    st.subheader("Company Management")
    
    companies = list(markets_data.keys())
    if not companies:
        st.info("No companies to manage.")
        return

    company_to_delete = st.selectbox("Select Company to Delete", options=companies)
    
    if st.button("Delete Company", key="delete_company_btn"):
        if company_to_delete:
            # Confirmation step
            if 'confirm_delete' not in st.session_state:
                st.session_state.confirm_delete = company_to_delete
                st.rerun()

    if 'confirm_delete' in st.session_state and st.session_state.confirm_delete:
        if st.session_state.confirm_delete == company_to_delete:
            st.warning(f"Are you sure you want to permanently delete the company '{company_to_delete}' and all its associated data? This action cannot be undone.")
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("Yes, Delete", type="primary"):
                    _delete_company_data(company_to_delete)
            with col2:
                if st.button("Cancel"):
                    del st.session_state.confirm_delete
                    st.rerun()

def admin_page(markets_data):
    """Main function to render the admin page."""
    st.title("Admin Page")

    if not st.session_state.get("is_admin"):
        st.error("You do not have permission to view this page.")
        return

    companies_with_all = ["All Companies"] + list(markets_data.keys())

    _render_user_management(companies_with_all)
    st.divider()
    _render_add_user_form(companies_with_all)
    st.divider()
    _render_company_management(markets_data)