-- PriceScout Unified PostgreSQL Schema
-- Version: 1.0.0
-- Date: November 13, 2025
-- Purpose: Unified multi-tenant schema for Azure PostgreSQL migration
-- Supports: Company isolation, RBAC, audit logging, pricing data

-- ============================================================================
-- CORE TABLES: Multi-tenancy and User Management
-- ============================================================================

-- Companies table: Multi-tenancy foundation
CREATE TABLE IF NOT EXISTS companies (
    company_id SERIAL PRIMARY KEY,
    company_name VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    settings JSONB DEFAULT '{}',  -- Company-specific configuration
    CONSTRAINT company_name_not_empty CHECK (char_length(company_name) > 0)
);

CREATE INDEX idx_companies_active ON companies (is_active);
CREATE INDEX idx_companies_name ON companies (company_name);

-- Users table: Authentication and RBAC (migrated from users.db)
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    company_id INTEGER,
    default_company_id INTEGER,  -- For multi-company users
    home_location_type VARCHAR(50),  -- 'director', 'market', or 'theater'
    home_location_value VARCHAR(255),
    allowed_modes JSONB DEFAULT '[]',  -- Sidebar mode permissions
    is_admin BOOLEAN DEFAULT FALSE,
    must_change_password BOOLEAN DEFAULT FALSE,
    reset_code VARCHAR(10),
    reset_code_expiry BIGINT,
    reset_attempts INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL,
    FOREIGN KEY (default_company_id) REFERENCES companies(company_id) ON DELETE SET NULL,
    CONSTRAINT valid_role CHECK (role IN ('admin', 'manager', 'user')),
    CONSTRAINT valid_home_location CHECK (
        home_location_type IS NULL OR 
        home_location_type IN ('director', 'market', 'theater')
    )
);

CREATE INDEX idx_users_username ON users (username);
CREATE INDEX idx_users_company ON users (company_id);
CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_active ON users (is_active);

-- Audit log: Security and compliance tracking
CREATE TABLE IF NOT EXISTS audit_log (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    user_id INTEGER,
    username VARCHAR(100),
    company_id INTEGER,
    event_type VARCHAR(100) NOT NULL,  -- 'login', 'logout', 'data_access', 'config_change', etc.
    event_category VARCHAR(50) NOT NULL,  -- 'authentication', 'authorization', 'data', 'system'
    severity VARCHAR(20) DEFAULT 'info',  -- 'info', 'warning', 'error', 'critical'
    details JSONB,
    ip_address INET,
    user_agent TEXT,
    session_id VARCHAR(255),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE SET NULL
);

CREATE INDEX idx_audit_timestamp ON audit_log (timestamp DESC);
CREATE INDEX idx_audit_user ON audit_log (user_id);
CREATE INDEX idx_audit_company ON audit_log (company_id);
CREATE INDEX idx_audit_event_type ON audit_log (event_type);
CREATE INDEX idx_audit_severity ON audit_log (severity);

-- ============================================================================
-- PRICING DATA TABLES: Scraped theater and film information
-- ============================================================================

-- Scrape runs: Track data collection sessions
CREATE TABLE IF NOT EXISTS scrape_runs (
    run_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    run_timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    mode VARCHAR(100) NOT NULL,  -- 'market', 'operating_hours', 'compsnipe', etc.
    user_id INTEGER,
    status VARCHAR(50) DEFAULT 'completed',  -- 'running', 'completed', 'failed'
    records_scraped INTEGER DEFAULT 0,
    error_message TEXT,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE SET NULL
);

CREATE INDEX idx_scrape_runs_company ON scrape_runs (company_id);
CREATE INDEX idx_scrape_runs_timestamp ON scrape_runs (run_timestamp DESC);
CREATE INDEX idx_scrape_runs_mode ON scrape_runs (mode);

-- Showings: Theater screening information
CREATE TABLE IF NOT EXISTS showings (
    showing_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    play_date DATE NOT NULL,
    theater_name VARCHAR(255) NOT NULL,
    film_title VARCHAR(500) NOT NULL,
    showtime VARCHAR(20) NOT NULL,
    format VARCHAR(100),  -- '2D', '3D', 'IMAX', 'Dolby', etc.
    daypart VARCHAR(50),  -- 'matinee', 'evening', 'late_night'
    is_plf BOOLEAN DEFAULT FALSE,  -- Premium Large Format
    ticket_url TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT unique_showing UNIQUE (company_id, play_date, theater_name, film_title, showtime, format)
);

