# Price Scout Demo Instructions

**Demo Account Credentials:**
- **Username**: `Marcus90`
- **Password**: `Testing90!`
- **Role**: User
- **Company**: Marcus Theatres

---

## Getting Started

### 1. Access Price Scout

1. Open your browser
2. Navigate to: **https://pricescout.marketpricescout.com** (or your server URL)
3. You'll see the login screen

### 2. Login

1. Enter username: `Marcus90`
2. Enter password: `Testing90!`
3. Click **"Login"**

You'll be taken to the main dashboard.

---

## Demo Walkthrough

### Demo 1: Market Mode - Compare Pricing

**Scenario:** Compare ticket prices for a popular film across 3 Marcus theaters

**Steps:**

1. **Select Mode**
   - Click **"Market Mode"** in the left sidebar

2. **Choose Your Market**
   - Select your market from the dropdown (e.g., "Milwaukee Metro")

3. **Select Theaters**
   - Click on 2-3 Marcus theaters to highlight them (green = selected)
   - Example: Marcus Ridge, Marcus North Shore, Marcus Majestic

4. **Choose a Film**
   - Use the search box to find a current film
   - Type: "Wicked" or another popular movie
   - Select it from the results

5. **Pick a Date**
   - Use the date picker to select today or tomorrow
   - Note: After 4 PM, next-day data works better

