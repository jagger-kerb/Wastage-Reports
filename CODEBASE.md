# Wastage Dashboard — Codebase Guide

## Project Structure

```mermaid
graph LR
    subgraph Repo["Wastage-Reports/"]
        DC[".devcontainer/\ndevcontainer.json"]
        subgraph App["Warehouse stock & Wastage/"]
            WD["wastage_dashboard.py\n~1025 lines — entire app"]
            RB["run_dashboard.bat"]
        end
        REQ["requirements.txt"]
        SPEC["SPEC.md"]
        CODE["CODEBASE.md"]
    end

    style WD fill:#006653,color:#fff
    style App fill:#94F3E4,color:#000
```

## Single-File Architecture

The entire app lives in `wastage_dashboard.py` (~1025 lines). It follows Streamlit's top-to-bottom execution model — the file runs from top to bottom on every interaction.

## File Sections

```mermaid
graph TD
    subgraph wastage_dashboard.py
        S1["1. Imports & Page Config\nlines 1–25"]
        S2["2. KERB Brand CSS\nlines 27–234"]
        S3["3. API Constants\nlines 236–240"]
        S4["4. Session State Defaults\nlines 242–255"]
        S5["5. Helper Functions\nlines 258–388"]
        S6["6. PDF Generation\nlines 391–601"]
        S7["7. Sidebar UI\nlines 604–700"]
        S8["8. Data Fetching\nlines 703–791"]
        S9["9. Dashboard Rendering\nlines 793–1025"]
    end

    S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7 --> S8 --> S9

    style S2 fill:#F190AE,color:#000
    style S5 fill:#94F3E4,color:#000
    style S6 fill:#94F3E4,color:#000
    style S7 fill:#006653,color:#fff
    style S8 fill:#006653,color:#fff
    style S9 fill:#FAC430,color:#000
```

### Section Details

**1. Imports & Page Config** — Standard library + third-party imports. `st.set_page_config()` must be the first Streamlit call.

**2. KERB Brand CSS** — A large `st.markdown()` block injecting custom CSS via `<style>` tags. Streamlit components are targeted via `data-testid` attributes. Sidebar vs main area distinguished using `[data-testid="stSidebar"]` vs `[data-testid="stAppViewContainer"]`.

**3. API Constants** — Three endpoint URLs and a date format string.

**4. Session State Defaults** — Initialises keys in `st.session_state` on first run.

**5. Helper Functions:**

| Function | Purpose |
|----------|---------|
| `do_login()` | POST credentials, store token |
| `fetch_outlets()` | GET outlet list |
| `make_daterange()` | Format date pair for API payload |
| `fetch_wastage()` | POST to wastage API. Accepts single ID or list of IDs |
| `bucket_dates()` | Split date range into weekly/monthly buckets |
| `products_from_response()` | Extract product + ingredient rows from API response |
| `summary_from_response()` | Extract period-level cost totals from API response |

**6. PDF Generation** — `generate_pdf()` builds a branded landscape A4 PDF. Key internals: `draw_bg()`, `embed_chart()`, `section_heading()`, KPI cards with absolute positioning, side-by-side tables.

**7. Sidebar UI** — Login form → outlet selector → date pickers → fetch buttons.

**8. Data Fetching** — Cache key management, API calls per time bucket, DataFrame construction.

**9. Dashboard Rendering** — KPI cards → view toggle → 4 charts → raw data → PDF export.

## Data Flow

```mermaid
flowchart TD
    API["Goodtill API\n/api/ajax/super_wastages"]

    API -->|"JSON response"| FW["fetch_wastage()"]

    FW --> SFR["summary_from_response()"]
    FW --> PFR["products_from_response()"]

    SFR --> DFS["df_summary\n─────────────\nperiod\nproduct_cost_price\ningredient_cost_price\ntotal_cost_price"]

    PFR --> DFP["df_products\n─────────────\nperiod, outlet\ncost_type, product_name\nproduct_sku, quantity\ncost_price, purchase_price\nretail_value"]

    DFS --> KPI["KPI Cards"]
    DFS --> C1["Chart 1\nCost Over Time"]

    DFP --> C2["Chart 2\nTop 15 by Cost"]
    DFP --> C3["Chart 3\nTop 15 by Units"]
    DFP --> C4["Chart 4\nItem Trends"]
    DFP --> RAW["Raw Data Table"]

    C1 --> PDF["PDF Report"]
    C2 --> PDF
    C3 --> PDF
    C4 --> PDF
    KPI --> PDF

    style DFS fill:#006653,color:#fff
    style DFP fill:#006653,color:#fff
    style PDF fill:#F190AE,color:#000
    style API fill:#94F3E4,color:#000
```

## Session State Management

