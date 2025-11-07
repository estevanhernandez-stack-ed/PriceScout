import pytest
import os
import json
import shutil
import tempfile
from unittest.mock import patch, MagicMock, call
from app.admin import _delete_company_data, _render_user_row, _render_user_management, _render_add_user_form, _render_company_management, admin_page


@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory structure for testing."""
    # Create data directory with company subdirectories
    data_dir = tmp_path / "data"
    
    # Company 1: AMC Theatres
    amc_dir = data_dir / "AMC Theatres"
    amc_dir.mkdir(parents=True)
    markets_file = amc_dir / "markets.json"
    markets_file.write_text(json.dumps({
        "AMC Theatres": {
            "St. Louis": {"theaters": ["AMC West Olive"]}
        }
    }))
    
    # Company 2: Marcus Theatres
    marcus_dir = data_dir / "Marcus Theatres"
    marcus_dir.mkdir(parents=True)
    markets_file = marcus_dir / "markets.json"
    markets_file.write_text(json.dumps({
        "Marcus Theatres": {
            "Milwaukee": {"theaters": ["Marcus Majestic"]}
        }
    }))
    
    return tmp_path


def test_delete_company_data_success(temp_project_dir):
    """Test successful deletion of company data."""
    with patch('app.admin.PROJECT_DIR', temp_project_dir):
        with patch('app.admin.st.success') as mock_success:
            with patch('app.admin.st.session_state', {'confirm_delete': 'AMC Theatres'}):
                with patch('app.admin.st.rerun'):
                    _delete_company_data('AMC Theatres')
                    
                    # Verify directory was deleted
                    amc_dir = temp_project_dir / "data" / "AMC Theatres"
                    assert not amc_dir.exists()
                    
                    # Verify Marcus directory still exists
                    marcus_dir = temp_project_dir / "data" / "Marcus Theatres"
                    assert marcus_dir.exists()
                    
                    # Verify success message was called
                    mock_success.assert_called_once()
                    assert "AMC Theatres" in mock_success.call_args[0][0]


def test_delete_company_data_not_found(temp_project_dir):
    """Test deletion when company doesn't exist."""
    with patch('app.admin.PROJECT_DIR', temp_project_dir):
        with patch('app.admin.st.error') as mock_error:
            _delete_company_data('Nonexistent Company')
            
            # Verify error message was called
            mock_error.assert_called_once()
            assert "Could not find" in mock_error.call_args[0][0]


def test_delete_company_data_no_markets_file(tmp_path):
    """Test deletion when no markets.json files exist."""
    with patch('app.admin.PROJECT_DIR', tmp_path):
        with patch('app.admin.st.error') as mock_error:
            _delete_company_data('Any Company')
            
            # Should error because no company directory found
            mock_error.assert_called_once()
            assert "Could not find" in mock_error.call_args[0][0]


def test_delete_company_data_exception_handling(temp_project_dir):
    """Test that exceptions are properly caught and displayed."""
    with patch('app.admin.PROJECT_DIR', temp_project_dir):
        with patch('app.admin.st.error') as mock_error:
            # Mock glob to raise an exception
            with patch('glob.glob', side_effect=Exception("Test error")):
                _delete_company_data('AMC Theatres')
                
                # Verify error was caught and displayed
                mock_error.assert_called_once()
                assert "An error occurred" in mock_error.call_args[0][0]
                assert "Test error" in mock_error.call_args[0][0]


def test_delete_company_data_preserves_other_companies(temp_project_dir):
    """Test that deleting one company doesn't affect others."""
    with patch('app.admin.PROJECT_DIR', temp_project_dir):
        with patch('app.admin.st.success'):
            with patch('app.admin.st.session_state', {'confirm_delete': 'AMC Theatres'}):
                with patch('app.admin.st.rerun'):
                    # Read Marcus data before deletion
                    marcus_file = temp_project_dir / "data" / "Marcus Theatres" / "markets.json"
                    marcus_data_before = json.loads(marcus_file.read_text())
                    
                    # Delete AMC
                    _delete_company_data('AMC Theatres')
                    
                    # Verify Marcus data is unchanged
                    assert marcus_file.exists()
                    marcus_data_after = json.loads(marcus_file.read_text())
                    assert marcus_data_before == marcus_data_after


def test_delete_company_data_with_multiple_markets(temp_project_dir):
    """Test deletion when company has data in markets.json."""
    # Create a company with additional files
    company_dir = temp_project_dir / "data" / "AMC Theatres"
    
    # Add extra files to verify entire directory is deleted
    extra_file = company_dir / "extra_data.txt"
    extra_file.write_text("Some data")
    
    subdir = company_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("Nested data")
    
    with patch('app.admin.PROJECT_DIR', temp_project_dir):
        with patch('app.admin.st.success'):
            with patch('app.admin.st.session_state', {'confirm_delete': 'AMC Theatres'}):
                with patch('app.admin.st.rerun'):
                    _delete_company_data('AMC Theatres')
                    
                    # Verify entire directory tree was deleted
                    assert not company_dir.exists()
                    assert not extra_file.exists()
                    assert not subdir.exists()