6. **Run the Scrape**
   - Click **"🎬 Scrape Pricing Data"**
   - Confirm by clicking **"✅ Yes, Proceed"**
   - Wait 2-4 minutes (don't close the browser)

7. **Review Results**
   - Table shows all showtimes with prices
   - Look for price differences between theaters
   - Notice different formats (Standard, IMAX, Dolby)
   - Check different ticket types (Adult, Senior, Child)

8. **Export the Report**
   - Click **"📊 Download as Excel"**
   - Open the file to see formatted data
   - Good for sharing with management

**Key Observations:**
- Which theater has the highest/lowest prices?
- How much do premium formats (IMAX) cost vs standard?
- Are matinee prices different from evening shows?

---

### Demo 2: Operating Hours Mode

**Scenario:** Check theater hours for the upcoming week

**Steps:**

1. **Select Mode**
   - Click **"Operating Hours Mode"** in the sidebar

2. **Choose Market and Theaters**
   - Select your market
   - Select 2-3 theaters

3. **Set Date Range**
   - Start Date: Today
   - End Date: 7 days from today

4. **Run Scrape**
   - Click **"🕒 Scrape Operating Hours"**
   - Confirm and wait

5. **Review Results**
   - See opening and closing times for each theater
   - Notice any variations (weekday vs weekend)
   - Empty cells = theater is closed

6. **Export**
   - Download as CSV for scheduling analysis

**Key Observations:**
- Do weekend hours differ from weekdays?
- Are any theaters closed on certain days?
- What's the earliest/latest showing across theaters?

---

### Demo 3: CompSnipe Mode - Competitor Analysis

**Scenario:** Check what competitors are charging near one of your theaters

**Steps:**

1. **Select Mode**
   - Click **"CompSnipe Mode"**

2. **ZIP Code Search**
   - Enter a ZIP code near a Marcus theater
   - Example: 53045 (Brookfield, WI)
   - Select date: This weekend (Friday or Saturday)
   - Click **"Search"**

3. **Select Competitor Theaters**
   - You'll see nearby theaters (including non-Marcus)
   - Click on 2-3 competitor theaters (AMC, Regal, etc.)
   - Note their operating hours shown

4. **Confirm Date**
   - Verify the date shown
   - Click to proceed

5. **Search for Film**
   - Enter a blockbuster film name
   - Example: "Moana 2"
   - Press Enter

6. **Select Films and Dayparts**
   - Click the film you want to analyze
   - Optional: Filter by daypart (Matinee, Evening)
   - Select specific showtimes if desired

7. **Run Scrape**
   - Click **"🎬 Scrape Selected Showtimes"**
   - Confirm and wait

8. **Analyze Results**
   - Compare competitor pricing to your knowledge of Marcus prices
   - Look for pricing gaps or opportunities
   - Export for competitive analysis report

**Key Observations:**
- Are competitors priced higher or lower?
- Do they offer different premium formats?
- What's their pricing strategy (e.g., lower matinees)?

---

### Demo 4: Historical Data and Analysis

**Scenario:** Analyze how a recent film performed

**Steps:**

1. **Select Mode**
   - Click **"Historical Data and Analysis"**

2. **Choose Analysis Type**
   - Select **"Film Analysis"** tab

3. **Set Parameters**
   - Date Range: Last 30 days
   - Markets: Leave empty (all markets) or select specific one
   - Theaters: Leave empty (all) or select specific ones

4. **Select Film**
   - Search for a recent release
   - Example: "Dune: Part Two" or recent blockbuster
   - Click the film

5. **Apply Filters (Optional)**
   - Genre: Action, Drama, etc.
   - Rating: PG-13, R, etc.
   - Price Range: $10-$20

6. **View Analysis**
   - Summary Metrics:
     - Total showings
     - Average price
     - Theaters screened
   - Detailed tables by theater and date
   - Price distribution

7. **Export Analysis**
   - Download complete report
   - Share with team for review

**Key Observations:**
- Which theaters showed the film most?
- Did pricing vary by theater or date?
- What was the average ticket price?

---

### Demo 5: Poster Board Mode

**Scenario:** Generate a weekly schedule poster

**Steps:**

1. **Select Mode**
   - Click **"Poster Board"**

2. **View Available Films**
   - See all films in the database
   - Notice titles and years

3. **Discover New Films (Optional)**
   - Click **"🎟️ Discover from Fandango"**
   - Adds current releases to database

4. **Select Theaters**
   - Choose 1-2 theaters
   - Example: Your flagship location

5. **Set Date Range**
   - Start: This Friday
   - End: Next Thursday (7 days)

6. **Choose Films**
   - Check individual films OR
   - Click **"Select All"** for full schedule

7. **Generate Poster**
   - Click **"Generate Poster Report"**
   - Wait for scraping to complete

8. **View and Export**
   - See formatted schedule by theater and date
   - Download as Excel
   - Format for printing or lobby display

**Key Observations:**
- How many showtimes per film?
- Which films have the most showings?
- Format variety (Standard, IMAX, 3D)?

---

## Demo Tips

### Best Practices to Show

1. **Start Small**
   - Begin with 2-3 theaters, not all at once
   - Choose 1-2 popular films everyone knows

2. **Timing Matters**
   - Best demo time: Morning (faster scraping)
   - Avoid peak hours (6-10 PM)
   - Next-day data works better after 4 PM

3. **Data Quality**
   - Spot-check results against Fandango.com
   - Show how to verify pricing accuracy
   - Explain missing data (theater closed, film not showing)

4. **Workflow Efficiency**
   - Use search instead of scrolling for films
   - Ctrl+Click for multi-select in dropdowns
   - Export reports immediately for records

### Common Demo Questions

**Q: How long does a scrape take?**
A: Typically 1-2 minutes per theater. 3 theaters = 3-6 minutes.

**Q: How often should we scrape?**
A: Weekly for routine monitoring, daily for competitive analysis periods.

**Q: Can I scrape past dates?**
A: No - only current and future dates (up to 7 days ahead).

**Q: What if a film isn't in the database?**
A: Use Poster Mode's "Discover from Fandango" or ask admin to add it.

**Q: Can I compare Marcus to non-Marcus theaters?**
A: Yes! Use CompSnipe Mode for cross-chain comparisons.

---

## Demo Script (5-Minute Version)

**Quick walkthrough for busy stakeholders:**

1. **Login** (30 seconds)
   - Show credentials, explain role-based access

2. **Market Mode Demo** (2 minutes)
   - "Let's compare pricing for Wicked across 3 Milwaukee theaters"
   - Select market, theaters, film, date
   - Run scrape
   - While waiting, explain the use case

3. **Show Results** (1 minute)
   - Point out price differences
   - Show format variations (Standard vs IMAX)
   - Export to Excel

4. **Quick Mode Tour** (1 minute)
   - Click through other modes
   - Brief explanation of each
   - "Operating Hours for scheduling, CompSnipe for competitors, Analysis for trends"

5. **Q&A** (30 seconds)
   - Answer specific questions
   - Offer to do deeper dive on any mode

---

## Demo Script (15-Minute Version)

**Comprehensive walkthrough:**

1. **Introduction** (2 minutes)
   - Explain Price Scout purpose
   - Show login and dashboard
   - Overview of available modes

2. **Market Mode** (5 minutes)
   - Full workflow as described above
   - Explain business value (pricing strategy, competitive positioning)
   - Show export options

3. **CompSnipe Mode** (4 minutes)
   - ZIP code search demonstration
   - Competitor selection
   - Results analysis
   - Competitive intelligence use cases

4. **Quick Tour of Other Modes** (3 minutes)
   - Operating Hours (scheduling)
   - Historical Analysis (performance review)
   - Poster Board (marketing/operations)

5. **Wrap-up** (1 minute)
   - Admin capabilities (user management, role permissions)
   - Security features (password requirements, session timeout)
   - Q&A

---

## After the Demo

### Follow-up Materials
- Share this demo guide
- Provide USER_GUIDE.md for detailed instructions
- Offer ADMIN_GUIDE.md for admin users

### Next Steps
1. Create accounts for actual users
2. Configure markets and theaters
3. Set up role permissions
4. Schedule regular scraping workflows

### Training Resources
- **User Guide**: `docs/USER_GUIDE.md`
- **Admin Guide**: `docs/ADMIN_GUIDE.md`
- **Bulk Upload**: `BULK_USER_UPLOAD_GUIDE.md`
- **Troubleshooting**: See USER_GUIDE.md → Troubleshooting

---

## Troubleshooting During Demo

### Scrape Takes Too Long
- Reduce number of theaters
- Try different time of day
- Check internet connection

### Film Not Found
- Use exact title
- Try "Discover from Fandango" in Poster Mode
- Contact admin to add manually

### Login Fails
- Verify caps lock is off
- Check password: `Testing90!` (capital T and !)
- Username is case-sensitive: `Marcus90`

### Page Refresh During Scrape
- Don't panic - let it complete
- Don't close browser
- Data saves automatically

---

## Demo Scenarios by Audience

### For Executives
- Focus on: CompSnipe Mode, Historical Analysis
- Show: Excel reports, pricing insights, competitive gaps
- Emphasize: ROI, competitive advantage, data-driven decisions

### For Theater Managers
- Focus on: Market Mode, Operating Hours, Poster Board
- Show: Day-to-day operational use, scheduling, marketing
- Emphasize: Time savings, automation, consistency

### For Pricing Analysts
- Focus on: Market Mode, Historical Analysis, CompSnipe
- Show: Data export, analysis workflows, trend identification
- Emphasize: Data quality, flexibility, comprehensive reports

### For IT/Security
- Focus on: User management, role permissions, security features
- Show: Bulk upload, password policies, audit logging
- Emphasize: Enterprise security, scalability, deployment options

---

**Demo Account Summary**

| Setting | Value |
|---------|-------|
| **Username** | Marcus90 |
| **Password** | Testing90! |
| **Role** | User |
| **Company** | Marcus Theatres |
| **Access Level** | Standard operational modes |
| **No Access To** | Admin, User Management, System Settings |

---

**Version:** 1.0
**Last Updated:** 2025-01-09
**For:** Demo and Testing Purposes
