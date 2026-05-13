"""
Settings — Configure costing method, period close, wastage types, and global parameters.
"""
import streamlit as st
import os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_settings, save_settings, WASTAGE_TYPES, DEFAULT_SETTINGS

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
st.markdown("## Settings")
st.caption("Configure costing method, inventory period locks, and global parameters")

settings = load_settings()

# ---------------------------------------------------------------------------
# Tabs by configuration area
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "💰 Costing Method", "🔒 Inventory Period", "🗑️ Wastage Types", "🌐 Global Parameters"
])

# ---------------------------------------------------------------------------
# TAB 1: Costing Method
# ---------------------------------------------------------------------------

with tab1:
    st.markdown("### How should new invoice prices update canonical cost?")
    st.caption("This determines how the canonical_price_list.json is updated when an invoice is confirmed.")

    method = st.radio(
        "Costing Method",
        options=["moving_average", "weighted_average", "last_cost"],
        index=["moving_average", "weighted_average", "last_cost"].index(settings.get("costing_method", "moving_average")),
        format_func=lambda x: {
            "moving_average": "Moving Average — qty-weighted (recommended)",
            "weighted_average": "Weighted Average — 50/50 blend",
            "last_cost": "Last Cost — use the most recent invoice price",
        }[x],
        help="Moving Average factors in current stock and quantity received. Weighted Average is a simple blend. Last Cost just overwrites with the latest invoice."
    )

    st.markdown("---")
    st.markdown("**Edge case handling:**")

    disc = st.toggle(
        "Discounted items affect average cost",
        value=settings.get("discounted_items_affect_cost", False),
        help="If the supplier marks an item as a discount/special, should that affect the rolling cost?"
    )
    st.caption("OFF (default): discounted prices are recorded but don't change the canonical baseline.")

    zero = st.toggle(
        "Zero-priced items affect average cost",
        value=settings.get("zero_priced_items_affect_cost", False),
        help="If an item appears on invoice with price = 0 (free sample, etc.), should it pull the average to zero?"
    )
    st.caption("OFF (default): zero-priced items don't crash your costing.")

    fees = st.toggle(
        "Invoice-level fees/discounts affect average cost",
        value=settings.get("fees_affect_cost", True),
        help="Should delivery fees or invoice-level discounts be allocated across line items?"
    )

    if st.button("Save Costing Settings", type="primary", key="save_costing"):
        settings["costing_method"] = method
        settings["discounted_items_affect_cost"] = disc
        settings["zero_priced_items_affect_cost"] = zero
        settings["fees_affect_cost"] = fees
        save_settings(settings)
        st.success("Saved")

# ---------------------------------------------------------------------------
# TAB 2: Inventory Period
# ---------------------------------------------------------------------------

with tab2:
    st.markdown("### Lock inventory edits before a date")
    st.caption("Once a period is locked, stock movements before the lock date can't be edited — useful for month-end close.")

    current_lock = settings.get("inventory_period_lock_date")
    if current_lock:
        st.warning(f"🔒 Inventory is currently locked through **{current_lock}**. Movements before this date are read-only.")
    else:
        st.info("No period lock active.")

    new_lock = st.date_input(
        "Lock all movements on or before this date",
        value=date.fromisoformat(current_lock) if current_lock else None,
        help="Pick the last day of your closed accounting period."
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Apply Lock", type="primary"):
            settings["inventory_period_lock_date"] = str(new_lock) if new_lock else None
            save_settings(settings)
            st.success(f"Locked through {new_lock}")
            st.rerun()
    with col2:
        if current_lock and st.button("Remove Lock", type="secondary"):
            settings["inventory_period_lock_date"] = None
            save_settings(settings)
            st.success("Lock removed")
            st.rerun()

    st.divider()
    st.markdown("**Stock Count Restrictions**")

    restriction = st.radio(
        "When can users update inventory?",
        options=["no_period_restriction", "lock_after_count", "period_close"],
        index=["no_period_restriction", "lock_after_count", "period_close"].index(
            settings.get("stock_count_restriction", "no_period_restriction")),
        format_func=lambda x: {
            "no_period_restriction": "No restrictions — inventory can be updated anytime",
            "lock_after_count": "Lock after count — once a stock count is submitted, prior data can't be edited",
            "period_close": "Period close — only the current open period can be edited",
        }[x]
    )

    if st.button("Save Restrictions", key="save_restrictions"):
        settings["stock_count_restriction"] = restriction
        save_settings(settings)
        st.success("Saved")

# ---------------------------------------------------------------------------
# TAB 3: Wastage Types (read-only display)
# ---------------------------------------------------------------------------

with tab3:
    st.markdown("### Wastage Types — Reference")
    st.caption("These types are used in Wastage Tracking page. 'Expense' types count as P&L cost; 'Loss' types count as inventory shrinkage.")

    import pandas as pd
    df = pd.DataFrame([
        {
            "Type": wt["name"],
            "Category": "💼 Expense" if wt["expense"] else "💸 Loss",
            "Description": wt["description"],
        }
        for wt in WASTAGE_TYPES
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)

    st.info("Wastage types are defined in `utils.py:WASTAGE_TYPES`. To change, edit the source and redeploy. "
            "Editable UI for wastage types could be added if you regularly need to add custom categories.")

# ---------------------------------------------------------------------------
# TAB 4: Global Parameters
# ---------------------------------------------------------------------------

with tab4:
    st.markdown("### Global Pricing & Tax Parameters")
    st.caption("These values are used across the app for calculations (pricing waterfall, tax, etc.)")

    col1, col2, col3 = st.columns(3)
    with col1:
        currency = st.text_input("Currency code", value=settings.get("currency", "AED"))
    with col2:
        vat = st.number_input("VAT %", min_value=0.0, max_value=100.0,
                              value=float(settings.get("vat_percentage", 5)), step=0.5)
    with col3:
        delivery = st.number_input("Delivery charge (per order)", min_value=0.0,
                                    value=float(settings.get("delivery_charge", 4)), step=0.5)

    col1, col2 = st.columns(2)
    with col1:
        commission = st.number_input("Aggregator commission %", min_value=0.0, max_value=100.0,
                                     value=float(settings.get("commission_pct", 30)), step=1.0,
                                     help="Talabat/Deliveroo/Careem typically 30%")
    with col2:
        cm_target = st.number_input("Target CM%", min_value=0.0, max_value=100.0,
                                    value=float(settings.get("target_cm_pct", 20)), step=1.0,
                                    help="Contribution margin target as % of menu price")

    if st.button("Save Global Parameters", type="primary", key="save_global"):
        settings["currency"] = currency
        settings["vat_percentage"] = vat
        settings["delivery_charge"] = delivery
        settings["commission_pct"] = commission
        settings["target_cm_pct"] = cm_target
        save_settings(settings)
        st.success("Saved")

    st.divider()
    st.caption("**Note:** Some settings affect calculations across the app. The Inventory Dashboard tabs and Food Costing page use VAT, delivery, commission, and target CM% from here.")

    if st.button("Reset to Defaults", type="secondary"):
        save_settings(DEFAULT_SETTINGS.copy())
        st.success("Reset to defaults")
        st.rerun()
