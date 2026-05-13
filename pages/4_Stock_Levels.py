"""
Stock Levels — Real-time view of ingredient inventory with alerts,
per-item movement history, and stock value snapshots over time.
"""
import streamlit as st
import pandas as pd
import os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_stock_levels, load_stock_movements, load_canonical_prices_raw,
                   load_canonical_prices_dict, update_stock,
                   get_item_activity, take_stock_snapshot, load_stock_snapshots)

st.set_page_config(page_title="Stock Levels", page_icon="📦", layout="wide")
st.markdown("## Stock Levels")
st.caption("Real-time inventory | Item activity | Stock value over time")

tab1, tab2, tab3 = st.tabs(["📦 Current Stock", "🔎 Item Activity", "📈 Stock Value History"])

# ---------------------------------------------------------------------------
# TAB 1: Current Stock
# ---------------------------------------------------------------------------

with tab1:
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

    # Recent movements
    st.divider()
    st.markdown("### Recent Stock Movements")
    movements = load_stock_movements()
    if movements:
        recent = list(reversed(movements[-50:]))
        df_mov = pd.DataFrame(recent)
        st.dataframe(df_mov, use_container_width=True, hide_index=True, height=300,
                     column_config={"quantity": st.column_config.NumberColumn(format="%.3f"),
                                    "running_balance": st.column_config.NumberColumn(format="%.3f")})
    else:
        st.caption("No movements recorded yet.")

# ---------------------------------------------------------------------------
# TAB 2: Item Activity (per-ingredient drilldown)
# ---------------------------------------------------------------------------

with tab2:
    st.markdown("### Per-Ingredient Movement History")
    st.caption("Pick an ingredient to see every receipt, depletion, and adjustment.")

    canonical_raw = load_canonical_prices_raw()
    ingredient_options = sorted({item["ingredient"] for item in canonical_raw.get("items", [])})

    col1, col2 = st.columns([3, 1])
    with col1:
        picked = st.selectbox("Ingredient", ingredient_options, key="activity_pick")
    with col2:
        days_back = st.selectbox("Period", [7, 14, 30, 90, 180, 365], format_func=lambda x: f"Last {x} days", index=3, key="activity_days")

    if picked:
        activity = get_item_activity(picked, days_back=days_back)
        if activity:
            # KPIs
            receipts = [a for a in activity if a.get("type") == "receipt"]
            depletions = [a for a in activity if a.get("type") == "depletion"]
            adjustments = [a for a in activity if a.get("type") == "adjustment"]

            total_in = sum(a.get("quantity", 0) for a in receipts)
            total_out = sum(a.get("quantity", 0) for a in depletions)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Movements", len(activity))
            c2.metric("Received", f"{total_in:.3f}")
            c3.metric("Depleted", f"{total_out:.3f}")
            c4.metric("Adjustments", len(adjustments))

            # Net flow chart by date
            df_activity = pd.DataFrame(activity)
            if not df_activity.empty:
                df_activity["signed_qty"] = df_activity.apply(
                    lambda r: r["quantity"] if r["type"] == "receipt" else -r["quantity"], axis=1
                )
                daily = df_activity.groupby("date")["signed_qty"].sum().reset_index()
                if len(daily) > 1:
                    st.markdown("**Net daily flow** (positive = received more than used, negative = consumed)")
                    st.bar_chart(daily.set_index("date")["signed_qty"], height=200)

            st.markdown("**Full Movement Log**")
            st.dataframe(df_activity, use_container_width=True, hide_index=True, height=400,
                         column_config={
                             "quantity": st.column_config.NumberColumn(format="%.3f"),
                             "running_balance": st.column_config.NumberColumn(format="%.3f"),
                         })
        else:
            st.info(f"No movements found for **{picked}** in the last {days_back} days.")

# ---------------------------------------------------------------------------
# TAB 3: Stock Value Snapshots
# ---------------------------------------------------------------------------

with tab3:
    st.markdown("### Stock Value Over Time")
    st.caption("Capture today's inventory valuation to track changes month over month.")

    snaps = load_stock_snapshots()
    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("📸 Take Snapshot Now", type="primary"):
            snap = take_stock_snapshot()
            st.success(f"Captured: AED {snap['total_value']:,.2f} across {snap['item_count']} items")
            st.rerun()

    if snaps:
        df_snaps = pd.DataFrame([
            {"Date": s["date"], "Total Value (AED)": s["total_value"],
             "Item Count": s["item_count"], "Categories": len(s.get("by_category", {}))}
            for s in snaps
        ])
        df_snaps = df_snaps.sort_values("Date")

        c1, c2, c3 = st.columns(3)
        c1.metric("Snapshots Taken", len(snaps))
        c2.metric("Latest Value (AED)", f"{snaps[-1]['total_value']:,.0f}")
        if len(snaps) >= 2:
            change = snaps[-1]["total_value"] - snaps[-2]["total_value"]
            c3.metric("Change Since Last", f"AED {change:+,.0f}")
        else:
            c3.metric("Change Since Last", "—")

        st.markdown("**Stock Value Trend**")
        st.line_chart(df_snaps.set_index("Date")["Total Value (AED)"], height=300)

        st.markdown("**All Snapshots**")
        st.dataframe(df_snaps.iloc[::-1], use_container_width=True, hide_index=True,
                     column_config={"Total Value (AED)": st.column_config.NumberColumn(format="%.2f")})

        # Show latest by category
        if snaps[-1].get("by_category"):
            st.markdown("**Latest Snapshot by Category**")
            by_cat = sorted(snaps[-1]["by_category"].items(), key=lambda x: -x[1])
            df_cat = pd.DataFrame(by_cat, columns=["Category", "Value (AED)"])
            st.dataframe(df_cat, use_container_width=True, hide_index=True,
                         column_config={"Value (AED)": st.column_config.NumberColumn(format="%.2f")})
    else:
        st.caption("No snapshots yet. Click 'Take Snapshot Now' to capture today's inventory value.")
