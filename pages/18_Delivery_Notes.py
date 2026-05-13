"""
Delivery Notes (GRN) — Record goods received before a full invoice arrives.
Common scenario: supplier delivers in the morning, sends invoice by email later.
GRN updates stock immediately; can be matched to invoice later.
"""
import streamlit as st
import pandas as pd
import os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_grns, save_grns, record_grn, load_suppliers,
                   load_canonical_prices_dict, load_purchase_orders,
                   link_invoice_to_grn)

st.set_page_config(page_title="Delivery Notes", page_icon="📦", layout="wide")
st.markdown("## Delivery Notes (GRN)")
st.caption("Record what was delivered today — stock updates immediately, link to invoice when it arrives")

grns = load_grns()
suppliers = load_suppliers()
active_suppliers = sorted([s["name"] for s in suppliers if s.get("active", True)])
canonical = load_canonical_prices_dict()
ingredient_options = sorted([info["ingredient"] for info in canonical.values()])

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

received = [g for g in grns if g.get("status") == "received"]
matched = [g for g in grns if g.get("status") == "matched"]
unmatched_value = sum(g.get("total_value", 0) for g in received)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total GRNs", len(grns))
c2.metric("Awaiting Invoice", len(received))
c3.metric("Matched", len(matched))
c4.metric("Unmatched Value (AED)", f"{unmatched_value:,.0f}")

# ---------------------------------------------------------------------------
# Record New GRN
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Record New Delivery")

if not active_suppliers:
    st.warning("No active suppliers. Go to Suppliers page to add them.")
    st.stop()

# Session state for items
if "grn_items" not in st.session_state:
    st.session_state.grn_items = []

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    supplier = st.selectbox("Supplier", active_suppliers, key="grn_supplier")
with col2:
    delivery_date = st.date_input("Delivery Date", value=date.today(), key="grn_date")
with col3:
    # Link to PO if one exists
    pos = load_purchase_orders()
    open_pos = [p for p in pos
                if p.get("supplier_name") == supplier
                and p.get("status") in ("sent", "draft")]
    po_options = ["(none)"] + [p["po_number"] for p in open_pos]
    linked_po = st.selectbox("Link to PO", po_options, key="grn_po")

col1, col2 = st.columns(2)
with col1:
    vehicle = st.text_input("Vehicle # / Plate", placeholder="Optional", key="grn_vehicle")
with col2:
    driver = st.text_input("Driver Name", placeholder="Optional", key="grn_driver")

st.markdown("**Items Delivered**")
col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
with col1:
    pick = st.selectbox("Ingredient", ["(pick one)"] + ingredient_options, key="grn_pick", label_visibility="collapsed")
with col2:
    qty = st.number_input("Qty", min_value=0.0, value=1.0, step=0.5, key="grn_qty", label_visibility="collapsed")
with col3:
    # Default UOM from canonical
    default_uom = "Kg"
    if pick != "(pick one)":
        for info in canonical.values():
            if info["ingredient"] == pick:
                default_uom = info["uom"]
                break
    uom = st.selectbox("UOM", ["Kg", "L", "Piece", "Carton", "Box"],
                       index=["Kg", "L", "Piece", "Carton", "Box"].index(default_uom) if default_uom in ("Kg", "L", "Piece") else 0,
                       key="grn_uom", label_visibility="collapsed")
with col4:
    if st.button("Add", use_container_width=True, disabled=(pick == "(pick one)" or qty <= 0)):
        st.session_state.grn_items.append({"ingredient": pick, "quantity": qty, "uom": uom})
        st.rerun()

if st.session_state.grn_items:
    st.markdown("#### Items Added")
    for i, item in enumerate(list(st.session_state.grn_items)):
        cols = st.columns([4, 1, 1, 1])
        cols[0].text(item["ingredient"])
        cols[1].text(f"{item['quantity']} {item['uom']}")
        # Compute estimated value
        canon_info = next((info for info in canonical.values() if info["ingredient"] == item["ingredient"]), {})
        price = canon_info.get("price_per_unit", 0)
        cols[2].text(f"AED {item['quantity'] * price:.2f}")
        if cols[3].button("Remove", key=f"grn_rm_{i}"):
            st.session_state.grn_items.pop(i)
            st.rerun()

notes = st.text_area("Notes", placeholder="e.g. Carton damaged, requested replacement", key="grn_notes")

col1, col2 = st.columns(2)
with col1:
    if st.button("Save GRN & Update Stock", type="primary", use_container_width=True,
                 disabled=not st.session_state.grn_items):
        grn = record_grn(
            supplier_name=supplier,
            items=st.session_state.grn_items,
            delivery_date=str(delivery_date),
            linked_po=linked_po if linked_po != "(none)" else None,
            vehicle_number=vehicle,
            driver_name=driver,
            notes=notes,
        )
        st.session_state.grn_items = []
        st.session_state.last_grn = grn
        st.success(f"Saved **{grn['grn_number']}** — AED {grn['total_value']:.2f}, stock updated")
        st.rerun()
with col2:
    if st.button("Clear", use_container_width=True):
        st.session_state.grn_items = []
        st.rerun()

# ---------------------------------------------------------------------------
# GRN History
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### GRN History")

if grns:
    col1, col2 = st.columns(2)
    with col1:
        sup_filter = st.selectbox("Supplier", ["All"] + sorted({g.get("supplier_name", "") for g in grns}), key="grn_sup_filter")
    with col2:
        status_filter = st.selectbox("Status", ["All", "received", "matched"], key="grn_status_filter")

    filtered = grns
    if sup_filter != "All":
        filtered = [g for g in filtered if g.get("supplier_name") == sup_filter]
    if status_filter != "All":
        filtered = [g for g in filtered if g.get("status") == status_filter]
    filtered = sorted(filtered, key=lambda g: g.get("created_at", ""), reverse=True)

    for g in filtered:
        status_color = "🟡" if g.get("status") == "received" else "🟢"
        title = (f"{status_color} **{g.get('grn_number')}** — {g.get('supplier_name')} — "
                 f"AED {g.get('total_value', 0):.2f} — {g.get('delivery_date')} "
                 f"({g.get('status')})")
        with st.expander(title):
            c1, c2, c3 = st.columns(3)
            c1.caption(f"Driver: {g.get('driver_name') or '—'}")
            c2.caption(f"Vehicle: {g.get('vehicle_number') or '—'}")
            c3.caption(f"Linked PO: {g.get('linked_po') or '—'}")
            if g.get("linked_invoice"):
                st.caption(f"Linked Invoice: {g['linked_invoice']}")
            if g.get("notes"):
                st.caption(f"Notes: {g['notes']}")
            items_df = pd.DataFrame(g.get("items", []))
            if not items_df.empty:
                st.dataframe(items_df, use_container_width=True, hide_index=True)
else:
    st.caption("No GRNs recorded yet.")
