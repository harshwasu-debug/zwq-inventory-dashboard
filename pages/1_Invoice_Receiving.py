"""
Invoice Receiving — Upload supplier invoices (image/PDF), AI extraction, fuzzy matching, price updates.
"""
import streamlit as st
import pandas as pd
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (load_canonical_prices_raw, load_aliases, process_uploaded_file,
                   fuzzy_match_ingredient, normalize_price, confirm_invoice, INVOICES_DIR,
                   load_vendor_profiles, validate_invoice_math,
                   get_open_pos_for_supplier, link_invoice_to_po)

st.set_page_config(page_title="Invoice Receiving", page_icon="🗃", layout="wide")
st.markdown("## Invoice Receiving")
st.caption("Upload supplier invoices | Auto-match & price tracking")

# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------

if "invoices_to_review" not in st.session_state:
    st.session_state.invoices_to_review = []
if "current_invoice_idx" not in st.session_state:
    st.session_state.current_invoice_idx = 0
if "upload_mode" not in st.session_state:
    st.session_state.upload_mode = "choose"  # choose, upload_processing, review, manual, done

# ---------------------------------------------------------------------------
# MODE: CHOOSE (upload or manual)
# ---------------------------------------------------------------------------

if st.session_state.upload_mode == "choose":
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### Upload Supplier Invoice")
        st.caption("Supports JPG, PNG, WebP, PDF (multi-page)")

        # Supplier picker — activates the matching vendor profile (column layout,
        # known quirks, pack conventions) for this OCR run.
        profiles = load_vendor_profiles()
        supplier_options = ["(auto-detect)"] + sorted(profiles.keys())
        supplier_pick = st.selectbox(
            "Supplier (helps OCR — pick if known)",
            supplier_options,
            key="invoice_supplier_pick",
            help="Picking the supplier injects their column layout, known quirks, and "
                 "saved pack mappings into the OCR prompt — much better extraction. "
                 "Leave on auto-detect only if the supplier isn't in the list."
        )
        if supplier_pick != "(auto-detect)" and supplier_pick in profiles:
            p = profiles[supplier_pick]
            st.caption(
                f"📋 Profile loaded — UOM hints: {', '.join(p.get('typical_units', []))} | "
                f"Expense category: {p.get('expense_category', '?')} | "
                f"{len(p.get('known_quirks', []))} quirks active"
            )

        uploaded = st.file_uploader("Drop an image or PDF", type=["jpg", "jpeg", "png", "webp", "pdf"],
                                     key="invoice_upload", label_visibility="collapsed")
        if uploaded:
            with st.spinner("Reading invoice with AI... (this may take 30-60 seconds)"):
                try:
                    file_bytes = uploaded.read()
                    supplier_hint = None if supplier_pick == "(auto-detect)" else supplier_pick
                    results = process_uploaded_file(file_bytes, uploaded.name, supplier_hint=supplier_hint)
                    st.session_state.invoices_to_review = results
                    st.session_state.current_invoice_idx = 0
                    st.session_state.upload_mode = "review"
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with col2:
        st.markdown("### Manual Entry")
        st.caption("Type invoice details manually — same matching & price tracking")
        if st.button("Start Manual Entry", use_container_width=True):
            st.session_state.upload_mode = "manual"
            st.rerun()

# ---------------------------------------------------------------------------
# MODE: MANUAL ENTRY
# ---------------------------------------------------------------------------

