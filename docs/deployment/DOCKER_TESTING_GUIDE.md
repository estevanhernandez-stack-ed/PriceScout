# Docker Testing Guide

**Version:** 1.0.0  
**Last Updated:** November 13, 2025  
**Status:** Phase 1 Complete - Ready for Local Testing

---

## Overview

This guide covers local Docker testing of PriceScout before Azure deployment. We'll verify the containerized application works with PostgreSQL and Playwright browser automation.

---

## Prerequisites

### Required Software

- **Docker Desktop**: Version 4.25.0+
  - Download: https://www.docker.com/products/docker-desktop/
  - Includes Docker Engine and Docker Compose

- **PowerShell**: Version 7+ (recommended)
  - Download: https://github.com/PowerShell/PowerShell/releases

### System Requirements

- **OS**: Windows 10/11, macOS, or Linux
- **RAM**: 8GB minimum (16GB recommended)
- **Disk**: 10GB free space for images and volumes
- **CPU**: 4+ cores recommended for Playwright

---

## Quick Start

### 1. Build and Start Services

```powershell
# Navigate to project directory
cd "c:\Users\estev\Desktop\Price Scout"

# Start PostgreSQL + PriceScout
docker-compose up -d

# View logs
docker-compose logs -f pricescout
```

**Expected Output:**
```
✓ Container pricescout-postgres  Healthy
✓ Container pricescout-app       Started
```

### 2. Verify Application

Open browser to: **http://localhost:8000**

**Login Credentials:**
- Username: `admin`
- Password: `admin`

### 3. Test Health Check

```powershell
# Check health endpoint
curl http://localhost:8000/_stcore/health

# Expected: HTTP 200 OK
```

### 4. Stop Services

```powershell
# Stop containers (preserve data)
docker-compose down

# Stop containers and remove volumes (clean slate)
docker-compose down -v
```

---

## Configuration

### Environment Variables

Create `.env` file in project root:

```env
# PostgreSQL password
POSTGRES_PASSWORD=strong_password_here

# Application secret
SECRET_KEY=your-secret-key-here

# Optional: OMDB API key
OMDB_API_KEY=your_omdb_key

# Optional: pgAdmin password
PGADMIN_PASSWORD=admin_password
```

### Docker Compose Services

**Included by default:**
- `postgres` - PostgreSQL 14 database
- `pricescout` - Main application

