-- PriceScout: Add ScrapeSources Table
-- Version: 1.1.0
-- Date: November 28, 2025
-- Purpose: Add configurable scrape source management per claude.md standards

SET NOCOUNT ON;
GO

PRINT 'Adding ScrapeSources table...';
GO

-- ============================================================================
-- SCRAPE SOURCES TABLE
-- Configurable scrape sources (Fandango, AMC Direct, etc.)
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.tables WHERE name = 'scrape_sources')
BEGIN
    CREATE TABLE scrape_sources (
        source_id INT IDENTITY(1,1) PRIMARY KEY,
        company_id INT NOT NULL,
        name NVARCHAR(100) NOT NULL,
        source_type NVARCHAR(50) NOT NULL DEFAULT 'web',  -- web, api, file
        base_url NVARCHAR(500) NULL,
        scrape_frequency_minutes INT DEFAULT 60,
        is_active BIT DEFAULT 1,
        last_scrape_at DATETIME2 NULL,
        last_scrape_status NVARCHAR(50) NULL,  -- success, failed, partial
        last_scrape_records INT DEFAULT 0,
        configuration NVARCHAR(MAX) DEFAULT '{}',  -- JSON config
        created_at DATETIME2 DEFAULT GETUTCDATE(),
        updated_at DATETIME2 DEFAULT GETUTCDATE(),
        created_by INT NULL,
        FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
        FOREIGN KEY (created_by) REFERENCES users(user_id) ON DELETE SET NULL,
        CONSTRAINT unique_source_per_company UNIQUE (company_id, name),
        CONSTRAINT valid_source_type CHECK (source_type IN ('web', 'api', 'file'))
    );
    PRINT 'Created table: scrape_sources';
END
GO

-- Indexes
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_scrape_sources_company')
    CREATE INDEX idx_scrape_sources_company ON scrape_sources (company_id);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_scrape_sources_active')
    CREATE INDEX idx_scrape_sources_active ON scrape_sources (company_id, is_active);
IF NOT EXISTS (SELECT * FROM sys.indexes WHERE name = 'idx_scrape_sources_last_scrape')
    CREATE INDEX idx_scrape_sources_last_scrape ON scrape_sources (last_scrape_at DESC);
GO

-- ============================================================================
-- UPDATE SCRAPE_RUNS TO REFERENCE SCRAPE_SOURCES
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('scrape_runs') AND name = 'source_id')
BEGIN
    ALTER TABLE scrape_runs ADD source_id INT NULL;
    PRINT 'Added source_id column to scrape_runs';
END
GO

-- Add foreign key if not exists
IF NOT EXISTS (SELECT * FROM sys.foreign_keys WHERE name = 'FK_scrape_runs_source')
BEGIN
    ALTER TABLE scrape_runs
    ADD CONSTRAINT FK_scrape_runs_source
    FOREIGN KEY (source_id) REFERENCES scrape_sources(source_id) ON DELETE SET NULL;
    PRINT 'Added foreign key FK_scrape_runs_source';
END
GO

-- ============================================================================
-- SEED DEFAULT SCRAPE SOURCES
-- ============================================================================

DECLARE @system_company_id INT;
SELECT @system_company_id = company_id FROM companies WHERE company_name = 'System';

IF @system_company_id IS NOT NULL
BEGIN
    IF NOT EXISTS (SELECT 1 FROM scrape_sources WHERE company_id = @system_company_id AND name = 'Fandango')
    BEGIN
        INSERT INTO scrape_sources (company_id, name, source_type, base_url, scrape_frequency_minutes, is_active, configuration)
        VALUES (
            @system_company_id,
            'Fandango',
            'web',
            'https://www.fandango.com',
            60,
            1,
            '{"parser": "playwright", "delay_ms": 2000, "retry_count": 3}'
        );
        PRINT 'Inserted Fandango scrape source';
    END

    IF NOT EXISTS (SELECT 1 FROM scrape_sources WHERE company_id = @system_company_id AND name = 'Box Office Mojo')
    BEGIN
        INSERT INTO scrape_sources (company_id, name, source_type, base_url, scrape_frequency_minutes, is_active, configuration)
        VALUES (
            @system_company_id,
            'Box Office Mojo',
            'web',
            'https://www.boxofficemojo.com',
            1440,
            1,
            '{"parser": "playwright", "delay_ms": 1000, "retry_count": 2}'
        );
        PRINT 'Inserted Box Office Mojo scrape source';
    END
END
GO

PRINT '';
PRINT 'ScrapeSources migration complete!';
GO
