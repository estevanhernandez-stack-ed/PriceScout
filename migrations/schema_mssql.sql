-- PriceScout Azure SQL (MSSQL) Schema
-- Version: 1.0.0
-- Date: November 28, 2025
-- Target: Azure SQL Database
--
-- Key differences from PostgreSQL:
-- - IDENTITY instead of SERIAL
-- - NVARCHAR instead of VARCHAR for Unicode
-- - DATETIME2 instead of TIMESTAMP WITH TIME ZONE
-- - No JSONB (use NVARCHAR(MAX) with JSON functions)
-- - Different constraint syntax
--
-- Usage:
--   sqlcmd -S <server>.database.windows.net -d pricescout -U <user> -P <password> -i schema_mssql.sql

SET NOCOUNT ON;
GO

PRINT 'Creating PriceScout Azure SQL schema...';
GO

-- ============================================================================
-- CORE TABLES: Multi-tenancy and User Management
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'companies')
BEGIN
    CREATE TABLE companies (
        company_id INT IDENTITY(1,1) PRIMARY KEY,
        company_name NVARCHAR(255) NOT NULL UNIQUE,
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        is_active BIT DEFAULT 1,
        settings NVARCHAR(MAX) DEFAULT '{}',  -- JSON string
        CONSTRAINT company_name_not_empty CHECK (LEN(company_name) > 0)
    );
    PRINT 'Created table: companies';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_companies_active')
    CREATE INDEX idx_companies_active ON companies (is_active);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_companies_name')
    CREATE INDEX idx_companies_name ON companies (company_name);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'users')
