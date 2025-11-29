"""
PriceScout Configuration Module
Version: 1.0.0 (Azure-Ready)
Date: November 13, 2025

This module manages application configuration with support for:
- Local development (SQLite, file-based storage)
- Azure production (PostgreSQL, managed services)
- Environment variable overrides
- Automatic deployment detection
"""

import os
from pathlib import Path

# ============================================================================
# EARLY .ENV LOADING (must happen before any os.getenv() calls)
# ============================================================================

def _early_load_env():
    """Load .env file early, before any configuration is read."""
    # Determine project directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    env_path = os.path.join(project_dir, '.env')

    if not os.path.exists(env_path):
        return

    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and not os.getenv(key):  # Don't override existing
                            os.environ[key] = value
    except Exception as e:
        print(f"Warning: Failed to load .env: {e}")

# Load .env FIRST before anything else
_early_load_env()

# ============================================================================
# DEPLOYMENT ENVIRONMENT DETECTION
# ============================================================================

def is_azure_deployment():
    """
    Detect if running in Azure environment.
    
    Returns:
        bool: True if deployed to Azure, False for local development
    """
    # Check explicit environment variable
    if os.getenv('DEPLOYMENT_ENV') == 'azure':
        return True
    
    # Check for Azure-specific environment variables
    azure_indicators = [
        'WEBSITE_SITE_NAME',           # Azure App Service
        'AZURE_KEY_VAULT_URL',         # Key Vault configured
        'APPSETTING_WEBSITE_SITE_NAME', # Azure App Service setting
        'WEBSITE_INSTANCE_ID',         # Azure App Service instance
    ]
    
    return any(os.getenv(var) for var in azure_indicators)


def is_production():
    """
    Check if running in production mode.
    
    Returns:
        bool: True if production, False if development
    """
    env = os.getenv('ENVIRONMENT', '').lower()
    return env in ('production', 'prod') or is_azure_deployment()


def is_development():
    """
    Check if running in development mode.
    
    Returns:
        bool: True if development, False otherwise
    """
    return not is_production()


# ============================================================================
# CORE DIRECTORY PATHS
# ============================================================================

# Script and project directories (always local paths)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# Data directories
DATA_DIR = os.getenv('DATA_DIR', os.path.join(PROJECT_DIR, 'data'))
DEBUG_DIR = os.getenv('DEBUG_DIR', os.path.join(PROJECT_DIR, 'debug_snapshots'))
REPORTS_DIR = os.getenv('REPORTS_DIR', os.path.join(PROJECT_DIR, 'reports'))

# Ensure directories exist
for directory in [DATA_DIR, DEBUG_DIR, REPORTS_DIR]:
    Path(directory).mkdir(parents=True, exist_ok=True)


# ============================================================================
# DATABASE CONFIGURATION
# ============================================================================

# Database type detection (handled by db_session.py)
# Local: SQLite (file-based)
# Azure: PostgreSQL (connection string from env or Key Vault)

# Legacy SQLite paths (for backward compatibility)
DB_FILE = None  # Set by application based on selected company
USER_DB_FILE = os.getenv('USER_DB_FILE', os.path.join(PROJECT_DIR, 'users.db'))

# PostgreSQL connection (for Azure deployment)
DATABASE_URL = os.getenv('DATABASE_URL')  # Full connection string
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
POSTGRES_DB = os.getenv('POSTGRES_DB', 'pricescout_db')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'pricescout_app')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')

# Current company context (for multi-tenancy)
CURRENT_COMPANY_ID = None  # Set by application after user login


# ============================================================================
# AZURE SERVICES CONFIGURATION
# ============================================================================

# Azure Key Vault
AZURE_KEY_VAULT_URL = os.getenv('AZURE_KEY_VAULT_URL')  # e.g., https://pricescout-kv-prod.vault.azure.net/

# Azure Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING = os.getenv('APPLICATIONINSIGHTS_CONNECTION_STRING')
APPINSIGHTS_INSTRUMENTATION_KEY = os.getenv('APPINSIGHTS_INSTRUMENTATION_KEY')

AZURE_SERVICE_BUS_CONNECTION_STRING = os.getenv('AZURE_SERVICE_BUS_CONNECTION_STRING')

