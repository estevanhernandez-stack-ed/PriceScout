-- PriceAlerts Migration for PriceScout
-- Version: 1.0.0
-- Date: November 28, 2025
-- Compatible with: PostgreSQL 14+

-- ============================================================================
-- PRICE ALERTS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS price_alerts (
    alert_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,

    -- Reference to the price that triggered the alert
    price_id INTEGER,
    showing_id INTEGER,

    -- Alert details
    theater_name VARCHAR(255) NOT NULL,
    film_title VARCHAR(500),
    ticket_type VARCHAR(100),
    format VARCHAR(100),

    -- Price change information
    alert_type VARCHAR(50) NOT NULL,  -- 'price_increase', 'price_decrease', 'new_offering', 'discontinued'
    old_price NUMERIC(6, 2),
    new_price NUMERIC(6, 2),
    price_change_percent NUMERIC(5, 2),  -- Computed: ((new - old) / old) * 100

    -- Timestamps
    triggered_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    play_date DATE,

    -- Acknowledgment
    is_acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_by INTEGER,
    acknowledged_at TIMESTAMP WITH TIME ZONE,
    acknowledgment_notes TEXT,

    -- Notification tracking
    notification_sent BOOLEAN DEFAULT FALSE,
    notification_sent_at TIMESTAMP WITH TIME ZONE,

    -- Foreign keys
    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    FOREIGN KEY (price_id) REFERENCES prices(price_id) ON DELETE SET NULL,
    FOREIGN KEY (showing_id) REFERENCES showings(showing_id) ON DELETE SET NULL,
    FOREIGN KEY (acknowledged_by) REFERENCES users(user_id) ON DELETE SET NULL,

    -- Constraints
    CONSTRAINT valid_alert_type CHECK (
        alert_type IN ('price_increase', 'price_decrease', 'new_offering', 'discontinued', 'significant_change')
    ),
    CONSTRAINT price_change_logic CHECK (
        (alert_type = 'new_offering' AND old_price IS NULL) OR
        (alert_type = 'discontinued' AND new_price IS NULL) OR
        (old_price IS NOT NULL AND new_price IS NOT NULL)
    )
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_price_alerts_company ON price_alerts (company_id);
CREATE INDEX IF NOT EXISTS idx_price_alerts_theater ON price_alerts (company_id, theater_name);
CREATE INDEX IF NOT EXISTS idx_price_alerts_triggered ON price_alerts (triggered_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_alerts_unacknowledged ON price_alerts (company_id, is_acknowledged)
    WHERE is_acknowledged = FALSE;
CREATE INDEX IF NOT EXISTS idx_price_alerts_type ON price_alerts (alert_type);

-- Comments
COMMENT ON TABLE price_alerts IS 'Price change alerts for competitor monitoring';
COMMENT ON COLUMN price_alerts.alert_type IS 'Type: price_increase, price_decrease, new_offering, discontinued, significant_change';
COMMENT ON COLUMN price_alerts.price_change_percent IS 'Percentage change: positive = increase, negative = decrease';

-- ============================================================================
-- ALERT CONFIGURATION TABLE (Optional - for threshold settings)
-- ============================================================================

CREATE TABLE IF NOT EXISTS alert_configurations (
    config_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL,

    -- Alert thresholds
    min_price_change_percent NUMERIC(5, 2) DEFAULT 5.0,  -- Only alert if change >= 5%
    min_price_change_amount NUMERIC(6, 2) DEFAULT 1.00,  -- Or change >= $1.00

    -- Alert types enabled
    alert_on_increase BOOLEAN DEFAULT TRUE,
    alert_on_decrease BOOLEAN DEFAULT TRUE,
    alert_on_new_offering BOOLEAN DEFAULT TRUE,
    alert_on_discontinued BOOLEAN DEFAULT TRUE,

    -- Notification settings
    notification_email VARCHAR(255),
    notification_enabled BOOLEAN DEFAULT TRUE,

    -- Filters
    theaters_filter JSONB DEFAULT '[]',  -- Empty = all theaters
    ticket_types_filter JSONB DEFAULT '[]',  -- Empty = all types

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (company_id) REFERENCES companies(company_id) ON DELETE CASCADE,
    CONSTRAINT unique_company_config UNIQUE (company_id)
);

CREATE INDEX IF NOT EXISTS idx_alert_config_company ON alert_configurations (company_id);

COMMENT ON TABLE alert_configurations IS 'Per-company configuration for price alert thresholds';

-- ============================================================================
-- VIEW: Unacknowledged Alerts Summary
-- ============================================================================

CREATE OR REPLACE VIEW v_pending_alerts AS
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
WHERE pa.is_acknowledged = FALSE
GROUP BY pa.company_id, c.company_name, pa.theater_name, pa.alert_type
ORDER BY COUNT(*) DESC;

-- ============================================================================
-- FUNCTION: Detect Price Changes and Create Alerts
-- ============================================================================

CREATE OR REPLACE FUNCTION detect_price_changes()
RETURNS TRIGGER AS $$
DECLARE
    prev_price NUMERIC(6, 2);
    change_percent NUMERIC(5, 2);
    alert_type_val VARCHAR(50);
    config_row alert_configurations%ROWTYPE;
BEGIN
    -- Get alert configuration for this company
    SELECT * INTO config_row
    FROM alert_configurations
    WHERE company_id = NEW.company_id;

    -- Default config if none exists
    IF NOT FOUND THEN
        config_row.min_price_change_percent := 5.0;
        config_row.min_price_change_amount := 1.00;
        config_row.alert_on_increase := TRUE;
        config_row.alert_on_decrease := TRUE;
    END IF;

    -- Find previous price for same showing + ticket type
    SELECT p.price INTO prev_price
    FROM prices p
    JOIN showings s ON p.showing_id = s.showing_id
    WHERE s.company_id = NEW.company_id
      AND s.theater_name = (SELECT theater_name FROM showings WHERE showing_id = NEW.showing_id)
      AND p.ticket_type = NEW.ticket_type
      AND p.price_id != NEW.price_id
    ORDER BY p.created_at DESC
    LIMIT 1;

    -- Calculate change if previous price exists
    IF prev_price IS NOT NULL AND prev_price > 0 THEN
        change_percent := ((NEW.price - prev_price) / prev_price) * 100;

        -- Determine alert type
        IF NEW.price > prev_price THEN
            alert_type_val := 'price_increase';
        ELSE
            alert_type_val := 'price_decrease';
        END IF;

        -- Check if change meets threshold
        IF ABS(change_percent) >= config_row.min_price_change_percent
           OR ABS(NEW.price - prev_price) >= config_row.min_price_change_amount THEN

            -- Check if this alert type is enabled
            IF (alert_type_val = 'price_increase' AND config_row.alert_on_increase)
               OR (alert_type_val = 'price_decrease' AND config_row.alert_on_decrease) THEN

                INSERT INTO price_alerts (
                    company_id, price_id, showing_id, theater_name,
                    film_title, ticket_type, format, alert_type,
                    old_price, new_price, price_change_percent, play_date
                )
                SELECT
                    NEW.company_id, NEW.price_id, NEW.showing_id, s.theater_name,
                    s.film_title, NEW.ticket_type, s.format, alert_type_val,
                    prev_price, NEW.price, change_percent, s.play_date
                FROM showings s
                WHERE s.showing_id = NEW.showing_id;
            END IF;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (disabled by default - enable when ready)
-- DROP TRIGGER IF EXISTS trigger_price_change_detection ON prices;
-- CREATE TRIGGER trigger_price_change_detection
--     AFTER INSERT ON prices
--     FOR EACH ROW
--     EXECUTE FUNCTION detect_price_changes();

-- ============================================================================
-- END OF MIGRATION
-- ============================================================================