CREATE INDEX idx_showings_company ON showings (company_id);
CREATE INDEX idx_showings_theater_date ON showings (company_id, theater_name, play_date);
CREATE INDEX idx_showings_film ON showings (company_id, film_title);
CREATE INDEX idx_showings_date ON showings (play_date);

-- Prices: Ticket pricing data
CREATE TABLE IF NOT EXISTS prices (
    price_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    run_id INTEGER,
    showing_id INTEGER,
    ticket_type VARCHAR(100) NOT NULL,  -- 'Adult', 'Senior', 'Child', etc.
    price NUMERIC(6, 2) NOT NULL,
    capacity VARCHAR(50),  -- Optional: theater capacity info
    play_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id) ON DELETE SET NULL,
    FOREIGN KEY (showing_id) REFERENCES showings(showing_id) ON DELETE CASCADE,
    CONSTRAINT price_positive CHECK (price >= 0)
);

CREATE INDEX idx_prices_company ON prices (company_id);
CREATE INDEX idx_prices_run ON prices (run_id);
CREATE INDEX idx_prices_showing ON prices (showing_id);
CREATE INDEX idx_prices_date ON prices (play_date);

-- Films: Movie metadata (OMDB/IMDB data)
CREATE TABLE IF NOT EXISTS films (
    film_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    film_title VARCHAR(500) NOT NULL,
    imdb_id VARCHAR(20),
    genre VARCHAR(255),
    mpaa_rating VARCHAR(20),
    director VARCHAR(500),
    actors TEXT,
    plot TEXT,
    poster_url TEXT,
    metascore INTEGER,
    imdb_rating NUMERIC(3, 1),
    release_date VARCHAR(50),
    domestic_gross BIGINT,
    runtime VARCHAR(50),
    opening_weekend_domestic BIGINT,
    last_omdb_update TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT unique_film_per_company UNIQUE (company_id, film_title)
);

CREATE INDEX idx_films_company ON films (company_id);
CREATE INDEX idx_films_title ON films (company_id, film_title);
CREATE INDEX idx_films_imdb ON films (imdb_id);
CREATE INDEX idx_films_release_date ON films (release_date);