# Azure Entra ID (for SSO)
# Set ENTRA_ENABLED=true to enable Microsoft SSO login
ENTRA_ENABLED = os.getenv('ENTRA_ENABLED', 'false').lower() == 'true'
ENTRA_CLIENT_ID = os.getenv('ENTRA_CLIENT_ID')
ENTRA_TENANT_ID = os.getenv('ENTRA_TENANT_ID')
ENTRA_CLIENT_SECRET = os.getenv('ENTRA_CLIENT_SECRET')
ENTRA_REDIRECT_URI = os.getenv('ENTRA_REDIRECT_URI', 'http://localhost:8501/')
ENTRA_AUTHORITY = f"https://login.microsoftonline.com/{ENTRA_TENANT_ID}" if ENTRA_TENANT_ID else None

# Azure Storage (for file uploads, logs, backups)
AZURE_STORAGE_CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
AZURE_STORAGE_CONTAINER = os.getenv('AZURE_STORAGE_CONTAINER', 'pricescout-data')

# Azure API Management Gateway
APIM_GATEWAY_URL = os.getenv('APIM_GATEWAY_URL')  # e.g., https://apim-pricescout-prod.azure-api.net
APIM_SUBSCRIPTION_KEY = os.getenv('APIM_SUBSCRIPTION_KEY')  # Optional: for subscription-based access


# ============================================================================
# API / JWT Configuration
# ============================================================================
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_key_that_should_be_changed")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
OAUTH2_SCHEME = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


# ============================================================================
# APPLICATION SETTINGS
# ============================================================================

# Application metadata
APP_NAME = os.getenv('APP_NAME', 'PriceScout')
APP_VERSION = os.getenv('APP_VERSION', '1.0.0')
APP_ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# Web server configuration
HOST = os.getenv('HOST', '0.0.0.0')  # 0.0.0.0 for container, localhost for local
PORT = int(os.getenv('PORT', '8000'))  # Azure uses 8000, Streamlit default is 8501

# Security settings
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', SECRET_KEY)
SESSION_TIMEOUT_MINUTES = int(os.getenv('SESSION_TIMEOUT_MINUTES', '60'))

# Debug mode
DEBUG = os.getenv('DEBUG', 'false').lower() in ('true', '1', 'yes')
if is_production():
    DEBUG = False  # Never debug in production


# ============================================================================
# CACHE CONFIGURATION
# ============================================================================

CACHE_FILE = os.path.join(SCRIPT_DIR, 'theater_cache.json')
CACHE_EXPIRATION_DAYS = int(os.getenv('CACHE_EXPIRATION_DAYS', '7'))

# Redis cache (for Azure production - optional)
REDIS_HOST = os.getenv('REDIS_HOST')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
REDIS_SSL = os.getenv('REDIS_SSL', 'true').lower() in ('true', '1', 'yes')


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

# Log level
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO' if is_production() else 'DEBUG')

# Log file paths
RUNTIME_LOG_FILE = os.getenv('RUNTIME_LOG_FILE', os.path.join(PROJECT_DIR, 'runtime.log'))
ERROR_LOG_FILE = os.getenv('ERROR_LOG_FILE', os.path.join(PROJECT_DIR, 'errors.log'))

# Azure Application Insights (automatic logging in production)
ENABLE_APP_INSIGHTS = is_azure_deployment() and APPLICATIONINSIGHTS_CONNECTION_STRING


# ============================================================================
# SCRAPER CONFIGURATION
# ============================================================================

# Playwright settings
PLAYWRIGHT_TIMEOUT = int(os.getenv('PLAYWRIGHT_TIMEOUT', '30000'))  # milliseconds
PLAYWRIGHT_HEADLESS = os.getenv('PLAYWRIGHT_HEADLESS', 'true').lower() in ('true', '1', 'yes')

# In Azure container, always run headless
if is_azure_deployment():
    PLAYWRIGHT_HEADLESS = True

# Scraper rate limiting
SCRAPER_DELAY_SECONDS = float(os.getenv('SCRAPER_DELAY_SECONDS', '2.0'))
SCRAPER_MAX_RETRIES = int(os.getenv('SCRAPER_MAX_RETRIES', '3'))


# ============================================================================
# SCHEDULER CONFIGURATION
# ============================================================================

SCHEDULED_TASKS_DIR = os.getenv('SCHEDULED_TASKS_DIR', os.path.join(PROJECT_DIR, 'scheduled_tasks'))
Path(SCHEDULED_TASKS_DIR).mkdir(parents=True, exist_ok=True)

# Scheduler timezone
SCHEDULER_TIMEZONE = os.getenv('TZ', 'America/New_York')


# ============================================================================
# OMDB API CONFIGURATION
# ============================================================================

OMDB_API_KEY = os.getenv('OMDB_API_KEY', '')  # Get from http://www.omdbapi.com/apikey.aspx
OMDB_API_URL = 'http://www.omdbapi.com/'