BEGIN
    CREATE TABLE users (
        user_id INT IDENTITY(1,1) PRIMARY KEY,
        username NVARCHAR(100) NOT NULL UNIQUE,
        password_hash NVARCHAR(255) NOT NULL,
        role NVARCHAR(50) NOT NULL DEFAULT 'user',
        company_id INT NULL,
        default_company_id INT NULL,
        home_location_type NVARCHAR(50) NULL,
        home_location_value NVARCHAR(255) NULL,
        allowed_modes NVARCHAR(MAX) DEFAULT '[]',  -- JSON array
        is_admin BIT DEFAULT 0,
        must_change_password BIT DEFAULT 0,
        reset_code NVARCHAR(10) NULL,
        reset_code_expiry BIGINT NULL,
        reset_attempts INT DEFAULT 0,
        session_token NVARCHAR(255) NULL,
        session_token_expiry BIGINT NULL,
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        last_login DATETIME2 NULL,
        is_active BIT DEFAULT 1,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL,
        FOREIGN KEY (default_company_id) REFERENCES companies(company_id),
        CONSTRAINT valid_role CHECK (role IN ('admin', 'manager', 'user')),
        CONSTRAINT valid_home_location CHECK (
            home_location_type IS NULL OR
            home_location_type IN ('director', 'market', 'theater')
        )
    );
    PRINT 'Created table: users';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_users_username')
    CREATE INDEX idx_users_username ON users (username);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_users_company')
    CREATE INDEX idx_users_company ON users (company_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_users_role')
    CREATE INDEX idx_users_role ON users (role);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_users_active')
    CREATE INDEX idx_users_active ON users (is_active);
GO

-- Audit log table
IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'audit_log')
BEGIN
    CREATE TABLE audit_log (
        log_id INT IDENTITY(1,1) PRIMARY KEY,
        [timestamp] DATETIME2 DEFAULT GETUTCDATE(),
        user_id INT NULL,
        username NVARCHAR(100) NULL,
        company_id INT NULL,
        event_type NVARCHAR(100) NOT NULL,
        event_category NVARCHAR(50) NOT NULL,
        severity NVARCHAR(20) DEFAULT 'info',
        details NVARCHAR(MAX) NULL,  -- JSON
        ip_address NVARCHAR(45) NULL,
        user_agent NVARCHAR(MAX) NULL,
        session_id NVARCHAR(255) NULL,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL
    );
    PRINT 'Created table: audit_log';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_audit_timestamp')
    CREATE INDEX idx_audit_timestamp ON audit_log ([timestamp] DESC);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_audit_user')
    CREATE INDEX idx_audit_user ON audit_log (user_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_audit_company')
    CREATE INDEX idx_audit_company ON audit_log (company_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_audit_event_type')
    CREATE INDEX idx_audit_event_type ON audit_log (event_type);
GO

-- ============================================================================
-- PRICING DATA TABLES
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'scrape_runs')
BEGIN
    CREATE TABLE scrape_runs (
        run_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        run_timestamp DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
        mode NVARCHAR(100) NOT NULL,
        user_id INT NULL,
        status NVARCHAR(50) DEFAULT 'completed',
        records_scraped INT DEFAULT 0,
        error_message NVARCHAR(MAX) NULL,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
    );
    PRINT 'Created table: scrape_runs';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_scrape_runs_company')
    CREATE INDEX idx_scrape_runs_company ON scrape_runs (company_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_scrape_runs_timestamp')
    CREATE INDEX idx_scrape_runs_timestamp ON scrape_runs (run_timestamp DESC);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'showings')
BEGIN
    CREATE TABLE showings (
        showing_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        play_date DATE NOT NULL,
        theater_name NVARCHAR(255) NOT NULL,
        film_title NVARCHAR(500) NOT NULL,
        showtime NVARCHAR(20) NOT NULL,
        format NVARCHAR(100) NULL,
        daypart NVARCHAR(50) NULL,
        is_plf BIT DEFAULT 0,
        ticket_url NVARCHAR(MAX) NULL,
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
        CONSTRAINT unique_showing UNIQUE (company_id, play_date, theater_name, film_title, showtime, format)
    );
    PRINT 'Created table: showings';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_showings_company')
    CREATE INDEX idx_showings_company ON showings (company_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_showings_theater_date')
    CREATE INDEX idx_showings_theater_date ON showings (company_id, theater_name, play_date);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_showings_film')
    CREATE INDEX idx_showings_film ON showings (company_id, film_title);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_showings_date')
    CREATE INDEX idx_showings_date ON showings (play_date);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'prices')
BEGIN
    CREATE TABLE prices (
        price_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        run_id INT NULL,
        showing_id INT NULL,
        ticket_type NVARCHAR(100) NOT NULL,
        price DECIMAL(6, 2) NOT NULL,
        capacity NVARCHAR(50) NULL,
        play_date DATE NULL,
        scraped_at DATETIME2 DEFAULT GETUTCDATE(),
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
        FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id) ON DELETE SET NULL,
        FOREIGN KEY (showing_id) REFERENCES showings(showing_id),
        CONSTRAINT price_positive CHECK (price >= 0)
    );
    PRINT 'Created table: prices';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_prices_company')
    CREATE INDEX idx_prices_company ON prices (company_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_prices_run')
    CREATE INDEX idx_prices_run ON prices (run_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_prices_showing')
    CREATE INDEX idx_prices_showing ON prices (showing_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_prices_date')
    CREATE INDEX idx_prices_date ON prices (play_date);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'films')
BEGIN
    CREATE TABLE films (
        film_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        film_title NVARCHAR(500) NOT NULL,
        imdb_id NVARCHAR(20) NULL,
        genre NVARCHAR(255) NULL,
        mpaa_rating NVARCHAR(20) NULL,
        director NVARCHAR(500) NULL,
        actors NVARCHAR(MAX) NULL,
        plot NVARCHAR(MAX) NULL,
        poster_url NVARCHAR(MAX) NULL,
        metascore INT NULL,
        imdb_rating DECIMAL(3, 1) NULL,
        release_date NVARCHAR(50) NULL,
        domestic_gross BIGINT NULL,
        runtime NVARCHAR(50) NULL,
        opening_weekend_domestic BIGINT NULL,
        last_omdb_update DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
        CONSTRAINT unique_film_per_company UNIQUE (company_id, film_title)
    );
    PRINT 'Created table: films';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_films_company')
    CREATE INDEX idx_films_company ON films (company_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_films_title')
    CREATE INDEX idx_films_title ON films (company_id, film_title);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_films_imdb')
    CREATE INDEX idx_films_imdb ON films (imdb_id);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'operating_hours')
BEGIN
    CREATE TABLE operating_hours (
        operating_hours_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        run_id INT NULL,
        market NVARCHAR(255) NULL,
        theater_name NVARCHAR(255) NOT NULL,
        scrape_date DATE NOT NULL,
        open_time NVARCHAR(20) NULL,
        close_time NVARCHAR(20) NULL,
        duration_hours DECIMAL(5, 2) NULL,
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
        FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id) ON DELETE SET NULL
    );
    PRINT 'Created table: operating_hours';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_operating_hours_company')
    CREATE INDEX idx_operating_hours_company ON operating_hours (company_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_operating_hours_theater_date')
    CREATE INDEX idx_operating_hours_theater_date ON operating_hours (company_id, theater_name, scrape_date);
GO

-- ============================================================================
-- PRICE ALERTS TABLE (New - from Gap Analysis)
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'price_alerts')
BEGIN
    CREATE TABLE price_alerts (
        alert_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        price_id INT NULL,
        showing_id INT NULL,
        theater_name NVARCHAR(255) NOT NULL,
        film_title NVARCHAR(500) NULL,
        ticket_type NVARCHAR(100) NULL,
        format NVARCHAR(100) NULL,
        alert_type NVARCHAR(50) NOT NULL,
        old_price DECIMAL(6, 2) NULL,
        new_price DECIMAL(6, 2) NULL,
        price_change_percent DECIMAL(5, 2) NULL,
        triggered_at DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
        play_date DATE NULL,
        is_acknowledged BIT DEFAULT 0,
        acknowledged_by INT NULL,
        acknowledged_at DATETIME2 NULL,
        acknowledgment_notes NVARCHAR(MAX) NULL,
        notification_sent BIT DEFAULT 0,
        notification_sent_at DATETIME2 NULL,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
        FOREIGN KEY (price_id) REFERENCES prices(price_id) ON DELETE SET NULL,
        FOREIGN KEY (showing_id) REFERENCES showings(showing_id),
        FOREIGN KEY (acknowledged_by) REFERENCES users(user_id) ON DELETE SET NULL,
        CONSTRAINT valid_alert_type CHECK (
            alert_type IN ('price_increase', 'price_decrease', 'new_offering', 'discontinued', 'significant_change')
        )
    );
    PRINT 'Created table: price_alerts';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_price_alerts_company')
    CREATE INDEX idx_price_alerts_company ON price_alerts (company_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_price_alerts_theater')
    CREATE INDEX idx_price_alerts_theater ON price_alerts (company_id, theater_name);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_price_alerts_triggered')
    CREATE INDEX idx_price_alerts_triggered ON price_alerts (triggered_at DESC);
GO

-- Filtered index for unacknowledged alerts
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_price_alerts_unack')
    CREATE INDEX idx_price_alerts_unack ON price_alerts (company_id, is_acknowledged)
    WHERE is_acknowledged = 0;
GO

-- ============================================================================
-- ALERT CONFIGURATIONS TABLE
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'alert_configurations')
BEGIN
    CREATE TABLE alert_configurations (
        config_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL UNIQUE,
        min_price_change_percent DECIMAL(5, 2) DEFAULT 5.0,
        min_price_change_amount DECIMAL(6, 2) DEFAULT 1.00,
        alert_on_increase BIT DEFAULT 1,
        alert_on_decrease BIT DEFAULT 1,
        alert_on_new_offering BIT DEFAULT 1,
        alert_on_discontinued BIT DEFAULT 1,
        notification_email NVARCHAR(255) NULL,
        notification_enabled BIT DEFAULT 1,
        theaters_filter NVARCHAR(MAX) DEFAULT '[]',
        ticket_types_filter NVARCHAR(MAX) DEFAULT '[]',
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        updated_at DATETIME2 DEFAULT GETUTCDATE(),
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
    );
    PRINT 'Created table: alert_configurations';
END
GO

-- ============================================================================
-- API KEYS TABLE (for rate-limited API access)
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'api_keys')
BEGIN
    CREATE TABLE api_keys (
        id INT IDENTITY(1,1) PRIMARY KEY,
        key_hash NVARCHAR(64) NOT NULL UNIQUE,
        key_prefix NVARCHAR(12) NOT NULL,
        client_name NVARCHAR(255) NOT NULL,
        tier NVARCHAR(50) NOT NULL DEFAULT 'free',
        is_active BIT DEFAULT 1,
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        expires_at DATETIME2 NULL,
        last_used_at DATETIME2 NULL,
        total_requests INT DEFAULT 0,
        notes NVARCHAR(MAX) NULL
    );
    PRINT 'Created table: api_keys';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_api_keys_hash')
    CREATE INDEX idx_api_keys_hash ON api_keys (key_hash);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_api_keys_active')
    CREATE INDEX idx_api_keys_active ON api_keys (is_active);
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'api_key_usage')
BEGIN
    CREATE TABLE api_key_usage (
        id INT IDENTITY(1,1) PRIMARY KEY,
        key_prefix NVARCHAR(12) NOT NULL,
        [timestamp] DATETIME2 DEFAULT GETUTCDATE(),
        endpoint NVARCHAR(255) NOT NULL,
        method NVARCHAR(10) NOT NULL,
        status_code INT NULL,
        response_time_ms INT NULL
    );
    PRINT 'Created table: api_key_usage';
