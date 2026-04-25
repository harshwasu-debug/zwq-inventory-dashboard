"""
PO History — View all POs, re-send via WhatsApp, mark delivered, link invoices.
"""
import streamlit as st
import pandas as pd
import os, sys
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_purchase_orders, save_purchase_orders, build_whatsapp_url,
                   format_po_message, load_suppliers)

st.set_page_config(page_title="PO History", page_icon="📜", layout="wide")
st.markdown("## Purchase Order History")
st.caption("All POs — re-send via WhatsApp, track delivery, link invoices")

pos = load_purchase_orders()
suppliers = load_suppliers()
sup_lookup = {s["name"]: s for s in suppliers}

if not pos:
    st.info("No purchase orders yet. Create one in **Create PO** page.")
    st.stop()

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

draft = [p for p in pos if p.get("status") == "draft"]
sent = [p for p in pos if p.get("status") == "sent"]
delivered = [p for p in pos if p.get("status") == "delivered"]
cancelled = [p for p in pos if p.get("status") == "cancelled"]

outstanding_value = sum(p.get("grand_total", 0) for p in (draft + sent))

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total POs", len(pos))
c2.metric("Draft", len(draft))
c3.metric("Sent", len(sent))
c4.metric("Delivered", len(delivered))
c5.metric("Outstanding (AED)", f"{outstanding_value:,.0f}")

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

c1, c2, c3 = st.columns(3)
with c1:
    supplier_filter = st.selectbox("Supplier", ["All"] + sorted({p.get("supplier_name", "") for p in pos}), key="po_sup_filter")
with c2:
    status_filter = st.selectbox("Status", ["All", "draft", "sent", "delivered", "cancelled"], key="po_status_filter")
with c3:
    days_back = st.selectbox("Period", [30, 90, 180, 365, 9999],
                              format_func=lambda x: "All time" if x == 9999 else f"Last {x} days", index=1)

filtered = pos
if supplier_filter != "All":
    filtered = [p for p in filtered if p.get("supplier_name") == supplier_filter]
if status_filter != "All":
    filtered = [p for p in filtered if p.get("status") == status_filter]
if days_back < 9999:
    cutoff = (date.today() - __import__("datetime").timedelta(days=days_back)).isoformat()
    filtered = [p for p in filtered if p.get("po_date", "") >= cutoff]

# Most recent first
filtered = sorted(filtered, key=lambda p: p.get("created_at", ""), reverse=True)

# ---------------------------------------------------------------------------
# Each PO as expandable row
# ---------------------------------------------------------------------------

st.divider()
for po in filtered:
    status = po.get("status", "draft")
    status_color = {"draft": "🟡", "sent": "🔵", "delivered": "🟢", "cancelled": "⚫"}.get(status, "⚪")
    title = (f"{status_color} **{po.get('po_number', '?')}** — "
             f"{po.get('supplier_name', '?')} — "
             f"AED {po.get('grand_total', 0):.2f} — "
             f"{po.get('po_date', '?')} — "
             f"_{status}_")

    with st.expander(title):
        # PO summary
        c1, c2, c3 = st.columns(3)
        with c1:
            st.caption(f"Supplier: {po.get('supplier_name')}")
            st.caption(f"Created: {po.get('created_at', '')[:19]}")
        with c2:
            st.caption(f"PO Date: {po.get('po_date')}")
            st.caption(f"Expected: {po.get('expected_delivery', '—')}")
        with c3:
            if po.get("sent_at"):
                st.caption(f"Sent: {po['sent_at'][:19]}")
            if po.get("linked_invoice"):
                st.caption(f"Invoice: {po['linked_invoice']}")

        # Items
        items_df = pd.DataFrame(po.get("items", []))
        if not items_df.empty:
            st.dataframe(items_df, use_container_width=True, hide_index=True,
                         column_config={
                             "quantity": st.column_config.NumberColumn("Qty", format="%.2f"),
                             "unit_price": st.column_config.NumberColumn("Unit Price", format="%.2f"),
                             "total": st.column_config.NumberColumn("Total", format="%.2f"),
                         })

        # Totals
        st.caption(f"Subtotal: AED {po.get('subtotal', 0):.2f} | "
                   f"VAT ({po.get('vat_percentage', 0)}%): AED {po.get('vat_amount', 0):.2f} | "
                   f"**Total: AED {po.get('grand_total', 0):.2f}**")

        if po.get("notes"):
            st.caption(f"Notes: {po['notes']}")

        # Actions
        action_cols = st.columns(4)

        # 1. Send / Re-send via WhatsApp (if has phone and not delivered)
        whatsapp_phone = po.get("supplier_whatsapp") or sup_lookup.get(po.get("supplier_name", ""), {}).get("whatsapp", "")
        if whatsapp_phone and status in ("draft", "sent"):
            msg = format_po_message(po)
            url = build_whatsapp_url(whatsapp_phone, msg)
            if url:
                with action_cols[0]:
                    label = "📱 Send via WhatsApp" if status == "draft" else "📱 Re-send"
                    st.markdown(
                        f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
                        f'style="display:inline-block;background:#25D366;color:white;padding:8px 16px;'
                        f'border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">{label}</a>',
                        unsafe_allow_html=True
                    )

        # 2. Mark as Sent (for drafts)
        if status == "draft":
            with action_cols[1]:
                if st.button("Mark Sent", key=f"sent_{po['po_number']}", use_container_width=True):
                    po["status"] = "sent"
                    po["sent_at"] = datetime.now().isoformat()
                    save_purchase_orders(pos)
                    st.rerun()

        # 3. Mark Delivered
        if status in ("draft", "sent"):
            with action_cols[2]:
                if st.button("Mark Delivered", key=f"del_{po['po_number']}", use_container_width=True):
                    po["status"] = "delivered"
                    po["delivered_at"] = datetime.now().isoformat()
                    save_purchase_orders(pos)
                    st.rerun()

        # 4. Cancel
        if status in ("draft", "sent"):
            with action_cols[3]:
                if st.button("Cancel PO", key=f"cancel_{po['po_number']}", use_container_width=True):
                    po["status"] = "cancelled"
                    po["cancelled_at"] = datetime.now().isoformat()
                    save_purchase_orders(pos)
                    st.rerun()