# ============================================================================
# FEATURE FLAGS
# ============================================================================

# Enable/disable features based on environment
ENABLE_ADMIN_MODE = os.getenv('ENABLE_ADMIN_MODE', 'true').lower() in ('true', '1', 'yes')
ENABLE_DATA_EXPORT = os.getenv('ENABLE_DATA_EXPORT', 'true').lower() in ('true', '1', 'yes')
ENABLE_BULK_UPLOAD = os.getenv('ENABLE_BULK_UPLOAD', 'true').lower() in ('true', '1', 'yes')

# Production safety features
ENABLE_DATABASE_RESET = not is_production()  # Never allow reset in production
ENABLE_TEST_MODE = not is_production()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_config_summary():
    """
    Get a summary of current configuration (safe for logging).
    Masks sensitive values.
    
    Returns:
        dict: Configuration summary
    """
    return {
        'environment': APP_ENVIRONMENT,
        'deployment': 'azure' if is_azure_deployment() else 'local',
        'debug': DEBUG,
        'database': 'postgresql' if DATABASE_URL else 'sqlite',
        'key_vault': 'enabled' if AZURE_KEY_VAULT_URL else 'disabled',
        'app_insights': 'enabled' if ENABLE_APP_INSIGHTS else 'disabled',
        'host': HOST,
        'port': PORT,
        'version': APP_VERSION,
    }


def validate_configuration():
    """
    Validate critical configuration settings.
    Raises ValueError if required settings are missing.
    """
    errors = []
    
    # Production-specific validations
    if is_production():
        if SECRET_KEY == 'dev-secret-key-change-in-production':
            errors.append("SECRET_KEY must be changed in production")
        
        if not DATABASE_URL and not AZURE_KEY_VAULT_URL:
            errors.append("DATABASE_URL or AZURE_KEY_VAULT_URL required in production")
        
        if not APPLICATIONINSIGHTS_CONNECTION_STRING:
            errors.append("APPLICATIONINSIGHTS_CONNECTION_STRING recommended for production")
    
    # General validations
    if not os.path.exists(PROJECT_DIR):
        errors.append(f"PROJECT_DIR does not exist: {PROJECT_DIR}")
    
    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return True


def load_env_file(env_file='.env'):
    """
    Load environment variables from .env file (for local development).
    Note: In production, use Azure App Service Configuration or Key Vault.
    
    Args:
        env_file (str): Path to .env file relative to PROJECT_DIR
    """
    env_path = os.path.join(PROJECT_DIR, env_file)
    
    if not os.path.exists(env_path):
        return False
    
    try:
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and not os.getenv(key):  # Don't override existing env vars
                        os.environ[key] = value
        return True
    except Exception as e:
        print(f"Warning: Failed to load {env_file}: {e}")
        return False


def load_secrets_from_key_vault():
    """
    Load secrets from Azure Key Vault and set them as environment variables.
    """
    if AZURE_KEY_VAULT_URL:
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential

            credential = DefaultAzureCredential()
            client = SecretClient(vault_url=AZURE_KEY_VAULT_URL, credential=credential)

            secret_properties = client.list_properties_of_secrets()
            for secret_prop in secret_properties:
                secret_name = secret_prop.name
                # Secret names in Key Vault often use dashes, but env vars use underscores
                env_var_name = secret_name.replace('-', '_').upper()
                if not os.getenv(env_var_name):
                    secret_value = client.get_secret(secret_name).value
                    os.environ[env_var_name] = secret_value
            return True
        except Exception as e:
            print(f"Warning: Failed to load secrets from Key Vault: {e}")
            return False
    return False

# ============================================================================
# INITIALIZATION
# ============================================================================

# Attempt to load .env file for local development
if is_development():
    load_env_file()

# Load secrets from Key Vault if in Azure
if is_azure_deployment():
    load_secrets_from_key_vault()


# Validate configuration on import
try:
    if is_production():
        validate_configuration()
except ValueError as e:
    print(f"[WARNING] Configuration Warning: {e}")


# Print configuration summary on import (debug mode only)
if DEBUG:
    print("\n" + "="*60)
    print("PriceScout Configuration")
    print("="*60)
    summary = get_config_summary()
    for key, value in summary.items():
        print(f"  {key:20s}: {value}")
    print("="*60 + "\n")


# ============================================================================
# LEGACY COMPATIBILITY
# ============================================================================

# Keep these for backward compatibility with existing code
# New code should use environment detection functions above

# --- Constants ---
# (Legacy constants maintained for compatibility)