-- Operating hours: Theater operating schedules
CREATE TABLE IF NOT EXISTS operating_hours (
    operating_hours_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    run_id INTEGER,
    market VARCHAR(255),
    theater_name VARCHAR(255) NOT NULL,
    scrape_date DATE NOT NULL,
    open_time VARCHAR(20),
    close_time VARCHAR(20),
    duration_hours NUMERIC(5, 2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES scrape_runs(run_id) ON DELETE SET NULL
);

CREATE INDEX idx_operating_hours_company ON operating_hours (company_id);
CREATE INDEX idx_operating_hours_theater_date ON operating_hours (company_id, theater_name, scrape_date);
CREATE INDEX idx_operating_hours_market ON operating_hours (company_id, market);

-- ============================================================================
-- REFERENCE AND ERROR TRACKING TABLES
-- ============================================================================

-- Unmatched films: Films that couldn't be matched to OMDB
CREATE TABLE IF NOT EXISTS unmatched_films (
    unmatched_film_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    film_title VARCHAR(500) NOT NULL,
    first_seen TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    occurrence_count INTEGER DEFAULT 1,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT unique_unmatched_film UNIQUE (company_id, film_title)
);

CREATE INDEX idx_unmatched_films_company ON unmatched_films (company_id);
CREATE INDEX idx_unmatched_films_title ON unmatched_films (film_title);

-- Ignored films: Films intentionally excluded from processing
CREATE TABLE IF NOT EXISTS ignored_films (
    ignored_film_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    film_title VARCHAR(500) NOT NULL,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL,
    CONSTRAINT unique_ignored_film UNIQUE (company_id, film_title)
);

CREATE INDEX idx_ignored_films_company ON ignored_films (company_id);

-- Unmatched ticket types: Ticket descriptions that couldn't be parsed
CREATE TABLE IF NOT EXISTS unmatched_ticket_types (
    unmatched_ticket_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,
    original_description TEXT,
    unmatched_part VARCHAR(255),
    first_seen TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    theater_name VARCHAR(255),
    film_title VARCHAR(500),
    showtime VARCHAR(20),
    format VARCHAR(100),
    play_date DATE,
    occurrence_count INTEGER DEFAULT 1,
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT unique_unmatched_ticket UNIQUE (company_id, unmatched_part, theater_name, film_title, play_date)
);

CREATE INDEX idx_unmatched_tickets_company ON unmatched_ticket_types (company_id);
CREATE INDEX idx_unmatched_tickets_theater ON unmatched_ticket_types (company_id, theater_name);

-- ============================================================================
-- INITIAL DATA: Default admin user and system company
-- ============================================================================

-- Insert system company (for shared resources and admin operations)
INSERT INTO companies (company_name, is_active, settings)
VALUES ('System', TRUE, '{"type": "system", "description": "Internal system operations"}')
ON CONFLICT (company_name) DO NOTHING;

-- Insert default admin user (password: 'admin' - MUST BE CHANGED IN PRODUCTION)
-- Password hash generated with bcrypt: bcrypt.hashpw(b'admin', bcrypt.gensalt())
INSERT INTO users (
    username, 
    password_hash, 
    role, 
    company_id, 
    is_admin, 
    allowed_modes,
    must_change_password
)
VALUES (
    'admin',
    '$2b$12$rXjXOQ3MKDxPZ.qEgMZ9HuGVVz6V0z1JVD0pXKI1J6cHpV4iU9x7a',  -- 'admin'
    'admin',
    (SELECT company_id FROM companies WHERE company_name = 'System'),
    TRUE,
    '["Market Mode", "Operating Hours Mode", "CompSnipe Mode", "Historical Data and Analysis", "Data Management", "Theater Matching", "Admin", "Poster Board"]',
    TRUE  -- Force password change on first login
)
ON CONFLICT (username) DO NOTHING;

-- ============================================================================
-- VIEWS: Convenient data access patterns
-- ============================================================================

-- View: Recent scrape runs with user information
CREATE OR REPLACE VIEW v_recent_scrapes AS
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
LEFT JOIN users u ON sr.user_id = u.user_id
ORDER BY sr.run_timestamp DESC;

-- View: Pricing summary by theater and date
CREATE OR REPLACE VIEW v_pricing_summary AS
SELECT 
    s.company_id,
    c.company_name,
    s.theater_name,
    s.play_date,
    s.film_title,
    COUNT(DISTINCT s.showing_id) AS showing_count,
    COUNT(p.price_id) AS price_count,
    MIN(p.price) AS min_price,
    MAX(p.price) AS max_price,
    AVG(p.price) AS avg_price
FROM showings s
JOIN companies c ON s.company_id = c.company_id
LEFT JOIN prices p ON s.showing_id = p.showing_id
GROUP BY s.company_id, c.company_name, s.theater_name, s.play_date, s.film_title
ORDER BY s.play_date DESC, s.theater_name, s.film_title;

-- View: Film performance metrics
CREATE OR REPLACE VIEW v_film_metrics AS
SELECT 
    f.company_id,
    c.company_name,
    f.film_title,
    f.imdb_rating,
    f.metascore,
    f.domestic_gross,
    f.opening_weekend_domestic,
    COUNT(DISTINCT s.showing_id) AS total_showings,
    COUNT(DISTINCT s.theater_name) AS theater_count,
    MIN(s.play_date) AS first_showing,
    MAX(s.play_date) AS last_showing
FROM films f
JOIN companies c ON f.company_id = c.company_id
LEFT JOIN showings s ON f.company_id = s.company_id AND f.film_title = s.film_title
GROUP BY f.company_id, c.company_name, f.film_title, f.imdb_rating, 
         f.metascore, f.domestic_gross, f.opening_weekend_domestic
ORDER BY f.company_id, f.film_title;

-- ============================================================================
-- FUNCTIONS: Business logic helpers
-- ============================================================================

-- Function: Update unmatched film occurrence
CREATE OR REPLACE FUNCTION update_unmatched_film_occurrence(
    p_company_id INTEGER,
    p_film_title VARCHAR(500)
) RETURNS VOID AS $$
BEGIN
    INSERT INTO unmatched_films (company_id, film_title, first_seen, last_seen, occurrence_count)
    VALUES (p_company_id, p_film_title, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
    ON CONFLICT (company_id, film_title) 
    DO UPDATE SET 
        last_seen = CURRENT_TIMESTAMP,
        occurrence_count = unmatched_films.occurrence_count + 1;
END;
$$ LANGUAGE plpgsql;

-- Function: Update unmatched ticket type occurrence
CREATE OR REPLACE FUNCTION update_unmatched_ticket_occurrence(
    p_company_id INTEGER,
    p_unmatched_part VARCHAR(255),
    p_theater_name VARCHAR(255),
    p_film_title VARCHAR(500),
    p_play_date DATE,
    p_original_description TEXT,
    p_showtime VARCHAR(20),
    p_format VARCHAR(100)
) RETURNS VOID AS $$
BEGIN
    INSERT INTO unmatched_ticket_types (
        company_id, unmatched_part, theater_name, film_title, play_date,
        original_description, showtime, format, first_seen, last_seen, occurrence_count
    )
    VALUES (
        p_company_id, p_unmatched_part, p_theater_name, p_film_title, p_play_date,
        p_original_description, p_showtime, p_format, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1
    )
    ON CONFLICT (company_id, unmatched_part, theater_name, film_title, play_date)
    DO UPDATE SET
        last_seen = CURRENT_TIMESTAMP,
        occurrence_count = unmatched_ticket_types.occurrence_count + 1,
        original_description = p_original_description,
        showtime = p_showtime,
        format = p_format;
END;
$$ LANGUAGE plpgsql;

-- Function: Clean up old audit logs (retention policy)
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs(
    retention_days INTEGER DEFAULT 90
) RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM audit_log
    WHERE timestamp < CURRENT_TIMESTAMP - (retention_days || ' days')::INTERVAL
    AND severity IN ('info', 'warning');  -- Keep error and critical logs longer
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS): Multi-tenant data isolation
-- ============================================================================

-- Enable RLS on all company-scoped tables
ALTER TABLE scrape_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE showings ENABLE ROW LEVEL SECURITY;
ALTER TABLE prices ENABLE ROW LEVEL SECURITY;
ALTER TABLE films ENABLE ROW LEVEL SECURITY;
ALTER TABLE operating_hours ENABLE ROW LEVEL SECURITY;
ALTER TABLE unmatched_films ENABLE ROW LEVEL SECURITY;
ALTER TABLE ignored_films ENABLE ROW LEVEL SECURITY;
ALTER TABLE unmatched_ticket_types ENABLE ROW LEVEL SECURITY;

-- Note: RLS policies will be created by application layer based on user's company_id
-- Example policy (to be implemented in application):
-- CREATE POLICY company_isolation ON showings
-- FOR ALL TO app_user
-- USING (company_id = current_setting('app.current_company_id')::INTEGER);

-- ============================================================================
-- GRANTS: Default permissions for application user
-- ============================================================================

-- Note: Execute these after creating the application database user
-- CREATE USER pricescout_app WITH PASSWORD 'secure_password_from_keyvault';

-- GRANT CONNECT ON DATABASE pricescout_db TO pricescout_app;
-- GRANT USAGE ON SCHEMA public TO pricescout_app;
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO pricescout_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO pricescout_app;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO pricescout_app;

-- ============================================================================
-- MAINTENANCE: Automated cleanup jobs
-- ============================================================================

-- Note: Set up periodic cleanup job in Azure (via pg_cron or Azure Automation)
-- Example: SELECT cleanup_old_audit_logs(90);  -- Run weekly

-- ============================================================================
-- COMMENTS: Documentation for future reference
-- ============================================================================

COMMENT ON TABLE companies IS 'Multi-tenant companies with isolated data access';
COMMENT ON TABLE users IS 'Application users with RBAC (admin/manager/user roles)';
COMMENT ON TABLE audit_log IS 'Security audit trail for compliance and debugging';
COMMENT ON TABLE scrape_runs IS 'Data collection sessions tracking';
COMMENT ON TABLE showings IS 'Theater screening schedules with pricing';
COMMENT ON TABLE prices IS 'Ticket pricing data by type (Adult/Senior/Child/etc)';
COMMENT ON TABLE films IS 'Movie metadata from OMDB/IMDB enrichment';
COMMENT ON TABLE operating_hours IS 'Theater daily operating schedules';
COMMENT ON TABLE unmatched_films IS 'Films that failed OMDB matching (needs review)';
COMMENT ON TABLE ignored_films IS 'Films intentionally excluded from processing';
COMMENT ON TABLE unmatched_ticket_types IS 'Unparseable ticket descriptions (needs review)';

COMMENT ON COLUMN users.allowed_modes IS 'JSON array of permitted sidebar modes';
COMMENT ON COLUMN users.home_location_type IS 'User home context: director/market/theater';
COMMENT ON COLUMN users.must_change_password IS 'Force password change on next login';
COMMENT ON COLUMN showings.is_plf IS 'Premium Large Format (IMAX, Dolby Cinema, etc)';
COMMENT ON COLUMN prices.capacity IS 'Optional theater capacity metadata';

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