**Optional (uncomment in docker-compose.yml):**
- `redis` - Cache service
- `pgadmin` - Database management UI (http://localhost:5050)

---

## Testing Scenarios

### Test 1: PostgreSQL Connection

```powershell
# Connect to database
docker exec -it pricescout-postgres psql -U pricescout_app -d pricescout_db

# Run test query
SELECT COUNT(*) FROM companies;
# Expected: 1 (default "System" company)

# Exit
\q
```

### Test 2: Schema Verification

```sql
-- List all tables
\dt

-- Expected tables:
-- companies, users, audit_log, scrape_runs, showings, prices, 
-- films, operating_hours, unmatched_films, ignored_films, 
-- unmatched_ticket_types
```

### Test 3: User Authentication

1. Open http://localhost:8000
2. Login with admin/admin
3. Verify main dashboard loads
4. Check sidebar for navigation options

### Test 4: Playwright Browser

```powershell
# Check Chromium installation
docker exec -it pricescout-app playwright --version

# Expected: Version 1.55.0
```

### Test 5: Data Persistence

```powershell
# Create test data in application
# Stop containers
docker-compose down

# Restart
docker-compose up -d

# Verify data still exists
```

---

## Troubleshooting

### Issue: Port Already in Use

**Symptom:**
```
Error starting userland proxy: listen tcp 0.0.0.0:8000: bind: address already in use
```

**Solution:**
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process (replace PID)
taskkill /PID <PID> /F

# Or change port in docker-compose.yml
ports:
  - "8001:8000"  # Map to different host port
```

### Issue: PostgreSQL Won't Start

**Symptom:**
```
pricescout-postgres | ERROR: database files are incompatible with server
```

**Solution:**
```powershell
# Remove volume and recreate
docker-compose down -v
docker-compose up -d
```

### Issue: Application Crashes on Startup

**Check logs:**
```powershell
docker-compose logs pricescout
```

**Common causes:**
- Database not ready (wait 30s for health check)
- Missing environment variables
- Port conflict

**Solution:**
```powershell
# Restart with clean state
docker-compose down -v
docker-compose up -d

# Wait for health check
docker-compose ps
```

### Issue: Health Check Failing

**Symptom:**
```
pricescout-app | Health: starting
```

**Check:**
```powershell
# View health check output
docker inspect pricescout-app --format='{{json .State.Health}}'

# Access container shell
docker exec -it pricescout-app /bin/bash

# Test curl manually
curl -f http://localhost:8000/_stcore/health
```

### Issue: Playwright Browser Errors

**Symptom:**
```
playwright._impl._api_types.Error: Executable doesn't exist
```

**Solution:**
```powershell
# Rebuild image
docker-compose build --no-cache pricescout
docker-compose up -d
```

---

## Advanced Testing

### Database Migration Testing

```powershell
# 1. Create test SQLite database
# (use existing data/ directory with company DBs)

# 2. Run migration script inside container
docker exec -it pricescout-app python migrations/migrate_to_postgresql.py \
  --migrate-all \
  --pg-conn "postgresql://pricescout_app:dev_password_change_me@postgres:5432/pricescout_db"

# 3. Verify data migrated
docker exec -it pricescout-postgres psql -U pricescout_app -d pricescout_db -c "SELECT COUNT(*) FROM scrape_runs;"
```

### Multi-Company Testing

```powershell
# 1. Create multiple companies
docker exec -it pricescout-postgres psql -U pricescout_app -d pricescout_db

INSERT INTO companies (name, subdomain, settings) 
VALUES 
  ('Company A', 'company-a', '{}'),
  ('Company B', 'company-b', '{}');

# 2. Test isolation - verify company_id filtering works
```

### Performance Testing

```powershell
# 1. Load test data (1000+ showings)
# (run scraper or insert via script)

# 2. Monitor resource usage
docker stats pricescout-app pricescout-postgres

# 3. Check query performance
docker exec -it pricescout-postgres psql -U pricescout_app -d pricescout_db

EXPLAIN ANALYZE 
SELECT * FROM showings 
WHERE company_id = 1 
  AND showtime_date = '2025-11-15';
```

---

## Build Optimization

### Check Image Size

```powershell
docker images pricescout

# Expected: ~800MB (multi-stage build optimized)
```

### Analyze Layers

```powershell
docker history pricescout:latest
```

### Reduce Build Time

```powershell
# Cache requirements layer
docker-compose build --build-arg BUILDKIT_INLINE_CACHE=1

# Parallel builds
docker-compose build --parallel
```

---

## Cleanup

### Remove All Containers and Volumes

```powershell
# Nuclear option - removes everything
docker-compose down -v
docker system prune -a --volumes

# Confirm
# This will remove:
#   - All stopped containers
#   - All volumes not used by at least one container
#   - All images without at least one container
#   - All build cache
```

### Remove Specific Volumes

```powershell
docker volume ls
docker volume rm pricescout_postgres_data
```

---

## Next Steps

### After Local Testing Passes:

1. **Tag Image for Azure:**
   ```powershell
   docker tag pricescout:latest pricescoutacrprod.azurecr.io/pricescout:latest
   ```

2. **Push to Azure Container Registry:**
   ```powershell
   az acr login --name pricescoutacrprod
   docker push pricescoutacrprod.azurecr.io/pricescout:latest
   ```

3. **Deploy to Azure App Service:**
   ```powershell
   az webapp config container set \
     --name pricescout-app-prod \
     --resource-group pricescout-prod-rg-eastus \
     --docker-custom-image-name pricescoutacrprod.azurecr.io/pricescout:latest
   ```

4. **Proceed to Task 5:** Azure Resource Provisioning

---

## Verification Checklist

Before proceeding to Azure deployment:

- [ ] Docker build completes without errors
- [ ] PostgreSQL container starts and passes health check
- [ ] PriceScout container starts and passes health check
- [ ] Application accessible at http://localhost:8000
- [ ] Login works (admin/admin)
- [ ] Database schema created correctly (11 tables)
- [ ] Playwright browser automation functional
- [ ] Health endpoint responds (/_stcore/health)
- [ ] Data persists after container restart
- [ ] Logs show no critical errors
- [ ] Resource usage acceptable (< 2GB RAM)

---

## Support

**Issues?**
- Check `docker-compose logs pricescout`
- Review `test_config.py` output
- Consult DEPLOYMENT_SUMMARY.md

**Ready for Azure?**
- Proceed to AZURE_DEPLOYMENT_PLAN.md Section 3.2
- Start Task 5: Azure Resource Provisioning
