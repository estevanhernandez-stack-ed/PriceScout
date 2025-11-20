import streamlit as st
from app import users
from app.config import PROJECT_DIR
import glob
import os
import json
import shutil

def _get_home_location_options(cache_data, selected_company):
    """
    Extract all markets and theaters for a given company from cache_data.
    Returns dict with 'directors', 'markets', 'theaters' lists.
    """
    if not selected_company or selected_company == "All Companies" or not cache_data:
        return {'directors': [], 'markets': [], 'theaters': []}

    # Extract from cache_data structure: cache_data['markets'][market_name]['theaters']
    markets = []
    theaters = []

    for market_name, market_data in cache_data.get('markets', {}).items():
        # Get company-specific theaters if company is selected
        market_theaters = []
        for theater in market_data.get('theaters', []):
            if theater.get('company') == selected_company:
                theater_name = theater.get('name', '')
                if theater_name:
                    market_theaters.append(theater_name)
                    theaters.append(theater_name)

        # Only add market if it has theaters for this company
        if market_theaters:
            markets.append(market_name)

    return {
        'directors': [],  # Not used in current cache structure
        'markets': sorted(markets),
        'theaters': sorted(theaters)
    }

def _render_user_row(user, companies, cache_data):
    """Renders a single row in the user management list with role-based access control."""
    with st.container():
        # First row: basic info
        col1, col2, col3, col4 = st.columns([2, 1.5, 1.5, 1.5])

        with col1:
            new_username = st.text_input("Username", value=user['username'], key=f"username_{user['id']}")

        with col2:
            # Role selection (modes determined by role permissions)
            role_options = ["admin", "manager", "user"]
            current_role = user['role'] if 'role' in user.keys() else 'user'
            if current_role not in role_options:
                current_role = 'user'  # Fallback
            role_index = role_options.index(current_role)
            selected_role = st.selectbox("Role", options=role_options, index=role_index, key=f"role_{user['id']}")

        with col3:
            # Company assignment
            try:
                company_index = companies.index(user['company'])
            except (ValueError, TypeError):
                company_index = 0
            selected_company = st.selectbox("Company", options=companies, index=company_index, key=f"company_{user['id']}")

        with col4:
            # Default Company Selector
            try:
                default_index = companies.index(user['default_company'])
            except (ValueError, TypeError):
                default_index = 0
            selected_default_company = st.selectbox("Default Co.", options=companies, index=default_index, key=f"default_company_{user['id']}")

        # Second row: home location
        col5, col6, col7, col8 = st.columns([2, 2, 2, 2])

        with col5:
            location_types = ["None", "Director", "Market", "Theater"]
            # sqlite3.Row uses dictionary-style access
            try:
                current_type = user['home_location_type'] if 'home_location_type' in user.keys() else None
            except (KeyError, TypeError):
                current_type = None

            if current_type is None:
                current_type = "None"
            else:
                current_type = current_type.capitalize()

            if current_type not in location_types:
                current_type = "None"

            type_index = location_types.index(current_type)
            selected_location_type = st.selectbox("Home Location Type", options=location_types, index=type_index, key=f"loc_type_{user['id']}")

        with col6:
            # Get location options based on selected company
            home_options = _get_home_location_options(cache_data, selected_company)
            
            if selected_location_type == "Director":
                options = [""] + home_options['directors']
            elif selected_location_type == "Market":
                options = [""] + home_options['markets']
            elif selected_location_type == "Theater":
                options = [""] + home_options['theaters']
            else:
                options = [""]
            
            # sqlite3.Row uses dictionary-style access
            try:
                current_value = user['home_location_value'] if 'home_location_value' in user.keys() else ''
            except (KeyError, TypeError):
                current_value = ''
            
            if current_value is None:
                current_value = ''
            
            if current_value not in options:
                current_value = ""
            
            value_index = options.index(current_value) if current_value in options else 0
            selected_location_value = st.selectbox("Home Location", options=options, index=value_index, key=f"loc_value_{user['id']}")
        
        with col7:
            if st.button("Update", key=f"update_{user['id']}"):
                company = selected_company if selected_company != "All Companies" else None
                default_company = selected_default_company if selected_default_company != "All Companies" else None
                is_admin = (selected_role == "admin")
                
                # Prepare home location values
                home_type = selected_location_type.lower() if selected_location_type != "None" else None
                home_value = selected_location_value if selected_location_value else None
                
                users.update_user(user['id'], new_username, is_admin, company, default_company, 
                                role=selected_role, allowed_modes=None, 
                                home_location_type=home_type, home_location_value=home_value)
                st.success(f"User {new_username} updated.")
                st.rerun()
        
        with col8:
            if st.button("Delete", key=f"delete_{user['id']}"):
                users.delete_user(user['id'])
                st.success(f"User {user['username']} deleted.")
                st.rerun()
        
        st.divider()

