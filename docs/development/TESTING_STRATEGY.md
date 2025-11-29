# Testing Coverage Strategy & Recommendations

## 📊 Current Status (Overall: 38%)

**Total:** 169 tests passing, 6875 statements, 38% coverage

## 🎯 High-Impact Targets (Prioritized)

### ✅ COMPLETED
- ✅ **imdb_scraper.py**: 25% → **100%** (+11 tests)
- ✅ **database.py**: 38% → **60%** (+22 tests)
- ✅ **box_office_mojo_scraper.py**: 48% → **66%** (+9 tests)
- ✅ **utils.py**: 36% → **47%** (+34 tests)
- ✅ **admin.py**: 11% → **25%** (+6 tests)

### 🎯 NEXT PRIORITIES (Quick Wins)

#### 1. **users.py** - 21% ⭐ HIGHEST PRIORITY
- **Size:** 53 statements (SMALL!)
- **Type:** Database operations (user CRUD)
- **Target:** 70%
- **Effort:** LOW - Pure business logic
- **Impact:** HIGH - Critical security functionality
- **Testable functions:**
  - `create_user()` - User creation with password hashing
  - `authenticate_user()` - Login validation
  - `update_user()` - User updates
  - `delete_user()` - User deletion
  - `get_all_users()` - User listing
  - Password hashing/verification

#### 2. **omdb_client.py** - 59% ⭐ HIGH PRIORITY
- **Size:** 145 statements
- **Type:** API client
- **Target:** 80%
- **Effort:** LOW - API mocking is straightforward
- **Impact:** HIGH - Core metadata fetching
- **Testable functions:**
  - `search_film()` - Film search
  - `get_film_by_imdb_id()` - Fetch by ID
  - `_parse_response()` - Response parsing
  - Error handling for API failures
  - Rate limiting
  - Response caching

#### 3. **theming.py** - 89% ⭐ QUICK WIN
- **Size:** 28 statements (TINY!)
- **Current:** 89% - Missing only 3 statements
- **Target:** 100%
- **Effort:** MINIMAL
- **Impact:** LOW but easy completion

### 🔧 MEDIUM PRIORITIES (Core Business Logic)

#### 4. **scraper.py** - 43%
- **Size:** 830 statements (LARGE)
- **Type:** Core async scraping logic
- **Target:** 60-65%
- **Effort:** MEDIUM - Requires async mocking
- **Impact:** VERY HIGH - Core functionality
- **Focus areas:**
  - `scrape_theater()` - Main scraping function
  - `_parse_showings()` - HTML parsing
  - `_parse_ticket_types()` - Ticket parsing
  - Error handling and retries
  - Cache management

#### 5. **data_management_v2.py** - 36%
- **Size:** 735 statements (VERY LARGE)
- **Type:** Business logic + some UI
- **Target:** 50-60%
- **Effort:** MEDIUM
- **Impact:** HIGH - Core data operations
- **Focus areas:**
  - Film discovery functions
  - Data enrichment
  - Cache management
  - Ignore list handling

### 📱 MODE FILES (UI Heavy - Strategic Testing)

#### **market_mode.py** - 80% ✅ SUCCESS MODEL
- Already well-tested!
- Use as template for other modes

#### **analysis_mode.py** - 46%
- 662 statements
- Mix of business logic and UI
- Test data processing functions
- Use UI test helpers for rendering

#### **poster_mode.py** - 14%
- 414 statements
- Likely heavy UI
- Focus on data fetching/processing
- Skip pure rendering

#### **operating_hours_mode.py** - 18%
- 624 statements  
- Focus on business logic only

#### **compsnipe_mode.py** - 4%
- 165 statements
- Almost completely untested
- Start with error handling

### ❌ LOW PRIORITY / SKIP

#### **theater_matching_tool.py** - 0%
- 639 statements
- Likely complex UI tool
- Skip unless critical bugs found

#### **ui_components.py** - 36%
- Streamlit widgets
- Test only if used in critical paths

#### **price_scout_app.py** - 44%
- Main app file
- Heavy Streamlit orchestration
- Focus on route logic only

## 📈 Recommended Action Plan

### Week 1: Quick Wins (Easy 5-10% coverage gain)
1. ✅ **imdb_scraper.py** - COMPLETED (100%)
2. **users.py** (21% → 70%)
   - ~8-10 tests for CRUD operations
   - Test password hashing
   - Test authentication
   
