"""
Create Purchase Order — Build a PO and send via WhatsApp click-to-chat.
"""
import streamlit as st
import pandas as pd
import os, sys
from datetime import date, timedelta, datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_suppliers, get_supplier_items, load_canonical_prices_dict,
                   load_purchase_orders, save_purchase_orders, generate_po_number,
                   build_whatsapp_url, format_po_message)

st.set_page_config(page_title="Create PO", page_icon="📝", layout="wide")
st.markdown("## Create Purchase Order")
st.caption("Build a PO and send to supplier via WhatsApp")

# ---------------------------------------------------------------------------
# Session state for line items
# ---------------------------------------------------------------------------

if "po_items" not in st.session_state:
    st.session_state.po_items = []  # list of {ingredient, qty, uom, unit_price}

# ---------------------------------------------------------------------------
# Step 1: Select supplier
# ---------------------------------------------------------------------------

suppliers = load_suppliers()
active = [s for s in suppliers if s.get("active", True)]

if not active:
    st.warning("No active suppliers found. Go to **Suppliers** page to add or activate suppliers.")
    st.stop()

active_sorted = sorted(active, key=lambda s: s["name"])

c1, c2 = st.columns([3, 2])
with c1:
    supplier_names = [s["name"] for s in active_sorted]
    sel = st.selectbox("Select Supplier", supplier_names, key="po_supplier")
with c2:
    show_all_items = st.checkbox(
        "Show all ingredients (override supplier list)", value=False,
        help="By default, only items this supplier carries appear. Tick this to pick from any ingredient."
    )

selected_supplier = next((s for s in active_sorted if s["name"] == sel), None)

# Show supplier info
info_cols = st.columns(4)
info_cols[0].metric("Contact", selected_supplier.get("contact_person") or "—")
info_cols[1].metric("WhatsApp", selected_supplier.get("whatsapp") or "MISSING")
info_cols[2].metric("Payment Terms", selected_supplier.get("payment_terms") or "—")
info_cols[3].metric("Items in Catalog", len(get_supplier_items(selected_supplier["name"])))

if not selected_supplier.get("whatsapp"):
    st.warning("No WhatsApp number for this supplier — add one in the **Suppliers** page to enable Send via WhatsApp.")

# ---------------------------------------------------------------------------
# Step 2: Pick items
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Add Items to PO")

# Build item picker options
if show_all_items:
    canonical = load_canonical_prices_dict()
    options = sorted(
        [{"ingredient": v["ingredient"], "uom": v["uom"], "price_per_unit": v["price_per_unit"]}
         for v in canonical.values()],
        key=lambda x: x["ingredient"],
    )
else:
    options = get_supplier_items(selected_supplier["name"])

option_names = [o["ingredient"] for o in options]
option_lookup = {o["ingredient"]: o for o in options}

if not option_names:
    st.info("This supplier has no items in the canonical price list. Tick 'Show all ingredients' to add items manually.")

c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
with c1:
    pick = st.selectbox("Ingredient", ["(pick one)"] + option_names, key="po_pick", label_visibility="collapsed")
with c2:
    qty = st.number_input("Qty", min_value=0.0, value=1.0, step=0.5, key="po_qty", label_visibility="collapsed")
with c3:
    if pick != "(pick one)":
        prefilled_price = option_lookup[pick]["price_per_unit"]
    else:
        prefilled_price = 0.0
    unit_price = st.number_input("Unit Price (AED)", min_value=0.0, value=float(prefilled_price), step=0.5, key="po_price", label_visibility="collapsed")
with c4:
    if st.button("Add", use_container_width=True, disabled=(pick == "(pick one)" or qty <= 0)):
        if pick != "(pick one)":
            o = option_lookup[pick]
            st.session_state.po_items.append({
                "ingredient": pick,
                "quantity": qty,
                "uom": o["uom"],
                "unit_price": unit_price,
                "total": qty * unit_price,
            })
            st.rerun()

# Show line items
if st.session_state.po_items:
    st.markdown("#### Line Items")
    for i, item in enumerate(list(st.session_state.po_items)):
        cols = st.columns([4, 1, 1, 2, 1])
        cols[0].text(item["ingredient"])
        cols[1].text(f"{item['quantity']} {item['uom']}")
        cols[2].text(f"AED {item['unit_price']:.2f}")
        cols[3].text(f"AED {item['total']:.2f}")
        if cols[4].button("Remove", key=f"rm_{i}"):
            st.session_state.po_items.pop(i)
            st.rerun()
else:
    st.caption("No items added yet.")

# ---------------------------------------------------------------------------
# Step 3: Header & totals
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### PO Details")

c1, c2, c3 = st.columns(3)
with c1:
    po_date = st.date_input("PO Date", value=date.today(), key="po_date")
with c2:
    expected = st.date_input("Expected Delivery", value=date.today() + timedelta(days=1), key="po_expected")