def _render_user_management(companies, cache_data):
    """Renders the user management section."""
    st.subheader("User Management")
    all_users = users.get_all_users()
    for user in all_users:
        _render_user_row(user, companies, cache_data)

def _render_add_user_form(companies, cache_data):
    """Renders the form for adding a new user with role selection."""
    st.subheader("Add New User")
    st.write("User modes are determined by role permissions. Configure role permissions above.")

    # Remove "All Companies" from options for new users - users must be assigned to a specific company
    real_companies = [c for c in companies if c != "All Companies"]

    if not real_companies:
        st.warning("No companies found. Please add company data first.")
        return

    with st.form("add_user_form"):
        col1, col2 = st.columns(2)

        with col1:
            new_username = st.text_input("New Username")
            new_password = st.text_input("New Password", type="password")
            role = st.selectbox("Role", options=["admin", "manager", "user"], index=2)

        with col2:
            company = st.selectbox("Assigned Company", options=real_companies)
            default_company = st.selectbox("Default Company on Login", options=real_companies)

        # Home Location row
        st.write("**Optional: Set Home Location**")
        col3, col4 = st.columns(2)

        with col3:
            location_type = st.selectbox("Home Location Type", options=["None", "Director", "Market", "Theater"], key="new_user_loc_type")

        with col4:
            # Get location options based on selected company
            # Since "All Companies" is no longer an option, company will always be a real company
            home_options = _get_home_location_options(cache_data, company)
            
            if location_type == "Director":
                location_options = [""] + home_options['directors']
            elif location_type == "Market":
                location_options = [""] + home_options['markets']
            elif location_type == "Theater":
                location_options = [""] + home_options['theaters']
            else:
                location_options = [""]
            
            location_value = st.selectbox("Home Location", options=location_options, key="new_user_loc_value")
        
        submitted = st.form_submit_button("Add User")

        if submitted:
            if new_username and new_password:
                # Since "All Companies" is no longer an option, use the selected companies directly
                selected_company = company
                selected_default = default_company
                is_admin = (role == "admin")
                
                # Prepare home location
                home_type = location_type.lower() if location_type != "None" else None
                home_value = location_value if location_value else None
                
                success, message = users.create_user(
                    new_username, new_password, is_admin, 
                    selected_company, selected_default,
                    role=role, allowed_modes=None,  # Modes from role permissions
                    home_location_type=home_type, home_location_value=home_value
                )
                
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

def _render_role_permissions():
    """Renders the role permissions configuration section."""
    st.subheader("Role Permissions")
    st.write("Configure which modes each role can access. Changes apply to all users with that role.")
    
    role_perms = users.load_role_permissions()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("### Admin Role")
        admin_modes = st.multiselect(
            "Admin Modes",
            options=users.ALL_SIDEBAR_MODES,
            default=role_perms.get(users.ROLE_ADMIN, users.ADMIN_DEFAULT_MODES),
            key="admin_modes"
        )
    
    with col2:
        st.markdown("### Manager Role")
        manager_modes = st.multiselect(
            "Manager Modes",
            options=users.ALL_SIDEBAR_MODES,
            default=role_perms.get(users.ROLE_MANAGER, users.MANAGER_DEFAULT_MODES),
            key="manager_modes"
        )
    
    with col3:
        st.markdown("### User Role")
        user_modes = st.multiselect(
            "User Modes",
            options=users.ALL_SIDEBAR_MODES,
            default=role_perms.get(users.ROLE_USER, users.USER_DEFAULT_MODES),
            key="user_modes"
        )
    
    if st.button("Save Role Permissions", type="primary"):
        new_perms = {
            users.ROLE_ADMIN: admin_modes,
            users.ROLE_MANAGER: manager_modes,
            users.ROLE_USER: user_modes
        }
        users.save_role_permissions(new_perms)
        st.success("Role permissions updated! Changes will apply to all users.")
        st.rerun()

