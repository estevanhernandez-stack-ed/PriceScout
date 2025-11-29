# PriceScout Operations Runbook

> **Document Version:** 1.0
> **Last Updated:** November 28, 2025
> **Owner:** Estevan Hernandez / 626labs LLC
> **Status:** Production

---

## Overview

This runbook provides operational procedures for PriceScout, including routine maintenance, monitoring, troubleshooting, and incident response.

---

## Quick Reference

| Resource | URL/Command |
|----------|-------------|
| **Production App** | https://www.marketpricescout.com |
| **API Docs** | https://api.pricescout.io/api/v1/docs |
| **Azure Portal** | https://portal.azure.com → `rg-pricescout-prod` |
| **App Insights** | Azure Portal → `pricescout-appinsights` |
| **Health Check** | `GET /api/v1/health` |
| **Logs** | Azure Portal → App Service → Log stream |

---

## Daily Operations

### Morning Health Check (5 min)

1. **Check application health:**
   ```bash
   curl https://api.pricescout.io/api/v1/health
   ```
   Expected: `{"status": "healthy", "database": "connected"}`

2. **Review overnight scrapes:**
   - Open App Insights → Transaction Search
   - Filter: `customDimensions.scraper.status = "completed"`
   - Verify scrapes ran successfully

3. **Check pending alerts:**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.pricescout.io/api/v1/price-alerts/summary
   ```

### Weekly Tasks

| Task | Frequency | Procedure |
|------|-----------|-----------|
| Review error rates | Weekly | App Insights → Failures blade |
| Check database size | Weekly | Azure Portal → SQL Database → Metrics |
| Verify backups | Weekly | Azure Portal → SQL → Backups |
| Review API usage | Weekly | APIM → Analytics |

---

## Monitoring

### Key Metrics to Watch

| Metric | Normal Range | Alert Threshold |
|--------|--------------|-----------------|
| API Response Time (P95) | < 500ms | > 2000ms |
| Error Rate | < 1% | > 5% |
| Scrape Success Rate | > 95% | < 80% |
| Database DTU Usage | < 60% | > 85% |
| App Service CPU | < 70% | > 90% |

### Application Insights Queries

**Failed Scrapes (last 24h):**
```kusto
traces
| where timestamp > ago(24h)
| where message contains "scrape" and severityLevel >= 3
| summarize count() by bin(timestamp, 1h)
```

**Slow API Calls:**
```kusto
requests
| where timestamp > ago(1h)
| where duration > 2000
| project timestamp, name, duration, resultCode
| order by duration desc
```

**Price Alerts Generated:**
```kusto
customEvents
| where name == "PriceAlertGenerated"
| where timestamp > ago(24h)
| summarize count() by tostring(customDimensions.alert_type)
```

---

## Common Procedures

### Manually Trigger a Scrape

**Via API:**
```bash
# Get source ID
curl -H "Authorization: Bearer $TOKEN" \
  https://api.pricescout.io/api/v1/scrape-sources

# Trigger scrape
curl -X POST -H "Authorization: Bearer $TOKEN" \
  https://api.pricescout.io/api/v1/scrape-jobs/trigger/{source_id}
```

**Via Azure Portal:**
1. Go to Service Bus → Queues → `scrape-queue`
2. Send message: `{"source_id": 1, "triggered_by": "manual"}`

### Restart Application

**Soft Restart (no downtime):**
```powershell
az webapp restart --name app-pricescout-prod --resource-group rg-pricescout-prod
```

**Hard Restart (brief downtime):**
```powershell
az webapp stop --name app-pricescout-prod --resource-group rg-pricescout-prod
Start-Sleep -Seconds 10
az webapp start --name app-pricescout-prod --resource-group rg-pricescout-prod
```

### Scale Up/Down

```powershell
# Scale up to P1v2 (more resources)
az appservice plan update --name asp-pricescout-prod \
  --resource-group rg-pricescout-prod --sku P1V2

# Scale down to B1 (cost savings)
az appservice plan update --name asp-pricescout-prod \
  --resource-group rg-pricescout-prod --sku B1
```

### Database Maintenance

**Check table sizes:**
```sql
SELECT
    t.name AS TableName,
    p.rows AS RowCount,
    SUM(a.total_pages) * 8 / 1024 AS TotalSpaceMB