elif st.session_state.upload_mode == "manual":
    st.markdown("### Manual Invoice Entry")

    with st.form("manual_invoice"):
        col1, col2, col3 = st.columns(3)
        with col1: supplier = st.text_input("Supplier Name", placeholder="e.g. Jaleel Traders LLC")
        with col2: inv_date = st.date_input("Invoice Date")
        with col3: inv_number = st.text_input("Invoice Number", placeholder="e.g. INV-2026-001")

        st.markdown("#### Line Items")
        num_items = st.number_input("Number of items", min_value=1, max_value=50, value=5, step=1)

        items = []
        for i in range(int(num_items)):
            cols = st.columns([3, 1, 1, 1])
            with cols[0]: name = st.text_input(f"Item {i+1}", key=f"m_name_{i}", label_visibility="collapsed", placeholder=f"Item name {i+1}")
            with cols[1]: qty = st.number_input("Qty", min_value=0.0, value=1.0, step=0.5, key=f"m_qty_{i}", label_visibility="collapsed")
            with cols[2]: unit = st.selectbox("Unit", ["Kg", "L", "Piece", "Box", "Carton", "Pack"], key=f"m_unit_{i}", label_visibility="collapsed")
            with cols[3]: price = st.number_input("Price", min_value=0.0, value=0.0, step=0.5, key=f"m_price_{i}", label_visibility="collapsed")
            if name and qty > 0:
                items.append({"item_name": name, "quantity": qty, "unit": unit, "unit_price": price, "total_price": qty * price})

        vat_pct = st.number_input("VAT %", min_value=0.0, max_value=100.0, value=5.0, step=0.5)
        submitted = st.form_submit_button("Process & Match Items", use_container_width=True)

    if submitted:
        if not supplier:
            st.error("Please enter supplier name")
        elif not items:
            st.error("Please add at least one item")
        else:
            subtotal = sum(i["total_price"] for i in items)
            vat_amount = subtotal * (vat_pct / 100)
            manual_data = {
                "supplier_name": supplier, "invoice_date": str(inv_date),
                "invoice_number": inv_number or f"MANUAL-{int(__import__('time').time())}",
                "currency": "AED", "items": items, "subtotal": subtotal,
                "vat_percentage": vat_pct, "vat_amount": vat_amount, "grand_total": subtotal + vat_amount,
            }
            # Fuzzy match items
            canonical_data = load_canonical_prices_raw()
            aliases = load_aliases()
            matched_items = []
            for item in items:
                match = fuzzy_match_ingredient(item["item_name"], canonical_data, aliases)
                internal_price, normalized_price, price_change_pct = None, None, None
                if match["canonical_item"]:
                    ci = match["canonical_item"]
                    internal_price = ci["price_per_unit"]
                    normalized_price = normalize_price(item.get("unit_price", 0), 1, item.get("unit", ""), ci["uom"], ci.get("buying_unit"))
                    if normalized_price and internal_price > 0:
                        price_change_pct = round((normalized_price - internal_price) / internal_price * 100, 1)
                matched_items.append({**item, "match": match, "internal_price": internal_price,
                                      "normalized_invoice_price": normalized_price, "price_change_pct": price_change_pct})
            manual_data["items"] = matched_items
            st.session_state.invoices_to_review = [manual_data]
            st.session_state.current_invoice_idx = 0
            st.session_state.upload_mode = "review"
            st.rerun()

    if st.button("Cancel"):
        st.session_state.upload_mode = "choose"
        st.rerun()

# ---------------------------------------------------------------------------
# MODE: REVIEW
# ---------------------------------------------------------------------------

