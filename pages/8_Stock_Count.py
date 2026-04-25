"""
Stock Count — Periodic physical inventory entry.
Compares counted quantities to system stock and calculates variance.
"""
import streamlit as st
import pandas as pd
import os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_stock_levels, load_canonical_prices_raw, record_stock_count,
                   load_stock_counts)

st.set_page_config(page_title="Stock Count", page_icon="📋", layout="wide")
st.markdown("## Stock Count")
st.caption("Enter physical inventory counts → system calculates variance and adjusts stock")

# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------

if "count_mode" not in st.session_state:
    st.session_state.count_mode = "entry"  # entry, results

# ---------------------------------------------------------------------------
# ENTRY MODE
# ---------------------------------------------------------------------------

if st.session_state.count_mode == "entry":
    canonical = load_canonical_prices_raw()
    stock = load_stock_levels()

    cogs_items = [i for i in canonical.get("items", []) if i.get("affects_cogs") == "Yes"]

    col1, col2, col3 = st.columns(3)
    with col1: count_date = st.date_input("Count Date", value=date.today())
    with col2:
        category_filter = st.selectbox("Filter by Category",
            ["All"] + sorted(set(i.get("category", "") for i in cogs_items)))
    with col3:
        only_with_stock = st.checkbox("Only show items with stock", value=False)

    notes = st.text_input("Count Notes", placeholder="e.g. End of month count, conducted by Chef Ahmed")

    # Filter items
    filter_items = cogs_items
    if category_filter != "All":
        filter_items = [i for i in filter_items if i.get("category") == category_filter]
    if only_with_stock:
        filter_items = [i for i in filter_items if stock.get(i["ingredient"].lower(), {}).get("quantity", 0) > 0]

    st.markdown(f"### Count Sheet — {len(filter_items)} ingredients")
    st.caption("Enter the actual counted quantity. Leave blank to skip an item.")

    # Build editable count entries
    counts = []
    cols_header = st.columns([3, 1, 2, 2, 1])
    cols_header[0].markdown("**Ingredient**")
    cols_header[1].markdown("**UOM**")
    cols_header[2].markdown("**System Qty**")
    cols_header[3].markdown("**Counted Qty**")
    cols_header[4].markdown("**Difference**")

    for i, item in enumerate(filter_items):
        ing = item["ingredient"]
        uom = item.get("uom", "")
        system_qty = stock.get(ing.lower(), {}).get("quantity", 0)

        cols = st.columns([3, 1, 2, 2, 1])
        cols[0].text(ing)
        cols[1].text(uom)
        cols[2].text(f"{system_qty:.3f}")
        with cols[3]:
            counted = st.number_input(f"count_{i}", min_value=0.0, value=0.0, step=0.1,
                                      key=f"count_{i}", label_visibility="collapsed")
        diff = counted - system_qty
        diff_color = "red" if diff < 0 else "green" if diff > 0 else "gray"
        cols[4].markdown(f":{diff_color}[{diff:+.3f}]")

        if counted > 0 or st.session_state.get(f"count_{i}_touched"):
            counts.append({"ingredient": ing, "counted_qty": counted, "uom": uom})

    st.divider()
    if st.button("Submit Stock Count", type="primary", use_container_width=True):
        if not counts:
            st.error("No counts entered")
        else:
            result = record_stock_count(counts, str(count_date), notes)
            st.session_state.count_result = result
            st.session_state.count_mode = "results"
            st.rerun()

# ---------------------------------------------------------------------------
# RESULTS MODE
# ---------------------------------------------------------------------------

elif st.session_state.count_mode == "results":
    result = st.session_state.count_result
    variances = result["variances"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Items Counted", result["items_counted"])
    over = sum(1 for v in variances if v["variance"] > 0.001)
    under = sum(1 for v in variances if v["variance"] < -0.001)
    match = result["items_counted"] - over - under
    c2.metric("Match", match)
    c3.metric("Over / Under", f"{over} / {under}")
    impact = result["total_value_impact"]
    c4.metric("Net Value Impact", f"AED {impact:+.2f}",
              help="Negative = inventory loss; Positive = unrecorded receipt")

    st.markdown("### Variance Detail")
    df = pd.DataFrame(variances)
    df = df.sort_values("value_impact", key=lambda s: s.abs(), ascending=False)
    st.dataframe(df, use_container_width=True, hide_index=True, height=500,
                 column_config={
                     "system_qty": st.column_config.NumberColumn("System Qty", format="%.3f"),
                     "counted_qty": st.column_config.NumberColumn("Counted Qty", format="%.3f"),
                     "variance": st.column_config.NumberColumn("Variance", format="%.3f"),
                     "variance_pct": st.column_config.NumberColumn("Var %", format="%.1f%%"),
                     "unit_price": st.column_config.NumberColumn("Price", format="%.2f"),
                     "value_impact": st.column_config.NumberColumn("Value Impact", format="%.2f"),
                 })

    if st.button("New Count", use_container_width=True):
        st.session_state.count_mode = "entry"
        st.session_state.pop("count_result", None)
        st.cache_data.clear()
        st.rerun()

# ---------------------------------------------------------------------------
# COUNT HISTORY
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Stock Count History")
counts_history = load_stock_counts()
if counts_history:
    counts_history = list(reversed(counts_history))
    for ev in counts_history[:10]:
        with st.expander(f"{ev['date']} — {ev['items_counted']} items, Net Impact: AED {ev['total_value_impact']:+.2f}"):
            if ev.get("notes"):
                st.caption(ev["notes"])
            df = pd.DataFrame(ev.get("variances", []))
            if not df.empty:
                df = df.sort_values("value_impact", key=lambda s: s.abs(), ascending=False).head(20)
                st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.caption("No stock counts recorded yet.")