# ===== UI Component Tests =====

def test_render_user_row_creates_ui_elements():
    """Test that user row creates appropriate UI structure."""
    user = {
        'id': 1,
        'username': 'test_user',
        'is_admin': False,
        'company': 'AMC Theatres',
        'default_company': 'Marcus Theatres'
    }
    companies = ['All Companies', 'AMC Theatres', 'Marcus Theatres']
    
    with patch('app.admin.st') as mock_st:
        # Setup basic mocks
        mock_st.container.return_value.__enter__ = MagicMock()
        mock_st.container.return_value.__exit__ = MagicMock()
        
        _render_user_row(user, companies)
        
        # Verify container was created
        mock_st.container.assert_called_once()
        # Verify columns were created with 6 columns
        mock_st.columns.assert_called_once()


def test_render_user_management_calls_get_all_users():
    """Test that user management retrieves and displays all users."""
    mock_users = [
        {'id': 1, 'username': 'user1', 'is_admin': True, 'company': 'AMC Theatres', 'default_company': 'AMC Theatres'},
        {'id': 2, 'username': 'user2', 'is_admin': False, 'company': 'Marcus Theatres', 'default_company': 'Marcus Theatres'}
    ]
    companies = ['All Companies', 'AMC Theatres', 'Marcus Theatres']
    
    with patch('app.admin.st') as mock_st:
        with patch('app.admin.users.get_all_users', return_value=mock_users) as mock_get_users:
            with patch('app.admin._render_user_row') as mock_render_row:
                _render_user_management(companies)
                
                # Verify get_all_users was called
                mock_get_users.assert_called_once()
                
                # Verify _render_user_row was called for each user
                assert mock_render_row.call_count == 2
                mock_render_row.assert_any_call(mock_users[0], companies)
                mock_render_row.assert_any_call(mock_users[1], companies)
                
                # Verify subheader was created
                mock_st.subheader.assert_called_once_with("User Management")


def test_render_add_user_form_creates_form():
    """Test that add user form creates proper form structure."""
    companies = ['All Companies', 'AMC Theatres']
    
    with patch('app.admin.st') as mock_st:
        # Mock form context manager
        mock_form_ctx = MagicMock()
        mock_st.form.return_value.__enter__.return_value = mock_form_ctx
        mock_st.form.return_value.__exit__.return_value = None
        
        # Mock columns to return two column objects
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns.return_value = [mock_col1, mock_col2]
        
        # Mock form submission as not submitted
        mock_st.form_submit_button.return_value = False
        
        _render_add_user_form(companies)
        
        # Verify form was created
        mock_st.form.assert_called_once_with("add_user_form")
        
        # Verify subheader
        mock_st.subheader.assert_called_once_with("Add New User")
        
        # Verify columns were created
        mock_st.columns.assert_called_once_with(2)


def test_render_add_user_form_empty_submission():
    """Test form validation with empty fields."""
    companies = ['All Companies', 'AMC Theatres']
    
    with patch('app.admin.st') as mock_st:
        # Mock form context
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        
        # Mock columns
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns.return_value = [mock_col1, mock_col2]
        
        # Mock inputs - empty username and password
        mock_st.text_input.side_effect = ['', '']
        mock_st.selectbox.side_effect = ['user', 'AMC Theatres', 'AMC Theatres']  # role, company, default_company
        mock_st.form_submit_button.return_value = True
        
        _render_add_user_form(companies)
        
        # Verify error was shown
        mock_st.error.assert_called_once_with("Please provide both a username and password.")
        mock_st.error.assert_called_once()
        assert "username and password" in str(mock_st.error.call_args)


def test_render_add_user_form_successful_creation():
    """Test successful user creation."""
    companies = ['All Companies', 'AMC Theatres']
    
    with patch('app.admin.st') as mock_st:
        # Mock form context
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        
        # Mock columns
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns.return_value = [mock_col1, mock_col2]
        
        # Mock valid inputs (username, password, role, company, default_company)
        mock_st.text_input.side_effect = ['newuser', 'StrongPass123!']
        mock_st.selectbox.side_effect = ['user', 'AMC Theatres', 'AMC Theatres']
        mock_st.form_submit_button.return_value = True
        
        with patch('app.admin.users.create_user', return_value=(True, 'User created')) as mock_create:
            _render_add_user_form(companies)
            
            # Verify create_user was called with correct parameters (including role)
            mock_create.assert_called_once_with(
                'newuser', 'StrongPass123!', False, 
                'AMC Theatres', 'AMC Theatres',
                role='user', allowed_modes=None
            )
            
            # Verify success and rerun
            mock_st.success.assert_called_once()
            mock_st.rerun.assert_called_once()
            mock_st.rerun.assert_called_once()


