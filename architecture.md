# Architecture Documentation — CMF XBRL Financial Data Warehouse

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Component Architecture](#component-architecture)
4. [Data Flow](#data-flow)
5. [Database Schema](#database-schema)
6. [Component Interactions](#component-interactions)
7. [Error Handling Strategy](#error-handling-strategy)
8. [Performance Considerations](#performance-considerations)
9. [Scalability Patterns](#scalability-patterns)
10. [Security Considerations](#security-considerations)

---

## System Overview

### Purpose

The CMF XBRL Financial Data Warehouse is a **multi-source financial data integration system** that:

1. **Acquires** financial data from multiple sources:
   - CMF (Chilean Financial Market Commission) XBRL filings
   - CMF SBIF API v3 for banking data
   - AFP (Pension Fund Manager) PDF reports

2. **Processes** raw data through standardized pipelines:
   - XBRL parsing and fact extraction
   - Data normalization and mapping
   - Quality assessment and validation

3. **Stores** in a structured warehouse:
   - Normalized financials table
   - Derived metrics table
   - Quality flags table

4. **Enables** financial analysis:
   - Ratio calculations
   - Cross-company comparisons
   - Time-series analysis

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA SOURCES                                  │
├─────────────────┬─────────────────┬─────────────────────────────────┤
│  CMF Portal     │  CMF API SBIF   │  AFP PDF Reports                │
│  (XBRL files)   │  v3 (Banks)     │  (Planvital, Capital, etc.)     │
└────────┬────────┴────────┬────────┴────────────────────────────────┘
         │                 │
         ▼                 ▼
┌─────────────────┐ ┌─────────────────┐
│  scraper/       │ │  cmf_api.py     │
│  fetcher.py     │ │  afp_pipeline.py│
│  parser.py      │ │                 │
│  downloader.py  │ │                 │
└────────┬────────┘ └────────┬────────┘
         │                   │
         ▼                   ▼
┌─────────────────┐ ┌─────────────────┐
│  data/          │ │  data/          │
│  {rut}/{year}/  │ │  afp/           │
│  {month}/.zip   │ │  .pdf           │
└────────┬────────┘ └────────┬────────┘
         │                   │
         ▼                   ▼
┌─────────────────┐ ┌─────────────────┐
│  xbrl_parser.py │ │  afp_pipeline.py│
│  (ZIP → CSV)    │ │  (PDF → CSV)    │
└────────┬────────┘ └────────┬────────┘
         │                   │
         └─────────┬─────────┘
                   ▼
         ┌─────────────────┐
         │  pipeline.py    │
         │  (normalize,    │
         │   derive,       │
         │   quality)      │
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │  output/        │
         │  warehouse.db   │
         │  (3 tables)     │
         └────────┬────────┘
                  ▼
         ┌─────────────────┐
         │  ratios.py      │
         │  query.py       │
         │  (analysis)     │
         └─────────────────┘
```

---

## Architecture Principles

### 1. **Separation of Concerns**

Each module has a single, well-defined responsibility:

| Module | Responsibility |
|--------|---------------|
| `scraper/` | HTTP requests and file downloads only |
| `xbrl_parser.py` | XBRL parsing, no business logic |
| `pipeline.py` | Data transformation and normalization |
| `ratios.py` | Financial calculations only |
| `query.py` | Data retrieval and presentation |

### 2. **Fail-Safe Design**

- **Never stop on individual errors**: Log and continue
- **Partial results are acceptable**: 90% data is better than 0%
- **Audit trails**: Every decision is logged
- **Data validation**: Quality scores on every row

### 3. **Idempotency**

- **Re-runnable**: Scripts can be executed multiple times safely
- **Deduplication**: Skip existing files, upsert database rows
- **Deterministic**: Same inputs → same outputs

### 4. **Configurability**

- **YAML mappings**: Business logic in `concept_map.yaml`, not code
- **CLI arguments**: All parameters exposed via command-line
- **Environment variables**: Sensitive data in `.env`

### 5. **Data Quality First**

- **Quality flags**: Every row has quality assessments
- **Source tracking**: Every derived value has a `*_source` field
- **Completeness metrics**: Percentage of critical fields present

---

## Component Architecture

### Phase 1: Data Acquisition

#### 1.1 CMF Scraper (`scraper/`)

**Purpose**: Download XBRL ZIP files from CMF portal

**Components**:

```python
scraper/
├── main.py              # Orchestrator
├── fetcher.py           # HTTP client
├── parser.py            # HTML parser
├── downloader.py        # File handler
├── logger.py            # Logging utility
└── company_index.py     # Company registry
```

**Key Design Patterns**:

- **Strategy Pattern**: Flexible URL detection in `parser.py`
- **Retry Pattern**: Exponential backoff in `fetcher.py`
- **Template Method**: Standardized flow in `main.py`

**Data Flow**:

```
main.py
  ├── fetcher.get_company_list()
  ├── parser.extract_companies()
  ├── FOR each period:
  │   ├── FOR each company:
  │   │   ├── fetcher.get_company_period()
  │   │   ├── parser.find_xbrl_url()
  │   │   ├── fetcher.download_file()
  │   │   └── downloader.save()
  │   └── log summary
  └── print audit report
```

#### 1.2 CMF API Client (`cmf_api.py`)

**Purpose**: Fetch banking data from CMF SBIF API v3

**Coverage**:
- Banks **without** XBRL: BCI.SN, BSANTANDER.SN, ITAUCL.SN
- Banks **with** XBRL (enrichment): CHILE.SN, BICE.SN

**Key Features**:
- **Account mapping**: CMF codes → warehouse columns
- **Negation handling**: Cost fields stored as positive values
- **Upsert semantics**: Replace existing data by (ticker, year, month)

**Architecture**:

```
main()
  ├── build_row() [per ticker/year]
  │   ├── fetch_balance() → BALANCE_MAP
  │   ├── fetch_income() → INCOME_MAP
  │   └── combine into warehouse row
  ├── upsert_rows()
  │   ├── identify new vs update
  │   └── custom UPSERT method
  └── refresh_derived()
      └── recalculate metrics for affected tickers
```

#### 1.3 AFP Pipeline (`afp_pipeline.py`)

**Purpose**: Process AFP PDF reports when XBRL is unavailable

**Workflow**:
1. Download PDF from AFP websites
2. Extract tables using `pdfplumber`
3. Map to warehouse schema
4. Validate against known benchmarks

**Challenges**:
- **Non-standard formats**: Each AFP has different PDF layout
- **Table detection**: Heuristics to identify financial tables
- **Currency handling**: Some report in CLP, others in USD

### Phase 2: XBRL Processing

#### 2.1 XBRL Parser (`xbrl_parser.py`)

**Purpose**: Extract all financial facts from XBRL files

**Key Innovation**: **Context Role Assignment**

The parser uses a **two-strategy approach** to assign semantic meaning to XBRL contexts:

**Strategy 1: Named Context IDs** (Early XBRL files)
```python
NAMED_CONTEXT_ROLE = {
    "CierreTrimestreActual":    "balance_current",
    "SaldoActualInicio":        "balance_prev_year_end",
    "TrimestreAcumuladoActual": "period_current",
    "AnualAnterior":            "period_prev_year",
}
```

**Strategy 2: Date Analysis** (Generic IDs)
```python
# Find instant closest to year-end (±20 days)
# Find full-year duration (300-400 days)
# Assign based on proximity to target dates
```

**Output Schema**:

```csv
rut,ticker,year,month,prefix,concept,context_id,context_role,
period_type,date,period_start,unit,value,value_raw
```

**Performance Optimizations**:
- **itertuples()**: 10x faster than iterrows()
- **Selective parsing**: Skip dimensional contexts
- **Memory efficient**: Stream processing of large files

### Phase 3: Data Transformation

#### 3.1 Pipeline (`pipeline.py`)

**Purpose**: Transform raw XBRL facts into structured warehouse

**Three-Step Process**:

**Step 1: Normalize**
```python
def normalize(facts, concept_map, industry_map):
    # One row per (ticker, year, month)
    # Priority: consolidated > CLP > full-year
    # Industry-aware field selection
```

**Step 2: Derive Metrics**
```python
def derive_metrics(norm):
    # FCF = CFO - CapEx
    # debt_total = short_term + long_term
    # net_debt = debt_total - cash
    # ebitda_calc = operating_income + D&A
    # financing_liabilities (banks only)
```

**Step 3: Quality Flags**
```python
def quality_flags(norm):
    # operating_expenses_quality: full/partial/poor
    # debt_quality: reliable/proxy/poor
    # fcf_quality: high/medium/low
    # data_completeness_pct: % of critical fields
```

**Industry Handling**:

```python
# Financial (Banks, AFPs)
- Debt fields: NULL (not applicable)
- Bank-specific fields: deposits_from_customers, loans_to_customers

# Non-financial
- Debt fields: short_term, long_term, borrowings
- Bank-specific fields: NULL (not applicable)
```

### Phase 4: Analysis

#### 4.1 Ratios Calculator (`ratios.py`)

**Purpose**: Calculate financial ratios for analysis

**Categories**:
- **Liquidity**: current_ratio, quick_ratio
- **Solvency**: debt_to_equity, debt_to_assets
- **Profitability**: roe, roa, net_margin
- **Efficiency**: asset_turnover

#### 4.2 Query Interface (`query.py`)

**Purpose**: Provide convenient access to warehouse data

**Features**:
- **Filtered queries**: By ticker, year, industry
- **Aggregations**: Sum, avg, min, max by period
- **Time-series**: Multi-year trends
- **Comparisons**: Cross-company metrics

---

## Data Flow

### End-to-End Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. ACQUISITION                                                  │
└─────────────────────────────────────────────────────────────────┘
CMF Portal → scraper/main.py → data/{rut}/{year}/{month}/{id}.zip
CMF API → cmf_api.py → warehouse.db (direct insert)
AFP PDF → afp_pipeline.py → warehouse.db (direct insert)

┌─────────────────────────────────────────────────────────────────┐
│ 2. PARSING                                                      │
└─────────────────────────────────────────────────────────────────┘
data/*.zip → xbrl_parser.py → output/facts_raw.csv
              └─ Extract contexts
              └─ Extract facts
              └─ Assign roles

┌─────────────────────────────────────────────────────────────────┐
│ 3. TRANSFORMATION                                               │
└─────────────────────────────────────────────────────────────────┘
facts_raw.csv → pipeline.py → warehouse.db
                ├─ normalize()
                ├─ derive_metrics()
                └─ quality_flags()

┌─────────────────────────────────────────────────────────────────┐
│ 4. ANALYSIS                                                     │
└─────────────────────────────────────────────────────────────────┘
warehouse.db → ratios.py → output/ratios.csv
warehouse.db → query.py → stdout/CSV/plot
```

### Data Schema Evolution

```
Raw XBRL (hierarchical)
    ↓ extract
Facts Raw (flat, denormalized)
    ↓ normalize
Normalized Financials (wide format)
    ↓ derive
Derived Metrics (calculated fields)
    ↓ quality
Quality Flags (metadata)
```

---

## Database Schema

### Table 1: `normalized_financials`

**Purpose**: One row per company per period

**Primary Key**: (ticker, year, month)

**Indexes**:
- `idx_norm_ticker_year`: (ticker, year)
- `idx_norm_ticker_year_month`: (ticker, year, month)

**Schema**:

```sql
CREATE TABLE normalized_financials (
    -- Identifiers
    ticker TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    industry TEXT NOT NULL,  -- 'financial' or 'non_financial'
    reporting_currency TEXT,  -- 'CLP', 'USD', etc.

    -- Balance Sheet
    assets REAL,
    current_assets REAL,
    non_current_assets REAL,
    liabilities REAL,
    current_liabilities REAL,
    non_current_liabilities REAL,
    equity REAL,
    equity_parent REAL,
    minority_interest REAL,

    -- Assets Detail
    cash REAL,
    trade_receivables REAL,
    inventories REAL,
    intangibles REAL,
    ppe REAL,
    goodwill REAL,

    -- Liabilities Detail
    trade_payables REAL,
    debt_short_term REAL,          -- non_financial only
    debt_long_term REAL,           -- non_financial only
    borrowings REAL,               -- non_financial only
    deposits_from_customers REAL,  -- financial only
    loans_to_customers REAL,       -- financial only

    -- Equity Detail
    issued_capital REAL,
    retained_earnings REAL,

    -- Income Statement
    revenue REAL,
    cost_of_sales REAL,
    gross_profit REAL,
    operating_income REAL,
    distribution_costs REAL,
    administrative_expense REAL,
    other_expense REAL,
    other_income REAL,
    ebit REAL,
    depreciation_amortization REAL,
    employee_benefits REAL,
    finance_income REAL,
    finance_costs REAL,

    -- Profitability
    profit_before_tax REAL,
    income_tax REAL,
    net_income REAL,
    net_income_parent REAL,

    -- Cash Flow
    cfo REAL,                      -- operating cash flow
    capex REAL,                    -- capital expenditures
    investing_cf REAL,
    dividends_paid REAL,
    proceeds_from_borrowings REAL,
    repayment_of_borrowings REAL,
    financing_cf REAL,
    net_change_cash REAL,

    -- Per-Share Data
    eps_basic REAL,
    eps_diluted REAL,
    shares_outstanding REAL,

    PRIMARY KEY (ticker, year, month)
);
```

### Table 2: `derived_metrics`

**Purpose**: Calculated metrics with source tracking

**Primary Key**: (ticker, year, month)

**Indexes**:
- `idx_derived_ticker_year`: (ticker, year)

**Schema**:

```sql
CREATE TABLE derived_metrics (
    -- Identifiers
    ticker TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    industry TEXT NOT NULL,

    -- Free Cash Flow
    fcf REAL,                      -- cfo - capex
    fcf_source TEXT,               -- 'cfo_minus_capex', 'missing_capex', etc.

    -- Debt Metrics (non_financial only)
    debt_total REAL,
    debt_total_source TEXT,        -- 'short_plus_long', 'borrowings_total', etc.
    net_debt REAL,                 -- debt_total - cash

    -- Profitability
    ebitda_calc REAL,
    ebitda_source TEXT,            -- 'ebit_plus_da', 'missing'

    -- Bank-specific (financial only)
    financing_liabilities REAL,    -- deposits_from_customers

    PRIMARY KEY (ticker, year, month),
    FOREIGN KEY (ticker, year, month)
        REFERENCES normalized_financials(ticker, year, month)
);
```

### Table 3: `quality_flags`

**Purpose**: Data quality assessments per period

**Primary Key**: (ticker, year, month)

**Indexes**:
- `idx_quality_ticker_year`: (ticker, year)

**Schema**:

```sql
CREATE TABLE quality_flags (
    -- Identifiers
    ticker TEXT NOT NULL,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    industry TEXT NOT NULL,

    -- Quality Assessments
    operating_expenses_quality TEXT,  -- 'full', 'partial', 'poor'
    debt_quality TEXT,                -- 'reliable', 'proxy', 'poor', 'not_applicable'
    fcf_quality TEXT,                 -- 'high', 'medium', 'low'

    -- Field Presence
    has_revenue INTEGER,
    has_assets INTEGER,
    has_equity INTEGER,
    has_operating_cf INTEGER,

    -- Completeness
    data_completeness_pct REAL,       -- % of critical fields present

    PRIMARY KEY (ticker, year, month),
    FOREIGN KEY (ticker, year, month)
        REFERENCES normalized_financials(ticker, year, month)
);
```

---

## Component Interactions

### Interaction Matrix

| Caller | Component | Data In | Data Out | Side Effects |
|--------|-----------|----------|----------|--------------|
| User | scraper/main.py | CLI args | ZIP files | logs/* |
| scraper/main.py | scraper/fetcher.py | URLs | HTML | HTTP requests |
| scraper/main.py | scraper/parser.py | HTML | URLs | None |
| scraper/main.py | scraper/downloader.py | Binary | ZIP files | Disk I/O |
| User | xbrl_parser.py | CLI args | facts_raw.csv | None |
| User | pipeline.py | facts_raw.csv | warehouse.db | CSV outputs |
| pipeline.py | pipeline (self) | facts_raw.csv | 3 tables | DB inserts |
| User | cmf_api.py | CLI args | warehouse.db | API requests |
| cmf_api.py | pipeline.py | ticker list | 2 tables | DB updates |
| User | ratios.py | warehouse.db | ratios.csv | None |
| User | query.py | warehouse.db | stdout/CSV | None |

### Dependency Graph

```
┌─────────────────┐
│  User / Cron    │
└────────┬────────┘
         │
    ┌────┴─────┐
    │          │
    ▼          ▼
┌────────┐  ┌────────────┐
│scraper/│  │ cmf_api.py │
└────┬───┘  └─────┬──────┘
     │            │
     ▼            ▼
┌────────────┐    │
│data/       │    │
│*.zip files │    │
└─────┬──────┘    │
     │           │
     ▼           │
┌────────────┐   │
│xbrl_parser.│   │
│py          │   │
└─────┬──────┘   │
     │          │
     ▼          │
┌────────────┐   │
│output/     │   │
│facts_raw.  │   │
│csv         │   │
└─────┬──────┘   │
     │          │
     └────┬─────┘
          ▼
    ┌────────────┐
    │ pipeline.py│
    └─────┬──────┘
          │
    ┌─────┴─────┐
    │           │
    ▼           ▼
┌─────────┐ ┌──────────┐
│ratios.py│ │ query.py │
└─────────┘ └──────────┘
```

---

## Error Handling Strategy

### Layered Error Handling

```python
# Layer 1: Network Level (fetcher.py, cmf_api.py)
try:
    response = requests.get(url, timeout=30)
except requests.exceptions.RequestException as e:
    logger.error(f"Network error: {e}")
    return None  # Caller decides retry logic

# Layer 2: Parse Level (parser.py, xbrl_parser.py)
try:
    soup = BeautifulSoup(html, 'lxml')
    data = extract_data(soup)
except (AttributeError, ValueError) as e:
    logger.warning(f"PARSE_WARNING: {e}")
    return {}  # Return empty, continue processing

# Layer 3: Business Logic Level (pipeline.py)
try:
    result = process_row(row)
except Exception as e:
    logger.error(f"Processing error for {row['ticker']}: {e}")
    return None  # Skip this row, continue

# Layer 4: Storage Level (downloader.py, pipeline.py)
try:
    save_to_database(data)
except sqlite3.Error as e:
    logger.critical(f"Database error: {e}")
    raise  # Re-raise - this is critical
```

### Error Categories

| Category | Action | Example |
|----------|--------|---------|
| **Network transient** | Retry (3x, exponential backoff) | Timeout, connection reset |
| **Network permanent** | Log and skip | 404 Not Found, 403 Forbidden |
| **Parse error** | Log warning, return empty | Unexpected HTML structure |
| **Data missing** | Log info, use NULL | Field not found in XBRL |
| **Data invalid** | Log warning, skip row | Negative cash balance |
| **Database error** | Log critical, raise | Disk full, lock timeout |

### Logging Hierarchy

```python
# CRITICAL: System-level failures
logger.critical("Database connection failed")

# ERROR: Data loss scenarios
logger.error(f"Failed to process {ticker}: {error}")

# WARNING: Recoverable issues
logger.warning(f"PARSE_WARNING: {field} not found in XBRL")

# INFO: Normal operations
logger.info(f"Downloaded {count} files for {period}")

# DEBUG: Detailed diagnostics
logger.debug(f"Context {ctx_id} assigned role {role}")
```

---

## Performance Considerations

### Bottleneck Analysis

| Component | Bottleneck | Optimization |
|-----------|-----------|--------------|
| scraper/main.py | Sequential HTTP requests | Parallelization (future) |
| xbrl_parser.py | XML parsing (lxml) | Use itertuples(), skip contexts |
| pipeline.py | DataFrame operations | Vectorization, avoid iterrows |
| cmf_api.py | API rate limits | Configurable delays |
| SQLite | Single-threaded writes | Bulk inserts, transactions |

### Performance Benchmarks

**Typical Execution Times** (as of 2025):

```python
# Scraper (100 companies, 1 year)
scraper/main.py --year 2023       # ~5 minutes

# XBRL Parser (100 ZIP files)
xbrl_parser.py                     # ~2 minutes

# Pipeline (10k facts → warehouse)
pipeline.py                        # ~30 seconds

# CMF API (3 banks, 15 years)
cmf_api.py --ticker BCI.SN        # ~1 minute

# Ratios (warehouse → calculations)
ratios.py                          # ~10 seconds
```

### Memory Management

**Strategies**:
- **Chunk processing**: Process XBRL files one at a time
- **Streaming**: Don't load entire dataset into memory
- **Typed operations**: Use specific dtypes in DataFrames
- **Resource cleanup**: Explicit close() on file handles

**Example**:

```python
# BAD: Loads entire dataset into memory
all_data = []
for zip_file in zip_files:
    data = parse_zip(zip_file)
    all_data.append(data)
df = pd.concat(all_data)  # Memory spike!

# GOOD: Process incrementally
chunks = []
for zip_file in zip_files:
    data = parse_zip(zip_file)
    chunks.append(data)
    if len(chunks) >= 100:
        df = pd.concat(chunks)
        process_chunk(df)
        chunks = []  # Free memory
```

---

## Scalability Patterns

### Current Limitations

| Constraint | Current Limit | Reason |
|------------|---------------|--------|
| Concurrent downloads | 1 (sequential) | Avoid rate limiting |
| Warehouse size | ~1M rows comfortably | SQLite performance |
| XBRL file size | ~100MB | Memory constraints |
| API requests | ~250/day | CMF rate limits |

### Future Scaling Options

#### 1. Horizontal Scaling (Multi-Process)

```python
# Potential implementation (not currently used)
from concurrent.futures import ProcessPoolExecutor

def scrape_year(year):
    return run_scraper(year)

with ProcessPoolExecutor(max_workers=4) as executor:
    executor.map(scrape_year, range(2020, 2025))
```

#### 2. Database Migration

```python
# SQLite → PostgreSQL migration path
# (When warehouse exceeds 1M rows)

# Current
DB_PATH = "output/warehouse.db"
con = sqlite3.connect(DB_PATH)

# Future
import psycopg2
con = psycopg2.connect(
    host="localhost",
    database="cmf_xbrl",
    user="analyst",
    password="***"
)
```

#### 3. Caching Layer

```python
# Potential Redis caching for API responses
# (not currently implemented)

import redis
cache = redis.Redis(host='localhost', port=6379)

def fetch_with_cache(url):
    cached = cache.get(url)
    if cached:
        return json.loads(cached)

    data = fetch_from_api(url)
    cache.setex(url, 3600, json.dumps(data))
    return data
```

---

## Security Considerations

### Credential Management

**Current Approach**:
```bash
# .env file (not versioned)
CMF_API_KEY=secret_key_here
```

**Best Practices**:
- ✅ File permissions: `chmod 600 .env`
- ✅ Git ignore: `.env` in `.gitignore`
- ✅ Template: `.env.example` with placeholder
- ❌ Avoid: Hardcoded keys in source code

### API Key Security

```python
# Good: Environment variable
API_KEY = os.getenv("CMF_API_KEY", "")

# Bad: Hardcoded
API_KEY = "abc123xyz"  # NEVER do this!

# Bad: In config files (if committed)
# config.yaml
api_key: "abc123xyz"  # NEVER do this!
```

### Input Validation

```python
# Validate ticker symbols
def validate_ticker(ticker: str) -> bool:
    """Chilean tickers end with .SN and are 4-12 chars."""
    pattern = r'^[A-Z]{2,10}\.SN$'
    return re.match(pattern, ticker) is not None

# Validate years
def validate_year(year: int) -> bool:
    """Reasonable year range."""
    return 1990 <= year <= datetime.now().year + 1

# Validate file paths
def safe_path_join(base: str, *parts) -> str:
    """Prevent directory traversal attacks."""
    full = os.path.join(base, *parts)
    if not full.startswith(base):
        raise ValueError("Invalid path")
    return full
```

### SQL Injection Prevention

```python
# Good: Parameterized queries
ticker = "BCI.SN"
query = "SELECT * FROM normalized_financials WHERE ticker = ?"
df = pd.read_sql(query, con, params=[ticker])

# Bad: String interpolation (SQL injection risk)
ticker = "BCI.SN"
query = f"SELECT * FROM normalized_financials WHERE ticker = '{ticker}'"
df = pd.read_sql(query, con)  # DON'T DO THIS!
```

### HTTPS Everywhere

```python
# All external requests use HTTPS
BASE_URL = "https://www.cmfchile.cl"
API_URL = "https://api.cmfchile.cl"

# Verify SSL certificates (default in requests)
response = requests.get(url, timeout=30)  # verify=True by default
```

---

## Appendix

### File Dependencies

```
agent.md                 # Project guidelines
architecture.md          # This file
requirements.txt         # Python dependencies
config.yaml             # Global configuration
.env                    # Environment variables (not versioned)
├── CMF_API_KEY

concept_map.yaml        # XBRL → warehouse mapping
concept_map_banks.yaml  # Bank-specific mapping
concept_map_afp.yaml    # AFP-specific mapping

tickers_chile.json      # Ticker universe
nemo_map.json          # NEMO → ticker mapping

data/                  # Raw downloads
├── {rut}/
│   └── {year}/{month:02d}/{filing_id}.zip
└── index.json         # Company registry

output/               # Processed data
├── facts_raw.csv     # Extracted XBRL facts
├── facts_raw.xlsx    # Excel version
├── warehouse.db      # SQLite database
├── normalized_financials.csv
├── derived_metrics.csv
└── quality_flags.csv

logs/                 # Execution logs
└── run_{timestamp}.log
```

### Code Statistics

```
Language              Files    Lines    Code    Comments    Blanks
───────────────────── ──────   ──────   ──────  ──────────  ──────
Python                   15     3245     2456        412       377
YAML                      3      287      234          0        53
JSON                      2      154      154          0         0
Markdown                  2      678      678          0         0
───────────────────── ──────   ──────   ──────  ──────────  ──────
TOTAL                    22     4364     3522        412       430
```

### Glossary

| Term | Definition |
|------|------------|
| **XBRL** | eXtensible Business Reporting Language - XML standard for financial reporting |
| **CMF** | Comisión para el Mercado Financiero (Chilean Financial Market Commission) |
| **SBIF** | Superintendencia de Bancos e Instituciones Financieras (merged into CMF) |
| **AFP** | Administradora de Fondos de Pensión (Pension Fund Manager) |
| **RUT** | Rol Único Tributario (Chilean tax ID number) |
| **IFRS** | International Financial Reporting Standards |
| **Context** | XBRL element defining time period and dimensional scope |
| **Fact** | Single reported value in XBRL (concept + context + value) |
| **Warehouse** | Central repository storing structured data from multiple sources |

---

## Related Documentation

### Validation and Quality
- **[VALIDACION.md](VALIDACION.md)** - Complete validation report against Excel manual data
- **[TABLA_COMPLETITUD.md](TABLA_COMPLETITUD.md)** - Data completeness table by ticker and year
- **[RESUMEN_COMPLETITUD.md](RESUMEN_COMPLETITUD.md)** - Executive summary of data completeness

### User Guides
- **[README.md](README.md)** - User guide and system documentation (v4.1)
- **[GUIA_ARCHIVOS.md](GUIA_ARCHIVOS.md)** - File and database guide

### Development
- **[agent.md](agent.md)** - Development guidelines and specifications
- **[INDICE_DOCUMENTACION.md](INDICE_DOCUMENTACION.md)** - Complete documentation index

---

**Document Version**: 1.1
**Last Updated**: 2026-04-05
**Maintainer**: Development Team
**License**: Project-specific license applies
