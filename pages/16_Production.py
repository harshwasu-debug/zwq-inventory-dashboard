"""
Production — Track Semi-Finished (SF) recipe batches.
Records when chef prepares a base/marinade/sauce/pre-prep in bulk
and depletes the input ingredients from stock accordingly.
"""
import streamlit as st
import pandas as pd
import os, sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils import load_all_recipes, record_production, load_production_log

st.set_page_config(page_title="Production", page_icon="🍳", layout="wide")
st.markdown("## Production Tracking")
st.caption("Record batches of semi-finished recipes (sauces, marinades, prep) — depletes inputs from stock")

# ---------------------------------------------------------------------------
# Load SF recipes
# ---------------------------------------------------------------------------

all_recipes = load_all_recipes()
sf_recipes = [r for r in all_recipes if r["type"] == "semi_finished"]
sf_by_cuisine = {}
for r in sf_recipes:
    sf_by_cuisine.setdefault(r.get("cuisine", "Other"), []).append(r)

log = load_production_log()

# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

today_str = date.today().isoformat()
today_log = [e for e in log if e.get("date") == today_str]
week_cutoff = (date.today() - timedelta(days=7)).isoformat()
week_log = [e for e in log if e.get("date", "") >= week_cutoff]

c1, c2, c3, c4 = st.columns(4)
c1.metric("SF Recipes Available", len(sf_recipes))
c2.metric("Batches Today", sum(e.get("batches", 0) for e in today_log))
c3.metric("Batches This Week", sum(e.get("batches", 0) for e in week_log))
c4.metric("Total Logged", len(log))

# ---------------------------------------------------------------------------
# Record New Batch
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Record New Batch")

with st.form("production_form", clear_on_submit=True):
    col1, col2 = st.columns([3, 1])
    with col1:
        cuisine_pick = st.selectbox("Cuisine", ["All"] + sorted(sf_by_cuisine.keys()))
    with col2:
        prod_date = st.date_input("Date", value=date.today())

    # Build recipe list
    if cuisine_pick == "All":
        recipe_options = sorted([r["dish_name"] for r in sf_recipes])
    else:
        recipe_options = sorted([r["dish_name"] for r in sf_by_cuisine.get(cuisine_pick, [])])

    if not recipe_options:
        st.info("No SF recipes for this cuisine.")
    else:
        col1, col2, col3 = st.columns([3, 1, 2])
        with col1:
            recipe_pick = st.selectbox("Recipe", recipe_options)
        with col2:
            batches = st.number_input("Batches", min_value=0.1, value=1.0, step=0.5,
                                      help="How many batches of this recipe were made")
        with col3:
            produced_by = st.text_input("Produced by", placeholder="Chef name (optional)")

        # Show what ingredients will be depleted
        chosen = next((r for r in sf_recipes if r["dish_name"] == recipe_pick), None)
        if chosen:
            with st.expander(f"Inputs that will be depleted (× {batches} batches)"):
                rows = []
                for ing in chosen.get("ingredients", []):
                    qty = ing["quantity"] * batches
                    wastage = ing.get("wastage_pct", 0)
                    if wastage > 0:
                        qty *= (1 + wastage / 100)
                    rows.append({
                        "Ingredient": ing["ingredient"],
                        "Per Batch": ing["quantity"],
                        "Total": round(qty, 4),
                        "UOM": ing.get("uom", ""),
                        "Wastage %": wastage,
                    })
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

        notes = st.text_area("Notes (optional)", placeholder="e.g. New batch for the weekend service")
        submitted = st.form_submit_button("Record Production", type="primary", use_container_width=True)

        if submitted:
            result = record_production(recipe_pick, batches, notes, produced_by)
            if result.get("success"):
                st.success(f"Recorded **{batches} batch(es)** of {result['recipe']} — depleted {len(result['depleted'])} ingredient(s)")
                if result.get("notes_list"):
                    for n in result["notes_list"]:
                        st.caption(f"⚠️ {n}")
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(result.get("error", "Failed"))

# ---------------------------------------------------------------------------
# Production History
# ---------------------------------------------------------------------------

st.divider()
st.markdown("### Production History")

if log:
    col1, col2 = st.columns(2)
    with col1:
        days_back = st.selectbox("Period", [7, 14, 30, 90, 365], format_func=lambda x: f"Last {x} days", index=2, key="prod_days")
    with col2:
        cuisine_filter = st.selectbox("Cuisine", ["All"] + sorted({e.get("cuisine", "") for e in log if e.get("cuisine")}), key="prod_cuisine_hist")

    cutoff = (date.today() - timedelta(days=days_back)).isoformat()
    filtered = [e for e in log if e.get("date", "") >= cutoff]
    if cuisine_filter != "All":
        filtered = [e for e in filtered if e.get("cuisine") == cuisine_filter]
    filtered = list(reversed(filtered))

    rows = []
    for e in filtered:
        rows.append({
            "Date": e.get("date", ""),
            "Recipe": e.get("recipe_name", ""),
            "Cuisine": e.get("cuisine", ""),
            "Batches": e.get("batches", 0),
            "Inputs Depleted": len(e.get("depleted", [])),
            "Produced by": e.get("produced_by", "") or "—",
            "Notes": e.get("notes", "") or "—",
        })

    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=400)
    else:
        st.caption("No production records match the filters.")

    # By-recipe summary
    if filtered:
        st.markdown("#### Most Produced (in period)")
        agg = {}
        for e in filtered:
            r = e.get("recipe_name", "")
            agg[r] = agg.get(r, 0) + e.get("batches", 0)
        summary = sorted(agg.items(), key=lambda x: -x[1])[:10]
        st.dataframe(pd.DataFrame(summary, columns=["Recipe", "Total Batches"]), use_container_width=True, hide_index=True)
else:
    st.caption("No production records yet. Record a batch above to start tracking.")
