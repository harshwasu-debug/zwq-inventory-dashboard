"""
Slow Moving Items — Identify ingredients with low consumption.
Flags overstocking and aging inventory.
"""
import streamlit as st
import pandas as pd
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import calculate_slow_moving

st.set_page_config(page_title="Slow Moving Items", page_icon="🐢", layout="wide")
st.markdown("## Slow Moving Items")
st.caption("Ingredients with low consumption — capital tied up in unused stock")

# ---------------------------------------------------------------------------
# CONTROLS
# ---------------------------------------------------------------------------

col1, col2 = st.columns(2)
with col1:
    days_lookback = st.selectbox("Lookback Period", [7, 14, 30, 60, 90],
                                 index=2, format_func=lambda x: f"Last {x} days")
with col2:
    threshold = st.slider("Movement threshold", 0, 5, 2,
                          help="Show items with this many or fewer depletion events in the period")

slow_items = calculate_slow_moving(days_lookback=days_lookback, threshold_movements=threshold)

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

if slow_items:
    df = pd.DataFrame(slow_items)
    total_capital = df["stock_value"].sum()
    zero_movement = sum(1 for s in slow_items if s["movements_in_period"] == 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slow Moving Items", len(df))
    c2.metric("Zero Movement", zero_movement)
    c3.metric("Capital Tied Up (AED)", f"{total_capital:,.0f}")
    if len(df) > 0:
        c4.metric("Avg Days Supply", f"{df[df['days_supply'] != 'infinite']['days_supply'].astype(float).median():.0f}" if any(d != "infinite" for d in df["days_supply"]) else "∞")

    # Filter
    col1, col2 = st.columns(2)
    with col1:
        cat_filter = st.selectbox("Category", ["All"] + sorted(df["category"].dropna().unique().tolist()))
    with col2:
        only_zero = st.checkbox("Only zero movement", value=False)

    filtered = df.copy()
    if cat_filter != "All":
        filtered = filtered[filtered["category"] == cat_filter]
    if only_zero:
        filtered = filtered[filtered["movements_in_period"] == 0]

    st.dataframe(filtered, use_container_width=True, hide_index=True, height=500,
                 column_config={
                     "ingredient": st.column_config.TextColumn("Ingredient"),
                     "category": st.column_config.TextColumn("Category"),
                     "current_stock": st.column_config.NumberColumn("Current Stock", format="%.3f"),
                     "uom": st.column_config.TextColumn("UOM"),
                     "stock_value": st.column_config.NumberColumn("Stock Value (AED)", format="%.2f"),
                     "movements_in_period": st.column_config.NumberColumn("Movements"),
                     "consumed_qty": st.column_config.NumberColumn("Consumed", format="%.3f"),
                     "avg_daily_use": st.column_config.NumberColumn("Avg Daily Use", format="%.4f"),
                     "days_supply": st.column_config.TextColumn("Days Supply"),
                 })

    # Recommendations
    st.divider()
    st.markdown("### Recommendations")
    high_value_zero = df[(df["movements_in_period"] == 0) & (df["stock_value"] > 50)]
    if not high_value_zero.empty:
        st.warning(f"**{len(high_value_zero)} high-value items with zero movement** — total AED {high_value_zero['stock_value'].sum():,.0f} tied up. "
                   "Consider running promotions, reducing par levels, or removing from menus.")
    if zero_movement > len(df) * 0.5:
        st.info("More than half your tracked stock had no movement. Either sales depletion isn't being uploaded regularly, or inventory needs trimming.")
else:
    st.info(f"No slow-moving items detected in the last {days_lookback} days. Either everything's moving well, or no movement data exists yet (upload sales to see this).")
