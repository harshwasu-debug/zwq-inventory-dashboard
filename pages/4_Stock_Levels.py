"""
Stock Levels — Real-time view of ingredient inventory with alerts.
"""
import streamlit as st
import pandas as pd
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_stock_levels, load_stock_movements, load_canonical_prices_raw,
                   load_canonical_prices_dict, update_stock)

st.set_page_config(page_title="Stock Levels", page_icon="📦", layout="wide")
st.markdown("## Stock Levels")
st.caption("Real-time ingredient inventory | Updated by invoice receipts and sales depletion")

# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------

stock = load_stock_levels()
canonical = load_canonical_prices_dict()
canonical_raw = load_canonical_prices_raw()

# Build display data
rows = []
for key, info in sorted(stock.items(), key=lambda x: x[1].get("ingredient", "")):
    qty = info.get("quantity", 0)
    uom = info.get("uom", "")
    price = canonical.get(key, {}).get("price_per_unit", 0)
    category = canonical.get(key, {}).get("category", "")
    value = qty * price if qty > 0 and price > 0 else 0

    # Status based on quantity
    if qty <= 0:
        status = "Out of Stock"
    elif qty < 1:
        status = "Critical"
    elif qty < 5:
        status = "Low"
    else:
        status = "OK"

    rows.append({
        "Ingredient": info.get("ingredient", key),
        "Category": category,
        "Qty On Hand": round(qty, 3),
        "UOM": uom,
        "Unit Price": round(price, 2),
        "Stock Value": round(value, 2),
        "Status": status,
        "Last Received": info.get("last_received", "-"),
        "Last Updated": info.get("last_updated", "-"),
    })

# Also show ingredients with zero stock (from canonical list but not in stock)
stocked_keys = set(stock.keys())
for item in canonical_raw.get("items", []):
    key = item["ingredient"].strip().lower()
    if key not in stocked_keys and item.get("affects_cogs") == "Yes":
        rows.append({
            "Ingredient": item["ingredient"],
            "Category": item.get("category", ""),
            "Qty On Hand": 0,
            "UOM": item.get("uom", ""),
            "Unit Price": item.get("price_per_unit", 0),
            "Stock Value": 0,
            "Status": "No Stock Data",
            "Last Received": "-",
            "Last Updated": "-",
        })

df = pd.DataFrame(rows) if rows else pd.DataFrame()

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

if not df.empty:
    in_stock = len(df[df["Qty On Hand"] > 0])
    out_of_stock = len(df[df["Status"].isin(["Out of Stock", "No Stock Data"])])
    low_stock = len(df[df["Status"].isin(["Low", "Critical"])])
    total_value = df["Stock Value"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("In Stock", in_stock)
    c2.metric("Low / Critical", low_stock)
    c3.metric("Out of Stock", out_of_stock)
    c4.metric("Total Stock Value", f"AED {total_value:,.0f}")

    # Filters
    col1, col2, col3 = st.columns([3, 2, 2])
    with col1:
        search = st.text_input("Search", placeholder="Search ingredients...", key="stock_search", label_visibility="collapsed")
    with col2:
        cat_filter = st.selectbox("Category", ["All"] + sorted(df["Category"].dropna().unique().tolist()), key="stock_cat", label_visibility="collapsed")
    with col3:
        status_filter = st.selectbox("Status", ["All", "OK", "Low", "Critical", "Out of Stock", "No Stock Data"], key="stock_status", label_visibility="collapsed")

    filtered = df.copy()
    if search:
        filtered = filtered[filtered["Ingredient"].str.contains(search, case=False, na=False)]
    if cat_filter != "All":
        filtered = filtered[filtered["Category"] == cat_filter]
    if status_filter != "All":
        filtered = filtered[filtered["Status"] == status_filter]

    st.dataframe(filtered, use_container_width=True, hide_index=True, height=500,
                 column_config={
                     "Qty On Hand": st.column_config.NumberColumn(format="%.3f"),
                     "Unit Price": st.column_config.NumberColumn(format="%.2f"),
                     "Stock Value": st.column_config.NumberColumn(format="%.2f"),
                 })

    # Manual stock adjustment
    st.divider()
    st.markdown("### Manual Stock Adjustment")
    st.caption("Use this for stock counts, waste recording, or corrections")
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    with col1:
        adj_ingredient = st.selectbox("Ingredient", sorted(df["Ingredient"].unique()), key="adj_ing")
    with col2:
        adj_qty = st.number_input("New Qty", min_value=0.0, step=0.5, key="adj_qty")
    with col3:
        adj_reason = st.selectbox("Reason", ["Stock Count", "Waste", "Correction", "Other"], key="adj_reason")
    with col4:
        if st.button("Apply", use_container_width=True):
            update_stock(adj_ingredient, adj_qty, "", "adjustment", f"{adj_reason}")
            st.success(f"Updated {adj_ingredient} to {adj_qty}")
            st.rerun()

else:
    st.info("No stock data yet. Confirm an invoice in Invoice Receiving to start tracking stock.")

# ---------------------------------------------------------------------------
# RECENT MOVEMENTS
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Recent Stock Movements")
movements = load_stock_movements()
if movements:
    recent = movements[-50:]
    recent.reverse()
    df_mov = pd.DataFrame(recent)
    st.dataframe(df_mov, use_container_width=True, hide_index=True, height=300,
                 column_config={"quantity": st.column_config.NumberColumn(format="%.3f"),
                                "running_balance": st.column_config.NumberColumn(format="%.3f")})
else:
    st.caption("No movements recorded yet.")
