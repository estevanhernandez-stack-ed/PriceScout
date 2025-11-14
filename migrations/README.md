# PriceScout Database Migrations

This directory contains database migration tools and schemas for transitioning from SQLite to PostgreSQL.

## Files

### `schema.sql`
Production-ready PostgreSQL schema with:
- **Multi-tenant architecture**: Company-based data isolation
- **RBAC support**: User roles (admin/manager/user) with permissions
- **Audit logging**: Security compliance tracking
- **Performance indexes**: Optimized for common queries
- **Data integrity**: Foreign keys, constraints, and CHECK rules
- **Helper functions**: Business logic for common operations
- **Views**: Convenient data access patterns

**Tables:**
- `companies` - Multi-tenant companies
- `users` - Authentication and RBAC
- `audit_log` - Security audit trail
- `scrape_runs` - Data collection sessions
- `showings` - Theater screening schedules
- `prices` - Ticket pricing data
- `films` - Movie metadata (OMDB enrichment)
- `operating_hours` - Theater schedules
- `unmatched_films` - Films needing OMDB review
- `ignored_films` - Excluded films
- `unmatched_ticket_types` - Unparseable ticket descriptions

### `migrate_to_postgresql.py`
Python migration script to transfer data from SQLite to PostgreSQL.

**Features:**
- Preserves all data and relationships
- Batch inserts for performance (1000 records/batch)
- Company discovery (scans `data/` directory)
- Error handling and rollback
- Progress tracking and statistics
- Supports Azure Key Vault for connection strings

## Usage

### 1. Create PostgreSQL Database (Local Testing)

```bash
# Install PostgreSQL locally (Windows)
# Download from: https://www.postgresql.org/download/windows/

# Create database
psql -U postgres
CREATE DATABASE pricescout_db;
CREATE USER pricescout_app WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE pricescout_db TO pricescout_app;
\q

# Apply schema
psql -U pricescout_app -d pricescout_db -f migrations/schema.sql
```

### 2. Set Connection String

```powershell
# Option 1: Environment variable
$env:DATABASE_URL = "postgresql://pricescout_app:your_password@localhost:5432/pricescout_db"

# Option 2: Azure Key Vault (production)
$env:AZURE_KEY_VAULT_URL = "https://pricescout-kv-prod.vault.azure.net/"
```

### 3. Install Dependencies

```bash
pip install psycopg2-binary azure-identity azure-keyvault-secrets
```

### 4. Run Migration

```bash
# Migrate users only
python migrations/migrate_to_postgresql.py --migrate-users

# Migrate specific company
python migrations/migrate_to_postgresql.py --company "AMC Theatres" --sqlite-db "data/AMC Theatres/AMC Theatres.db"

# Migrate everything (users + all companies)
python migrations/migrate_to_postgresql.py --migrate-all

# With explicit connection string
python migrations/migrate_to_postgresql.py --migrate-all --pg-conn "postgresql://user:pass@host:5432/db"
```

### 5. Verify Migration

```sql
-- Check record counts
SELECT 
    (SELECT COUNT(*) FROM companies) AS companies,
    (SELECT COUNT(*) FROM users) AS users,
    (SELECT COUNT(*) FROM showings) AS showings,
    (SELECT COUNT(*) FROM prices) AS prices,
    (SELECT COUNT(*) FROM films) AS films;

-- Check company data isolation
SELECT company_id, company_name, 
       (SELECT COUNT(*) FROM showings WHERE showings.company_id = companies.company_id) AS showings_count,
       (SELECT COUNT(*) FROM prices WHERE prices.company_id = companies.company_id) AS prices_count
FROM companies
ORDER BY company_name;

-- Verify users
SELECT username, role, company_id, is_active FROM users ORDER BY role, username;
```

## Azure PostgreSQL Deployment

### Create Azure PostgreSQL Flexible Server

```bash
# Set variables
$RESOURCE_GROUP = "pricescout-prod-rg-eastus"
$LOCATION = "eastus"
$PG_SERVER = "pricescout-db-prod"
$ADMIN_USER = "pricescoutadmin"
$ADMIN_PASSWORD = "SecurePassword123!"  # Use Key Vault in production

# Create PostgreSQL server
az postgres flexible-server create `
  --resource-group $RESOURCE_GROUP `
  --name $PG_SERVER `
  --location $LOCATION `
  --admin-user $ADMIN_USER `
  --admin-password $ADMIN_PASSWORD `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32 `
  --version 14 `
  --public-access 0.0.0.0 `
  --backup-retention 7 `
  --yes

# Create database
az postgres flexible-server db create `
  --resource-group $RESOURCE_GROUP `
  --server-name $PG_SERVER `
  --database-name pricescout_db

# Get connection string
az postgres flexible-server show-connection-string `
  --server-name $PG_SERVER `
  --database-name pricescout_db `
  --admin-user $ADMIN_USER `
  --admin-password $ADMIN_PASSWORD
```

### Apply Schema to Azure PostgreSQL

```bash
# Install psql client (Windows)
# Included with PostgreSQL installation

# Connect and apply schema
psql "host=$PG_SERVER.postgres.database.azure.com port=5432 dbname=pricescout_db user=$ADMIN_USER password=$ADMIN_PASSWORD sslmode=require" -f migrations/schema.sql
```

### Store Connection String in Key Vault

```bash
$VAULT_NAME = "pricescout-kv-prod"
$CONN_STRING = "postgresql://pricescoutadmin:SecurePassword123!@pricescout-db-prod.postgres.database.azure.com:5432/pricescout_db?sslmode=require"

