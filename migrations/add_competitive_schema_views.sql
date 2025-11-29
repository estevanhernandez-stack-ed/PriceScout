-- PriceScout: Add Competitive Schema Views
-- Version: 1.2.0
-- Date: November 28, 2025
-- Purpose: Create schema-compliant views matching claude.md naming standards
--
-- This creates a 'competitive' schema with views that map to existing tables,
-- providing the expected naming convention without breaking existing code.
--
-- Expected naming (claude.md):     Actual table:
--   competitive.ScrapeSources   →  scrape_sources
--   competitive.ScrapeJobs      →  scrape_runs
--   competitive.PriceChecks     →  prices + showings
--   competitive.PriceHistory    →  (computed view)
--   competitive.PriceAlerts     →  price_alerts
--   competitive.MarketAnalysis  →  (computed view)

SET NOCOUNT ON;
GO

PRINT 'Creating competitive schema and views...';
GO

-- ============================================================================
-- CREATE SCHEMA
-- ============================================================================

IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'competitive')
BEGIN
    EXEC('CREATE SCHEMA competitive');
    PRINT 'Created schema: competitive';
END
GO

-- ============================================================================
-- SCRAPE SOURCES VIEW
-- ============================================================================

IF OBJECT_ID('competitive.ScrapeSources', 'V') IS NOT NULL
    DROP VIEW competitive.ScrapeSources;
GO

CREATE VIEW competitive.ScrapeSources AS
SELECT
    source_id AS Id,
    company_id AS CompanyId,
    name AS Name,
    source_type AS SourceType,
    base_url AS BaseUrl,
    scrape_frequency_minutes AS ScrapeFrequencyMinutes,
    is_active AS IsActive,
    last_scrape_at AS LastScrapeAt,
    last_scrape_status AS LastScrapeStatus,
    last_scrape_records AS LastScrapeRecords,
    configuration AS Configuration,
    created_at AS CreatedAt,
    updated_at AS UpdatedAt
FROM scrape_sources;
GO

PRINT 'Created view: competitive.ScrapeSources';
GO

-- ============================================================================
-- SCRAPE JOBS VIEW (maps to scrape_runs)
-- ============================================================================

IF OBJECT_ID('competitive.ScrapeJobs', 'V') IS NOT NULL
    DROP VIEW competitive.ScrapeJobs;
GO

CREATE VIEW competitive.ScrapeJobs AS
SELECT
    run_id AS Id,
    source_id AS ScrapeSourceId,
    company_id AS CompanyId,
    run_timestamp AS StartedAt,
    NULL AS CompletedAt,  -- Not tracked separately
    status AS Status,
    records_scraped AS RecordsScraped,
    error_message AS ErrorMessage,
    mode AS Mode,
    user_id AS UserId
FROM scrape_runs;
GO

PRINT 'Created view: competitive.ScrapeJobs';
GO

-- ============================================================================
-- PRICE CHECKS VIEW (joins prices + showings)
-- ============================================================================

IF OBJECT_ID('competitive.PriceChecks', 'V') IS NOT NULL
    DROP VIEW competitive.PriceChecks;
GO

CREATE VIEW competitive.PriceChecks AS
SELECT
    p.price_id AS Id,
    p.run_id AS ScrapeJobId,
    p.company_id AS CompanyId,
    s.theater_name AS CompetitorLocationName,
    p.scraped_at AS CheckedAt,
    s.film_title AS MovieTitle,
    s.play_date AS ShowDate,
    s.showtime AS ShowTime,
    p.ticket_type AS TicketType,
    ISNULL(s.format, 'Standard') AS Format,
    p.price AS Price,
    NULL AS RawData  -- Not stored separately
FROM prices p
JOIN showings s ON p.showing_id = s.showing_id;
GO

PRINT 'Created view: competitive.PriceChecks';
GO

-- ============================================================================
-- PRICE HISTORY VIEW (aggregated price changes)
-- ============================================================================

IF OBJECT_ID('competitive.PriceHistory', 'V') IS NOT NULL
    DROP VIEW competitive.PriceHistory;
GO

CREATE VIEW competitive.PriceHistory AS
WITH PriceChanges AS (
    SELECT
        p.company_id,
        s.theater_name,
        p.ticket_type,
        ISNULL(s.format, 'Standard') AS format,
        s.play_date AS effective_date,
        p.price,
        LAG(p.price) OVER (
            PARTITION BY p.company_id, s.theater_name, p.ticket_type, ISNULL(s.format, 'Standard')
            ORDER BY s.play_date
        ) AS previous_price
    FROM prices p
    JOIN showings s ON p.showing_id = s.showing_id
)
SELECT
    ROW_NUMBER() OVER (ORDER BY company_id, theater_name, effective_date) AS Id,
    company_id AS CompanyId,
    theater_name AS CompetitorLocationName,
    ticket_type AS TicketType,
    format AS Format,
    effective_date AS EffectiveDate,
    price AS Price,
    previous_price AS PreviousPrice,
    CASE
        WHEN previous_price IS NOT NULL AND previous_price > 0
        THEN ROUND(((price - previous_price) / previous_price) * 100, 2)
        ELSE NULL
    END AS ChangePercent
FROM PriceChanges
WHERE previous_price IS NOT NULL AND price != previous_price;
GO

PRINT 'Created view: competitive.PriceHistory';
GO

-- ============================================================================
-- PRICE ALERTS VIEW
-- ============================================================================