with c3:
    apply_vat = st.checkbox("Apply VAT (5%)", value=True)

notes = st.text_area("Notes (optional)", placeholder="Special instructions, delivery slot etc.", key="po_notes")

subtotal = sum(i["total"] for i in st.session_state.po_items)
vat_pct = 5 if apply_vat else 0
vat_amount = subtotal * (vat_pct / 100)
grand_total = subtotal + vat_amount

c1, c2, c3 = st.columns(3)
c1.metric("Subtotal", f"AED {subtotal:.2f}")
c2.metric(f"VAT ({vat_pct}%)", f"AED {vat_amount:.2f}")
c3.metric("Grand Total", f"AED {grand_total:.2f}")

# ---------------------------------------------------------------------------
# Step 4: Save / Send
# ---------------------------------------------------------------------------

st.divider()

can_save = bool(st.session_state.po_items) and selected_supplier is not None
has_whatsapp = bool(selected_supplier.get("whatsapp")) if selected_supplier else False

c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Save Draft", use_container_width=True, disabled=not can_save):
        po_number = generate_po_number()
        new_po = {
            "po_number": po_number,
            "supplier_name": selected_supplier["name"],
            "supplier_id": selected_supplier["supplier_id"],
            "supplier_whatsapp": selected_supplier.get("whatsapp", ""),
            "po_date": str(po_date),
            "expected_delivery": str(expected),
            "status": "draft",
            "items": st.session_state.po_items,
            "subtotal": round(subtotal, 2),
            "vat_percentage": vat_pct,
            "vat_amount": round(vat_amount, 2),
            "grand_total": round(grand_total, 2),
            "notes": notes,
            "created_at": datetime.now().isoformat(),
            "sent_at": None,
            "linked_invoice": None,
        }
        pos = load_purchase_orders()
        pos.append(new_po)
        save_purchase_orders(pos)
        st.session_state.po_items = []
        st.session_state.last_saved_po = new_po
        st.success(f"Saved as **{po_number}** (Draft)")
        st.rerun()

with c2:
    if st.button("Save & Send via WhatsApp", type="primary", use_container_width=True,
                 disabled=(not can_save or not has_whatsapp)):
        po_number = generate_po_number()
        new_po = {
            "po_number": po_number,
            "supplier_name": selected_supplier["name"],
            "supplier_id": selected_supplier["supplier_id"],
            "supplier_whatsapp": selected_supplier.get("whatsapp", ""),
            "po_date": str(po_date),
            "expected_delivery": str(expected),
            "status": "sent",
            "items": st.session_state.po_items,
            "subtotal": round(subtotal, 2),
            "vat_percentage": vat_pct,
            "vat_amount": round(vat_amount, 2),
            "grand_total": round(grand_total, 2),
            "notes": notes,
            "created_at": datetime.now().isoformat(),
            "sent_at": datetime.now().isoformat(),
            "linked_invoice": None,
        }
        pos = load_purchase_orders()
        pos.append(new_po)
        save_purchase_orders(pos)
        st.session_state.po_items = []
        st.session_state.last_saved_po = new_po
        st.rerun()

with c3:
    if st.button("Clear Form", use_container_width=True):
        st.session_state.po_items = []
        st.rerun()

# ---------------------------------------------------------------------------
# Show WhatsApp link after save+send
# ---------------------------------------------------------------------------

last_po = st.session_state.get("last_saved_po")
if last_po and last_po.get("status") == "sent":
    msg = format_po_message(last_po)
    url = build_whatsapp_url(last_po.get("supplier_whatsapp"), msg)
    if url:
        st.success(f"PO **{last_po['po_number']}** saved as Sent. Click below to open WhatsApp with the pre-filled message.")
        st.markdown(f'<a href="{url}" target="_blank" rel="noopener noreferrer" style="display:inline-block;background:#25D366;color:white;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;">📱 Open WhatsApp to send</a>', unsafe_allow_html=True)

        with st.expander("Preview message"):
            st.code(msg, language="text")
    else:
        st.warning("Saved as Sent, but couldn't build WhatsApp link (invalid phone number).")
        st.code(format_po_message(last_po), language="text")

elif last_po and last_po.get("status") == "draft":
    st.info(f"Saved **{last_po['po_number']}** as Draft. View it in PO History to send later.")

# ---------------------------------------------------------------------------
# Live message preview (only when items present)
# ---------------------------------------------------------------------------

if st.session_state.po_items:
    with st.expander("Preview WhatsApp message (before saving)"):
        preview_po = {
            "po_number": "PO-PREVIEW",
            "po_date": str(po_date),
            "expected_delivery": str(expected),
            "items": st.session_state.po_items,
            "subtotal": round(subtotal, 2),
            "vat_percentage": vat_pct,
            "vat_amount": round(vat_amount, 2),
            "grand_total": round(grand_total, 2),
            "notes": notes,
        }
        st.code(format_po_message(preview_po), language="text")
