"""
Sales Upload & Stock Depletion — Upload daily Deliverect/Grubtech sales data,
auto-calculate ingredient consumption from recipe mappings, deplete stock.
"""
import streamlit as st
import pandas as pd
import json
import os, sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import (process_sales_depletion, load_brand_recipe_map, SALES_UPLOADS_DIR,
                   save_json, load_json)

st.set_page_config(page_title="Sales Upload", page_icon="📊", layout="wide")
st.markdown("## Sales Upload & Stock Depletion")
st.caption("Upload daily sales data from Deliverect/Grubtech to auto-deplete ingredient stock")

# ---------------------------------------------------------------------------
# SESSION STATE
# ---------------------------------------------------------------------------

if "sales_mode" not in st.session_state:
    st.session_state.sales_mode = "upload"
if "sales_results" not in st.session_state:
    st.session_state.sales_results = None

# ---------------------------------------------------------------------------
# CHECK PREREQUISITES
# ---------------------------------------------------------------------------

brm = load_brand_recipe_map()
mapping_count = len(brm.get("mappings", []))

if mapping_count == 0:
    st.warning("No brand-recipe mappings found. Go to **Brand Recipe Map** page first to link menu items to recipes.")
    st.stop()

st.caption(f"{mapping_count} brand-recipe mappings loaded")

# ---------------------------------------------------------------------------
# UPLOAD MODE
# ---------------------------------------------------------------------------

if st.session_state.sales_mode == "upload":
    st.markdown("### Upload Sales Data")

    st.markdown("""
    **Accepted formats:**
    - **JSON** — Deliverect/Grubtech export with fields: `Brand`, `Menu Item`, `Modifier`, `Qty`
    - **CSV** — with columns: `Brand`, `Menu Item`, `Modifier`, `Qty`

    The system matches each sold item to its recipe via the Brand Recipe Map,
    then calculates total ingredient consumption and depletes stock.
    """)

    uploaded = st.file_uploader("Upload sales file", type=["json", "csv"], key="sales_file")

    sales_date = st.date_input("Sales Date", value=date.today())

    if uploaded:
        try:
            file_bytes = uploaded.read()
            filename = uploaded.name

            if filename.endswith(".json"):
                raw_data = json.loads(file_bytes)
                # Handle different JSON structures
                if isinstance(raw_data, list):
                    items = raw_data
                elif isinstance(raw_data, dict):
                    # Try common keys
                    items = raw_data.get("orders", raw_data.get("items", raw_data.get("data", [])))
                else:
                    items = []
            elif filename.endswith(".csv"):
                import io
                df = pd.read_csv(io.BytesIO(file_bytes))
                items = df.to_dict("records")
            else:
                st.error("Unsupported file format")
                items = []

            if not items:
                st.error("No items found in uploaded file")
                st.stop()

            # Normalize field names (handle various naming conventions)
            normalized = []
            for item in items:
                normalized.append({
                    "brand": item.get("Brand") or item.get("brand") or item.get("brand_name", ""),
                    "menu_item": item.get("Menu Item") or item.get("menu_item") or item.get("item_name") or item.get("name", ""),
                    "modifier": item.get("Modifier") or item.get("modifier") or item.get("modifier_name", ""),
                    "qty": float(item.get("Qty") or item.get("qty") or item.get("quantity", 1)),
                })

            st.markdown(f"**{len(normalized)} line items loaded** from {filename}")

            # Preview
            preview_df = pd.DataFrame(normalized[:20])
            st.dataframe(preview_df, use_container_width=True, hide_index=True)
            if len(normalized) > 20:
                st.caption(f"Showing first 20 of {len(normalized)} items")

            # Aggregate by brand + menu item
            agg = {}
            for item in normalized:
                key = (item["brand"], item["menu_item"], item["modifier"])
                if key in agg:
                    agg[key]["qty"] += item["qty"]
                else:
                    agg[key] = dict(item)

            st.markdown(f"**{len(agg)} unique menu items** across {len(set(i['brand'] for i in normalized))} brands")

            if st.button("Process & Deplete Stock", type="primary", use_container_width=True):
                with st.spinner("Matching sales to recipes and calculating consumption..."):
                    reference = f"Sales {sales_date}"
                    results = process_sales_depletion(normalized, reference=reference)

                    # Save the upload
                    save_json(os.path.join(SALES_UPLOADS_DIR, f"{sales_date}_{filename}.json"), {
                        "date": str(sales_date),
                        "filename": filename,
                        "total_items": len(normalized),
                        "matched": results["matched_count"],
                        "unmatched": len(results["unmatched"]),
                        "ingredients_depleted": results["total_ingredients_depleted"],
                    })

                    st.session_state.sales_results = results
                    st.session_state.sales_mode = "results"
                    st.rerun()

        except Exception as e:
            st.error(f"Error processing file: {e}")

# ---------------------------------------------------------------------------
# RESULTS MODE
# ---------------------------------------------------------------------------

elif st.session_state.sales_mode == "results":
    results = st.session_state.sales_results

    st.success("Sales processed and stock depleted!")

    c1, c2, c3 = st.columns(3)
    c1.metric("Items Matched", results["matched_count"])
    c2.metric("Unmatched Items", len(results["unmatched"]))
    c3.metric("Ingredients Depleted", results["total_ingredients_depleted"])

    # Depletion summary
    if results["depletion_summary"]:
        st.markdown("### Ingredient Consumption Summary")
        df_dep = pd.DataFrame(results["depletion_summary"])
        st.dataframe(df_dep, use_container_width=True, hide_index=True,
                     column_config={
                         "consumed": st.column_config.NumberColumn("Consumed", format="%.3f"),
                         "remaining": st.column_config.NumberColumn("Remaining Stock", format="%.3f"),
                     })

    # Unmatched items
    if results["unmatched"]:
        st.markdown("### Unmatched Items")
        st.warning(f"{len(results['unmatched'])} items could not be matched to a recipe. "
                   "Link them in the **Brand Recipe Map** page.")
        df_unmatched = pd.DataFrame(results["unmatched"])
        st.dataframe(df_unmatched, use_container_width=True, hide_index=True)

    if st.button("Upload More Sales", use_container_width=True):
        st.session_state.sales_mode = "upload"
        st.session_state.sales_results = None
        st.rerun()

# ---------------------------------------------------------------------------
# UPLOAD HISTORY
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Upload History")
if os.path.exists(SALES_UPLOADS_DIR):
    files = sorted([f for f in os.listdir(SALES_UPLOADS_DIR) if f.endswith(".json")], reverse=True)
    if files:
        rows = []
        for f in files[:20]:
            data = load_json(os.path.join(SALES_UPLOADS_DIR, f), default={})
            rows.append({
                "Date": data.get("date", ""),
                "File": data.get("filename", f),
                "Total Items": data.get("total_items", 0),
                "Matched": data.get("matched", 0),
                "Unmatched": data.get("unmatched", 0),
                "Ingredients Depleted": data.get("ingredients_depleted", 0),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No sales uploads yet.")
else:
    st.caption("No sales uploads yet.")