```mermaid
stateDiagram-v2
    [*] --> LoggedOut

    LoggedOut --> LoggedIn: do_login() succeeds
    LoggedIn --> LoggedOut: Sign out clicked

    LoggedIn --> DataReady: Fetch Data / Fetch All
    DataReady --> DataReady: Change view filter
    DataReady --> DataStale: Change date/outlet
    DataStale --> DataReady: Re-fetch

    state DataReady {
        [*] --> SingleOutlet
        SingleOutlet --> AllOutlets: Fetch All Outlets
        AllOutlets --> SingleOutlet: Fetch Data
    }

    note right of DataReady
        cache_key tracks:
        outlet | start | end | granularity
        Prefix "ALL|" for all-outlets mode
    end note
```

## Cache Key Logic

```mermaid
flowchart TD
    START{Button pressed?}
    START -->|Fetch Data| SK["cache_key =\n{outlet_id}|{start}|{end}|{gran}"]
    START -->|Fetch All| AK["cache_key =\nALL|{start}|{end}|{gran}"]
    START -->|No button\njust rerun| CHECK{Was last fetch\nall-outlets?}

    CHECK -->|"loaded_label\nstarts with ALL|"| AK2["cache_key =\nALL|{start}|{end}|{gran}"]
    CHECK -->|No| SK2["cache_key =\n{outlet_id}|{start}|{end}|{gran}"]

    SK --> MATCH{cache_key ==\nloaded_label?}
    AK --> MATCH
    AK2 --> MATCH
    SK2 --> MATCH

    MATCH -->|Yes| SHOW[Show cached data]
    MATCH -->|No & button pressed| FETCH[Fetch from API]
    MATCH -->|No & no button| PROMPT["Show 'Select outlet…' prompt"]

    style AK fill:#F190AE,color:#000
    style AK2 fill:#F190AE,color:#000
    style SK fill:#94F3E4,color:#000
    style SK2 fill:#94F3E4,color:#000
```

## Dashboard Layout

```mermaid
graph TD
    subgraph Sidebar["Sidebar (teal #006653)"]
        LOGO["EVENTS by KERB"]
        AUTH["Login / Sign Out"]
        OUTLET["Outlet Selector"]
        DATE["Date Range + Bucket Size"]
        FETCH["Fetch Data Button"]
        FETCHALL["Fetch All Outlets\n⚠️ Warning"]
    end

    subgraph Main["Main Area (warm white #FAF2EB)"]
        HEADER["Wastage Trends — {Outlet}"]
        KPIS["KPI Cards × 4"]
        TOGGLE["Products / Ingredients / Both"]
        CHART1["Wastage Cost Over Time\nStacked Bar + Line"]
        subgraph TwoCol["Side by Side"]
            CHART2["Top 15\nby Cost"]
            CHART3["Top 15\nby Units"]
        end
        CHART4["Selected Item Trends\n(conditional)"]
        RAWDATA["Raw Data Expander + CSV"]
        PDFEXPORT["PDF Export\nCommentary + Download"]
    end

    LOGO --> AUTH --> OUTLET --> DATE --> FETCH --> FETCHALL
    HEADER --> KPIS --> TOGGLE --> CHART1 --> TwoCol --> CHART4 --> RAWDATA --> PDFEXPORT

    style Sidebar fill:#006653,color:#fff
    style Main fill:#FAF2EB,color:#000
    style KPIS fill:#006653,color:#fff
    style TOGGLE fill:#006653,color:#fff
    style PDFEXPORT fill:#F190AE,color:#000
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| streamlit | latest | Web framework |
| requests | latest | HTTP client for Goodtill API |
| pandas | latest | Data manipulation |
| plotly | latest | Interactive charts |
| python-dateutil | latest | `relativedelta` for monthly bucketing |
| fpdf2 | latest | PDF generation |
| kaleido | 0.2.1 | Plotly chart → PNG export (pinned — see SPEC.md) |

## Deployment

Hosted on **Streamlit Cloud** at `wastage-reports-kerb.streamlit.app`. Deploys automatically from the `main` branch on push.

The entry point is configured to `Warehouse stock & Wastage/wastage_dashboard.py`.

## Common Tasks

### Adding a new chart
1. Compute the data from `df_summary` or `df_products` (after the view-mode filter)
2. Create a Plotly figure with brand colours (pink `#F190AE`, mint `#94F3E4`, teal `#006653`)
3. Set `font=dict(color="#1A1A1A")` and explicit axis tick/title colours in the layout
4. Use `plot_bgcolor="rgba(0,0,0,0)"` and `paper_bgcolor="rgba(0,0,0,0)"` for transparent background
5. Optionally add it to `generate_pdf()` using `embed_chart()`

### Adding a new KPI card
Add another column to the `k1, k2, k3, k4 = st.columns(4)` line and call `.metric()`.

### Modifying CSS
All custom CSS is in the single `st.markdown("""<style>...</style>""")` block near the top. Use `data-testid` selectors. Remember:
- Sidebar text defaults to white via `[data-testid="stSidebar"] * { color: #FFFFFF }`
- Main area text is controlled per-component
- Metric cards need explicit overrides to stay white on teal

### Changing brand colours
Update all three locations:
1. CSS variables in `:root { }` block
2. RGB tuples in `generate_pdf()` (`TEAL`, `MINT`, `PINK`, etc.)
3. Hex values in Plotly chart `marker_color` / `color_continuous_scale` properties
