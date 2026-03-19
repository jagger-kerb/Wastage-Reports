"""
Wastage Trends Dashboard
Authenticates via the Goodtill login endpoint, fetches outlets for a
searchable dropdown, then pulls wastage data in date buckets to build
time-series trend charts.
"""

import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date, timedelta, datetime
from dateutil.relativedelta import relativedelta

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Wastage Dashboard",
    page_icon="chart_with_upwards_trend",
    layout="wide",
)

# ── API constants ──────────────────────────────────────────────────────────────
LOGIN_URL    = "https://api.thegoodtill.com/api/login"
OUTLETS_URL  = "https://api.thegoodtill.com/api/outlets"
WASTAGE_URL  = "https://api.thegoodtill.com/api/ajax/super_wastages"
DATE_FMT     = "%d/%m/%Y %I:%M %p"

# ── Session state defaults ─────────────────────────────────────────────────────
for key, default in {
    "token":        None,
    "user_name":    None,
    "outlets":      [],   # list of {"id": ..., "outlet_name": ...}
    "login_error":  None,
    "df_summary":   None,
    "df_products":  None,
    "period_order": None,
    "loaded_label": None,  # "outlet | start – end" to detect stale cache
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Auth helpers ───────────────────────────────────────────────────────────────
def do_login(subdomain: str, username: str, password: str) -> bool:
    """POST credentials, store token + user info in session state."""
    try:
        r = requests.post(
            LOGIN_URL,
            json={"subdomain": subdomain, "username": username, "password": password},
            timeout=15,
        )
        r.raise_for_status()
        body = r.json()
    except requests.exceptions.RequestException as e:
        st.session_state.login_error = f"Request failed: {e}"
        return False

    token = body.get("token")
    if not token:
        st.session_state.login_error = (
            body.get("message") or "Login failed — no token returned."
        )
        return False

    st.session_state.token     = token
    st.session_state.user_name = body.get("user_name", username)
    st.session_state.login_error = None
    return True


def fetch_outlets(token: str) -> list[dict]:
    """GET all outlets the user can access."""
    try:
        r = requests.get(
            OUTLETS_URL,
            headers={"Authorization": f"Bearer {token}"},
            timeout=15,
        )
        r.raise_for_status()
        body = r.json()
        return body.get("data", [])
    except requests.exceptions.RequestException:
        return []


# ── Wastage helpers ────────────────────────────────────────────────────────────
def make_daterange(start: date, end: date) -> str:
    s = datetime.combine(start, datetime.min.time())
    e = datetime.combine(end,   datetime.min.time())
    return f"{s.strftime(DATE_FMT)} - {e.strftime(DATE_FMT)}"


def fetch_wastage(token: str, outlet_id: str, start: date, end: date) -> dict | None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
        "Outlet-Id":     outlet_id,
    }
    payload = {
        "daterange":              make_daterange(start, end),
        "consider_ingredient_cost": 1,
        "outlet_id":              [outlet_id],
    }
    try:
        r = requests.post(WASTAGE_URL, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        body = r.json()
        if not body.get("status"):
            st.warning(f"API status=false for {start} to {end}")
            return None
        return body["data"]
    except requests.exceptions.RequestException as e:
        st.error(f"Request failed ({start} to {end}): {e}")
        return None


def bucket_dates(start: date, end: date, granularity: str) -> list[tuple[date, date]]:
    buckets, cursor = [], start
    while cursor < end:
        next_cursor = (
            cursor + timedelta(weeks=1)
            if granularity == "Weekly"
            else cursor + relativedelta(months=1)
        )
        buckets.append((cursor, min(next_cursor - timedelta(days=1), end)))
        cursor = next_cursor
    return buckets


def products_from_response(data: dict, period_label: str) -> list[dict]:
    rows = []
    for outlet in data.get("outlets", []):
        outlet_name = outlet.get("outlet_name", "")

        for p in outlet.get("products", []):
            rows.append({
                "period":         period_label,
                "outlet":         outlet_name,
                "cost_type":      "Product",
                "product_name":   p.get("product_name", ""),
                "product_sku":    p.get("product_sku", ""),
                "quantity":       float(p.get("quantity", 0) or 0),
                "cost_price":     float(p.get("cost_price", 0) or 0),
                "purchase_price": float(p.get("purchase_price", 0) or 0),
                "retail_value":   float(p.get("retail_value", 0) or 0),
            })

        for ing in outlet.get("ingredients", []):
            rows.append({
                "period":         period_label,
                "outlet":         outlet_name,
                "cost_type":      "Ingredient",
                "product_name":   ing.get("ingredient_name") or ing.get("product_name", ""),
                "product_sku":    ing.get("ingredient_sku")  or ing.get("product_sku", ""),
                "quantity":       float(ing.get("quantity", 0) or 0),
                "cost_price":     float(ing.get("cost_price", 0) or 0),
                "purchase_price": float(ing.get("purchase_price", 0) or 0),
                "retail_value":   float(ing.get("retail_value", 0) or 0),
            })

    return rows


def summary_from_response(data: dict, period_label: str) -> dict:
    return {
        "period":                period_label,
        "product_cost_price":    data.get("product_cost_price", 0) or 0,
        "ingredient_cost_price": data.get("ingredient_cost_price", 0) or 0,
        "total_cost_price":      data.get("total_cost_price", 0) or 0,
    }


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.title("Wastage Dashboard")

    # ── Login / logged-in state ────────────────────────────────────────────────
    if st.session_state.token is None:
        st.subheader("Sign in")
        subdomain = st.text_input("Subdomain",
                                  placeholder="e.g. mystore",
                                  help="Your Goodtill store subdomain")
        username  = st.text_input("Username")
        password  = st.text_input("Password", type="password")

        if st.button("Login", type="primary", use_container_width=True):
            if not all([subdomain, username, password]):
                st.error("Please fill in all fields.")
            else:
                with st.spinner("Authenticating…"):
                    if do_login(subdomain, username, password):
                        st.session_state.outlets = fetch_outlets(st.session_state.token)
                        st.rerun()

        if st.session_state.login_error:
            st.error(st.session_state.login_error)

        st.stop()   # Nothing else to show until logged in

    else:
        # ── Logged-in header ───────────────────────────────────────────────────
        st.success(f"Signed in as **{st.session_state.user_name}**")
        if st.button("Sign out", use_container_width=True):
            for k in ("token", "user_name", "outlets", "login_error"):
                st.session_state[k] = None if k != "outlets" else []
            st.rerun()

        st.divider()

        # ── Outlet selector ────────────────────────────────────────────────────
        st.subheader("Outlet")
        outlets = st.session_state.outlets

        if not outlets:
            st.warning("No outlets found for this account.")
            st.stop()

        outlet_names = [o["outlet_name"] for o in outlets]
        outlet_map   = {o["outlet_name"]: o["id"] for o in outlets}

        # st.selectbox supports type-to-filter natively
        chosen_name = st.selectbox(
            "Select outlet",
            options=outlet_names,
            help="Start typing to filter",
        )
        outlet_id = outlet_map[chosen_name]

        st.divider()

        # ── Date range & options ───────────────────────────────────────────────
        st.subheader("Date Range")
        c1, c2 = st.columns(2)
        default_start = date.today() - timedelta(days=90)
        start_date = c1.date_input("From", value=default_start)
        end_date   = c2.date_input("To",   value=date.today())

        granularity = st.selectbox("Bucket size", ["Weekly", "Monthly"])

        fetch_btn = st.button("Fetch Data", type="primary", use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN AREA  (only reached when logged in)
# ══════════════════════════════════════════════════════════════════════════════
st.header(f"Wastage Trends — {chosen_name}")

cache_key = f"{outlet_id}|{start_date}|{end_date}|{granularity}"
data_ready = st.session_state.loaded_label == cache_key

if fetch_btn:
    if start_date >= end_date:
        st.error("Start date must be before end date.")
        st.stop()

    # ── Fetch data in buckets ──────────────────────────────────────────────
    buckets = bucket_dates(start_date, end_date, granularity)
    st.write(f"Fetching **{len(buckets)}** {granularity.lower()} buckets for **{chosen_name}**…")

    progress      = st.progress(0)
    all_summaries = []
    all_products  = []

    for i, (b_start, b_end) in enumerate(buckets):
        label = b_start.strftime("%d %b %Y")
        data  = fetch_wastage(st.session_state.token, outlet_id, b_start, b_end)
        if data:
            all_summaries.append(summary_from_response(data, label))
            all_products.extend(products_from_response(data, label))
        progress.progress((i + 1) / len(buckets))

    progress.empty()

    if not all_summaries:
        st.warning("No wastage data returned for this outlet and date range.")
        st.stop()

    period_order = [b[0].strftime("%d %b %Y") for b in buckets]
    df_summary   = pd.DataFrame(all_summaries)
    df_products  = pd.DataFrame(all_products)

    for df in (df_summary, df_products):
        df["period"] = pd.Categorical(df["period"], categories=period_order, ordered=True)

    st.session_state.df_summary   = df_summary.sort_values("period")
    st.session_state.df_products  = df_products.sort_values("period")
    st.session_state.period_order = period_order
    st.session_state.loaded_label = cache_key
    data_ready = True

elif not data_ready:
    st.info("Select an outlet and date range in the sidebar, then click **Fetch Data**.")
    st.stop()

# Pull from session state (set above on fetch, or persisted from last fetch)
df_summary  = st.session_state.df_summary
df_products = st.session_state.df_products

# ── KPI Cards ──────────────────────────────────────────────────────────────────
total_cost         = df_summary["total_cost_price"].sum()
total_product_cost = df_summary["product_cost_price"].sum()
total_ingredient   = df_summary["ingredient_cost_price"].sum()
total_qty          = df_products["quantity"].sum() if not df_products.empty else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Wastage Cost",  f"£{total_cost:,.2f}")
k2.metric("Product Cost",        f"£{total_product_cost:,.2f}")
k3.metric("Ingredient Cost",     f"£{total_ingredient:,.2f}")
k4.metric("Total Units Wasted",  f"{total_qty:,.0f}")

st.divider()

# ── View toggle — applies to all charts below ──────────────────────────────────
view_mode = st.radio(
    "Show",
    ["Products", "Ingredients", "Both"],
    index=2,
    horizontal=True,
    key="view_mode",
)

st.divider()

# ── Chart 1: Cost over time ────────────────────────────────────────────────────
st.subheader("Wastage Cost Over Time")

fig_cost = go.Figure()

show_products    = view_mode in ("Products",    "Both")
show_ingredients = view_mode in ("Ingredients", "Both")

if show_products:
    fig_cost.add_trace(go.Bar(
        x=df_summary["period"],
        y=df_summary["product_cost_price"],
        name="Product Cost",
        marker_color="#ef4444",
        text=df_summary["product_cost_price"].apply(lambda v: f"£{v:,.2f}"),
        textposition="inside",
        textfont=dict(color="white", size=10),
    ))

if show_ingredients:
    fig_cost.add_trace(go.Bar(
        x=df_summary["period"],
        y=df_summary["ingredient_cost_price"],
        name="Ingredient Cost",
        marker_color="#f97316",
        text=df_summary["ingredient_cost_price"].apply(lambda v: f"£{v:,.2f}"),
        textposition="inside",
        textfont=dict(color="white", size=10),
    ))

# Total line: sum of whichever series are active
if view_mode == "Products":
    total_series = df_summary["product_cost_price"]
elif view_mode == "Ingredients":
    total_series = df_summary["ingredient_cost_price"]
else:
    total_series = df_summary["total_cost_price"]

fig_cost.add_trace(go.Scatter(
    x=df_summary["period"],
    y=total_series,
    name="Total",
    mode="lines+markers+text",
    line=dict(color="#1e40af", width=2),
    marker=dict(size=6),
    text=total_series.apply(lambda v: f"£{v:,.2f}"),
    textposition="top center",
    textfont=dict(size=10),
))
fig_cost.update_layout(
    barmode="stack",
    xaxis_title="Period",
    yaxis_title="Cost (£)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=400,
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    uniformtext_minsize=8, uniformtext_mode="show",
)
st.plotly_chart(fig_cost, use_container_width=True)

# ── Charts 2 & 3: Breakdown ────────────────────────────────────────────────────
if not df_products.empty:
    # Filter rows by cost_type based on toggle
    has_ingredients = (df_products["cost_type"] == "Ingredient").any()

    if view_mode == "Products":
        df_typed = df_products[df_products["cost_type"] == "Product"]
        breakdown_label = "Product"
    elif view_mode == "Ingredients":
        df_typed = df_products[df_products["cost_type"] == "Ingredient"]
        breakdown_label = "Ingredient"
    else:
        df_typed = df_products
        breakdown_label = "Product / Ingredient"

    if view_mode == "Ingredients" and not has_ingredients:
        st.info("No ingredient-level detail was returned by the API for this period. "
                "Ingredient cost is available as a total only (see chart above).")
    else:
        st.subheader(f"{breakdown_label} Analysis")

        all_items_list = sorted(df_typed["product_name"].unique())
        selected_products = st.multiselect(
            "Filter items (leave blank for all — start typing to search)",
            options=all_items_list,
        )
        df_filt = (
            df_typed if not selected_products
            else df_typed[df_typed["product_name"].isin(selected_products)]
        )

        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("**Top 15 by Wastage Cost**")
            top_cost = (
                df_filt.groupby("product_name")["cost_price"]
                .sum().sort_values(ascending=False).head(15).reset_index()
            )
            fig_top = px.bar(
                top_cost, x="cost_price", y="product_name", orientation="h",
                labels={"cost_price": "Total Cost (£)", "product_name": ""},
                color="cost_price", color_continuous_scale="Reds",
                text=top_cost["cost_price"].apply(lambda v: f"£{v:,.2f}"),
            )
            fig_top.update_traces(textposition="outside")
            fig_top.update_layout(
                height=450, coloraxis_showscale=False,
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(range=[0, top_cost["cost_price"].max() * 1.25]),
            )
            st.plotly_chart(fig_top, use_container_width=True)

        with col_right:
            st.markdown("**Top 15 by Units Wasted**")
            top_qty = (
                df_filt.groupby("product_name")["quantity"]
                .sum().sort_values(ascending=False).head(15).reset_index()
            )
            fig_qty = px.bar(
                top_qty, x="quantity", y="product_name", orientation="h",
                labels={"quantity": "Units Wasted", "product_name": ""},
                color="quantity", color_continuous_scale="Oranges",
                text=top_qty["quantity"].apply(lambda v: f"{v:,.0f}"),
            )
            fig_qty.update_traces(textposition="outside")
            fig_qty.update_layout(
                height=450, coloraxis_showscale=False,
                yaxis=dict(autorange="reversed"),
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(range=[0, top_qty["quantity"].max() * 1.25]),
            )
            st.plotly_chart(fig_qty, use_container_width=True)

        # ── Chart 4: Selected item trends over time ────────────────────────────
        if selected_products:
            st.subheader("Selected Item Trends Over Time")
            trend_data = (
                df_filt.groupby(["period", "product_name"])["cost_price"]
                .sum().reset_index()
            )
            fig_trend = px.line(
                trend_data, x="period", y="cost_price", color="product_name",
                markers=True,
                labels={"cost_price": "Cost (£)", "period": "Period", "product_name": "Item"},
                text=trend_data["cost_price"].apply(lambda v: f"£{v:,.2f}"),
            )
            fig_trend.update_traces(textposition="top center", textfont=dict(size=10))
            fig_trend.update_layout(
                height=400,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        st.divider()

        # ── Raw data table ─────────────────────────────────────────────────────
        st.subheader("Raw Data")
        with st.expander("Show detailed records"):
            display_df = df_filt[
                ["period", "cost_type", "product_name", "product_sku", "quantity", "cost_price", "retail_value"]
            ].copy()
            display_df.columns = ["Period", "Type", "Item", "SKU", "Qty", "Cost (£)", "Retail Value (£)"]
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            csv = display_df.to_csv(index=False).encode("utf-8")
            st.download_button("Download CSV", csv, "wastage_data.csv", "text/csv")