elif st.session_state.upload_mode == "review":
    invoices = st.session_state.invoices_to_review
    idx = st.session_state.current_invoice_idx
    inv = invoices[idx]

    if len(invoices) > 1:
        st.info(f"Invoice {idx + 1} of {len(invoices)} — This PDF contains {len(invoices)} separate invoices. Confirm each one individually.")

    # Header (editable)
    col1, col2, col3, col4 = st.columns(4)
    with col1: inv["supplier_name"] = st.text_input("Supplier", value=inv.get("supplier_name", ""), key=f"rev_supplier_{idx}")
    with col2: inv["invoice_date"] = st.text_input("Invoice Date", value=inv.get("invoice_date", ""), key=f"rev_date_{idx}")
    with col3: inv["invoice_number"] = st.text_input("Invoice #", value=inv.get("invoice_number", ""), key=f"rev_number_{idx}")
    with col4: st.text_input("Total", value=f"AED {inv.get('grand_total', 0):.2f}", key=f"rev_total_{idx}", disabled=True)

    # Math validation banner — re-check live so edits to totals reflect immediately
    is_valid, math_issues = validate_invoice_math(inv)
    mv = inv.get("_math_validation", {})
    if not is_valid:
        st.error("**Math check failed** — totals don't reconcile. Review and edit the Subtotal / VAT / Grand Total below before confirming.")
        for issue in math_issues:
            st.caption(f"• {issue}")
        if mv.get("status") == "failed_after_retry":
            st.caption("OCR was auto-retried once and still failed math. Likely a scan quality or layout issue — fix manually.")
    elif mv.get("status") == "passed_on_retry":
        st.info("Math reconciled on auto-retry (first OCR pass had a gap).")

    # Editable totals (so user can correct math without leaving the page)
    with st.expander("Edit totals", expanded=not is_valid):
        tcol1, tcol2, tcol3 = st.columns(3)
        with tcol1:
            inv["subtotal"] = st.number_input("Subtotal", value=float(inv.get("subtotal") or 0), step=0.01, key=f"rev_sub_{idx}")
        with tcol2:
            inv["vat_amount"] = st.number_input("VAT amount", value=float(inv.get("vat_amount") or 0), step=0.01, key=f"rev_vat_{idx}")
        with tcol3:
            inv["grand_total"] = st.number_input("Grand total", value=float(inv.get("grand_total") or 0), step=0.01, key=f"rev_grand_{idx}")

    # Price alerts
    increases = [i for i in inv.get("items", []) if (i.get("price_change_pct") or 0) > 10]
    if increases:
        st.warning(f"{len(increases)} item(s) with >10% price increase detected!")

    # Link to open PO from same supplier (optional)
    open_pos = get_open_pos_for_supplier(inv.get("supplier_name", ""))
    if open_pos:
        po_options = ["(no PO link)"] + [f"{p['po_number']} — AED {p.get('grand_total', 0):.2f} ({p.get('po_date', '')})" for p in open_pos]
        po_pick = st.selectbox(
            f"Link to Purchase Order ({len(open_pos)} open POs from this supplier)",
            po_options, key=f"po_link_{idx}",
            help="Optional: link this invoice to an open PO. The PO will be marked as delivered when you confirm."
        )
        if po_pick != "(no PO link)":
            picked_idx = po_options.index(po_pick) - 1
            inv["_linked_po_number"] = open_pos[picked_idx]["po_number"]
        else:
            inv["_linked_po_number"] = None

    # Build ingredient options for dropdowns
    canonical_data = load_canonical_prices_raw()
    all_ingredient_names = sorted([i["ingredient"] for i in canonical_data.get("items", [])])
    ingredient_options = ["(no match — skip)"] + all_ingredient_names

    # Editable items — each row has a dropdown to select/change the matched ingredient
    st.markdown("#### Line Items")
    st.caption("Select the correct ingredient match for each item. Change '(no match)' items to the right ingredient.")

    for i, item in enumerate(inv.get("items", [])):
        match = item.get("match", {})
        matched_name = match.get("canonical_name")
        suggestions = match.get("suggestions", [])
        change = item.get("price_change_pct")

        # Build default index for selectbox
        if matched_name and matched_name in all_ingredient_names:
            default_idx = all_ingredient_names.index(matched_name) + 1  # +1 for "(no match)" option
        elif suggestions:
            # Use first suggestion as default
            first_sug = suggestions[0]["name"]
            if first_sug in all_ingredient_names:
                default_idx = all_ingredient_names.index(first_sug) + 1
            else:
                default_idx = 0
        else:
            default_idx = 0

        # Color coding
        if change and change > 5:
            bg = "background-color: rgba(239,68,68,0.1)"
        elif change and change < -5:
            bg = "background-color: rgba(34,197,94,0.1)"
        else:
            bg = ""

        cols = st.columns([1, 4, 4, 1, 1, 2, 2])
        with cols[0]: st.text(f"{i+1}")
        with cols[1]:
            st.caption(item.get("item_name", ""))
            if suggestions and not matched_name:
                hint = ", ".join([f"{s['name']} ({s['score']:.0%})" for s in suggestions[:3]])
                st.caption(f"Suggestions: {hint}")
        with cols[2]:
            selected = st.selectbox(
                f"Match {i}", options=ingredient_options, index=default_idx,
                key=f"match_{idx}_{i}", label_visibility="collapsed"
            )
            # Store selection back into the invoice data
            if selected != "(no match — skip)":
                inv["items"][i]["_confirmed_match"] = selected
            else:
                inv["items"][i]["_confirmed_match"] = None
        with cols[3]: st.text(f"{item.get('quantity', 0)}")
        with cols[4]: st.text(f"{item.get('unit', '')}")
        with cols[5]:
            inv_price = item.get("unit_price", 0)
            int_price = item.get("internal_price")
            st.text(f"AED {inv_price:.2f}")
            if int_price:
                st.caption(f"Internal: {int_price:.2f}")
        with cols[6]:
            if change is not None:
                color = "red" if change > 0 else "green"
                st.markdown(f":{color}[{change:+.1f}%]")
                st.caption(f"AED {item.get('total_price', 0):.2f}")
            else:
                st.text(f"AED {item.get('total_price', 0):.2f}")

    # Totals
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1: st.metric("Subtotal", f"AED {inv.get('subtotal', 0):.2f}")
    with col2: st.metric(f"VAT ({inv.get('vat_percentage', 0)}%)", f"AED {inv.get('vat_amount', 0):.2f}")
    with col3: st.metric("Grand Total", f"AED {inv.get('grand_total', 0):.2f}")

    # Actions
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Cancel", use_container_width=True):
            st.session_state.upload_mode = "choose"
            st.session_state.invoices_to_review = []
            st.rerun()
    with col2:
        # Re-validate live (user may have edited totals above)
        confirm_valid, confirm_issues = validate_invoice_math(inv)
        force_confirm = False
        if not confirm_valid:
            force_confirm = st.checkbox(
                "Confirm anyway (math doesn't reconcile — flag for follow-up)",
                key=f"rev_force_{idx}",
                help="Tick this only if you're knowingly accepting a math gap (e.g. supplier rounding error). The invoice will be tagged for review."
            )
        can_confirm = confirm_valid or force_confirm
        if st.button("Confirm Invoice", type="primary", use_container_width=True, disabled=not can_confirm):
            # Stamp final validation state onto the invoice
            inv["_math_validation"] = {
                "status": "passed" if confirm_valid else "user_override",
                "issues": confirm_issues,
                "user_override": force_confirm and not confirm_valid,
            }
            # Build confirmation data from dropdown selections
            for item in inv.get("items", []):
                confirmed = item.get("_confirmed_match")
                item["confirmed_canonical_name"] = confirmed
                # Look up normalized price for the confirmed match
                if confirmed:
                    for ci in canonical_data.get("items", []):
                        if ci["ingredient"] == confirmed:
                            item["confirmed_price"] = normalize_price(
                                item.get("unit_price", 0), 1, item.get("unit", ""),
                                ci["uom"], ci.get("buying_unit"))
                            break

            price_updates = confirm_invoice(inv)

            # If user linked this invoice to a PO, mark the PO delivered
            linked_po = inv.get("_linked_po_number")
            if linked_po:
                inv_filename = f"{inv.get('invoice_date', '')}_{inv.get('invoice_number', '')}.json"
                link_invoice_to_po(linked_po, inv_filename)

            if idx < len(invoices) - 1:
                st.session_state.current_invoice_idx = idx + 1
                st.success(f"Invoice {idx + 1} confirmed! {len(price_updates)} price(s) updated. Loading next invoice...")
                st.rerun()
            else:
                st.session_state.upload_mode = "done"
                st.session_state.last_price_updates = price_updates
                st.session_state.last_invoice_count = len(invoices)
                st.rerun()

# ---------------------------------------------------------------------------
# MODE: DONE
# ---------------------------------------------------------------------------

elif st.session_state.upload_mode == "done":
    count = st.session_state.get("last_invoice_count", 1)
    updates = st.session_state.get("last_price_updates", [])

    st.success(f"{'All ' + str(count) + ' invoices' if count > 1 else 'Invoice'} confirmed successfully!")

    if updates:
        st.markdown("**Price Updates:**")
        for u in updates:
            direction = "up" if u["change_pct"] > 0 else "down"
            color = "red" if u["change_pct"] > 0 else "green"
            st.markdown(f"- {u['ingredient']}: AED {u['old_price']:.2f} -> AED {u['new_price']:.2f} (:{color}[{u['change_pct']:+.1f}%])")

    if st.button("Upload Another Invoice", use_container_width=True):
        st.session_state.upload_mode = "choose"
        st.session_state.invoices_to_review = []
        # Clear cache so dashboard picks up new prices
        st.cache_data.clear()
        st.rerun()