az keyvault secret set `
  --vault-name $VAULT_NAME `
  --name "postgresql-connection-string" `
  --value $CONN_STRING
```

## Testing Locally with PostgreSQL

### Option 1: Local PostgreSQL Installation

```bash
# Start PostgreSQL service (Windows)
net start postgresql-x64-14

# Create test database
psql -U postgres -c "CREATE DATABASE pricescout_test;"
psql -U postgres -d pricescout_test -f migrations/schema.sql

# Run migration
$env:DATABASE_URL = "postgresql://postgres:password@localhost:5432/pricescout_test"
python migrations/migrate_to_postgresql.py --migrate-all
```

### Option 2: Docker PostgreSQL

```bash
# Start PostgreSQL container
docker run --name pricescout-postgres `
  -e POSTGRES_PASSWORD=testpass `
  -e POSTGRES_DB=pricescout_db `
  -p 5432:5432 `
  -d postgres:14-alpine

# Wait for startup (5-10 seconds)
Start-Sleep -Seconds 10

# Apply schema
docker exec -i pricescout-postgres psql -U postgres -d pricescout_db < migrations/schema.sql

# Run migration
$env:DATABASE_URL = "postgresql://postgres:testpass@localhost:5432/pricescout_db"
python migrations/migrate_to_postgresql.py --migrate-all

# Stop and remove when done
docker stop pricescout-postgres
docker rm pricescout-postgres
```

## Migration Checklist

- [ ] Backup all SQLite databases (`users.db` + `data/*/*.db`)
- [ ] Create PostgreSQL database (local or Azure)
- [ ] Apply `schema.sql` schema
- [ ] Install Python dependencies (`psycopg2-binary`, etc.)
- [ ] Set `DATABASE_URL` or `AZURE_KEY_VAULT_URL`
- [ ] Test connection: `python -c "import psycopg2; psycopg2.connect(os.getenv('DATABASE_URL'))"`
- [ ] Run migration: `python migrations/migrate_to_postgresql.py --migrate-all`
- [ ] Verify record counts in PostgreSQL
- [ ] Test application with PostgreSQL (see Task 2: SQLAlchemy Abstraction)
- [ ] Update application configuration for PostgreSQL
- [ ] Archive SQLite databases (keep as backup)

## Troubleshooting

### Connection Refused
```bash
# Check PostgreSQL is running
Get-Service -Name postgresql*  # Windows
docker ps | Select-String postgres  # Docker

# Check firewall rules (Azure)
az postgres flexible-server firewall-rule create `
  --resource-group $RESOURCE_GROUP `
  --name $PG_SERVER `
  --rule-name AllowMyIP `
  --start-ip-address YOUR_IP `
  --end-ip-address YOUR_IP
```

### Authentication Failed
```bash
# Verify credentials
psql -U pricescoutadmin -d pricescout_db -h localhost -W

# Reset password (Azure)
az postgres flexible-server update `
  --resource-group $RESOURCE_GROUP `
  --name $PG_SERVER `
  --admin-password NewSecurePassword
```

### Foreign Key Violations
- Migration script respects FK order (companies → users → scrape_runs → showings → prices)
- If errors occur, check for orphaned records in SQLite
- Use `--migrate-users` first, then `--migrate-all` for company data

### Duplicate Key Errors
- Schema uses `ON CONFLICT ... DO NOTHING` for most inserts
- Safe to re-run migration script (idempotent)
- Check for duplicate usernames or company names in SQLite

## Performance Notes

- **Batch inserts**: 1000 records per batch using `execute_batch()`
- **Indexes**: Created during schema application (not post-migration)
- **Expected duration**: 
  - Small dataset (< 10K records): 1-2 minutes
  - Medium dataset (10K-100K): 5-10 minutes
  - Large dataset (> 100K): 15-30 minutes
- **Memory usage**: ~50MB per 10K records

## Next Steps

After successful migration:

1. **Task 2**: Implement SQLAlchemy abstraction layer (`app/db_models.py`)
2. **Task 3**: Update `app/config.py` for environment detection
3. **Test**: Run pytest suite with PostgreSQL backend
4. **Task 4**: Create Dockerfile with PostgreSQL support
5. **Deploy**: Follow Azure deployment plan (Phase 2)

## Security Notes

- ⚠️ Default admin password in schema is `'admin'` - **MUST CHANGE** before production
- ⚠️ Store all passwords in Azure Key Vault (never in code or env files)
- ⚠️ Use Managed Identity for Azure PostgreSQL (no passwords in connection strings)
- ⚠️ Enable SSL/TLS for all connections (`sslmode=require`)
- ⚠️ Configure Row Level Security (RLS) policies after migration
- ⚠️ Set up automated backups (7-day retention minimum)

## Support

For issues or questions:
- Review [AZURE_DEPLOYMENT_PLAN.md](../AZURE_DEPLOYMENT_PLAN.md) Phase 1
- Check PostgreSQL logs: `az postgres flexible-server server-logs list`
- Test connection: `python migrations/migrate_to_postgresql.py --migrate-users`
- Verify schema: `psql -d pricescout_db -c "\dt"` (list tables)
