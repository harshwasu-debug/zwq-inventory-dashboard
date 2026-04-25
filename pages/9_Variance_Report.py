"""
Variance Report — Theoretical (recipe-based) consumption vs Actual stock movements.
Identifies waste, theft, and portioning errors.
"""
import streamlit as st
import pandas as pd
import os, sys
from datetime import date, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_stock_movements, load_canonical_prices_dict, load_stock_counts)

st.set_page_config(page_title="Variance Report", page_icon="📉", layout="wide")
st.markdown("## Variance Report")
st.caption("Compare theoretical vs actual ingredient usage to identify hidden losses")

# ---------------------------------------------------------------------------
# DATE RANGE
# ---------------------------------------------------------------------------

col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input("From", value=date.today() - timedelta(days=30))
with col2:
    end_date = st.date_input("To", value=date.today())

start_str = str(start_date)
end_str = str(end_date)

# ---------------------------------------------------------------------------
# ANALYSIS
# ---------------------------------------------------------------------------

movements = load_stock_movements()
canonical = load_canonical_prices_dict()

# Filter movements within range
in_range = [m for m in movements if start_str <= m.get("date", "") <= end_str]

# Calculate per ingredient
per_ingredient = defaultdict(lambda: {
    "receipts": 0, "depletion_sales": 0, "depletion_wastage": 0,
    "depletion_other": 0, "adjustments": 0, "movement_count": 0
})

for m in in_range:
    ing_key = m.get("ingredient", "").strip().lower()
    qty = abs(m.get("quantity", 0))
    mtype = m.get("type", "")
    ref = m.get("reference", "").lower()

    per_ingredient[ing_key]["movement_count"] += 1

    if mtype == "receipt":
        per_ingredient[ing_key]["receipts"] += qty
    elif mtype == "depletion":
        if "sales" in ref:
            per_ingredient[ing_key]["depletion_sales"] += qty
        elif "wastage" in ref:
            per_ingredient[ing_key]["depletion_wastage"] += qty
        else:
            per_ingredient[ing_key]["depletion_other"] += qty
    elif mtype == "adjustment":
        per_ingredient[ing_key]["adjustments"] += 1  # count of adjustments

# Get last stock count results within range for variance
counts_history = load_stock_counts()
count_variances = defaultdict(lambda: {"variance": 0, "value_impact": 0})
for ev in counts_history:
    if start_str <= ev.get("date", "") <= end_str:
        for v in ev.get("variances", []):
            key = v["ingredient"].strip().lower()
            count_variances[key]["variance"] += v["variance"]
            count_variances[key]["value_impact"] += v["value_impact"]

# Build report rows
rows = []
for ing_key, stats in per_ingredient.items():
    canon = canonical.get(ing_key, {})
    name = canon.get("ingredient", ing_key)
    price = canon.get("price_per_unit", 0)

    total_consumed = stats["depletion_sales"] + stats["depletion_wastage"] + stats["depletion_other"]
    consumed_value = total_consumed * price

    count_var = count_variances.get(ing_key, {})
    count_var_value = count_var.get("value_impact", 0)

    rows.append({
        "Ingredient": name,
        "Category": canon.get("category", ""),
        "Receipts": round(stats["receipts"], 3),
        "Sales Use": round(stats["depletion_sales"], 3),
        "Wastage": round(stats["depletion_wastage"], 3),
        "Other Out": round(stats["depletion_other"], 3),
        "Total Consumed": round(total_consumed, 3),
        "Consumed Value (AED)": round(consumed_value, 2),
        "Count Variance": round(count_var.get("variance", 0), 3),
        "Variance Value (AED)": round(count_var_value, 2),
        "UOM": canon.get("uom", ""),
        "Movements": stats["movement_count"],
    })

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

if rows:
    df = pd.DataFrame(rows)
    total_receipts = df["Receipts"].sum()
    total_sales_use = df["Sales Use"].sum()
    total_wastage = df["Wastage"].sum()
    total_consumed_value = df["Consumed Value (AED)"].sum()
    total_variance_loss = -df[df["Variance Value (AED)"] < 0]["Variance Value (AED)"].sum()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ingredients with Activity", len(df))
    c2.metric("Total Consumed (AED)", f"{total_consumed_value:,.0f}")
    c3.metric("Wastage Volume", f"{total_wastage:.1f}")
    c4.metric("Count Variance Loss", f"AED {total_variance_loss:,.0f}", help="Inventory shrinkage from physical counts")

    # ---------------------------------------------------------------------------
    # FILTERS
    # ---------------------------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    with col1:
        search = st.text_input("Search ingredient", key="var_search", label_visibility="collapsed", placeholder="Search...")
    with col2:
        cat_filter = st.selectbox("Category", ["All"] + sorted(df["Category"].dropna().unique().tolist()), key="var_cat")
    with col3:
        sort_by = st.selectbox("Sort by", ["Consumed Value (AED)", "Wastage", "Count Variance",
                                            "Variance Value (AED)", "Sales Use"], key="var_sort")

    filtered = df.copy()
    if search:
        filtered = filtered[filtered["Ingredient"].str.contains(search, case=False, na=False)]
    if cat_filter != "All":
        filtered = filtered[filtered["Category"] == cat_filter]

    filtered = filtered.sort_values(sort_by, ascending=False, key=lambda s: s.abs() if sort_by in ("Count Variance", "Variance Value (AED)") else s)

    st.dataframe(filtered, use_container_width=True, hide_index=True, height=500)

    # Highlight problem ingredients
    st.divider()
    st.markdown("### Top Concerns")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Highest Wastage**")
        top_waste = df.nlargest(10, "Wastage")[["Ingredient", "Wastage", "UOM", "Consumed Value (AED)"]]
        top_waste = top_waste[top_waste["Wastage"] > 0]
        st.dataframe(top_waste, use_container_width=True, hide_index=True)
    with col2:
        st.markdown("**Largest Count Variances (Loss)**")
        loss_df = df[df["Variance Value (AED)"] < 0].nsmallest(10, "Variance Value (AED)")[
            ["Ingredient", "Count Variance", "Variance Value (AED)", "UOM"]]
        st.dataframe(loss_df, use_container_width=True, hide_index=True)

else:
    st.info(f"No stock movements recorded between {start_str} and {end_str}.")
