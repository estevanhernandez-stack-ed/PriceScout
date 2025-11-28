# 🔧 Price Scout Administrator Guide

**Version:** 1.0.0  
**Last Updated:** October 26, 2025  
**Target Audience:** System Administrators

---

## Table of Contents

1. [Administrator Overview](#administrator-overview)
2. [Initial Setup](#initial-setup)
3. [User Management](#user-management)
4. [Company Configuration](#company-configuration)
5. [Theater Cache Management](#theater-cache-management)
6. [Data Management Mode](#data-management-mode)
7. [Theater Matching Mode](#theater-matching-mode)
8. [Developer Tools](#developer-tools)
9. [System Diagnostics](#system-diagnostics)
10. [Database Administration](#database-administration)
11. [Troubleshooting & Maintenance](#troubleshooting--maintenance)
12. [Security Best Practices](#security-best-practices)

---

## Administrator Overview

### Admin Capabilities

As an administrator, you have access to all features plus:

✅ **User Management** - Create, modify, delete user accounts  
✅ **Company Management** - Configure companies and assignments  
✅ **Theater Cache** - Build and maintain theater database  
✅ **Data Management** - Import/export/merge databases  
✅ **Theater Matching** - Configure theater URLs and markets  
✅ **Developer Tools** - HTML capture, diagnostics, logging  
✅ **System Configuration** - Markets, tickets, themes  
✅ **Admin Mode** - Dedicated admin control panel  

### Admin-Only Modes

Three modes are restricted to administrators:

1. **Data Management** - Database operations, OMDb enrichment, cache onboarding
2. **Theater Matching** - Theater configuration, URL verification, cache building
3. **Admin** - User management, password resets, system settings

### Developer Tools (Admin Sidebar)

When logged in as admin, you'll see additional sidebar controls:

- **Capture HTML on Failure** - Save HTML snapshots when scraping fails
- **Capture HTML Snapshots** - Persistent HTML capture toggle
- **Run Market Diagnostic** - Test scraping across markets
- **Delete Theater Cache** - Remove cache file for rebuild
- **Developer Log** - Expandable scraper execution log at bottom of page

---

## Initial Setup

### First-Time Configuration

#### Step 1: Initial Admin Login

**Default Credentials:**
```
Username: admin
Password: admin
```

⚠️ **CRITICAL:** Change this password immediately!

1. Login with default credentials
2. Navigate to **Admin** mode
3. Click **Edit User** for admin account
4. Enter new secure password
5. Confirm password
6. Click **Save Changes**

#### Step 2: Create Company Structure

Before users can work, you need to configure companies:

1. **Navigate to Admin Mode**
2. **Company Management Section**
3. Click **"Add New Company"**
4. Enter company details:
   - **Company Name** (e.g., "Marcus Theatres", "AMC Theatres")
   - **Company Code** (e.g., "MARCUS", "AMC")
5. Click **Save**

**Best Practices:**
- Use official company names
- Keep codes short (3-10 characters)
- Consistent capitalization
- No special characters in codes

#### Step 3: Upload Theater Markets

Markets define geographic regions and theaters within them.

1. **Navigate to Data Management** mode
2. **Cache Onboarding** section
3. Prepare `markets.json` file:

```json
{
  "Company Name": {
    "Region Name": {
      "Market Name": {
        "Theater Name": {
          "name": "Theater Name",
          "url": "https://www.fandango.com/theater-name-code"
        }
      }
    }
  }
}
```

**Example Structure:**
```json
{
  "Marcus Theatres": {
    "Midwest": {
      "Milwaukee Metro": {
        "Marcus Majestic Cinema": {
          "name": "Marcus Majestic Cinema",
          "url": "https://www.fandango.com/marcus-majestic-cinema-aabcd"
        },
        "Marcus North Shore Cinema": {
          "name": "Marcus North Shore Cinema",
          "url": "https://www.fandango.com/marcus-north-shore-cinema-aabce"
        }
      },
      "Chicago Metro": {
        "Marcus Gurnee Cinema": {
          "name": "Marcus Gurnee Cinema",
          "url": "https://www.fandango.com/marcus-gurnee-cinema-aabcf"
        }
      }
    }
  }
}
```

4. Click **"Choose File"** and select your `markets.json`
5. Click **"Upload Markets Data"**
6. Verify success message
7. Markets now available in all modes

#### Step 4: Build Theater Cache

The theater cache is required for most modes to function.

1. **Navigate to Theater Matching** mode
2. **Build Cache** section
3. System will process uploaded markets
4. Click **"Build Cache from Markets"**
5. Wait for completion (may take 1-2 minutes)
6. Success message confirms cache creation
7. File saved to: `app/theater_cache.json`

#### Step 5: Create User Accounts

1. **Navigate to Admin** mode
2. **User Management** section
3. Click **"Add New User"**
4. Fill in details:
   - **Username** - Login identifier
   - **Password** - Initial password (user should change)
   - **Company** - Assign from dropdown
   - **Admin Status** - Check only for admins
5. Click **"Create User"**
6. Provide credentials to user

---

## User Management

### Role-Based Access Control (RBAC)

Price Scout uses a 3-tier role system to enforce least-privilege access:

#### **Admin Role**
- **Full system access** - All modes, all features
- **User management** - Create, update, delete users and change roles
- **Company management** - Configure companies and data
- **Available modes**: All 8 modes (Market, Operating Hours, CompSnipe, Historical Data, Data Management, Theater Matching, Admin, Poster Board)

#### **Manager Role**
- **Theater operations** - Standard business functions
- **No user management** - Cannot create/modify users
- **No admin access** - Cannot access Admin, Data Management, or Theater Matching modes
- **Available modes**: Market Mode, Operating Hours Mode, CompSnipe Mode, Historical Data and Analysis, Poster Board (5 modes)

#### **User Role** (Standard Access)
- **Basic functionality** - Price lookups and basic analysis
- **Read-only data** - Cannot modify system data
- **No administrative features**
- **Available modes**: Market Mode, CompSnipe Mode, Poster Board (3 modes)

### Configuring Role Permissions

**To change which modes each role can access:**

1. Navigate to **Admin** mode
2. **Role Permissions** section (at top of page)
3. Select modes for each role:
   - **Admin Modes**: Multiselect (default: all 8 modes)
   - **Manager Modes**: Multiselect (default: 5 modes)
   - **User Modes**: Multiselect (default: 3 modes)
4. Click **"Save Role Permissions"**
5. Changes apply immediately to all users with that role

**Configuration is stored in:** `role_permissions.json`

**Note:** Individual users cannot have custom mode permissions. Modes are assigned by role only. To give a user different modes, change their role.

### Bulk User Import

**To create multiple users at once:**

1. Navigate to **Admin** mode → **Bulk Import Users** section
2. Prepare JSON file (see `example_users.json`):
   ```json
   {
     "users": [
       {
         "username": "jsmith",
         "password": "SecurePass123!",
         "role": "manager",
         "company": "AMC",
         "default_company": "AMC"
       },
       {
         "username": "bdoe",
         "password": "AnotherPass456!",
         "role": "user",
         "company": "Marcus",
         "default_company": "Marcus"
       }
     ]
   }
   ```
3. Click **"Upload Users JSON"** and select file
4. Review the preview
5. Click **"Import Users"**
6. System reports success count and any errors

**Required fields:**
- `username`, `password`, `role`

**Optional fields:**
- `company`, `default_company`

**Password requirements still enforced:**
- 8+ characters, uppercase, lowercase, number, special character

### Creating Users

#### Standard User
```
Username: john.smith
Password: [generate strong password]
Role: user
Company: Marcus Theatres
Default Company: Marcus Theatres
Home Location Type: Theater (optional)
Home Location: Midwest > Chicago > Marcus Cinema (optional)
```

**User Capabilities:**
- Access modes assigned to "user" role (default: Market Mode, CompSnipe Mode, Poster Board)
- View only their company's data
- Cannot create/delete users
- Cannot access admin-only modes
- **Must change password on first login**

#### Manager User
```
Username: jane.manager
Password: [generate strong password]
Role: manager
Company: Marcus Theatres
Default Company: Marcus Theatres
Home Location Type: Market (optional)
Home Location: Midwest > Chicago (optional)
```

**Manager Capabilities:**
- Access modes assigned to "manager" role (default: 5 modes)
- Theater operations functionality
- Cannot manage users or access admin panel
- **Must change password on first login**

#### Admin User
```
Username: super.admin
Password: [generate strong password]
Role: admin
Company: [All Companies or specific]
Default Company: [All Companies or specific]
Home Location Type: Director (optional)
Home Location: Midwest (optional)
```

**Admin Capabilities:**
- All modes available
- Full admin panel access
- Developer tools in sidebar
- Can manage all users, roles, and companies

### Home Location Assignment (Optional)

**New Feature:** Assign users to a default organizational level for easier navigation and reporting.

**Home Location Types:**
1. **Director** - Top-level regional grouping (e.g., "Midwest", "East Coast")
2. **Market** - Specific market within a director (e.g., "Midwest > Chicago")
3. **Theater** - Individual theater location (e.g., "Midwest > Chicago > AMC River East 21")

**Setting Home Location:**

1. Navigate to **Admin** mode → **User Management**
2. Find user row (or use **Add New User** form)
3. In the second row of user fields:
   - Select **Home Location Type** (None, Director, Market, or Theater)
   - Select **Home Location** from dropdown
     - Dropdown populates based on selected company and type
     - Shows hierarchical structure (Director > Market > Theater)
4. Click **Update** (or **Add User** for new users)

**Use Cases:**
- **Theater Managers**: Set home to specific theater
- **Market Managers**: Set home to market level
- **Regional Directors**: Set home to director level
- **Corporate Users**: Leave as "None" for full access

**Benefits:**
- Future feature: Quick navigation to assigned location
- Future feature: Filtered reports for user's home location
- User context tracking for analytics

**Note:** Home location is optional and does not restrict access. It's primarily for convenience and future reporting features.

### First Login Password Change Requirement

**Security Enhancement:** All newly created users MUST change their password on first login.

**How It Works:**

1. Admin creates user with temporary password
2. User logs in with temporary credentials
3. System detects first login and requires password change
4. User must enter:
   - Current password (temporary one provided by admin)
   - New password (meeting security requirements)
   - Confirm new password
5. After successful password change, user gains full access

**Applies To:**
- ✅ All users created through Admin panel
- ✅ All users imported via Bulk Import
- ✅ Admin account using default "admin" password

**Security Benefits:**
- Prevents use of admin-set temporary passwords
- Ensures users control their own credentials
- Reduces risk of shared/known passwords
- Enforces password ownership from day one

**Admin Notes:**
- Temporary passwords should still meet complexity requirements
- Communicate temporary passwords securely (not via email)
- Users cannot bypass password change requirement
- Password change is required before accessing any features
- Database flag `must_change_password` automatically clears after successful change

**For Users:**
See `docs/USER_GUIDE.md` section "First Login" for step-by-step instructions.

### Editing Users

1. **Navigate to Admin** mode
2. Find user in **User Management** table
3. Columns displayed:
   - Username (editable)
   - Role (dropdown: admin/manager/user)
   - Company
   - Default Company
   - Update/Delete buttons
4. Modify fields as needed:
   - Change username
   - Change role (modes auto-update based on role)
   - Reassign company
5. Click **"Update"**

**Note:** Changing a user's role automatically updates their available modes based on role permissions configured in the Role Permissions section.

### Deleting Users

⚠️ **Warning:** This action is permanent!

1. Locate user in table
2. Click **"Delete"** button
3. Confirm deletion
4. User account removed from system

**Best Practices:**
- Archive user data before deletion
- Document reason for deletion
- Notify user of account removal
- Cannot delete currently logged-in user

### Password Resets

**Option 1: Admin Password Reset (Legacy)**

1. Navigate to **Admin** mode
2. Find user's account in User Management table
3. Click **"Edit User"**
4. Enter new temporary password
5. Click **"Save Changes"**
6. Communicate new password to user securely (not via email)
7. Instruct user to change password on next login

**Option 2: Self-Service Password Reset (Recommended)**

Users can reset their own passwords without admin intervention:

1. User clicks **"🔑 Forgot Password?"** on login page
2. Enters their username
3. System generates 6-digit reset code (valid 15 minutes)
4. User enters code and new password
5. Password reset complete

**Security Features:**
- Time-limited codes (15-minute expiry)
- Maximum 3 verification attempts per code
- Codes are bcrypt-hashed (same security as passwords)
- All attempts logged in `security.log`

**Admin Monitoring:**

Check password reset activity:
```bash
python scripts/security_monitor.py --days 7
```

Logs show:
- `password_reset_requested` - User requested code
- `password_reset_code_verified` - Valid code entered
- `password_reset_invalid_code` - Wrong code attempted
- `password_reset_completed` - Password changed successfully
- `password_reset_expired` - Expired code used
- `password_reset_max_attempts` - Too many failed attempts

**For detailed password reset documentation, see:** `docs/PASSWORD_RESET_GUIDE.md`

**Security Notes:**
- All passwords are hashed with BCrypt
- Admins cannot view existing passwords
- Password changes take effect immediately
- Users are not automatically logged out after password change

---

## Company Configuration

### Adding Companies

1. **Admin Mode** → Company Management
2. Click **"Add New Company"**
3. Enter details:
   - **Name:** Full company name
   - **Code:** Short identifier
   - **Description:** (optional) Notes about company
4. Click **"Save"**

### Editing Companies

1. Find company in list
2. Click **"Edit Company"**
3. Modify name or code
4. Click **"Save Changes"**

⚠️ **Warning:** Changing company name/code may break existing data associations!

**Safe Edits:**
- Adding description
- Fixing typos (if no data exists yet)

**Dangerous Edits:**
- Changing name after users assigned
- Changing code after data collected
- Deleting company with active users

### Company-Theater Association

Companies are linked to theaters via the markets JSON structure:

```json
{
  "CompanyName": {
    "Region": {
      "Market": {
        "Theater": {...}
      }
    }
  }
}
```

**To Change Theater Ownership:**
1. Edit `markets.json` file
2. Move theater to different company section
3. Re-upload via Data Management → Cache Onboarding
4. Rebuild theater cache

---

## Theater Cache Management

### Understanding the Cache

**Purpose:** Fast lookup of theater names, URLs, and metadata

**Location:** `app/theater_cache.json`

**Structure:**
```json
{
  "Theater Name": {
    "name": "Theater Name",
    "url": "https://www.fandango.com/...",
    "company": "Company Name",
    "market": "Market Name",
    "region": "Region Name"
  }
}
```

**Cache Expiration:** 7 days (configurable in `.env`)

### Building the Cache

#### Method 1: From Markets JSON (Recommended)

1. **Theater Matching** mode
2. **Cache Onboarding** tab
3. Upload `markets.json`
4. Click **"Build Cache from Markets"**
5. Cache file created automatically

#### Method 2: Manual Entry

1. **Theater Matching** mode
2. **Add Theater** section
3. Enter theater details:
   - Name
   - Fandango URL
   - Company
   - Market
   - Region
4. Click **"Add to Cache"**
5. Repeat for each theater

### Updating the Cache

**Add New Theaters:**
1. Edit `markets.json` to include new theaters
2. Re-upload via Data Management
3. Rebuild cache (preserves existing entries)

**Remove Theaters:**
1. Edit `markets.json` to remove theaters
2. Re-upload
3. Rebuild cache
4. Old entries automatically removed

**Modify Theater Details:**
1. Edit `markets.json` with corrections
2. Re-upload
3. Rebuild cache
4. Updated entries replace old ones

### Cache Troubleshooting

#### "Cache file missing or invalid"

**Solution:**
1. Navigate to Theater Matching
2. Rebuild cache from markets
3. Or manually delete `app/theater_cache.json` and rebuild

#### "Theater not found in cache"

**Solution:**
1. Verify theater exists in `markets.json`
2. Rebuild cache
3. Check spelling matches exactly
4. Check theater is under correct company

#### "Duplicate theater names"

**Problem:** Multiple theaters with same name in cache

**Solution:**
1. Theater Matching mode shows warning
2. Edit theater names in `markets.json` to be unique
3. Example: "AMC Mesquite 30" vs "AMC Mesquite (TX)"
4. Re-upload and rebuild

---

## Data Management Mode

### Overview

Data Management provides centralized database operations:

- **OMDb Enrichment** - Add film metadata
- **Database Merging** - Combine external databases
- **Cache Onboarding** - Upload markets/theaters
- **Data Export** - Bulk data extraction
- **Data Cleanup** - Remove duplicates, fix errors

### OMDb Film Enrichment

**Purpose:** Add metadata (genre, rating, year, plot) to films in database

#### Setup: Get OMDb API Key

1. Visit https://www.omdbapi.com/apikey.aspx
2. Select free tier (1,000 requests/day)
3. Enter email and verify
4. Copy API key

#### Configure API Key

**Method 1: Streamlit Secrets (Recommended)**
```bash
# .streamlit/secrets.toml (create at project root)
omdb_api_key = "your_key_here"
omdb_poster_api_key = "your_key_here"
```

**Method 2: Environment Variable**
```bash
# Windows PowerShell
$env:OMDB_API_KEY = "your_key_here"

# Or add to .env file
OMDB_API_KEY=your_key_here
```

**Precedence:** Streamlit secrets take priority, then environment variable fallback.

**Security:** `.streamlit/secrets.toml` is automatically excluded from git commits.

#### Enrich Films

**Automatic Enrichment (New Feature)**

Film metadata is now automatically fetched when scraping in these modes:
- **Daily Lineup Mode** - Auto-enriches after scraping showtimes
- **Other Scraping Modes** - Auto-enriches when new films detected

If auto-enrichment fails to find a film:
- Film is logged as "unmatched" for manual review
- Appears in **Unmatched Film Review** section below
- Can be manually enriched or marked as special event

**Manual Bulk Enrichment**

1. **Select Films** tab
2. View list of films in database
3. Select films needing enrichment (missing genre/rating)
4. Click **"Enrich Selected Films"**
5. System queries OMDb API
6. Metadata updated in database

**Per-Film Enrichment (Daily Lineup)**

When viewing a Daily Lineup with missing runtime data:
1. Each film missing Out-Time shows a **"Backfill '[Film]' runtime"** button
2. Click button to fetch that specific film's metadata
3. Lineup refreshes automatically with updated Out-Time
4. If OMDb can't find the film, it's logged for manual review

**Unmatched Film Review**

Films that couldn't be automatically matched appear here:
1. Navigate to **Unmatched Film Review** section
2. Review list of unmatched films
3. For each film, choose an action:
  - **Re-match with OMDb** - Try again with corrected title
  - **Search Fandango** - Fetch from Fandango as fallback
  - **Enter Manually** - Add metadata by hand
  - **Accept as Special Event** - Mark as non-standard film (private event, etc.)
  - **Mark as Mystery Movie** - Special case for unknown titles
4. Click action button and follow prompts
5. Successfully matched films removed from unmatched list

**What Gets Updated:**
- Genre (Action, Comedy, Drama, etc.)
- MPAA Rating (G, PG, PG-13, R)
- Runtime (for Out-Time calculations)
- Release Year
- Plot Summary
- Director
- Cast
- Poster URL

**Best Practices:**
- Enrich in batches (10-20 at a time)
- Monitor API usage (free tier = 1,000/day)
- Run after major scrapes to update new films
- Review unmatched films weekly to improve data quality
- Use per-film buttons in Daily Lineup for immediate fixes

### Database Merging

**Purpose:** Combine data from external Price Scout databases

**Use Cases:**
- Merging data from multiple locations
- Importing historical data
- Consolidating test databases
- Recovering from backup

#### Upload External Database

1. **Database Merge** section
2. Click **"Choose File"**
3. Select `.db` file from other Price Scout instance
4. Click **"Upload Database"**
5. File uploaded to temp location

#### Preview Merge

System shows what will be merged:
- **Scrape Runs:** X runs found
- **Showings:** Y showings found
- **Films:** Z films found
- **Conflicts:** Duplicate run IDs, overlapping dates

#### Execute Merge

1. Review preview
2. Click **"Merge Database"**
3. System performs merge:
   - Preserves existing data
   - Adds new runs/showings/films
   - Handles duplicates intelligently
4. Success message confirms merge

**Merge Logic:**
- **Scrape Runs:** Merged by run ID (duplicates skipped)
- **Showings:** Merged by unique showing ID
- **Films:** Merged by title + year (metadata updated if newer)
- **Operating Hours:** Merged by theater + date

⚠️ **Warning:** Always backup your database before merging!

```bash
# Backup command
cp data/CompanyName/price_scout.db data/CompanyName/backup_$(date +%Y%m%d).db
```

### Cache Onboarding

**Purpose:** Upload and configure theater markets

#### Upload Markets JSON

1. **Cache Onboarding** tab
2. Prepare `markets.json` (see structure in Initial Setup)
3. Click **"Choose File"**
4. Select your JSON file
5. Click **"Upload Markets Data"**
6. System validates structure
7. Success message confirms upload
8. Markets now available in dropdowns

#### Upload Ticket Types JSON

Define available ticket categories:

```json
{
  "Adult": {"base_price": 12.00},
  "Senior": {"base_price": 9.00},
  "Child": {"base_price": 8.00},
  "Student": {"base_price": 10.00},
  "Military": {"base_price": 10.00}
}
```

1. Click **"Choose File"** under Ticket Types
2. Select `ticket_types.json`
3. Click **"Upload Ticket Types"**
4. Types available in scraping modes

---

## Theater Matching Mode

### Overview

Theater Matching is the admin control center for theater configuration:

- **View Cache** - See all configured theaters
- **Add Theaters** - Manual entry
- **Edit Theaters** - Update URLs or details
- **Verify URLs** - Test Fandango URLs
- **Build Cache** - Generate cache from markets
- **Export Cache** - Download for backup

### Adding Individual Theaters

1. **Add Theater** section
2. Fill in form:
   - **Theater Name:** Official name
   - **Fandango URL:** Full URL from Fandango.com
   - **Company:** Select from dropdown
   - **Market:** Market within company
   - **Region:** Geographic region
3. Click **"Add to Cache"**

#### Finding Fandango URLs

1. Go to https://www.fandango.com
2. Search for theater by name or ZIP
3. Click theater name
4. Copy URL from browser address bar
5. URL format: `https://www.fandango.com/theater-name-code`

**Example:**
```
https://www.fandango.com/marcus-majestic-cinema-of-brookfield-aabcd
```

### Editing Theaters

1. **View Cache** section
2. Find theater in table
3. Click **"Edit"** button
4. Modify details (name, URL, market, etc.)
5. Click **"Save Changes"**

**Common Edits:**
- Fixing typos in theater names
- Updating URLs (if Fandango changed theater codes)
- Reassigning markets
- Changing company ownership

### Verifying Theater URLs

**Purpose:** Test that Fandango URLs are valid and accessible

1. **URL Verification** section
2. Paste Fandango URL
3. Click **"Verify URL"**
4. System attempts to load theater page
5. Results:
   - ✅ **Valid:** URL loads, theater data accessible
   - ❌ **Invalid:** URL broken, 404 error, or no theater data

**Troubleshooting Invalid URLs:**
- Theater closed or removed from Fandango
- URL code changed (search Fandango for new URL)
- Temporary website issue (try again later)

### Bulk Operations

#### Export Cache
1. Click **"Export Cache"**
2. Downloads `theater_cache.json`
3. Use for backups or sharing

#### Import Cache
1. Click **"Choose File"** under Import
2. Select previously exported cache JSON
3. Click **"Import Cache"**
4. Replaces current cache

⚠️ **Warning:** Import overwrites existing cache!

#### Rebuild Cache
1. Click **"Rebuild Cache from Markets"**
2. Regenerates cache from current markets data
3. Use after uploading new markets JSON

---

## Developer Tools

### HTML Capture on Failure

**Purpose:** Save HTML snapshots when scraping encounters errors

**How to Enable:**
1. Admin sidebar (when logged in as admin)
2. Toggle **"Capture HTML on Failure"**
3. Now enabled for all scrapes

**What Gets Captured:**
- Full page HTML when scraper fails
- Saved to: `debug_snapshots/`
- Filename: `failure_[timestamp]_[theater].html`

**Use Cases:**
- Debugging scraping failures
- Analyzing website changes
- Troubleshooting price extraction issues
- Documenting errors for support

**Viewing Captured HTML:**
1. Navigate to `debug_snapshots/` folder
2. Open `.html` file in browser
3. Inspect page structure
4. Look for changes in CSS selectors, JavaScript, etc.

### HTML Snapshots (Persistent)

Similar to "Capture on Failure" but captures ALL scrapes:

1. Toggle **"Capture HTML Snapshots"**
2. Every scrape saves HTML
3. Use for debugging or auditing

⚠️ **Warning:** Generates many large files! Clean up regularly.

### Run Market Diagnostic

**Purpose:** Test scraping functionality across all theaters in selected markets

**When to Use:**
- After website updates
- Testing new theater additions
- Validating cache accuracy
- Performance benchmarking

**How to Run:**
1. Click **"Run Market Diagnostic"** in sidebar
2. **OR** navigate to dedicated diagnostic section
3. Select markets to test
4. Click **"Start Full Diagnostic"**
5. System scrapes ALL theaters in selected markets
6. Wait for completion (may take 10-30 minutes)

**Results:**
- Success/failure per theater
- Timing metrics
- Error messages
- Data quality indicators

**Report Output:**
- Summary table
- Detailed logs
- Export to CSV for analysis

### Delete Theater Cache

**Purpose:** Quick way to remove cache for rebuild

1. Click **"Delete Theater Cache"** button
2. Confirms deletion
3. File `app/theater_cache.json` removed
4. Rebuild cache via Theater Matching mode

**When to Use:**
- Cache corrupted
- Major theater reorganization
- Testing cache rebuild process

### Developer Log

**Location:** Bottom of page (when admin logged in)

**Purpose:** View detailed scraper execution logs

**What's Logged:**
- Each step of scraping process
- HTTP requests and responses
- Selector matches
- Data extraction results
- Error stack traces

**How to Use:**
1. Run a scrape
2. Scroll to bottom of page
3. Expand **"Developer Mode: Scraper Log"**
4. View full log output
5. Copy/paste for bug reports

---

## System Diagnostics

### Full System Diagnostic

**Purpose:** Comprehensive health check of entire Price Scout system

**What Gets Tested:**
- Database connectivity
- Theater cache validity
- OMDb API connection
- Scraping functionality (all theaters)
- Data integrity
- Performance metrics

**How to Run:**

1. **Admin Mode** → System Diagnostics section
2. Configure diagnostic:
   - **Select Markets:** Which markets to test
   - **Date Range:** Test data from specific period
   - **Include Scraping:** Whether to perform live scrapes
3. Click **"Run Full Diagnostic"**
4. Wait for completion (10-60 minutes depending on scope)

**Report Includes:**
- ✅ **Passed Tests:** Count and details
- ❌ **Failed Tests:** Errors and recommended fixes
- ⚠️ **Warnings:** Non-critical issues
- 📊 **Performance Metrics:** Response times, data volumes
- 📈 **Recommendations:** Suggested improvements

### Interpreting Results

#### Database Health
```
✅ Database Connections: OK
✅ Table Integrity: OK
⚠️ Index Performance: Slow on showings table
❌ Foreign Keys: 3 orphaned records found
```

**Actions:**
- ✅ OK: No action needed
- ⚠️ Warning: Monitor, optimize if worsens
- ❌ Error: Fix immediately (see recommendations)

#### Scraping Health
```
✅ Chromium Browser: Installed
✅ Network Connectivity: OK
❌ Fandango.com: 3/50 theaters failed
⚠️ Response Times: Slower than baseline (avg 12s vs 8s)
```

**Actions:**
- Failed theaters: Verify URLs in Theater Matching
- Slow responses: Check network, try during off-peak hours

#### Data Quality
```
✅ Film Metadata: 95% complete
⚠️ Missing Prices: 12% of showings
❌ Duplicate Runs: 5 duplicate scrape_run IDs found
```

**Actions:**
- Enrich films via Data Management → OMDb
- Re-scrape theaters with missing prices
- Delete duplicate runs (see Database Administration)

---

## Database Administration

### Database Locations

**User Database:**
```
users.db
```
Contains: User accounts, passwords, company assignments

**Company Databases:**
```
data/[CompanyName]/price_scout.db
```
Contains: Scrape runs, showings, prices, films, operating hours

### Backup Procedures

#### Manual Backup

**PowerShell:**
```powershell
# Backup user database
Copy-Item users.db "users_backup_$(Get-Date -Format 'yyyyMMdd').db"

# Backup company database
Copy-Item "data\Marcus\price_scout.db" "data\Marcus\backup_$(Get-Date -Format 'yyyyMMdd').db"
```

**Linux/Mac:**
```bash
# Backup user database
cp users.db users_backup_$(date +%Y%m%d).db

# Backup company database
cp "data/Marcus/price_scout.db" "data/Marcus/backup_$(date +%Y%m%d).db"
```

#### Automated Backup Script

Create `backup.ps1`:
```powershell
$date = Get-Date -Format "yyyyMMdd"
$backupDir = "backups\$date"

# Create backup directory
New-Item -ItemType Directory -Force -Path $backupDir

# Backup user database
Copy-Item users.db "$backupDir\users.db"

# Backup all company databases
Get-ChildItem -Path "data\*\price_scout.db" | ForEach-Object {
    $company = $_.Directory.Name
    Copy-Item $_.FullName "$backupDir\${company}_price_scout.db"
}

Write-Host "Backup completed: $backupDir"
```

**Schedule via Task Scheduler (Windows):**
1. Open Task Scheduler
2. Create Basic Task
3. Name: "Price Scout Backup"
4. Trigger: Daily at 2:00 AM
5. Action: Start a program
6. Program: `powershell.exe`
7. Arguments: `-File "C:\Path\To\backup.ps1"`

### Database Maintenance

#### Vacuum (Reclaim Space)

SQLite databases can become fragmented. Vacuum rebuilds the database file.

```bash
sqlite3 data/Marcus/price_scout.db "VACUUM;"
```

**When to Run:**
- After deleting large amounts of data
- Database file unexpectedly large
- Monthly maintenance

#### Analyze (Optimize Queries)

Updates table statistics for better query planning.

```bash
sqlite3 data/Marcus/price_scout.db "ANALYZE;"
```

**When to Run:**
- After significant data changes
- Before generating large reports
- Monthly maintenance

#### Integrity Check

Verifies database is not corrupted.

```bash
sqlite3 data/Marcus/price_scout.db "PRAGMA integrity_check;"
```

**Expected Output:**
```
ok
```

**If Corrupted:**
1. Restore from most recent backup
2. Document what operations preceded corruption
3. Contact support if recurring

### Manual Database Operations

#### View Database Schema

```bash
sqlite3 data/Marcus/price_scout.db ".schema"
```

#### Query Data

```bash
sqlite3 data/Marcus/price_scout.db

# Example queries
SELECT COUNT(*) FROM scrape_runs;
SELECT COUNT(*) FROM showings;
SELECT title, COUNT(*) FROM showings GROUP BY title ORDER BY COUNT(*) DESC LIMIT 10;
.quit
```

#### Delete Old Data

⚠️ **Backup first!**

```sql
-- Delete scrape runs older than 90 days
DELETE FROM scrape_runs WHERE timestamp < datetime('now', '-90 days');

-- Delete orphaned showings (runs deleted but showings remain)
DELETE FROM showings WHERE run_id NOT IN (SELECT run_id FROM scrape_runs);
```

---

## Troubleshooting & Maintenance

### Common Admin Issues

#### "Unable to create user - username already exists"

**Cause:** Username must be unique

**Solution:**
1. Choose different username
2. OR delete existing user with that username first

#### "Database locked" error

**Cause:** Multiple processes accessing database simultaneously

**Solution:**
1. Close all Price Scout windows
2. Wait 30 seconds
3. Restart application
4. If persists, restart computer

#### "Cache file corrupted"

**Symptoms:**
- Modes won't load
- Theater dropdowns empty
- Cache-related errors

**Solution:**
1. Admin sidebar → Delete Theater Cache
2. Theater Matching → Rebuild Cache from Markets
3. Verify markets JSON is valid

#### Markets JSON upload fails

**Common Errors:**

**Invalid JSON syntax:**
```
Error: Unexpected token } in JSON at position 234
```
**Solution:** Validate JSON at https://jsonlint.com

**Duplicate theater names:**
```
Error: Duplicate theater name 'AMC Mesquite 30' found
```
**Solution:** Make theater names unique, rebuild cache

**Missing required fields:**
```
Error: Theater missing 'url' field
```
**Solution:** Ensure each theater has name and url fields

#### OMDb enrichment failing

**Symptoms:**
- "Film not found" errors
- API key invalid messages
- Rate limit exceeded

**Solutions:**

**Film not found:**
- Check spelling in database
- Film may not be in OMDb (add manually)

**Invalid API key:**
- Verify key at omdbapi.com
- Check `.env` file has correct key
- Re-enter in Data Management UI

**Rate limit:**
- Free tier = 1,000 requests/day
- Wait until next day
- OR upgrade to paid tier

### Performance Optimization

#### Slow Scraping

**Symptoms:** Scrapes taking 2-3x normal time

**Causes & Solutions:**

**Network Issues:**
- Test internet speed
- Check for VPN interference
- Try during off-peak hours (2 AM - 10 AM)

**Too Many Theaters:**
- Reduce scope (5-10 theaters max per scrape)
- Break large scrapes into smaller batches

**Website Changes:**
- Run diagnostic to identify problem theaters
- Update selectors if Fandango changed site structure

#### Database Queries Slow

**Symptoms:** Reports taking >30 seconds to generate

**Solutions:**

1. **Run ANALYZE:**
   ```bash
   sqlite3 data/Company/price_scout.db "ANALYZE;"
   ```

2. **Add Indexes:**
   ```sql
   CREATE INDEX idx_showings_date ON showings(play_date);
   CREATE INDEX idx_showings_theater ON showings(theater_name);
   CREATE INDEX idx_showings_film ON showings(title);
   ```

3. **Archive Old Data:**
   - Export data >1 year old
   - Delete from main database
   - Keep archives for historical reference

#### Memory Issues

**Symptoms:** Application crashes, "Out of memory" errors

**Solutions:**

1. **Reduce Cache Size:**
   - Delete old debug snapshots
   - Clear browser cache
   - Limit HTML capture

2. **Limit Date Ranges:**
   - Use smaller date windows (7-14 days vs 90 days)
   - Export large reports to files, analyze externally

3. **Increase Server Resources:**
   - Allocate more RAM to application
   - Use dedicated server (not shared hosting)

### Regular Maintenance Tasks

#### Daily
- ✅ Monitor user login issues
- ✅ Check for scraping errors in logs

#### Weekly
- ✅ Review diagnostic reports
- ✅ Update film metadata (OMDb enrichment)
- ✅ Clear debug snapshots folder

#### Monthly
- ✅ Backup all databases
- ✅ Run VACUUM and ANALYZE
- ✅ Review user accounts (remove inactive)
- ✅ Update theater cache (verify URLs)

#### Quarterly
- ✅ Archive old data (>90 days)
- ✅ Review and update markets JSON
- ✅ Test disaster recovery procedures
- ✅ Update documentation

#### Annually
- ✅ Security audit (password policies, access logs)
- ✅ Performance review (optimize queries, indexes)
- ✅ User training refresher
- ✅ System upgrade planning

---

## Security Best Practices

### Password Policies

#### Strong Password Requirements

**Enforce for all users:**
- Minimum 12 characters
- Mix of uppercase, lowercase, numbers, symbols
- No dictionary words
- No personal information

**Example Strong Passwords:**
```
Tr0pic@l$unset47!
Quantum#Leap2025$
Br1dge*Walker99
```

#### Admin Password Security

**Critical Rules:**
1. ✅ Change default admin password IMMEDIATELY
2. ✅ Use unique password (not used elsewhere)
3. ✅ Change every 90 days
4. ✅ Never share admin credentials
5. ✅ Use password manager to store securely

### Access Control

#### Principle of Least Privilege

**Grant minimum necessary access:**
- Standard users: Company-specific data only
- Admins: Full access, but limited number of admins

**Review Regularly:**
- Quarterly access audits
- Remove users who left organization
- Downgrade admin rights if no longer needed

#### Session Management

**User Sessions:**
- Auto-logout after 30 minutes inactivity (configurable)
- Force logout on password change
- Clear session data on logout

**Admin Sessions:**
- Consider shorter timeout (15 minutes)
- Require re-authentication for sensitive operations

### Data Protection

#### Database Encryption

**At Rest:**
```bash
# Enable SQLite encryption (requires SQLCipher)
sqlite3 data/Company/price_scout.db
PRAGMA key = 'your-encryption-key';
```

**In Transit:**
- Use HTTPS for web access
- VPN for remote admin access

#### Backup Security

**Protect Backups:**
1. Store in separate location (off-site)
2. Encrypt backup files
3. Restrict access (admin only)
4. Test restoration quarterly

**Retention Policy:**
- Daily backups: Keep 7 days
- Weekly backups: Keep 4 weeks
- Monthly backups: Keep 12 months
- Annual backups: Keep indefinitely

### Audit Logging

#### Enable Logging

**Security Event Logging:**

Price Scout automatically logs all security events to `security.log` including:
- Login attempts (success/failure)
- Password changes
- Password reset requests and completions
- User creation/deletion
- Admin operations
- Rate limiting events (account lockouts)
- Session timeouts

**Standard Application Logging:**

`.env` Configuration:
```bash
LOG_LEVEL=INFO
AUDIT_LOG_ENABLED=true
AUDIT_LOG_PATH=logs/audit.log
```

#### What is Logged

**Security Events (security.log):**
- ✅ `login_success` - Successful authentication
- ✅ `login_failed` - Invalid credentials
- ✅ `account_locked` - Too many failed attempts (rate limiting)
- ✅ `password_changed` - User changed password
- ✅ `password_reset_requested` - Reset code generated
- ✅ `password_reset_completed` - Password reset via code
- ✅ `password_reset_invalid_code` - Wrong code attempted
- ✅ `password_reset_expired` - Expired code used
- ✅ `password_reset_max_attempts` - Too many verification attempts
- ✅ `user_created` - New account created
- ✅ `user_deleted` - Account removed
- ✅ `session_timeout` - Automatic logout after inactivity

**Operational Events (audit.log):**
- ✅ Scrape executions
- ✅ Database merges
- ✅ Cache rebuilds
- ✅ Report generations
- ✅ File uploads

#### Review Logs with Security Monitor

**Automated Log Analysis:**

```bash
# Review last 7 days of security events
python scripts/security_monitor.py --days 7

# Review last 24 hours
python scripts/security_monitor.py --days 1

# Review last 30 days
python scripts/security_monitor.py --days 30
```

**Monitor Output:**
```
=== SECURITY LOG ANALYSIS ===
Period: Last 7 days

--- Login Activity ---
Total login attempts: 147
Successful logins: 142
Failed logins: 5
Account lockouts: 1

--- Password Activity ---
Password changes: 3
Password reset requests: 2
Password resets completed: 2

--- User Management ---
Users created: 1
Users deleted: 0

--- High Risk Events ---
⚠️ Account lockout: user 'jsmith' (2025-01-15 14:23:17)
⚠️ Multiple failed logins: user 'admin' (5 attempts in 10 minutes)

--- Recommendations ---
✅ Review lockout for 'jsmith' - may need assistance
✅ Investigate 'admin' failed attempts - possible attack
```

**Weekly Review Checklist:**
- [ ] Check for account lockouts (legitimate vs attacks)
- [ ] Identify unusual login patterns (off-hours, rapid attempts)
- [ ] Verify all admin operations are legitimate
- [ ] Review password reset activity (spike = potential issue)
- [ ] Monitor failed login attempts by username (brute force detection)

**Monthly Analysis:**
- [ ] Generate usage reports (logins per user/role)
- [ ] Identify training needs (excessive failed logins)
- [ ] Review security trends (increasing attacks?)
- [ ] Optimize rate limiting if needed (too strict/lenient?)

### Incident Response

#### Security Breach Procedure

**If Compromise Suspected:**

1. **Immediate Actions:**
   - Change all admin passwords
   - Review recent user activity
   - Check database for unauthorized changes
   - Disable affected user accounts

2. **Investigation:**
   - Review audit logs
   - Identify breach vector
   - Assess data exposure
   - Document findings

3. **Remediation:**
   - Fix security vulnerability
   - Restore from clean backup if needed
   - Notify affected users
   - Update security procedures

4. **Prevention:**
   - Implement additional controls
   - User training on identified issue
   - Monitor for recurring patterns

### Compliance Considerations

#### Data Privacy

**If handling PII (Personally Identifiable Information):**
- Document data retention policies
- Implement data deletion procedures
- Comply with GDPR/CCPA if applicable
- User consent for data collection

**Price Scout Data:**
- Theater pricing = generally public information
- User accounts = PII (usernames, company affiliations)
- Audit logs = may contain PII

#### Data Retention

**Recommended Policies:**
- Pricing data: 2 years
- User activity logs: 1 year
- Audit logs: 3 years
- Backup data: 1 year rolling

**Deletion Procedures:**
- Automated scripts for old data removal
- Secure deletion (not recoverable)
- Document retention compliance

---

## Quick Reference

### Essential Admin Commands

```bash
# Backup databases
Copy-Item users.db users_backup.db
Copy-Item data/Company/price_scout.db data/Company/backup.db

# Database maintenance
sqlite3 data/Company/price_scout.db "VACUUM; ANALYZE;"

# Check integrity
sqlite3 data/Company/price_scout.db "PRAGMA integrity_check;"

# View logs
Get-Content logs/audit.log -Tail 50

# Clear debug snapshots
Remove-Item debug_snapshots/* -Force
```

### Admin Checklist

#### New User Onboarding
- [ ] Create user account
- [ ] Assign to correct company
- [ ] Set temporary password
- [ ] Verify company has data/markets configured
- [ ] Communicate credentials securely
- [ ] Instruct to change password on first login
- [ ] Provide USER_GUIDE.md

#### New Company Setup
- [ ] Create company in Admin mode
- [ ] Prepare markets.json with theaters
- [ ] Upload markets via Data Management
- [ ] Build theater cache
- [ ] Verify cache in Theater Matching
- [ ] Create test user for company
- [ ] Test all modes with company data

#### Troubleshooting Steps
1. Check error message (screenshot if possible)
2. Review recent changes (users, markets, cache)
3. Check developer log (if admin)
4. Verify database integrity
5. Check cache validity
6. Test with different browser/user
7. Review documentation
8. Contact support if unresolved

---

## Advanced Topics

### Custom Market Configurations

**Beyond Standard Markets:**

```json
{
  "Company Name": {
    "Virtual Region": {
      "Special Events Market": {
        "Pop-up Theater": {
          "name": "Summer Drive-In",
          "url": "https://..."
        }
      },
      "Testing Market": {
        "Test Theater": {
          "name": "Sandbox Theater",
          "url": "https://..."
        }
      }
    }
  }
}
```

**Use Cases:**
- Temporary locations
- Testing environments
- Event-specific configurations

### API Integration

**Future Enhancement: REST API for Price Scout**

**Potential Endpoints:**
- `GET /api/prices?theater=X&date=Y`
- `POST /api/scrape` - Trigger scrape via API
- `GET /api/reports/latest` - Download latest report

**Authentication:**
- API keys per user
- Rate limiting
- Audit logging

### Multi-Tenant Deployment

**Hosting Multiple Companies on One Instance:**

**Current Setup:** One database per company
- Already supports multi-tenant
- Company isolation via user assignments
- Shared theater cache (all companies)

**Considerations:**
- Ensure data isolation
- Configure per-company settings
- Scale server resources appropriately

---

## Support & Resources

### Documentation

- **README.md** - Installation and quick start
- **USER_GUIDE.md** - End-user instructions
- **ADMIN_GUIDE.md** - This document
- **CODE_REVIEW_2025.md** - Technical details
- **API_REFERENCE.md** - Developer documentation

### Getting Help

**Before Escalating:**
1. Check this guide's troubleshooting section
2. Review relevant user documentation
3. Check developer log for errors
4. Test with minimal configuration
5. Document steps to reproduce

**When Reporting Issues:**
- Admin username (not password!)
- What operation you were performing
- Error message (exact text or screenshot)
- Recent changes (uploads, user modifications)
- Developer log excerpt (if available)

**Contact Information:**
- Technical Support: [Your support email]
- Emergency Contact: [24/7 contact if applicable]
- Documentation Updates: [GitHub repo or wiki]

---

**Administrator Guide Version:** 28.0  
**Last Updated:** October 2025  
**Status:** Production Ready  

---

**Remember:**
- 🔐 Security first - change default passwords
- 📊 Regular backups - automate them
- 📝 Document changes - help future admins
- 👥 Train users - prevent support burden
- 🧪 Test changes - use sandbox first
- 🔍 Monitor logs - catch issues early