def _render_bulk_import():
    """Renders the bulk user import section."""
    st.subheader("Bulk Import Users")

    # Instructions and template download
    st.markdown("""
    📥 **Upload a CSV, Excel, or JSON file** with user information to create multiple users at once.

    📄 **Templates Available:**
    - `bulk_user_upload_template.csv` - CSV format template
    - `bulk_user_upload_template.xlsx` - Excel format template
    - `example_users.json` - JSON format template

    📖 **Full Guide**: See `BULK_USER_UPLOAD_GUIDE.md` for detailed instructions.
    """)

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Upload Users File",
            type=['json', 'csv', 'xlsx'],
            help="Upload a JSON, CSV, or Excel file with user data."
        )

        if uploaded_file is not None:
            try:
                file_type = uploaded_file.name.split('.')[-1].lower()

                if file_type == 'json':
                    # Handle JSON files
                    users_data = json.load(uploaded_file)
                    st.json(users_data)

                elif file_type == 'csv':
                    # Handle CSV files
                    csv_content = uploaded_file.getvalue().decode('utf-8')
                    users_data = users.parse_csv_to_users_dict(csv_content)
                    st.success(f"✅ Parsed {len(users_data.get('users', []))} user(s) from CSV")

                    # Show preview
                    if users_data.get('users'):
                        st.write("**Preview (first 5 users):**")
                        import pandas as pd
                        preview_df = pd.DataFrame(users_data['users'][:5])
                        # Don't show passwords in preview
                        preview_df['password'] = '********'
                        st.dataframe(preview_df, use_container_width=True)

                elif file_type == 'xlsx':
                    # Handle Excel files
                    import pandas as pd
                    df = pd.read_excel(uploaded_file)

                    # Convert DataFrame to users dict format
                    users_list = []
                    for _, row in df.iterrows():
                        if pd.notna(row.get('username')) and pd.notna(row.get('password')):
                            user_data = {
                                'username': str(row.get('username', '')).strip(),
                                'password': str(row.get('password', '')).strip(),
                                'role': str(row.get('role', 'user')).strip().lower(),
                                'company': str(row.get('company', '')).strip() if pd.notna(row.get('company')) else None,
                                'default_company': str(row.get('default_company', '')).strip() if pd.notna(row.get('default_company')) else None,
                                'home_location_type': str(row.get('home_location_type', '')).strip().lower() if pd.notna(row.get('home_location_type')) else None,
                                'home_location_value': str(row.get('home_location_value', '')).strip() if pd.notna(row.get('home_location_value')) else None,
                            }
                            users_list.append(user_data)

                    users_data = {'users': users_list}
                    st.success(f"✅ Parsed {len(users_list)} user(s) from Excel")

                    # Show preview
                    if users_list:
                        st.write("**Preview (first 5 users):**")
                        preview_df = pd.DataFrame(users_list[:5])
                        # Don't show passwords in preview
                        preview_df['password'] = '********'
                        st.dataframe(preview_df, use_container_width=True)
                else:
                    st.error(f"Unsupported file type: {file_type}")
                    users_data = None

                # Import button
                if users_data and st.button("Import Users", type="primary", key="import_users_btn"):
                    success_count, errors = users.bulk_import_users(users_data)

                    if success_count > 0:
                        st.success(f"✅ Successfully imported {success_count} user(s)!")

                    if errors:
                        st.error(f"❌ Encountered {len(errors)} error(s):")
                        for error in errors:
                            st.text(f"  • {error}")

                    if success_count > 0:
                        st.rerun()

            except json.JSONDecodeError:
                st.error("Invalid JSON file format")
            except Exception as e:
                st.error(f"Error processing file: {str(e)}")

    with col2:
        st.markdown("### CSV Format")
        st.code('''username,password,role,company
jsmith,Pass123!,manager,AMC
bdoe,Pass456!,user,Marcus''', language='csv')

        st.markdown("### JSON Format")
        st.code('''{
  "users": [
    {
      "username": "jsmith",
      "password": "Pass123!",
      "role": "manager",
      "company": "AMC",
      "default_company": "AMC"
    }
  ]
}''', language='json')

def admin_page(markets_data, cache_data):
    """Main function to render the admin page."""
    st.title("Admin Page")

    if not st.session_state.get("is_admin"):
        st.error("You do not have permission to view this page.")
        return

    companies_with_all = ["All Companies"] + list(markets_data.keys())

    _render_role_permissions()
    st.divider()
    _render_bulk_import()
    st.divider()
    _render_user_management(companies_with_all, cache_data)
    st.divider()
    _render_add_user_form(companies_with_all, cache_data)
    st.divider()
    _render_company_management(markets_data)