def test_render_add_user_form_creation_fails():
    """Test when user creation fails."""
    companies = ['All Companies', 'AMC Theatres']
    
    with patch('app.admin.st') as mock_st:
        # Mock form context
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        
        # Mock columns
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns.return_value = [mock_col1, mock_col2]
        
        # Mock valid inputs (username, password, role, company, default_company)
        mock_st.text_input.side_effect = ['duplicate', 'StrongPass123!']
        mock_st.selectbox.side_effect = ['user', 'AMC Theatres', 'AMC Theatres']
        mock_st.form_submit_button.return_value = True
        
        with patch('app.admin.users.create_user', return_value=(False, 'Username already exists')):
            _render_add_user_form(companies)
            
            # Verify error message was shown
            mock_st.error.assert_called_once_with('Username already exists')


def test_render_company_management_no_companies():
    """Test company management with no companies available."""
    with patch('app.admin.st') as mock_st:
        _render_company_management({})
        
        # Verify info message was shown
        mock_st.info.assert_called_once_with("No companies to manage.")
        
        # Verify subheader was created
        mock_st.subheader.assert_called_once_with("Company Management")


def test_render_company_management_shows_selectbox():
    """Test that company management displays company selector."""
    markets_data = {
        'AMC Theatres': {},
        'Marcus Theatres': {}
    }
    
    with patch('app.admin.st') as mock_st:
        mock_st.selectbox.return_value = 'AMC Theatres'
        mock_st.button.return_value = False
        mock_st.session_state = {}
        
        _render_company_management(markets_data)
        
        # Verify selectbox was created with company list
        mock_st.selectbox.assert_called_once()
        call_args = mock_st.selectbox.call_args
        assert 'AMC Theatres' in call_args[1]['options']
        assert 'Marcus Theatres' in call_args[1]['options']


def test_admin_page_denies_non_admin():
    """Test admin page denies access to non-admin users."""
    with patch('app.admin.st') as mock_st:
        mock_st.session_state.get.return_value = False
        
        admin_page({})
        
        # Verify error was shown
        mock_st.error.assert_called_once()
        assert "permission" in str(mock_st.error.call_args).lower()


def test_admin_page_renders_for_admin():
    """Test admin page renders all sections for admin users."""
    markets_data = {'AMC Theatres': {}}
    
    with patch('app.admin.st') as mock_st:
        # Mock admin user
        mock_st.session_state.get.return_value = True
        
        with patch('app.admin._render_role_permissions') as mock_role_perms:
            with patch('app.admin._render_bulk_import') as mock_bulk_import:
                with patch('app.admin._render_user_management') as mock_user_mgmt:
                    with patch('app.admin._render_add_user_form') as mock_add_user:
                        with patch('app.admin._render_company_management') as mock_company_mgmt:
                            admin_page(markets_data)
                            
                            # Verify all five sections were rendered
                            mock_role_perms.assert_called_once()
                            mock_bulk_import.assert_called_once()
                            mock_user_mgmt.assert_called_once()
                            mock_add_user.assert_called_once()
                            mock_company_mgmt.assert_called_once_with(markets_data)
                            
                            # Verify dividers were added (4 dividers between 5 sections)
                            assert mock_st.divider.call_count == 4
                            
                            # Verify title
                            mock_st.title.assert_called_once_with("Admin Page")


def test_render_add_user_form_all_companies_conversion():
    """Test that 'All Companies' selection is converted to None."""
    companies = ['All Companies', 'AMC Theatres']
    
    with patch('app.admin.st') as mock_st:
        # Mock form context
        mock_st.form.return_value.__enter__.return_value = MagicMock()
        mock_st.form.return_value.__exit__.return_value = None
        
        # Mock columns
        mock_col1 = MagicMock()
        mock_col2 = MagicMock()
        mock_st.columns.return_value = [mock_col1, mock_col2]
        
        # Mock user selects "All Companies" (username, password, role, company, default_company)
        mock_st.text_input.side_effect = ['admin', 'AdminPass123!']
        mock_st.selectbox.side_effect = ['admin', 'All Companies', 'All Companies']
        mock_st.form_submit_button.return_value = True
        
        with patch('app.admin.users.create_user', return_value=(True, 'Created')) as mock_create:
            _render_add_user_form(companies)
            
            # Verify "All Companies" was converted to None, role passed correctly
            mock_create.assert_called_once_with(
                'admin', 'AdminPass123!', True, None, None,
                role='admin', allowed_modes=None
            )

