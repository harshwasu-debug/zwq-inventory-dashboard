"""
Suppliers Master — Manage supplier database (WhatsApp, contacts, terms).
Auto-bootstraps from canonical price list on first load.
"""
import streamlit as st
import pandas as pd
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_suppliers, save_suppliers, init_suppliers_from_canonical,
                   get_supplier_items)

st.set_page_config(page_title="Suppliers", page_icon="🏢", layout="wide")
st.markdown("## Suppliers Master")
st.caption("Manage WhatsApp numbers, contact persons, and payment terms — required for sending POs")

# ---------------------------------------------------------------------------
# Bootstrap on first load
# ---------------------------------------------------------------------------

if not load_suppliers():
    added = init_suppliers_from_canonical()
    if added > 0:
        st.success(f"Bootstrapped {added} suppliers from canonical price list")

if st.button("Resync from Canonical Price List", help="Add any new suppliers found in the price list (existing entries are preserved)"):
    added = init_suppliers_from_canonical()
    if added > 0:
        st.success(f"Added {added} new supplier(s)")
        st.rerun()
    else:
        st.info("No new suppliers found")

suppliers = load_suppliers()

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

active = [s for s in suppliers if s.get("active", True)]
with_whatsapp = [s for s in active if s.get("whatsapp")]

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Suppliers", len(suppliers))
c2.metric("Active", len(active))
c3.metric("WhatsApp Configured", len(with_whatsapp), help="Required for sending POs")
c4.metric("Missing WhatsApp", len(active) - len(with_whatsapp))

# ---------------------------------------------------------------------------
# Editable table — show item count per supplier and let user edit fields
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### All Suppliers")
st.caption("Edit inline. Click 'Save Changes' below to persist.")

# Build display DataFrame
rows = []
for s in suppliers:
    item_count = len(get_supplier_items(s["name"]))
    rows.append({
        "Name": s["name"],
        "WhatsApp": s.get("whatsapp", ""),
        "Contact": s.get("contact_person", ""),
        "Email": s.get("email", ""),
        "Payment Terms": s.get("payment_terms", ""),
        "Items Supplied": item_count,
        "Active": s.get("active", True),
        "_id": s["supplier_id"],
    })

df = pd.DataFrame(rows)

# Filter
col1, col2 = st.columns([3, 1])
with col1:
    search = st.text_input("Search supplier", placeholder="Type to filter…", key="sup_search", label_visibility="collapsed")
with col2:
    show_only_missing = st.checkbox("Only missing WhatsApp", value=False)

filtered = df.copy()
if search:
    filtered = filtered[filtered["Name"].str.contains(search, case=False, na=False)]
if show_only_missing:
    filtered = filtered[filtered["WhatsApp"].astype(str).str.strip() == ""]

edited = st.data_editor(
    filtered.drop(columns=["_id"]),
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    disabled=["Name", "Items Supplied"],
    column_config={
        "WhatsApp": st.column_config.TextColumn("WhatsApp", help="E.g. +971501234567 or 971501234567"),
        "Active": st.column_config.CheckboxColumn("Active"),
    },
    key="suppliers_editor",
)

# Detect changes by mapping back via supplier name (Name column is disabled, so it stays unique)
if st.button("Save Changes", type="primary"):
    changed = 0
    name_to_supplier = {s["name"]: s for s in suppliers}
    for _, row in edited.iterrows():
        s = name_to_supplier.get(row["Name"])
        if not s:
            continue
        new_whatsapp = str(row.get("WhatsApp", "") or "").strip()
        new_contact = str(row.get("Contact", "") or "").strip()
        new_email = str(row.get("Email", "") or "").strip()
        new_terms = str(row.get("Payment Terms", "") or "").strip()
        new_active = bool(row.get("Active", True))

        if (s.get("whatsapp", "") != new_whatsapp
            or s.get("contact_person", "") != new_contact
            or s.get("email", "") != new_email
            or s.get("payment_terms", "") != new_terms
            or s.get("active", True) != new_active):
            s["whatsapp"] = new_whatsapp
            s["contact_person"] = new_contact
            s["email"] = new_email
            s["payment_terms"] = new_terms
            s["active"] = new_active
            changed += 1

    save_suppliers(suppliers)
    st.success(f"Saved {changed} change(s)")
    st.rerun()

# ---------------------------------------------------------------------------
# Quick guide
# ---------------------------------------------------------------------------

with st.expander("WhatsApp number format help"):
    st.markdown("""
    Enter the supplier's WhatsApp in any of these formats — we strip non-digits:
    - `+971 50 123 4567`
    - `+971501234567`
    - `971501234567`
    - `(971) 50-123-4567`

    Make sure the **country code** is included. UAE is `971`, Saudi is `966`, India is `91`.

    The PO send button will **not appear** for suppliers without a valid number.
    """)