3. **theming.py** (89% → 100%)
   - Add 1-2 tests for missing lines

4. **omdb_client.py** (59% → 80%)
   - ~10 tests for API calls
   - Mock httpx responses
   - Test error handling

**Expected gain:** +5-7% overall coverage

### Week 2: Core Business Logic (8-12% coverage gain)
5. **scraper.py** (43% → 60%)
   - Focus on parsing functions
   - Test error paths
   - Mock async operations
   - ~20-25 tests

6. **data_management_v2.py** (36% → 50%)
   - Film discovery
   - Data enrichment
   - ~15-20 tests

**Expected gain:** +8-12% overall coverage

### Week 3: UI Mode Testing (5-8% coverage gain)
7. Use UI test helpers for modes:
   - **analysis_mode.py** (46% → 55%)
   - **poster_mode.py** (14% → 30%)
   - **operating_hours_mode.py** (18% → 30%)

**Expected gain:** +5-8% overall coverage

## 🎓 Testing Strategy by Module Type

### Pure Business Logic (Target: 80-90%)
- Scrapers (imdb_scraper ✅, box_office_mojo ✅)
- API clients (omdb_client, users)
- Data parsers
- Utility functions ✅

### Mixed Logic + UI (Target: 50-70%)
- data_management_v2
- scraper
- market_mode ✅
- analysis_mode

### UI-Heavy Modes (Target: 30-45%)
- poster_mode
- operating_hours_mode
- compsnipe_mode
- Use UI test helpers for error paths only

### Skip Testing (Accept low coverage)
- theater_matching_tool
- ui_components (unless critical)
- Pure Streamlit orchestration

## 🛠️ Tools Available

### UI Test Helpers ✅ READY TO USE
- **Location:** `tests/ui_test_helpers.py`
- **Guide:** `UI_TESTING_GUIDE.md`
- **Features:**
  - `mock_streamlit()` - Mock all Streamlit functions
  - `create_session_state()` - Mock session state
  - `assert_error_displayed()` - Check error messages
  - `simulate_button_click()` - Simulate user input
  - 10+ ready-to-use patterns

### Existing Test Patterns
- **Database tests:** `tests/test_database.py` (temp_db fixture)
- **Scraper tests:** `tests/test_box_office_mojo_scraper.py` (httpx mocking)
- **API tests:** `tests/test_imdb_scraper.py` (response mocking)
- **Admin tests:** `tests/test_admin.py` (file system mocking)

## 📊 Coverage Goals

### Aggressive Target (48% by next month)
- Complete Phase 1 & 2
- Focus on users.py, omdb_client.py, scraper.py
- Add selective mode tests

### Conservative Target (42% by next month)  
- Complete Phase 1
- users.py + omdb_client.py + theming.py
- Safer, achievable goal

### Stretch Target (55% if time permits)
- Complete all 3 phases
- Comprehensive mode testing
- Would require ~100+ new tests

## 💡 Key Insights

1. **Small files = Big wins**
   - users.py (53 lines) could add 2% coverage with 10 tests
   - theming.py (28 lines) could hit 100% with 2 tests

2. **Pure logic is easiest**
   - imdb_scraper went 25% → 100% quickly
   - API clients and scrapers are straightforward

3. **UI testing is strategic**
   - Don't aim for high coverage on UI-heavy modes
   - Focus on error handling and data processing
   - Use UI test helpers to reduce boilerplate

4. **Existing patterns work**
   - Fixture-based testing is proven
   - Mocking external dependencies is effective
   - Copy-paste patterns from successful tests

## 🎯 Success Metrics

- **Current:** 169 tests, 38% coverage
- **Phase 1 Target:** ~185 tests, 43% coverage (+16 tests)
- **Phase 2 Target:** ~220 tests, 50% coverage (+35 tests)
- **Phase 3 Target:** ~260 tests, 55% coverage (+40 tests)

## 📝 Next Steps

1. ✅ Review this document
2. ✅ Check out `UI_TESTING_GUIDE.md` for patterns
3. Start with **users.py** (highest impact, lowest effort)
4. Then **omdb_client.py** (API testing is straightforward)
5. Use coverage HTML report to find uncovered lines
6. Copy-paste test patterns from similar modules

---

**Remember:** Perfect is the enemy of good. Aim for:
- 80%+ on pure business logic
- 50-60% on mixed logic
- 30-40% on UI-heavy code
- Skip complex UI tools entirely
