# Wastage Dashboard — Specification

## Purpose

Internal reporting tool for KERB Events that connects to the Goodtill POS API to pull wastage data across outlets and time periods, visualise trends, and export branded PDF reports.

## Users

KERB operations and management staff. Access is controlled via Goodtill credentials (subdomain + username + password).

## User Journey

```mermaid
flowchart LR
    A[Open App] --> B[Login]
    B --> C[Select Outlet]
    C --> D[Set Date Range]
    D --> E{Fetch Mode}
    E -->|Single| F[Fetch Data]
    E -->|All| G[Fetch All Outlets]
    F --> H[View Dashboard]
    G --> H
    H --> I[Filter: Products / Ingredients / Both]
    I --> J[Analyse Charts & Tables]
    J --> K{Export?}
    K -->|PDF| L[Add Commentary → Generate PDF]
    K -->|CSV| M[Download CSV]
    K -->|No| J
```

## Core Features

### Authentication
- Login via Goodtill API (`/api/login`)
- Session-based token stored in Streamlit session state
- Sign out clears all cached data

### Outlet Selection
- Dropdown populated from Goodtill API (`/api/outlets`)
- **Single outlet**: Fetches data for the selected outlet
- **All outlets**: Fetches data across every outlet in a single API call per time bucket (warning displayed about longer load times)

### Date Range & Bucketing
- Configurable start/end date pickers (default: last 90 days)
- Bucket granularity: **Weekly** or **Monthly**
- Each bucket generates one API call to `/api/ajax/super_wastages`

### Data Views
- **Products / Ingredients / Both** toggle filters all charts and tables
- Toggle is a horizontal radio group

### Visualisations

| Chart | Type | Description |
|-------|------|-------------|
| Wastage Cost Over Time | Stacked bar + line | Product cost (pink) and ingredient cost (mint) stacked bars with a total line (teal). £-formatted labels on the total line. |
| Top 15 by Wastage Cost | Horizontal bar | Teal gradient, £-formatted labels outside bars |
| Top 15 by Units Wasted | Horizontal bar | Pink/amber gradient, numeric labels outside bars |
| Selected Item Trends | Line chart | Appears when items are selected in the multiselect filter. £-formatted labels on data points. |

### Data Table
- Expandable "Raw Data" section with all records matching current filters
- Columns: Period, Type, Item, SKU, Qty, Cost (£), Retail Value (£)
- CSV download button

### PDF Export
- Generates a branded landscape A4 PDF report containing:
  - Title bar with outlet name, date range, filter mode, generation timestamp
  - KPI summary cards (Total Wastage Cost, Product Cost, Ingredient Cost, Total Units Wasted)
  - Wastage Cost Over Time chart (rendered as PNG via kaleido)
  - Top 15 tables side by side (Wastage Cost + Units Wasted)
  - Selected Item Trends chart (if items are selected)
  - User commentary section (optional free-text input)
- Filename format: `{Outlet} - {Start Date} to {End Date} - Wastage Report.pdf`

### PDF Page Layout

```mermaid
block-beta
    columns 3

    block:page1:3
        columns 3
        p1title["Page 1: Report Cover + Chart"]:3
        p1a["Teal Title Bar\nWASTAGE REPORT"]:3
        p1b["Outlet Name | Date Range | Filter"]:3
        p1c["KPI Card\nTotal Cost"] p1d["KPI Card\nProduct Cost"] p1e["KPI Card\nIngredient Cost"]
        p1f["Wastage Cost Over Time Chart"]:3
    end

    block:page2:3
        columns 2
        p2title["Page 2: Top 15 Tables"]:2
        p2a["Top 15 by\nWastage Cost"] p2b["Top 15 by\nUnits Wasted"]
    end

    block:page3:3
        columns 1
        p3title["Page 3+: Optional"]
        p3a["Item Trends Chart\n(if items selected)"]
        p3b["Commentary\n(if provided)"]
    end
```

## Branding

KERB Events brand system applied throughout:

| Element | Colour | Hex |
|---------|--------|-----|
| Background | Warm White | `#FAF2EB` |
| Sidebar / Primary | Deep Teal | `#006653` |
| Accent 1 | Mint | `#94F3E4` |
| Accent 2 | Pink | `#F190AE` |
| Emphasis | Coral | `#E9496E` |
| Text | Dark | `#1A1A1A` |

- Typography: Karla (body), DIN Condensed (headings, uppercase)
- Sidebar: teal background, white text, mint labels, pink primary buttons
- Metric cards: teal background, mint label, white value, mint left border
- Charts: brand colour palette (no default Plotly colours)
- PDF: matching brand colours with teal title bar, mint accent lines, pink section underlines

## API Communication

```mermaid
sequenceDiagram
    participant U as User
    participant S as Streamlit App
    participant API as Goodtill API

    U->>S: Enter credentials
    S->>API: POST /api/login
    API-->>S: Bearer token

    S->>API: GET /api/outlets
    API-->>S: Outlet list

    U->>S: Select outlet + date range
    U->>S: Click "Fetch Data"

    loop Each time bucket
        S->>API: POST /api/ajax/super_wastages
        Note right of API: daterange + outlet_id[]
        API-->>S: Wastage data (summary + products)
    end

    S->>S: Build DataFrames
    S->>U: Render charts + tables
```

### Wastage API Payload
```json
{
  "daterange": "01/01/2026 12:00 AM - 31/01/2026 12:00 AM",
  "consider_ingredient_cost": 1,
  "outlet_id": ["outlet-uuid-here"]
}
```

### Wastage API Response Structure

```mermaid
classDiagram
    class APIResponse {
        +float product_cost_price
        +float ingredient_cost_price
        +float total_cost_price
        +Outlet[] outlets
    }
    class Outlet {
        +string outlet_name
        +Product[] products
        +Ingredient[] ingredients
    }
    class Product {
        +string product_name
        +string product_sku
        +float quantity
        +float cost_price
        +float purchase_price
        +float retail_value
    }
    class Ingredient {
        +string ingredient_name
        +string ingredient_sku
        +float quantity
        +float cost_price
        +float purchase_price
        +float retail_value
    }
    APIResponse --> Outlet
    Outlet --> Product
    Outlet --> Ingredient
```

## Tech Stack

```mermaid
graph TB
    subgraph Frontend
        ST[Streamlit]
        PL[Plotly Charts]
        CSS[Custom CSS / KERB Brand]
    end
    subgraph Backend
        PD[pandas]
        RQ[requests]
        FP[fpdf2]
        KL[kaleido 0.2.1]
    end
    subgraph External
        API[Goodtill POS API]
        SC[Streamlit Cloud]
    end

    ST --> PL
    ST --> CSS
    ST --> PD
    RQ --> API
    PD --> PL
    PD --> FP
    PL --> KL
    KL --> FP
    ST --> SC
```

| Component | Technology |
|-----------|-----------|
| Framework | Streamlit |
| Charts | Plotly (graph_objects + express) |
| PDF | fpdf2 |
| Chart export | kaleido 0.2.1 (bundles Chromium) |
| Data | pandas |
| API | requests |
| Hosting | Streamlit Cloud |

## Constraints & Known Limitations

- **kaleido pinned to 0.2.1**: Newer versions require system Chrome which Streamlit Cloud doesn't provide
- **All outlets mode**: Uses the API's list support for `outlet_id` — if the API doesn't properly filter by outlet list, totals may be inaccurate
- **No persistent storage**: All data is fetched on demand; no database or caching layer
- **Session-only auth**: Token is lost on browser refresh or session timeout