END
GO

IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_api_usage_prefix')
    CREATE INDEX idx_api_usage_prefix ON api_key_usage (key_prefix);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_api_usage_timestamp')
    CREATE INDEX idx_api_usage_timestamp ON api_key_usage ([timestamp] DESC);
GO

-- ============================================================================
-- REFERENCE TABLES
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'unmatched_films')
BEGIN
    CREATE TABLE unmatched_films (
        unmatched_film_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        film_title NVARCHAR(500) NOT NULL,
        first_seen DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
        last_seen DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
        occurrence_count INT DEFAULT 1,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
        CONSTRAINT unique_unmatched_film UNIQUE (company_id, film_title)
    );
    PRINT 'Created table: unmatched_films';
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'ignored_films')
BEGIN
    CREATE TABLE ignored_films (
        ignored_film_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        film_title NVARCHAR(500) NOT NULL,
        reason NVARCHAR(MAX) NULL,
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        created_by INT NULL,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL,
        CONSTRAINT unique_ignored_film UNIQUE (company_id, film_title)
    );
    PRINT 'Created table: ignored_films';
END
GO

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'unmatched_ticket_types')
BEGIN
    CREATE TABLE unmatched_ticket_types (
        unmatched_ticket_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        original_description NVARCHAR(MAX) NULL,
        unmatched_part NVARCHAR(255) NULL,
        first_seen DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
        last_seen DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
        theater_name NVARCHAR(255) NULL,
        film_title NVARCHAR(500) NULL,
        showtime NVARCHAR(20) NULL,
        format NVARCHAR(100) NULL,
        play_date DATE NULL,
        occurrence_count INT DEFAULT 1,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE
    );
    PRINT 'Created table: unmatched_ticket_types';
