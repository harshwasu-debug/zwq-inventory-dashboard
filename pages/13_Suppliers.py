"""
Suppliers Master — Manage supplier database (WhatsApp, contacts, terms),
view items per supplier, and review statement of accounts.
"""
import streamlit as st
import pandas as pd
import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_suppliers, save_suppliers, init_suppliers_from_canonical,
                   get_supplier_items, get_supplier_statement)

st.set_page_config(page_title="Suppliers", page_icon="🏢", layout="wide")
st.markdown("## Suppliers")
st.caption("Master data | Items by supplier | Statement of accounts")

tab1, tab2, tab3 = st.tabs(["📋 Suppliers Master", "🛒 Items by Supplier", "📊 Statement of Accounts"])

# ---------------------------------------------------------------------------
# Bootstrap if empty
# ---------------------------------------------------------------------------

if not load_suppliers():
    added = init_suppliers_from_canonical()
    if added > 0:
        st.success(f"Bootstrapped {added} suppliers from canonical price list")

# ---------------------------------------------------------------------------
# TAB 1: Master
# ---------------------------------------------------------------------------

with tab1:
    if st.button("Resync from Canonical Price List", help="Add any new suppliers found in the price list"):
        added = init_suppliers_from_canonical()
        if added > 0:
            st.success(f"Added {added} new supplier(s)")
            st.rerun()
        else:
            st.info("No new suppliers found")

    suppliers = load_suppliers()
    active = [s for s in suppliers if s.get("active", True)]
    with_whatsapp = [s for s in active if s.get("whatsapp")]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Suppliers", len(suppliers))
    c2.metric("Active", len(active))
    c3.metric("WhatsApp Configured", len(with_whatsapp))
    c4.metric("Missing WhatsApp", len(active) - len(with_whatsapp))

    st.divider()
    st.markdown("### All Suppliers")
    st.caption("Edit inline. Click 'Save Changes' below to persist.")

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
        })

    df = pd.DataFrame(rows)

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
        filtered, use_container_width=True, hide_index=True, num_rows="fixed",
        disabled=["Name", "Items Supplied"],
        column_config={
            "WhatsApp": st.column_config.TextColumn("WhatsApp", help="E.g. +971501234567"),
            "Active": st.column_config.CheckboxColumn("Active"),
        },
        key="suppliers_editor",
    )

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
            if (s.get("whatsapp", "") != new_whatsapp or
                s.get("contact_person", "") != new_contact or
                s.get("email", "") != new_email or
                s.get("payment_terms", "") != new_terms or
                s.get("active", True) != new_active):
                s["whatsapp"] = new_whatsapp
                s["contact_person"] = new_contact
                s["email"] = new_email
                s["payment_terms"] = new_terms
                s["active"] = new_active
                changed += 1
        save_suppliers(suppliers)
        st.success(f"Saved {changed} change(s)")
        st.rerun()

    with st.expander("WhatsApp number format help"):
        st.markdown("""
        Enter the supplier's WhatsApp in any of these formats — we strip non-digits:
        - `+971 50 123 4567` / `+971501234567` / `971501234567` / `(971) 50-123-4567`

        Make sure the **country code** is included. UAE is `971`. The PO send button
        will **not appear** for suppliers without a valid number.
        """)

# ---------------------------------------------------------------------------
# TAB 2: Items by Supplier
# ---------------------------------------------------------------------------

with tab2:
    st.markdown("### Items by Supplier")
    st.caption("See every ingredient supplied by a given vendor — useful for placing POs and price negotiation.")

    suppliers = load_suppliers()
    supplier_names = sorted({s["name"] for s in suppliers})

    picked = st.selectbox("Select Supplier", supplier_names, key="items_supplier")

    items = get_supplier_items(picked)
    if not items:
        st.info(f"No canonical items linked to **{picked}**. This may mean the supplier was bootstrapped but never had items mapped to them.")
    else:
        # KPIs
        total_value = sum(i.get("price_per_unit", 0) for i in items)  # not stock value, just price sum
        categories = {i.get("category", "") for i in items}

        c1, c2, c3 = st.columns(3)
        c1.metric("Items Supplied", len(items))
        c2.metric("Categories", len(categories))
        c3.metric("Avg Price/Unit", f"AED {(total_value/len(items)):.2f}")

        # Filter
        cat_filter = st.selectbox("Filter by category", ["All"] + sorted(categories - {""}), key="items_cat")

        filtered_items = items if cat_filter == "All" else [i for i in items if i.get("category") == cat_filter]

        df = pd.DataFrame([
            {
                "Ingredient": i["ingredient"],
                "Category": i.get("category", ""),
                "UOM": i["uom"],
                "Price/Unit (AED)": round(i["price_per_unit"], 2),
                "Buying Unit": i.get("buying_unit", ""),
                "Supplier Code": i.get("supplier_code", "") or "—",
            }
            for i in filtered_items
        ])
        st.dataframe(df, use_container_width=True, hide_index=True, height=500)

# ---------------------------------------------------------------------------
# TAB 3: Statement of Accounts
# ---------------------------------------------------------------------------

with tab3:
    st.markdown("### Supplier Statement of Accounts")
    st.caption("All invoices and POs for the selected supplier — useful for reconciliation and outstanding-balance tracking.")

    col1, col2 = st.columns([3, 1])
    with col1:
        stmt_supplier = st.selectbox("Select Supplier", supplier_names, key="stmt_supplier")
    with col2:
        days_back = st.selectbox("Period", [30, 90, 180, 365, 9999],
                                  format_func=lambda x: "All time" if x == 9999 else f"Last {x} days", index=3)

    days = days_back if days_back < 9999 else 36500
    stmt = get_supplier_statement(stmt_supplier, days_back=days)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Invoices", len(stmt["invoices"]))
    c2.metric("POs", len(stmt["pos"]))
    c3.metric("Total Invoiced (AED)", f"{stmt['total_invoiced']:,.0f}")
    c4.metric("Outstanding POs (AED)", f"{stmt['outstanding_pos']:,.0f}",
              help="POs sent but not yet delivered (no linked invoice)")

    if stmt["all_entries"]:
        st.markdown("**Combined Timeline**")
        rows = []
        for e in stmt["all_entries"]:
            rows.append({
                "Date": e.get("date", ""),
                "Type": "📄 Invoice" if e["type"] == "invoice" else "📝 PO",
                "Reference": e.get("reference", ""),
                "Items": e.get("items", 0),
                "Subtotal": e.get("subtotal", 0),
                "VAT": e.get("vat", 0),
                "Total (AED)": e.get("total", 0),
                "Status": e.get("status", "received") if e["type"] == "po" else "—",
                "Linked": e.get("linked_invoice", "") if e["type"] == "po" else "",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=500,
                     column_config={
                         "Subtotal": st.column_config.NumberColumn(format="%.2f"),
                         "VAT": st.column_config.NumberColumn(format="%.2f"),
                         "Total (AED)": st.column_config.NumberColumn(format="%.2f"),
                     })
    else:
        st.info(f"No invoices or POs found for **{stmt_supplier}** in the last {days_back if days_back < 9999 else 'all'} days.")
