"""
Wastage Tracking — Record staff meals, expired goods, damaged items, etc.
Auto-deplete stock and categorize as expense or loss.
"""
import streamlit as st
import pandas as pd
import os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_wastage_log, record_wastage, WASTAGE_TYPES,
                   load_stock_levels, load_canonical_prices_raw, load_brand_menus)

st.set_page_config(page_title="Wastage Tracking", page_icon="🗑️", layout="wide")
st.markdown("## Wastage Tracking")
st.caption("Record staff meals, expired goods, damaged items, and other ingredient losses")

# ---------------------------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------------------------

stock = load_stock_levels()
log = load_wastage_log()
canonical = load_canonical_prices_raw()
brand_menus = load_brand_menus()

ingredient_options = sorted([i["ingredient"] for i in canonical.get("items", [])])
ingredient_uom = {i["ingredient"]: i["uom"] for i in canonical.get("items", [])}
brand_options = ["(none)"] + sorted(brand_menus.keys())

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

if log:
    total_events = len(log)
    today_events = [e for e in log if e.get("date") == date.today().isoformat()]
    expense_value = 0
    loss_value = 0
    canonical_dict = {i["ingredient"].lower(): i for i in canonical.get("items", [])}
    for e in log:
        ing_key = e.get("ingredient", "").lower()
        price = canonical_dict.get(ing_key, {}).get("price_per_unit", 0)
        value = e.get("quantity", 0) * price
        if e.get("is_expense"):
            expense_value += value
        else:
            loss_value += value

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Events", total_events)
    c2.metric("Today's Events", len(today_events))
    c3.metric("Expense Value (AED)", f"{expense_value:.0f}", help="Staff meal, marketing, R&D — counted as legitimate expense")
    c4.metric("Loss Value (AED)", f"{loss_value:.0f}", help="Spoilage, damage — true inventory loss")
else:
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Events", 0)
    c2.metric("Expense Value", "AED 0")
    c3.metric("Loss Value", "AED 0")

# ---------------------------------------------------------------------------
# RECORD NEW WASTAGE
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Record Wastage Event")

with st.form("wastage_form", clear_on_submit=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        wastage_type = st.selectbox("Wastage Type", [wt["name"] for wt in WASTAGE_TYPES])
    with col2:
        brand = st.selectbox("Brand (optional)", brand_options)
    with col3:
        wastage_date = st.date_input("Date", value=date.today())

    # Show description of selected type
    selected_info = next((wt for wt in WASTAGE_TYPES if wt["name"] == wastage_type), {})
    if selected_info:
        if selected_info.get("expense"):
            st.caption(f"{selected_info['description']} — counted as **expense** (legitimate operating cost)")
        else:
            st.caption(f"{selected_info['description']} — counted as **loss** (true inventory shrinkage)")

    st.markdown("**Items Wasted**")
    num_items = st.number_input("Number of items", min_value=1, max_value=20, value=1, step=1)

    items = []
    for i in range(int(num_items)):
        cols = st.columns([3, 1, 1, 3])
        with cols[0]:
            ing = st.selectbox(f"Ingredient {i+1}", ingredient_options, key=f"w_ing_{i}", label_visibility="collapsed")
        with cols[1]:
            qty = st.number_input(f"Qty {i+1}", min_value=0.0, step=0.1, key=f"w_qty_{i}", label_visibility="collapsed")
        with cols[2]:
            uom = ingredient_uom.get(ing, "Kg")
            st.text_input(f"UOM {i+1}", value=uom, key=f"w_uom_{i}", label_visibility="collapsed", disabled=True)
        with cols[3]:
            note = st.text_input(f"Notes {i+1}", placeholder="Optional notes", key=f"w_note_{i}", label_visibility="collapsed")
        if ing and qty > 0:
            items.append({"ingredient": ing, "quantity": qty, "uom": uom, "notes": note})

    submitted = st.form_submit_button("Record Wastage", type="primary", use_container_width=True)

    if submitted:
        if not items:
            st.error("Add at least one item with quantity > 0")
        else:
            for item in items:
                record_wastage(
                    item["ingredient"], item["quantity"], item["uom"],
                    wastage_type, item["notes"], brand if brand != "(none)" else ""
                )
            st.success(f"Recorded {len(items)} wastage event(s) — stock depleted")
            st.cache_data.clear()
            st.rerun()

# ---------------------------------------------------------------------------
# WASTAGE HISTORY
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Wastage History")

if log:
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        type_filter = st.selectbox("Type", ["All"] + [wt["name"] for wt in WASTAGE_TYPES], key="hist_type")
    with col2:
        brand_filter = st.selectbox("Brand", ["All"] + sorted(set(e.get("brand", "") for e in log if e.get("brand"))), key="hist_brand")
    with col3:
        days_back = st.selectbox("Period", [7, 14, 30, 90, 365], format_func=lambda x: f"Last {x} days", key="hist_days")

    cutoff = (date.today() - __import__("datetime").timedelta(days=days_back)).isoformat()
    filtered = [e for e in log if e.get("date", "") >= cutoff]
    if type_filter != "All":
        filtered = [e for e in filtered if e.get("type") == type_filter]
    if brand_filter != "All":
        filtered = [e for e in filtered if e.get("brand") == brand_filter]

    filtered.reverse()

    rows = []
    canonical_dict = {i["ingredient"].lower(): i for i in canonical.get("items", [])}
    for e in filtered:
        ing_key = e.get("ingredient", "").lower()
        price = canonical_dict.get(ing_key, {}).get("price_per_unit", 0)
        value = round(e.get("quantity", 0) * price, 2)
        rows.append({
            "Date": e.get("date", ""),
            "Type": e.get("type", ""),
            "Ingredient": e.get("ingredient", ""),
            "Qty": e.get("quantity", 0),
            "UOM": e.get("uom", ""),
            "Value (AED)": value,
            "Category": "Expense" if e.get("is_expense") else "Loss",
            "Brand": e.get("brand", "-") or "-",
            "Notes": e.get("notes", "") or "-",
        })

    if rows:
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True, height=400,
                     column_config={"Qty": st.column_config.NumberColumn(format="%.3f"),
                                    "Value (AED)": st.column_config.NumberColumn(format="%.2f")})

        # Summary by type
        st.markdown("#### Summary by Type")
        type_summary = df.groupby("Type").agg(
            Events=("Date", "count"),
            **{"Total Value (AED)": ("Value (AED)", "sum")}
        ).reset_index().sort_values("Total Value (AED)", ascending=False)
        st.dataframe(type_summary, use_container_width=True, hide_index=True)
    else:
        st.caption("No events match the current filters.")
else:
    st.caption("No wastage events recorded yet.")
