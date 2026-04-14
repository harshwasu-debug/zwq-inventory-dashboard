"""
Daily Receiving Summary — Overview of invoices received, spend, and price movements for a given day.
"""
import streamlit as st
import pandas as pd
import os, sys, json
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_price_history, load_json, INVOICES_DIR

st.set_page_config(page_title="Daily Summary", page_icon="📊", layout="wide")
st.markdown("## Daily Receiving Summary")

target_date = st.date_input("Select Date", value=date.today())
target_str = str(target_date)

# Load invoices for this date
invoices = []
skip = {"ingredient_aliases.json", "price_history.json"}
if os.path.exists(INVOICES_DIR):
    for f in os.listdir(INVOICES_DIR):
        if f.endswith(".json") and f not in skip:
            try:
                data = load_json(os.path.join(INVOICES_DIR, f))
                if data.get("invoice_date") == target_str:
                    invoices.append(data)
            except (json.JSONDecodeError, KeyError):
                continue

total_spend = sum(inv.get("grand_total", 0) for inv in invoices)
total_vat = sum(inv.get("vat_amount", 0) for inv in invoices)
total_items = sum(len(inv.get("items", [])) for inv in invoices)

price_history = load_price_history()
today_changes = [h for h in price_history if h.get("date") == target_str]
increases = [h for h in today_changes if h.get("change_pct", 0) > 0]
decreases = [h for h in today_changes if h.get("change_pct", 0) < 0]
big_increases = [h for h in increases if h.get("change_pct", 0) > 10]

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Invoices Received", len(invoices))
c2.metric("Total Spend", f"AED {total_spend:.0f}")
c3.metric("VAT Paid", f"AED {total_vat:.0f}")
c4.metric("Items Received", total_items)
c5.metric("Price Increases", len(increases))
c6.metric("Price Decreases", len(decreases))

if big_increases:
    st.markdown("### Significant Price Increases (>10%)")
    rows = [{"Ingredient": h["ingredient"], "Old Price": h["old_price"], "New Price": h["new_price"],
             "Change %": h["change_pct"], "Supplier": h.get("supplier", "")} for h in big_increases]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True,
                 column_config={"Old Price": st.column_config.NumberColumn(format="%.2f"),
                                "New Price": st.column_config.NumberColumn(format="%.2f"),
                                "Change %": st.column_config.NumberColumn(format="%.1f%%")})

if invoices:
    st.markdown("### Invoices Received")
    rows = [{"Supplier": inv.get("supplier_name", ""), "Invoice #": inv.get("invoice_number", ""),
             "Items": len(inv.get("items", [])), "Total (AED)": inv.get("grand_total", 0),
             "Price Updates": len(inv.get("price_updates", []))} for inv in invoices]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
elif not big_increases:
    st.info(f"No invoices received on {target_str}")
