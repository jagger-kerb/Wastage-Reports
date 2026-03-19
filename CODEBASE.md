# Wastage Dashboard — Codebase Guide

## Project Structure

```
Wastage-Reports/
├── .devcontainer/
│   └── devcontainer.json          # Dev container configuration
├── Warehouse stock & Wastage/
│   ├── wastage_dashboard.py       # The entire application (single file)
│   └── run_dashboard.bat          # Windows batch script to launch locally
├── requirements.txt               # Python dependencies
├── SPEC.md                        # Feature specification
└── CODEBASE.md                    # This file
```

## Single-File Architecture

The entire app lives in `wastage_dashboard.py` (~1025 lines). It follows Streamlit's top-to-bottom execution model — the file runs from top to bottom on every interaction.

## File Sections (in order)

### 1. Imports & Page Config (lines 1–25)
Standard library + third-party imports. `st.set_page_config()` must be the first Streamlit call.

### 2. KERB Brand CSS (lines 27–234)
A large `st.markdown()` block injecting custom CSS via `<style>` tags. Covers:
- CSS variables for brand colours
- Sidebar, typography, metric cards, buttons, dividers
- Radio group, multiselect, expander styling
- Sidebar nav hiding

**Key pattern**: Streamlit components are targeted via `data-testid` attributes (e.g. `[data-testid="stMetric"]`). Sidebar vs main area is distinguished using `[data-testid="stSidebar"]` vs `[data-testid="stAppViewContainer"]`.

### 3. API Constants (lines 236–240)
Three endpoint URLs and a date format string.

### 4. Session State Defaults (lines 242–255)
Initialises keys in `st.session_state` on first run. Key state:
- `token` / `user_name` — auth
- `outlets` — cached outlet list
- `df_summary` / `df_products` — fetched data (pandas DataFrames)
- `loaded_label` — cache key string to detect stale data
- `display_name` — "All Outlets" or outlet name

### 5. Helper Functions (lines 258–388)

| Function | Purpose |
|----------|---------|
| `do_login()` | POST credentials, store token |
| `fetch_outlets()` | GET outlet list |
| `make_daterange()` | Format date pair for API payload |
| `fetch_wastage()` | POST to wastage API. Accepts single ID or list of IDs |
| `bucket_dates()` | Split date range into weekly/monthly buckets |
| `products_from_response()` | Extract product + ingredient rows from API response |
| `summary_from_response()` | Extract period-level cost totals from API response |

### 6. PDF Generation (lines 391–601)
`generate_pdf()` — builds a branded landscape A4 PDF using fpdf2. Receives all data and chart figures as arguments. Key internals:
- `draw_bg()` — fills page with warm white
- `embed_chart()` — converts Plotly figure to PNG via `fig.to_image()` (kaleido), writes to temp file, embeds in PDF
- `section_heading()` — teal text + pink underline accent
- KPI cards drawn with absolute positioning (`set_xy`)
- Two top-15 tables rendered side-by-side using column offsets

### 7. Sidebar UI (lines 604–700)
Built inside `with st.sidebar:`. Flow:
1. "Events by KERB" header (HTML/CSS)
2. Login form (if no token) → `st.stop()` blocks the rest
3. Logged-in state: sign out button, outlet selector, date pickers, bucket size
4. "Fetch Data" button (primary)
5. "Fetch All Outlets" button (below, with warning)

### 8. Main Area — Data Fetching (lines 703–791)
- Determines fetch mode (single outlet vs all outlets)
- Builds `cache_key` to detect whether cached data matches current selections
- On fetch: loops through time buckets, calls `fetch_wastage()`, builds DataFrames
- Stores results in session state

**Cache key pattern**: `"ALL|{start}|{end}|{granularity}"` for all-outlets mode, or `"{outlet_id}|{start}|{end}|{granularity}"` for single outlet. The `was_all_outlets` check prevents losing data when sidebar widgets cause a rerun.

### 9. Main Area — Dashboard (lines 793–1025)
Sequential rendering:
1. **KPI Cards** — 4-column metric display
2. **View toggle** — Products / Ingredients / Both radio
3. **Chart 1** — Stacked bar + line (Wastage Cost Over Time)
4. **Charts 2 & 3** — Horizontal bars in 2-column layout (Top 15 by Cost, Top 15 by Units)
5. **Chart 4** — Line chart (Selected Item Trends, conditional on multiselect)
6. **Raw Data** — Expandable dataframe + CSV download
7. **PDF Export** — Commentary text area + generate/download buttons

## Data Flow

```
Goodtill API
    │
    ▼
fetch_wastage() ──► raw JSON response
    │
    ├── summary_from_response() ──► df_summary (period-level totals)
    │                                 columns: period, product_cost_price,
    │                                          ingredient_cost_price, total_cost_price
    │
    └── products_from_response() ──► df_products (item-level detail)
                                      columns: period, outlet, cost_type,
                                               product_name, product_sku,
                                               quantity, cost_price,
                                               purchase_price, retail_value
```

`df_summary` drives Chart 1 and the KPI cards.
`df_products` drives Charts 2–4 and the raw data table.

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
Update both:
1. CSS variables in `:root { }` block
2. RGB tuples in `generate_pdf()` (`TEAL`, `MINT`, `PINK`, etc.)
3. Hex values in Plotly chart `marker_color` / `color_continuous_scale` properties