END
GO

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert system company
IF NOT EXISTS (SELECT 1 FROM companies WHERE company_name = 'System')
BEGIN
    INSERT INTO companies (company_name, is_active, settings)
    VALUES ('System', 1, '{"type": "system", "description": "Internal system operations"}');
    PRINT 'Inserted system company';
END
GO

-- Insert default admin user (password: 'admin' - CHANGE IN PRODUCTION)
-- Password hash: bcrypt hash of 'admin'
IF NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin')
BEGIN
    DECLARE @system_company_id INT;
    SELECT @system_company_id = company_id FROM companies WHERE company_name = 'System';

    INSERT INTO users (
        username, password_hash, role, company_id, is_admin,
        allowed_modes, must_change_password
    )
    VALUES (
        'admin',
        '$2b$12$rXjXOQ3MKDxPZ.qEgMZ9HuGVVz6V0z1JVD0pXKI1J6cHpV4iU9x7a',
        'admin',
        @system_company_id,
        1,
        '["Market Mode", "Operating Hours Mode", "CompSnipe Mode", "Historical Data and Analysis", "Data Management", "Theater Matching", "Admin", "Poster Board"]',
        1
    );
    PRINT 'Inserted admin user';
END
GO

-- ============================================================================
-- VIEWS
-- ============================================================================

-- View: Recent scrape runs
IF OBJECT_ID('v_recent_scrapes', 'V') IS NOT NULL
    DROP VIEW v_recent_scrapes;
GO

CREATE VIEW v_recent_scrapes AS
SELECT
    sr.run_id,
    sr.company_id,
    c.company_name,
    sr.run_timestamp,
    sr.mode,
    sr.status,
    sr.records_scraped,
    u.username AS run_by,
    sr.error_message
FROM scrape_runs sr
JOIN companies c ON sr.company_id = c.company_id
LEFT JOIN users u ON sr.user_id = u.user_id;
GO

PRINT 'Created view: v_recent_scrapes';
GO

-- View: Pending alerts summary
IF OBJECT_ID('v_pending_alerts', 'V') IS NOT NULL
    DROP VIEW v_pending_alerts;
GO

CREATE VIEW v_pending_alerts AS
SELECT
    pa.company_id,
    c.company_name,
    pa.theater_name,
    pa.alert_type,
    COUNT(*) as alert_count,
    MIN(pa.triggered_at) as oldest_alert,
    MAX(pa.triggered_at) as newest_alert,
    AVG(ABS(pa.price_change_percent)) as avg_change_percent
FROM price_alerts pa
JOIN companies c ON pa.company_id = c.company_id
WHERE pa.is_acknowledged = 0
GROUP BY pa.company_id, c.company_name, pa.theater_name, pa.alert_type;
GO

PRINT 'Created view: v_pending_alerts';
GO

-- ============================================================================
-- COMPLETION
-- ============================================================================

PRINT '';
PRINT '============================================';
PRINT 'PriceScout Azure SQL schema created successfully!';
PRINT '============================================';
PRINT '';
PRINT 'Tables created:';
PRINT '  - companies';
PRINT '  - users';
PRINT '  - audit_log';
PRINT '  - scrape_runs';
PRINT '  - showings';
PRINT '  - prices';
PRINT '  - films';
PRINT '  - operating_hours';
PRINT '  - price_alerts';
PRINT '  - alert_configurations';
PRINT '  - api_keys';
PRINT '  - api_key_usage';
PRINT '  - unmatched_films';
PRINT '  - ignored_films';
PRINT '  - unmatched_ticket_types';
PRINT '';
PRINT 'Views created:';
PRINT '  - v_recent_scrapes';
PRINT '  - v_pending_alerts';
PRINT '';
PRINT 'Default data:';
PRINT '  - System company';
PRINT '  - Admin user (password: admin - CHANGE THIS!)';
PRINT '';
GO