FROM sys.tables t
JOIN sys.partitions p ON t.object_id = p.object_id
JOIN sys.allocation_units a ON p.partition_id = a.container_id
GROUP BY t.name, p.rows
ORDER BY TotalSpaceMB DESC;
```

**Purge old data (retain 90 days):**
```sql
DELETE FROM prices WHERE scraped_at < DATEADD(day, -90, GETUTCDATE());
DELETE FROM showings WHERE created_at < DATEADD(day, -90, GETUTCDATE());
DELETE FROM audit_log WHERE timestamp < DATEADD(day, -90, GETUTCDATE());
```

---

## Troubleshooting

### Issue: Scrapes Failing

**Symptoms:** No new price data, scrape jobs showing "failed" status

**Diagnosis:**
1. Check App Insights for errors:
   ```kusto
   exceptions
   | where timestamp > ago(1h)
   | where outerMessage contains "scrape" or outerMessage contains "playwright"
   ```

2. Check if Fandango site structure changed:
   - Manually visit Fandango in browser
   - Compare HTML to expected selectors

**Resolution:**
- If site structure changed: Update selectors in `app/scraper.py`
- If rate limited: Increase delay in scrape source configuration
- If Playwright issue: Reinstall browsers: `playwright install chromium`

---

### Issue: High API Latency

**Symptoms:** P95 response time > 2s, user complaints

**Diagnosis:**
1. Check database DTU:
   ```powershell
   az sql db show --name pricescout --server sql-pricescout-prod \
     --resource-group rg-pricescout-prod --query "currentSku"
   ```

2. Check slow queries in App Insights

**Resolution:**
- Scale up database tier if DTU > 85%
- Add missing indexes based on query analysis
- Enable query caching for common requests

---

### Issue: Authentication Failures

**Symptoms:** Users can't log in, 401 errors

**Diagnosis:**
1. Check Entra ID app status in Azure Portal
2. Verify client secret hasn't expired
3. Check Key Vault access

**Resolution:**
- Rotate Entra ID client secret if expired
- Verify redirect URIs match deployment URL
- Check `ENTRA_ENABLED` environment variable

---

### Issue: Missing Price Alerts

**Symptoms:** Price changes not generating alerts

**Diagnosis:**
1. Check alert configuration:
   ```sql
   SELECT * FROM alert_configurations WHERE notification_enabled = 1;
   ```

2. Verify price change thresholds being met

**Resolution:**
- Adjust `min_price_change_percent` threshold
- Verify scrape data is being collected
- Check alert generation logic in `app/scraper.py`

---

## Incident Response

### Severity Levels

| Level | Definition | Response Time | Example |
|-------|------------|---------------|---------|
| SEV1 | Complete outage | 15 min | App unreachable |
| SEV2 | Major feature broken | 1 hour | Scraping failing |
| SEV3 | Minor feature broken | 4 hours | Single report failing |
| SEV4 | Cosmetic/minor | Next business day | UI glitch |

### SEV1 Response Procedure

1. **Acknowledge** - Confirm incident received
2. **Assess** - Check health endpoint, App Insights, logs
3. **Communicate** - Notify stakeholders
4. **Mitigate** - Restart app, scale up, or rollback
5. **Resolve** - Fix root cause
6. **Document** - Post-incident review

### Rollback Procedure

```powershell
# List deployment history
az webapp deployment list --name app-pricescout-prod \
  --resource-group rg-pricescout-prod

# Rollback to previous slot
az webapp deployment slot swap --name app-pricescout-prod \
  --resource-group rg-pricescout-prod \
  --slot staging --target-slot production
```

---

## Security Procedures

### Rotate Secrets

**Database Password:**
```powershell
# Generate new password
$newPassword = [System.Web.Security.Membership]::GeneratePassword(24,4)

# Update in Azure SQL
az sql server update --name sql-pricescout-prod \
  --resource-group rg-pricescout-prod \
  --admin-password $newPassword

# Update in Key Vault
az keyvault secret set --vault-name kv-pricescout-prod \
  --name DatabasePassword --value $newPassword

# Restart app to pick up new secret
az webapp restart --name app-pricescout-prod --resource-group rg-pricescout-prod
```

**API Keys:**
```bash
# Revoke compromised key
curl -X DELETE -H "Authorization: Bearer $ADMIN_TOKEN" \
  https://api.pricescout.io/api/v1/api-keys/{key_id}

# Generate new key via admin panel
```

### Audit Log Review

```sql
SELECT TOP 100
    timestamp, username, event_type, event_category,
    severity, ip_address, details
FROM audit_log
WHERE severity IN ('warning', 'error', 'critical')
ORDER BY timestamp DESC;
```

---

## Backup & Recovery

### Automated Backups

| Resource | Backup Type | Retention | Location |
|----------|-------------|-----------|----------|
| Azure SQL | Point-in-time | 7 days | Same region |
| Azure SQL | Long-term | 90 days | Paired region |
| Key Vault | Soft delete | 90 days | Same vault |
| App Config | Export | Manual | Storage account |

### Restore Database

**Point-in-time restore:**
```powershell
az sql db restore --dest-name pricescout-restored \
  --name pricescout \
  --server sql-pricescout-prod \
  --resource-group rg-pricescout-prod \
  --time "2025-11-28T12:00:00Z"
```

---

## Contacts

| Role | Contact | Escalation |
|------|---------|------------|
| On-Call Developer | Estevan Hernandez | Primary |
| Azure Support | Azure Portal | SEV1 only |

---

## Appendix: Environment Variables

| Variable | Purpose | Source |
|----------|---------|--------|
| `DATABASE_URL` | SQL connection string | Key Vault |
| `SECRET_KEY` | Session encryption | Key Vault |
| `OMDB_API_KEY` | Film metadata API | Key Vault |
| `ENTRA_CLIENT_ID` | SSO app ID | Key Vault |
| `ENTRA_CLIENT_SECRET` | SSO secret | Key Vault |
| `ENTRA_TENANT_ID` | Azure AD tenant | Key Vault |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | Telemetry | App Settings |

---

*Last updated: November 28, 2025*
