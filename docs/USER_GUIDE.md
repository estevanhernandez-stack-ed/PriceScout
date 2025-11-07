# 📖 Price Scout User Guide

**Version:** 1.0.0  
**Last Updated:** October 26, 2025  
**Target Audience:** End Users (Non-Admin)

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Navigation](#navigation)
3. [Market Mode](#market-mode)
4. [Operating Hours Mode](#operating-hours-mode)
5. [CompSnipe Mode](#compsnipe-mode)
6. [Historical Data and Analysis](#historical-data-and-analysis)
7. [Poster Board Mode](#poster-board-mode)
8. [Working with Reports](#working-with-reports)
9. [Tips & Best Practices](#tips--best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Getting Started

### First Login

1. **Open Price Scout**
   - Your admin will provide the URL (typically `http://localhost:8501` or a server address)
   - The application opens in your web browser

2. **Login Credentials**
   - Enter your username and password provided by your administrator
   - Click "Login"

3. **Initial Screen**
   - After login, you'll see the main dashboard
   - Sidebar shows available modes
   - Main area displays mode-specific controls

### Understanding Your Company Setup

Your account is assigned to a specific company (e.g., "Marcus Theatres", "AMC Theatres")
- You can only view and scrape data for theaters in your company
- Your admin configures which theaters and markets you can access
- All reports are scoped to your company's theaters

---

## Navigation

### Sidebar Controls

**Top Section:**
- **🚀 Start New Report / Abort** - Clears current workflow and starts fresh

**Mode Selection:**
- **Market Mode** - Compare pricing across your market
- **Operating Hours Mode** - Track theater operating hours
- **CompSnipe Mode** - Competitive intelligence by ZIP code
- **Historical Data and Analysis** - Deep dive into past performance
- **Poster Board** - Generate schedule and poster reports

**Status Indicators:**
- 🟢 Green (Primary) = Currently selected mode
- ⚪ Gray (Secondary) = Available mode
- 🔒 Disabled = Cache required (contact admin)

### Main Content Area

- **Date Pickers** - Select scrape dates or date ranges
- **Dropdowns** - Choose markets, theaters, films
- **Buttons** - Execute scrapes, generate reports
- **Tables** - View results and data
- **Export Controls** - Download CSV/Excel reports

---

## Market Mode

**Purpose:** Compare pricing across multiple theaters in your market for specific films.

### Workflow

#### Step 1: Select Your Market
1. Choose from the **Market** dropdown
   - Options configured by your admin
   - Represents geographic regions (e.g., "Dallas-Fort Worth", "Chicago Metro")

#### Step 2: Select Theaters
1. Click theaters from the displayed list
   - Theaters turn green when selected
   - Click again to deselect
   - Select 2+ theaters for meaningful comparisons

#### Step 3: Choose Films
1. **Option A: Search Films**
   - Use the search box to find films by title
   - Select from search results

2. **Option B: Browse Database**
   - Click "Show All Films in Database"
   - Browse complete list
   - Select desired films

#### Step 4: Select Date
1. Use the date picker to choose your scrape date
   - Defaults to today
   - Can select future dates (up to 7 days typically)
   - **Note:** After 4 PM, same-day availability may be limited

#### Step 5: Execute Scrape
1. Review your selections:
   - Market: [Selected Market]
   - Theaters: [List of selected theaters]
   - Films: [List of selected films]
   - Date: [Selected date]

2. Click **"🎬 Scrape Pricing Data"**
   - Confirmation prompt appears
   - Click **"✅ Yes, Proceed"**

3. **Wait for Completion**
   - Progress spinner displays
   - UI is locked during scrape (typically 1-5 minutes)
   - Do not close browser or navigate away

#### Step 6: View Results
1. **Live Report Display**
   - Table shows all showtimes with prices
   - Organized by Film → Theater → Showtime
   - Color-coded by daypart (Morning/Matinee/Evening/Late Night)

2. **Key Columns:**
   - **Film Title** - Movie name
   - **Theater Name** - Location
   - **Showtime** - Time of showing
   - **Format** - Standard, IMAX, Dolby, etc.
   - **Ticket Type** - Adult, Senior, Child, etc.
   - **Price** - Cost in dollars
   - **URL** - Link to purchase page

#### Step 7: Export Report
1. **Download as CSV**
   - Click **"📄 Download as CSV"**
   - Opens in Excel or text editor
   - Good for data analysis

2. **Download as Excel**
   - Click **"📊 Download as Excel"**
   - Formatted spreadsheet
   - Good for presentations

### Example Use Case

**Scenario:** Compare adult pricing for "Wicked" across 3 AMC theaters in Dallas

1. Select Market: "Dallas-Fort Worth"
2. Select Theaters: AMC Mesquite 30, AMC NorthPark 15, AMC Firewheel 18
3. Search Films: "Wicked"
4. Select Date: December 25, 2025
5. Click "Scrape Pricing Data" → Confirm
6. Wait 3-4 minutes
7. Review pricing table, looking for adult ticket prices
8. Export to Excel for management review

---

## Operating Hours Mode

**Purpose:** Track when theaters open and close each day.

### Workflow

#### Step 1: Select Market and Theaters
- Same process as Market Mode
- Choose market from dropdown
- Select one or more theaters

#### Step 2: Choose Date Range
- **Start Date** - First day to scrape
- **End Date** - Last day to scrape
- **Recommendation:** Limit to 7-14 days per scrape

#### Step 3: Execute Scrape
1. Click **"🕒 Scrape Operating Hours"**
2. Confirm the operation
3. Wait for completion (slower than pricing scrapes)

#### Step 4: View Results
- Table shows theater hours by date
- Columns: Theater | Date | Opening Time | Closing Time
- Empty cells indicate theater is closed

#### Step 5: Export Data
- CSV format recommended for spreadsheet analysis
- Useful for staffing and scheduling analysis

### Example Use Case

**Scenario:** Get holiday hours for all Marcus theaters

1. Select Market: "Milwaukee Metro"
2. Select all Marcus theaters in list
3. Date Range: Dec 24, 2025 - Jan 1, 2026
4. Scrape Operating Hours
5. Export to Excel
6. Share with operations team

---

## CompSnipe Mode

**Purpose:** Competitive intelligence - find and compare competitor pricing using ZIP code search.

### Workflow

#### Step 1: ZIP Code Search
1. **Enter ZIP Code**
   - Type 5-digit ZIP code (e.g., "75001")

2. **Select Date**
   - Choose date for showtime availability
   - This determines which theaters have showtimes

3. **Click Search**
   - Finds all theaters near ZIP code
   - Displays available theaters with operating hours

#### Step 2: Select Competitor Theaters
1. Theater buttons display with operating hours
2. Click to select (turns green)
3. Click again to deselect
4. Select multiple competitors

#### Step 3: Confirm Date
- Date picker shows your previously selected date
- Can change if needed
- Click to proceed

#### Step 4: Search Films
1. **Search by Title**
   - Enter film name in search box
   - Press Enter or click Search

2. **Browse Results**
   - All films showing at selected theaters appear
   - Films organized alphabetically

#### Step 5: Select Films and Showtimes
1. **Choose Films**
   - Click film titles to expand showtime details
   - Select films to compare

2. **Optional: Filter by Daypart**
   - Check boxes: Morning, Matinee, Evening, Late Night
   - Filters showtimes to specific time ranges

#### Step 6: Execute Scrape
1. Review selections
2. Click **"🎬 Scrape Selected Showtimes"**
3. Confirm and wait

#### Step 7: Analyze Results
- Side-by-side pricing comparison
- Identify competitive gaps
- Export for reporting

### Example Use Case

**Scenario:** Check competitor pricing for "Moana 2" near our theater

1. ZIP Code: 60601 (downtown Chicago)
2. Date: Saturday (peak day)
3. Search → Select 3 nearby AMC theaters
4. Search Films: "Moana 2"
5. Select Matinee daypart only
6. Scrape and compare pricing
7. Export findings to share with pricing team

---

## Historical Data and Analysis

**Purpose:** Deep dive into past performance with advanced filtering and visualizations.

### Film Analysis

#### Step 1: Select Analysis Type
- Choose **"Film Analysis"** tab

#### Step 2: Set Parameters
1. **Date Range**
   - Start Date and End Date
   - Limit to meaningful periods (week, month, quarter)

2. **Select Markets** (optional)
   - Filter to specific geographic areas
   - Leave empty for all markets

3. **Select Theaters** (optional)
   - Filter to specific locations
   - Leave empty for all theaters

#### Step 3: Choose Film
1. **Search** - Type film title
2. **Browse** - View all films in database
3. Click desired film

#### Step 4: Apply Filters (Optional)
- **Genre** - Filter by film category
- **Rating** - Filter by MPAA rating (G, PG, PG-13, R)
- **Price Range** - Set min/max price filters

#### Step 5: View Analysis
1. **Summary Metrics**
   - Total Revenue (estimated)
   - Total Showings
   - Average Price
   - Theaters Screened

2. **Detailed Tables**
   - Performance by theater
   - Performance by date
   - Price distribution

3. **Export Options**
   - Download complete analysis
   - Share with team

### Theater Analysis

#### Step 1: Select Analysis Type
- Choose **"Theater Analysis"** tab

#### Step 2: Set Parameters
- Same date range and market selection as Film Analysis

#### Step 3: Select Theater
- Choose theater from dropdown

#### Step 4: View Performance
1. **Theater Metrics**
   - Total showings in period
   - Film count
   - Average pricing

2. **Film Performance at Theater**
   - Which films performed best
   - Pricing trends

3. **Comparison Tables**
   - Compare to other theaters
   - Identify outliers

### Example Use Case

**Scenario:** Analyze "Dune: Part Two" performance in March

1. Select Film Analysis
2. Date Range: March 1-31, 2024
3. Search Film: "Dune: Part Two"
4. Apply Filters: IMAX format only
5. Review:
   - Which theaters had highest revenue
   - Average IMAX pricing
   - Performance trends over month
6. Export report for quarterly review

---

## Poster Board Mode

**Purpose:** Generate schedule and poster-style reports showing all films at selected theaters.

### Workflow

#### Step 1: View Available Films
- System displays all films in your company's database
- Films show with titles and years

#### Step 2: Optional - Discover New Films
1. **Discover from IMDb**
   - Click **"🎬 Discover from IMDb"**
   - Fetches currently trending films
   - Adds to database

2. **Discover from Fandango**
   - Click **"🎟️ Discover from Fandango"**
   - Fetches films from Fandango's listing
   - Adds to database

#### Step 3: Select Theaters
1. Choose from theater list
2. Click to select (multiple allowed)
3. Selected theaters highlighted

#### Step 4: Select Date Range
- Start Date and End Date
- Recommended: 7-day windows
- Generates posters for each date in range

#### Step 5: Choose Films
1. **Option A:** Check individual films
2. **Option B:** Click "Select All"
3. Only selected films appear in poster

#### Step 6: Generate Poster
1. Click **"Generate Poster Report"**
2. System scrapes showtimes for selected films
3. Wait for completion

#### Step 7: View Poster
- Clean, formatted display
- Organized by theater and date
- Shows all showtimes and formats
- Ready for printing or PDF export

#### Step 8: Export
- Download as Excel
- Print-friendly format
- Share with operations or marketing

### Example Use Case

**Scenario:** Weekly schedule poster for lobby display

1. Discover films from Fandango (refresh weekly)
2. Select all theaters in market
3. Date Range: Friday - Thursday (week)
4. Select all films
5. Generate Poster
6. Export to Excel
7. Format for 11x17" poster
8. Print and display in theater lobby

---

## Working with Reports

### Understanding Report Formats

#### CSV (Comma-Separated Values)
- **Best For:** Data analysis, imports, large datasets
- **Opens In:** Excel, Google Sheets, text editors
- **Advantages:** Universal compatibility, small file size
- **Use When:** Sharing with non-Windows users, importing to other systems

#### Excel (.xlsx)
- **Best For:** Presentations, formatted reports, charts
- **Opens In:** Microsoft Excel, Google Sheets
- **Advantages:** Preserves formatting, supports multiple sheets
- **Use When:** Management reports, printing, presentations

### Report Storage

All reports are automatically saved to:
```
data/[YourCompany]/reports/
```

**Naming Convention:**
- `[Date]T[Time]_export.csv` (e.g., `2025-10-26T15-30_export.csv`)
- Timestamped for easy tracking
- Sorted chronologically

### Best Practices

1. **Name Your Downloads**
   - Rename after downloading with descriptive names
   - Example: `AMC_DFW_Pricing_Dec25.xlsx`

2. **Organize by Purpose**
   - Create folders: Weekly Reports, Competitive Analysis, Ad Hoc
   - Use consistent naming conventions

3. **Keep Raw Data**
   - Don't overwrite original CSV exports
   - Make copies before editing

4. **Archive Old Reports**
   - Move reports older than 90 days to archive folder
   - Reduces clutter, maintains history

---

## Tips & Best Practices

### Scraping Best Practices

#### Timing
- ⏰ **Best Time:** 2 AM - 10 AM (less website traffic)
- ⚠️ **Avoid:** Peak hours (6 PM - 10 PM)
- 📅 **Same-Day After 4 PM:** Availability may be limited

#### Scope
- 🎯 **Start Small:** 2-3 theaters, 2-3 films initially
- 📈 **Scale Up:** Increase after confirming results
- ⏱️ **Estimate Time:** ~1 minute per theater

#### Date Selection
- 📆 **Future Dates:** Up to 7 days ahead typically available
- 🎟️ **Peak Days:** Fridays and Saturdays for release weekends
- 🎄 **Holidays:** Book early, high demand

### Data Quality

#### Verify Results
- ✅ **Check Samples:** Spot-check 2-3 showtimes against Fandango.com
- 🔍 **Look for Gaps:** Missing prices may indicate scraping issues
- 🎭 **Format Consistency:** IMAX vs iMax vs IMAX® variations

#### Handle Missing Data
- 🚫 **No Showtimes:** Theater may be closed or not showing film
- ❓ **No Prices:** Website may not display pricing (contact admin)
- ⚠️ **Partial Results:** Re-run scrape if incomplete

### Performance Tips

#### Speed Up Workflows
- 🔖 **Bookmark** common searches (market + theaters)
- 📋 **Document** standard procedures
- ⌨️ **Keyboard Shortcuts:** Ctrl+Click for multi-select

#### Reduce Errors
- 🎬 **Film Names:** Use exact titles from database
- 📅 **Date Validation:** Check start < end date
- 🔄 **Refresh Data:** Run new scrapes weekly for current pricing

---

## Troubleshooting

### Common Issues

#### "No Cache Available" - Mode Disabled
**Problem:** Mode button is gray and disabled

**Solution:**
1. Contact your administrator
2. Admin needs to build theater cache
3. Available in Theater Matching mode (admin only)

#### Scrape Takes Too Long
**Problem:** Scrape running over 10 minutes

**Solution:**
1. **Don't close browser** - let it complete
2. Reduce scope (fewer theaters/films) next time
3. Check internet connection
4. Try during off-peak hours

#### Missing Prices in Report
**Problem:** Showtimes display but prices are blank

**Possible Causes:**
- Theater website doesn't show pricing publicly
- Scraping occurred during website maintenance
- Format issue (e.g., subscription-only pricing)

**Solution:**
1. Verify on Fandango.com manually
2. Contact admin if persistent
3. Try re-scraping during different hours

#### "Database Error" Message
**Problem:** Error message when saving data

**Solution:**
1. Take screenshot of error
2. Note what you were doing
3. Contact administrator
4. Do not retry repeatedly - may corrupt data

#### Film Not in Database
**Problem:** Can't find film when searching

**Solution:**
1. **Poster Mode:** Use "Discover from Fandango" button
2. **Other Modes:** Contact admin to add film
3. Check spelling (exact title required)

#### Export Download Doesn't Start
**Problem:** Click download button but nothing happens

**Solution:**
1. Check browser's download folder
2. Check pop-up blocker settings
3. Try different browser (Chrome, Edge, Firefox)
4. Contact IT if persists

### Getting Help

**Before Contacting Admin:**
1. ✅ Try refreshing the page (F5)
2. ✅ Check this guide's troubleshooting section
3. ✅ Verify your selections are correct
4. ✅ Note any error messages (screenshot if possible)

**When Reporting Issues:**
Include:
- Your username
- Which mode you were using
- What you were trying to do
- Error message (exact text or screenshot)
- Time the issue occurred

**Contact Your Administrator:**
- For account issues
- For theater/market configuration changes
- For persistent errors
- For new feature requests

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Refresh Page | F5 |
| Multi-select (dropdowns) | Ctrl + Click |
| Select All Text | Ctrl + A |
| Copy | Ctrl + C |
| Search in Page | Ctrl + F |

---

## Glossary

**Cache** - Stored theater data that speeds up loading (managed by admin)

**CompSnipe** - Competitive intelligence mode using ZIP code search

**Daypart** - Time of day category (Morning, Matinee, Evening, Late Night)

**Format** - Film presentation type (Standard, IMAX, Dolby Atmos, 3D, etc.)

**Market** - Geographic region containing multiple theaters

**OMDb** - Online Movie Database (provides film metadata)

**Poster** - Schedule-style report showing all films at theater

**Scrape** - Automated data collection from theater websites

**Showtime** - Specific time a film is showing

**Ticket Type** - Category of ticket (Adult, Senior, Child, Student, etc.)

---

## Quick Reference Card

### Market Mode Quick Steps
1. Select Market
2. Select Theaters (2+)
3. Choose Films
4. Pick Date
5. Scrape → Confirm
6. Export Report

### CompSnipe Mode Quick Steps
1. Enter ZIP Code + Date
2. Select Competitor Theaters
3. Confirm Date
4. Search Films
5. Select Films/Showtimes
6. Scrape → Export

### Analysis Mode Quick Steps
1. Choose Film or Theater Analysis
2. Set Date Range
3. Select Markets/Theaters (optional)
4. Pick Film/Theater
5. Apply Filters
6. View Results → Export

### Poster Mode Quick Steps
1. (Optional) Discover New Films
2. Select Theaters
3. Set Date Range
4. Choose Films
5. Generate Poster
6. Export

---

**Need More Help?**
- 📖 See README.md for installation and setup
- 🔧 See ADMIN_GUIDE.md (if you're an admin)
- 📊 See CODE_REVIEW_2025.md for technical details

**Version:** 1.0.0  
**Last Updated:** October 26, 2025