IF OBJECT_ID('competitive.PriceAlerts', 'V') IS NOT NULL
    DROP VIEW competitive.PriceAlerts;
GO

CREATE VIEW competitive.PriceAlerts AS
SELECT
    alert_id AS Id,
    company_id AS CompanyId,
    theater_name AS CompetitorLocationName,
    CASE alert_type
        WHEN 'price_increase' THEN 'PriceIncrease'
        WHEN 'price_decrease' THEN 'PriceDecrease'
        WHEN 'new_offering' THEN 'NewOffering'
        WHEN 'discontinued' THEN 'Discontinued'
        ELSE alert_type
    END AS AlertType,
    triggered_at AS TriggeredAt,
    old_price AS OldPrice,
    new_price AS NewPrice,
    is_acknowledged AS IsAcknowledged,
    acknowledged_by AS AcknowledgedBy,
    acknowledged_at AS AcknowledgedAt,
    acknowledgment_notes AS Notes
FROM price_alerts;
GO

PRINT 'Created view: competitive.PriceAlerts';
GO

-- ============================================================================
-- MARKET ANALYSIS VIEW (computed positioning)
-- ============================================================================

IF OBJECT_ID('competitive.MarketAnalysis', 'V') IS NOT NULL
    DROP VIEW competitive.MarketAnalysis;
GO

CREATE VIEW competitive.MarketAnalysis AS
WITH TheaterPrices AS (
    SELECT
        p.company_id,
        s.theater_name,
        s.play_date AS analysis_date,
        p.ticket_type,
        AVG(p.price) AS avg_price
    FROM prices p
    JOIN showings s ON p.showing_id = s.showing_id
    WHERE s.play_date >= DATEADD(day, -7, GETUTCDATE())
    GROUP BY p.company_id, s.theater_name, s.play_date, p.ticket_type
),
MarketAvg AS (
    SELECT
        company_id,
        play_date AS analysis_date,
        ticket_type,
        AVG(avg_price) AS market_avg
    FROM TheaterPrices tp
    JOIN showings s ON tp.theater_name = s.theater_name
    GROUP BY company_id, play_date, ticket_type
)
SELECT
    ROW_NUMBER() OVER (ORDER BY tp.company_id, tp.theater_name, tp.analysis_date) AS Id,
    tp.company_id AS CompanyId,
    tp.theater_name AS LocationName,
    tp.analysis_date AS AnalysisDate,
    ma.market_avg AS AverageCompetitorPrice,
    tp.avg_price AS OurPrice,
    CASE
        WHEN tp.avg_price > ma.market_avg * 1.02 THEN 'Above'
        WHEN tp.avg_price < ma.market_avg * 0.98 THEN 'Below'
        ELSE 'At'
    END AS PositionVsMarket,
    ROUND(((tp.avg_price - ma.market_avg) / NULLIF(ma.market_avg, 0)) * 100, 2) AS PriceDifferencePercent,
    CASE
        WHEN tp.avg_price > ma.market_avg * 1.10 THEN 'Consider price reduction'
        WHEN tp.avg_price < ma.market_avg * 0.90 THEN 'Opportunity to increase'
        ELSE 'Maintain current pricing'
    END AS RecommendedAction
FROM TheaterPrices tp
LEFT JOIN MarketAvg ma ON tp.company_id = ma.company_id
    AND tp.analysis_date = ma.analysis_date
    AND tp.ticket_type = ma.ticket_type;
GO

PRINT 'Created view: competitive.MarketAnalysis';
GO

-- ============================================================================
-- PRICING CATEGORIES VIEW
-- ============================================================================

IF OBJECT_ID('competitive.PricingCategories', 'V') IS NOT NULL
    DROP VIEW competitive.PricingCategories;
GO

CREATE VIEW competitive.PricingCategories AS
SELECT DISTINCT
    ROW_NUMBER() OVER (ORDER BY ticket_type) AS Id,
    ticket_type AS Name,
    CASE ticket_type
        WHEN 'Adult' THEN 'Standard adult admission'
        WHEN 'Child' THEN 'Child admission (under 12)'
        WHEN 'Senior' THEN 'Senior admission (65+)'
        WHEN 'Matinee' THEN 'Matinee pricing (before 4pm)'
        WHEN 'Military' THEN 'Military discount'
        WHEN 'Student' THEN 'Student discount'
        ELSE 'Other ticket type'
    END AS Description,
    CASE ticket_type
        WHEN 'Adult' THEN 1
        WHEN 'Child' THEN 2
        WHEN 'Senior' THEN 3
        WHEN 'Matinee' THEN 4
        ELSE 10
    END AS SortOrder
FROM prices
WHERE ticket_type IS NOT NULL;
GO

PRINT 'Created view: competitive.PricingCategories';
GO

-- ============================================================================
-- COMPLETION
-- ============================================================================

PRINT '';
PRINT '============================================';
PRINT 'Competitive schema views created successfully!';
PRINT '============================================';
PRINT '';
PRINT 'Views created:';
PRINT '  - competitive.ScrapeSources';
PRINT '  - competitive.ScrapeJobs';
PRINT '  - competitive.PriceChecks';
PRINT '  - competitive.PriceHistory';
PRINT '  - competitive.PriceAlerts';
PRINT '  - competitive.MarketAnalysis';
PRINT '  - competitive.PricingCategories';
PRINT '';
PRINT 'These views provide claude.md standard naming while';
PRINT 'preserving existing table structure and code compatibility.';
PRINT '';
GO
