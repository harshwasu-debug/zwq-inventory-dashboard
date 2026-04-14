"""
Price Change History — Audit trail of all ingredient price changes from confirmed invoices.
"""
import streamlit as st
import pandas as pd
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_price_history

st.set_page_config(page_title="Price History", page_icon="📈", layout="wide")
st.markdown("## Price Change History")
st.caption("Audit trail of all ingredient price changes from confirmed invoices")

history = load_price_history()
history.reverse()  # Most recent first

if not history:
    st.info("No price changes recorded yet. Confirm an invoice to see price history here.")
    st.stop()

increases = [h for h in history if h.get("change_pct", 0) > 0]
decreases = [h for h in history if h.get("change_pct", 0) < 0]
big_moves = [h for h in history if abs(h.get("change_pct", 0)) > 10]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Changes", len(history))
c2.metric("Price Increases", len(increases))
c3.metric("Price Decreases", len(decreases))
c4.metric(">10% Moves", len(big_moves))

# Filter
search = st.text_input("Filter by ingredient", placeholder="Search ingredient...")

filtered = history
if search:
    filtered = [h for h in filtered if search.lower() in h.get("ingredient", "").lower()]

rows = []
for h in filtered:
    rows.append({
        "Date": h.get("date", ""),
        "Ingredient": h.get("ingredient", ""),
        "Old Price": h.get("old_price", 0),
        "New Price": h.get("new_price", 0),
        "Change %": h.get("change_pct", 0),
        "UOM": h.get("uom", ""),
        "Supplier": h.get("supplier", ""),
        "Invoice #": h.get("invoice_number", ""),
    })

df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True, hide_index=True, height=600,
             column_config={
                 "Old Price": st.column_config.NumberColumn(format="%.2f"),
                 "New Price": st.column_config.NumberColumn(format="%.2f"),
                 "Change %": st.column_config.NumberColumn(format="%.1f%%"),
             })
